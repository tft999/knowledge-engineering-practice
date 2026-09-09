"""Snapshot-scoped Neo4j persistence; importing never deletes existing data."""

import hashlib
import json
import os
from collections import Counter

import networkx as nx
from neo4j import GraphDatabase


class Neo4jStoreError(RuntimeError):
    """A concise public error that never includes connection secrets."""


def _config():
    names = ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD")
    missing = [name for name in names if not os.getenv(name)]
    if missing:
        raise Neo4jStoreError("Missing configuration: " + ", ".join(missing))
    return (*[os.environ[name] for name in names], os.getenv("NEO4J_DATABASE", "neo4j"))


def _snapshot(graph):
    dataset = graph.graph.get("dataset")
    commit = graph.graph.get("source_commit")
    if not dataset or not commit:
        raise Neo4jStoreError("Graph requires dataset and source_commit metadata")
    return {"dataset": dataset, "source_commit": commit}


def _key(snapshot, node_id):
    payload = json.dumps([snapshot["dataset"], snapshot["source_commit"], node_id])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _node_payload(attrs):
    return json.dumps(attrs, ensure_ascii=False, sort_keys=True)


def _relation(attrs):
    return attrs.get("relation") or {
        "required": "REQUIRES",
        "optional": "OPTIONALLY_USES",
    }.get(attrs.get("status"))


def _edge_tuple(source, target, attrs):
    return (source, target, _relation(attrs), attrs.get("status"),
            tuple(attrs.get("quantity_raw") or []), tuple(attrs.get("evidence") or []))


NODE_LABELS = {
    "recipe": "CookKGRecipe",
    "ingredient": "CookKGIngredient",
    "category": "CookKGCategory",
    "tool": "CookKGTool",
}
RELATION_ENDPOINTS = {
    "REQUIRES": ("recipe", "ingredient"),
    "OPTIONALLY_USES": ("recipe", "ingredient"),
    "IS_A": ("ingredient", "category"),
    "SUBCLASS_OF": ("category", "category"),
    "REQUIRES_TOOL": ("recipe", "tool"),
}


def import_graph(graph: nx.DiGraph) -> dict:
    """MERGE a graph snapshot atomically, batching rows inside one transaction."""
    uri, username, password, database = _config()
    snapshot = _snapshot(graph)
    nodes = {kind: [] for kind in NODE_LABELS}
    for node_id, attrs in graph.nodes(data=True):
        kind = attrs.get("kind")
        if kind not in nodes:
            raise Neo4jStoreError("Graph contains an unsupported node kind")
        nodes[kind].append({
            **snapshot, "key": _key(snapshot, node_id), "node_id": node_id,
            "id": attrs.get("id", node_id), "name": attrs.get("name", node_id),
            "kind": kind, "source_url": attrs.get("source_url"),
            "payload": _node_payload(attrs),
        })
    edges = {relation: [] for relation in RELATION_ENDPOINTS}
    for source, target, attrs in graph.edges(data=True):
        relation = _relation(attrs)
        if relation not in RELATION_ENDPOINTS:
            raise Neo4jStoreError("Graph contains an unsupported relation")
        expected = RELATION_ENDPOINTS[relation]
        actual = (graph.nodes[source].get("kind"), graph.nodes[target].get("kind"))
        if actual != expected:
            raise Neo4jStoreError("Graph relation endpoints do not match the schema")
        edges[relation].append({
            "source_key": _key(snapshot, source),
            "target_key": _key(snapshot, target),
            "status": attrs.get("status"),
            "quantity_raw": attrs.get("quantity_raw", []),
            "evidence": attrs.get("evidence", []),
        })

    def write(tx):
        tx.run(
            "MATCH (n) WHERE (n:CookKGRecipe OR n:CookKGIngredient "
            "OR n:CookKGCategory OR n:CookKGTool) "
            "AND n.dataset = $dataset AND n.source_commit = $source_commit "
            "DETACH DELETE n",
            **snapshot,
        ).consume()
        for kind, label in NODE_LABELS.items():
            for offset in range(0, len(nodes[kind]), 1000):
                tx.run(f"UNWIND $rows AS row MERGE (n:{label} {{key: row.key}}) SET n += row",
                       rows=nodes[kind][offset:offset + 1000]).consume()
        for relation, relation_rows in edges.items():
            source_kind, target_kind = RELATION_ENDPOINTS[relation]
            source_label = NODE_LABELS[source_kind]
            target_label = NODE_LABELS[target_kind]
            for offset in range(0, len(relation_rows), 1000):
                tx.run(
                    f"UNWIND $rows AS row "
                    f"MATCH (s:{source_label} {{key: row.source_key}}) "
                    f"MATCH (t:{target_label} {{key: row.target_key}}) "
                    f"MERGE (s)-[e:COOKKG_{relation}]->(t) "
                    "SET e.status = row.status, e.quantity_raw = row.quantity_raw, "
                    "e.evidence = row.evidence",
                    rows=relation_rows[offset:offset + 1000],
                ).consume()

    try:
        with GraphDatabase.driver(uri, auth=(username, password)) as driver:
            with driver.session(database=database) as session:
                for label in NODE_LABELS.values():
                    session.run(f"CREATE CONSTRAINT {label.lower()}_key IF NOT EXISTS "
                                f"FOR (n:{label}) REQUIRE n.key IS UNIQUE").consume()
                session.execute_write(write)
    except Exception:
        raise Neo4jStoreError(
            "Neo4j import failed; check connection, credentials and permissions"
        ) from None
    return {**snapshot, "nodes": graph.number_of_nodes(), "edges": graph.number_of_edges()}


