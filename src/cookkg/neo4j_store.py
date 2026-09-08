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


def _edge_tuple(recipe, ingredient, attrs):
    return (recipe, ingredient, attrs.get("status"),
            tuple(attrs.get("quantity_raw") or []), tuple(attrs.get("evidence") or []))


def import_graph(graph: nx.DiGraph) -> dict:
    """MERGE a graph snapshot atomically, batching rows inside one transaction."""
    uri, username, password, database = _config()
    snapshot = _snapshot(graph)
    nodes = {"recipe": [], "ingredient": []}
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
    edges = []
    for recipe, ingredient, attrs in graph.edges(data=True):
        if (graph.nodes[recipe].get("kind") != "recipe"
                or graph.nodes[ingredient].get("kind") != "ingredient"):
            raise Neo4jStoreError("Graph edges must connect recipe to ingredient")
        edges.append({
            "recipe_key": _key(snapshot, recipe), "ingredient_key": _key(snapshot, ingredient),
            "status": attrs.get("status"), "quantity_raw": attrs.get("quantity_raw", []),
            "evidence": attrs.get("evidence", []),
        })

    def write(tx):
        tx.run(
            "MATCH (n) WHERE (n:CookKGRecipe OR n:CookKGIngredient) "
            "AND n.dataset = $dataset AND n.source_commit = $source_commit "
            "DETACH DELETE n",
            **snapshot,
        ).consume()
        for kind, label in (("recipe", "CookKGRecipe"), ("ingredient", "CookKGIngredient")):
            for offset in range(0, len(nodes[kind]), 1000):
                tx.run(f"UNWIND $rows AS row MERGE (n:{label} {{key: row.key}}) SET n += row",
                       rows=nodes[kind][offset:offset + 1000]).consume()
        for offset in range(0, len(edges), 1000):
            tx.run("UNWIND $rows AS row "
                   "MATCH (r:CookKGRecipe {key: row.recipe_key}) "
                   "MATCH (i:CookKGIngredient {key: row.ingredient_key}) "
                   "MERGE (r)-[e:COOKKG_USES]->(i) "
                   "SET e.status = row.status, e.quantity_raw = row.quantity_raw, "
                   "e.evidence = row.evidence", rows=edges[offset:offset + 1000]).consume()

    try:
        with GraphDatabase.driver(uri, auth=(username, password)) as driver:
            with driver.session(database=database) as session:
                for label in ("CookKGRecipe", "CookKGIngredient"):
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
    ingredients = sorted(n for n, attrs in graph.nodes(data=True) if attrs["kind"] == "ingredient")
    sample = ingredients[0] if ingredients else None

    def read(tx):
        actual_nodes = Counter((row["node_id"], row["kind"], row["payload"]) for row in tx.run(
            "MATCH (n) WHERE (n:CookKGRecipe OR n:CookKGIngredient) "
            "AND n.dataset = $dataset AND n.source_commit = $source_commit "
            "RETURN n.node_id AS node_id, n.kind AS kind, n.payload AS payload", **snapshot))
        actual_edges = Counter(_edge_tuple(row["recipe"], row["ingredient"], row) for row in tx.run(
            "MATCH (r:CookKGRecipe)-[e:COOKKG_USES]->(i:CookKGIngredient) "
            "WHERE r.dataset = $dataset AND r.source_commit = $source_commit "
            "AND i.dataset = $dataset AND i.source_commit = $source_commit "
            "RETURN r.node_id AS recipe, i.node_id AS ingredient, e.status AS status, "
            "e.quantity_raw AS quantity_raw, e.evidence AS evidence", **snapshot))
        sample_actual = []
        if sample is not None:
            sample_actual = sorted(row["recipe"] for row in tx.run(
                "MATCH (r:CookKGRecipe)-[:COOKKG_USES]->(i:CookKGIngredient {key: $key}) "
                "WHERE r.dataset = $dataset AND r.source_commit = $source_commit "
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
