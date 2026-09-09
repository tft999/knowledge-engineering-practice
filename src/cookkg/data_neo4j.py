"""Typed Neo4j v2 snapshots with lossless payloads and full read-back comparison."""

from collections import defaultdict

from neo4j import GraphDatabase

from cookkg.data_pipeline import canonical_json, digest, graph_from_payload
from cookkg.neo4j_store import Neo4jStoreError, _config

NODE_KINDS = {"Recipe", "Ingredient", "IngredientCategory", "Tool", "ChoiceGroup"}
EDGE_KINDS = {"REQUIRES", "OPTIONALLY_USES", "ONE_OF", "UNRESOLVED_USE", "REQUIRES_TOOL",
              "OPTIONAL_TOOL", "TOOL_OPTION", "HAS_CHOICE_GROUP", "IS_A", "SUBCLASS_OF",
              "HAS_COMPONENT"}


def snapshot_rows(payload: dict) -> tuple[str, list[dict], list[dict]]:
    graph_from_payload(payload)
    metadata = payload["metadata"]
    if metadata.get("schema_version") != "2.0" or not all(
        metadata.get(key) for key in ("dataset", "source_commit")
    ):
        raise ValueError("Neo4j v2 requires dataset, source_commit and schema_version 2.0")
    scope = digest(metadata)
    nodes, edges = [], []
    node_kinds = {n["node_id"]: n["properties"]["kind"] for n in payload["nodes"]}
    for row in payload["nodes"]:
        attrs = row["properties"]
        if attrs["kind"] not in NODE_KINDS:
            raise ValueError("Invalid node kind")
        props = dict(key=digest([scope, row["node_id"]]), scope=scope, node_id=row["node_id"],
                     kind=attrs["kind"], name=attrs.get("name", row["node_id"]),
                     payload=canonical_json(attrs), **metadata)
        for key in ("id", "review_state", "strict_eligible", "source_url", "resource_kind",
                    "min_select", "max_select", "is_open"):
            if attrs.get(key) is not None:
                props[key] = attrs[key]
        nodes.append(props)
    for row in payload["edges"]:
        attrs = row["properties"]
        kind = attrs["type"]
        if kind not in EDGE_KINDS:
            raise ValueError("Invalid relationship type")
        pair = node_kinds[row["source"]], node_kinds[row["target"]]
        allowed = ({("Ingredient", "IngredientCategory")} if kind == "IS_A" else
                   {("IngredientCategory", "IngredientCategory")} if kind == "SUBCLASS_OF" else
                   {("Ingredient", "Ingredient")} if kind == "HAS_COMPONENT" else
                   {("Recipe", "ChoiceGroup")} if kind == "HAS_CHOICE_GROUP" else
                   {("Recipe", "Tool")} if kind in {"REQUIRES_TOOL", "OPTIONAL_TOOL", "TOOL_OPTION"}
                   else {("Recipe", "Ingredient")})
        if pair not in allowed:
            raise ValueError(f"Invalid endpoints for {kind}: {pair}")
        props = dict(key=digest([scope, row["source"], row["target"], row["key"]]), scope=scope,
                     edge_id=row["key"], payload=canonical_json(attrs))
        for key in ("review_state", "requirement", "group_id", "quantity_raw"):
            if attrs.get(key) is not None:
                props[key] = attrs[key]
        if attrs.get("evidence"):
            props["evidence_lines"] = [f'L{e["line"]}: {e["text"]}' for e in attrs["evidence"]]
        edges.append(dict(source=digest([scope, row["source"]]),
                          target=digest([scope, row["target"]]), type=kind, properties=props))
    return scope, nodes, edges