def verify_graph(graph: nx.DiGraph) -> dict:
    """Compare node identities and every edge (including attributes), plus one query."""
    uri, username, password, database = _config()
    snapshot = _snapshot(graph)
    expected_nodes = Counter(
        (node_id, attrs["kind"], _node_payload(attrs))
        for node_id, attrs in graph.nodes(data=True)
    )
    expected_edges = Counter(_edge_tuple(r, i, attrs) for r, i, attrs in graph.edges(data=True))
    ingredients = sorted(
        node
        for node, attrs in graph.nodes(data=True)
        if attrs["kind"] == "ingredient"
        and any(graph.nodes[source].get("kind") == "recipe" for source in graph.predecessors(node))
    )
    sample = ingredients[0] if ingredients else None

    def read(tx):
        actual_nodes = Counter((row["node_id"], row["kind"], row["payload"]) for row in tx.run(
            "MATCH (n) WHERE (n:CookKGRecipe OR n:CookKGIngredient "
            "OR n:CookKGCategory OR n:CookKGTool) "
            "AND n.dataset = $dataset AND n.source_commit = $source_commit "
            "RETURN n.node_id AS node_id, n.kind AS kind, n.payload AS payload", **snapshot))
        relation_types = [f"COOKKG_{relation}" for relation in RELATION_ENDPOINTS]
        actual_edges = Counter(_edge_tuple(row["source"], row["target"], row) for row in tx.run(
            "MATCH (s)-[e]->(t) WHERE type(e) IN $relation_types "
            "AND s.dataset = $dataset AND s.source_commit = $source_commit "
            "AND t.dataset = $dataset AND t.source_commit = $source_commit "
            "RETURN s.node_id AS source, t.node_id AS target, "
            "replace(type(e), 'COOKKG_', '') AS relation, e.status AS status, "
            "e.quantity_raw AS quantity_raw, e.evidence AS evidence",
            relation_types=relation_types, **snapshot))
        sample_actual = []
        if sample is not None:
            sample_actual = sorted(row["recipe"] for row in tx.run(
                "MATCH (r:CookKGRecipe)-[e]->(i:CookKGIngredient {key: $key}) "
                "WHERE type(e) IN ['COOKKG_REQUIRES', 'COOKKG_OPTIONALLY_USES'] "
                "AND r.dataset = $dataset AND r.source_commit = $source_commit "
                "RETURN r.node_id AS recipe", key=_key(snapshot, sample), **snapshot))
        return actual_nodes, actual_edges, sample_actual

    try:
        with GraphDatabase.driver(uri, auth=(username, password)) as driver:
            with driver.session(database=database) as session:
                actual_nodes, actual_edges, sample_actual = session.execute_read(read)
    except Exception:
        raise Neo4jStoreError(
            "Neo4j verification failed; check connection and credentials"
        ) from None
    sample_expected = sorted(graph.predecessors(sample)) if sample is not None else []
    counts_match = (actual_nodes.total() == expected_nodes.total()
                    and actual_edges.total() == expected_edges.total())
    nodes_match = actual_nodes == expected_nodes
    edges_match = actual_edges == expected_edges
    sample_match = sample_actual == sample_expected
    return {
        **snapshot, "ok": counts_match and nodes_match and edges_match and sample_match,
        "counts_match": counts_match, "nodes_match": nodes_match, "edges_match": edges_match,
        "nodes": actual_nodes.total(), "edges": actual_edges.total(),
        "sample_query": {"ingredient": sample, "expected": sample_expected,
                         "actual": sample_actual, "match": sample_match},
    }