def import_v2(payload: dict) -> dict:
    scope, nodes, edges = snapshot_rows(payload)
    uri, user, password, database = _config()
    node_batches, edge_batches = defaultdict(list), defaultdict(list)
    for node in nodes:
        node_batches[node["kind"]].append(node)
    for edge in edges:
        edge_batches[edge["type"]].append(edge)

    def write(tx):
        # A scope lock serializes concurrent imports of the same snapshot.
        tx.run("MERGE (s:CookKGV2Snapshot {scope:$scope}) "
               "SET s.graph_hash=$hash", scope=scope, hash=digest(payload)).consume()
        tx.run("MATCH (n:CookKGV2 {scope:$scope}) DETACH DELETE n", scope=scope).consume()
        for kind, batch in sorted(node_batches.items()):
            for start in range(0, len(batch), 500):
                tx.run(f"UNWIND $rows AS row MERGE (n:CookKGV2:{kind} {{key:row.key}}) "
                       "SET n = row", rows=batch[start:start + 500]).consume()
        for kind, batch in sorted(edge_batches.items()):
            for start in range(0, len(batch), 500):
                tx.run("UNWIND $rows AS row "
                       "MATCH (a:CookKGV2 {key:row.source}), (b:CookKGV2 {key:row.target}) "
                       f"MERGE (a)-[e:{kind} {{key:row.properties.key}}]->(b) "
                       "SET e = row.properties", rows=batch[start:start + 500]).consume()

    try:
        with GraphDatabase.driver(uri, auth=(user, password)) as driver:
            with driver.session(database=database) as session:
                session.run("CREATE CONSTRAINT cookkg_v2_key IF NOT EXISTS "
                            "FOR (n:CookKGV2) REQUIRE n.key IS UNIQUE").consume()
                session.run("CREATE CONSTRAINT cookkg_v2_scope IF NOT EXISTS "
                            "FOR (n:CookKGV2Snapshot) REQUIRE n.scope IS UNIQUE").consume()
                session.execute_write(write)
    except Exception:
        raise Neo4jStoreError("Neo4j v2 import failed; check connection and database permissions") \
            from None
    return dict(scope=scope, nodes=len(nodes), edges=len(edges), graph_hash=digest(payload))


def verify_v2(payload: dict) -> dict:
    scope, expected_nodes, expected_edges = snapshot_rows(payload)
    uri, user, password, database = _config()

    def read(tx):
        nodes = [dict(row["props"]) for row in tx.run(
            "MATCH (n:CookKGV2 {scope:$scope}) RETURN properties(n) AS props", scope=scope)]
        edges = [dict(source=row["source"], target=row["target"], type=row["type"],
                      properties=dict(row["props"])) for row in tx.run(
            "MATCH (a:CookKGV2 {scope:$scope})-[e]->(b) "
            "RETURN a.key AS source,b.key AS target,type(e) AS type,properties(e) AS props",
            scope=scope)]
        label_errors = tx.run(
            "MATCH (n:CookKGV2 {scope:$scope}) "
            "WHERE NOT n.kind IN labels(n) OR size(labels(n)) <> 2 "
            "RETURN count(n) AS count", scope=scope).single()["count"]
        return nodes, edges, label_errors

    try:
        with GraphDatabase.driver(uri, auth=(user, password)) as driver:
            with driver.session(database=database) as session:
                nodes, edges, label_errors = session.execute_read(read)
    except Exception:
        raise Neo4jStoreError("Neo4j v2 verification failed; check connection and permissions") \
            from None
    # Compare every projected property AND the complete serialized source payload.
    node_match = sorted(map(canonical_json, nodes)) == sorted(map(canonical_json, expected_nodes))
    edge_match = sorted(map(canonical_json, edges)) == sorted(map(canonical_json, expected_edges))
    return dict(ok=node_match and edge_match and label_errors == 0, scope=scope,
                nodes_match=node_match, edges_match=edge_match, labels_match=label_errors == 0,
                expected_nodes=len(expected_nodes), actual_nodes=len(nodes),
                expected_edges=len(expected_edges), actual_edges=len(edges))


QUERIES = {
    "node_counts": (
        "MATCH (n:CookKGV2 {scope:$scope}) RETURN n.kind AS kind,count(*) AS count ORDER BY kind"
    ),
    "alcohol_choices": (
        "MATCH (r:CookKGV2:Recipe {scope:$scope,name:'芥末黄油罗氏虾'})-[u:ONE_OF]->(i) "
        "MATCH (r)-[:HAS_CHOICE_GROUP]->(g:ChoiceGroup) WHERE g.id = u.group_id "
        "RETURN i.name AS ingredient,u.group_id AS group_id,u.review_state AS review_state, "
        "g.min_select AS min_select,g.max_select AS max_select ORDER BY ingredient"
    ),
    "chili_paths": (
        "MATCH (r:CookKGV2:Recipe {scope:$scope,name:'小炒肉'})-[:REQUIRES]->(i) "
        "MATCH (i)-[:IS_A]->(:IngredientCategory {name:'辣椒类'}) "
        "RETURN r.name AS recipe,i.name AS ingredient ORDER BY ingredient"
    ),
    "partial_components": (
        "MATCH (i:CookKGV2:Ingredient {scope:$scope,name:'甘竹牌鲮鱼罐头'})"
        "-[e:HAS_COMPONENT]->(c:Ingredient) "
        "RETURN c.name AS component,e.review_state AS review_state ORDER BY component"
    ),
    "shared_ingredients": (
        "MATCH (a:CookKGV2:Recipe {scope:$scope,name:'洋葱炒鸡蛋'})-[:REQUIRES]->(i:Ingredient)"
        "<-[:REQUIRES]-(b:CookKGV2:Recipe {scope:$scope,name:'菠菜炒鸡蛋'}) "
        "WHERE i.resource_kind='food' RETURN i.name AS ingredient ORDER BY ingredient"
    ),
    "strict_recipe_count": (
        "MATCH (r:CookKGV2:Recipe {scope:$scope}) WHERE r.strict_eligible=true "
        "RETURN count(r) AS count"
    ),
}


def run_queries_v2(payload: dict) -> dict:
    """Compare representative Cypher results with independent NetworkX traversals."""
    scope, _, _ = snapshot_rows(payload)
    graph = graph_from_payload(payload)
    uri, user, password, database = _config()

    def recipe_node(name):
        return next(n for n, a in graph.nodes(data=True)
                    if a["kind"] == "Recipe" and a["name"] == name)

    def ingredients(name, edge_type):
        return {v for _, v, a in graph.out_edges(recipe_node(name), data=True)
                if a["type"] == edge_type}

    try:
        with GraphDatabase.driver(uri, auth=(user, password)) as driver:
            with driver.session(database=database) as session:
                actual = {key: [dict(r) for r in session.run(query, scope=scope)]
                          for key, query in QUERIES.items()}
    except Exception:
        raise Neo4jStoreError("Representative query execution failed") from None
    from collections import Counter

    choice_recipe = recipe_node("芥末黄油罗氏虾")
    choice_groups = {graph.nodes[v]["id"]: graph.nodes[v]
                     for _, v, a in graph.out_edges(choice_recipe, data=True)
                     if a["type"] == "HAS_CHOICE_GROUP"}
    expected = dict(
        node_counts=[dict(kind=k, count=v) for k, v in sorted(Counter(
            a["kind"] for _, a in graph.nodes(data=True)).items())],
        alcohol_choices=[dict(ingredient=graph.nodes[i]["name"], group_id=a["group_id"],
                              review_state=a["review_state"],
                              min_select=choice_groups[a["group_id"]]["min_select"],
                              max_select=choice_groups[a["group_id"]]["max_select"])
                         for _, i, a in graph.out_edges(choice_recipe, data=True)
                         if a["type"] == "ONE_OF"],
        chili_paths=[dict(recipe="小炒肉", ingredient=graph.nodes[i]["name"])
                     for i in ingredients("小炒肉", "REQUIRES")
                     if graph.has_edge(i, "c:辣椒类")],
        partial_components=[dict(component=graph.nodes[v]["name"], review_state=a["review_state"])
                            for _, v, a in graph.out_edges("i:甘竹牌鲮鱼罐头", data=True)
                            if a["type"] == "HAS_COMPONENT"],
        shared_ingredients=[dict(ingredient=graph.nodes[i]["name"])
                            for i in ingredients("洋葱炒鸡蛋", "REQUIRES")
                            & ingredients("菠菜炒鸡蛋", "REQUIRES")
                            if graph.nodes[i].get("resource_kind") == "food"],
        strict_recipe_count=[dict(count=sum(bool(a.get("strict_eligible"))
                                            for _, a in graph.nodes(data=True)))],
    )
    checks = {key: dict(query=QUERIES[key], actual=actual[key], expected=expected[key],
                       match=sorted(map(canonical_json, actual[key]))
                       == sorted(map(canonical_json, expected[key]))) for key in QUERIES}
    return dict(ok=all(c["match"] for c in checks.values()), scope=scope, checks=checks)
