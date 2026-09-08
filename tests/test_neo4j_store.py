import os
from unittest.mock import MagicMock
from uuid import uuid4

import networkx as nx
import pytest

from cookkg import neo4j_store


@pytest.fixture
def graph():
    graph = nx.DiGraph(dataset="howtocook", source_commit="fixture")
    graph.add_node(
        "r:a.md",
        kind="recipe",
        id="a.md",
        name="菜",
        category="test",
        source_url="https://example.org",
        reviewed=True,
        steps="烹饪步骤",
    )
    graph.add_node("i:盐", kind="ingredient", id="盐", name="盐")
    graph.add_edge("r:a.md", "i:盐", status="required", quantity_raw=["少许"], evidence=["盐少许"])
    return graph


@pytest.fixture
def connection(monkeypatch):
    config = {"URI": "bolt://localhost:7687", "USERNAME": "neo4j", "PASSWORD": "secret"}
    for key, value in config.items():
        monkeypatch.setenv(f"NEO4J_{key}", value)
    driver = MagicMock()
    monkeypatch.setattr(neo4j_store.GraphDatabase, "driver", lambda *a, **kw: driver)
    session = driver.__enter__.return_value.session.return_value.__enter__.return_value
    session.execute_write.side_effect = lambda fn: fn(session)
    session.execute_read.side_effect = lambda fn: fn(session)
    return session


def test_missing_config_is_actionable(monkeypatch, graph):
    monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
    with pytest.raises(neo4j_store.Neo4jStoreError, match="NEO4J_PASSWORD"):
        neo4j_store.import_graph(graph)


def test_import_replaces_only_snapshot_and_preserves_properties(graph, connection):
    result = neo4j_store.import_graph(graph)
    assert result["nodes"] == 2 and result["edges"] == 1
    calls = connection.run.call_args_list
    edge_rows = [c.kwargs["rows"] for c in calls if "COOKKG_USES" in c.args[0]]
    assert edge_rows[0][0]["status"] == "required"
    assert edge_rows[0][0]["evidence"] == ["盐少许"]
    recipe_rows = [
        call.kwargs["rows"]
        for call in calls
        if "CookKGRecipe" in call.args[0] and "MERGE" in call.args[0]
    ]
    assert '"steps": "烹饪步骤"' in recipe_rows[0][0]["payload"]
    delete_calls = [c for c in calls if "DETACH DELETE" in c.args[0]]
    assert len(delete_calls) == 1
    assert delete_calls[0].kwargs == {"dataset": "howtocook", "source_commit": "fixture"}
    old_key = edge_rows[0][0]["recipe_key"]
    connection.reset_mock()
    graph.graph["source_commit"] = "second"
    neo4j_store.import_graph(graph)
    rows = [c.kwargs["rows"] for c in connection.run.call_args_list if "COOKKG_USES" in c.args[0]]
    assert rows[0][0]["recipe_key"] != old_key


def test_verify_rejects_equal_counts_but_wrong_edges(graph, connection):
    connection.run.side_effect = [
        [
            {"node_id": node, "kind": attrs["kind"], "payload": neo4j_store._node_payload(attrs)}
            for node, attrs in graph.nodes(data=True)
        ],
        [{"recipe": "r:a.md", "ingredient": "i:糖", "status": "required",
          "quantity_raw": ["少许"], "evidence": ["盐少许"]}],
        [{"recipe": "r:a.md"}],
    ]
    result = neo4j_store.verify_graph(graph)
    assert result["counts_match"]
    assert not result["edges_match"]
    assert not result["ok"]


def test_database_error_does_not_expose_credentials(graph, connection):
    connection.run.side_effect = RuntimeError("password=secret")
    with pytest.raises(neo4j_store.Neo4jStoreError) as error:
        neo4j_store.import_graph(graph)
    assert "secret" not in str(error.value)


@pytest.mark.parametrize("status, expected", [("required", True), ("optional", False)])
def test_verify_compares_properties_and_sample_query(graph, connection, status, expected):
    connection.run.side_effect = [
        [
            {"node_id": node, "kind": attrs["kind"], "payload": neo4j_store._node_payload(attrs)}
            for node, attrs in graph.nodes(data=True)
        ],
        [{"recipe": "r:a.md", "ingredient": "i:盐", "status": status,
          "quantity_raw": ["少许"], "evidence": ["盐少许"]}],
        [{"recipe": "r:a.md"}],
    ]
    result = neo4j_store.verify_graph(graph)
    assert result["ok"] is expected
    assert result["sample_query"]["match"]


def test_verify_rejects_wrong_node_payload(graph, connection):
    connection.run.side_effect = [
        [
            {"node_id": "r:a.md", "kind": "recipe", "payload": "{}"},
            {
                "node_id": "i:盐",
                "kind": "ingredient",
                "payload": neo4j_store._node_payload(graph.nodes["i:盐"]),
            },
        ],
        [
            {
                "recipe": "r:a.md",
                "ingredient": "i:盐",
                "status": "required",
                "quantity_raw": ["少许"],
                "evidence": ["盐少许"],
            }
        ],
        [{"recipe": "r:a.md"}],
    ]
    result = neo4j_store.verify_graph(graph)
    assert not result["nodes_match"]
    assert not result["ok"]


@pytest.mark.integration
def test_live_roundtrip_idempotent_and_snapshot_isolation(graph, monkeypatch):
    required = ("URI", "USERNAME", "PASSWORD")
    if not all(os.getenv(f"NEO4J_TEST_{name}") for name in required):
        pytest.skip("Set NEO4J_TEST_URI/USERNAME/PASSWORD for live Neo4j integration")
    for name in (*required, "DATABASE"):
        monkeypatch.setenv(f"NEO4J_{name}", os.getenv(f"NEO4J_TEST_{name}", "neo4j"))
    graph.graph["dataset"] = f"cookkg-test-{uuid4().hex}"
    neo4j_store.import_graph(graph)
    neo4j_store.import_graph(graph)
    assert neo4j_store.verify_graph(graph)["ok"]
    second = graph.copy()
    second.graph["source_commit"] = "second"
    second.remove_edge("r:a.md", "i:盐")
    neo4j_store.import_graph(second)
    assert neo4j_store.verify_graph(second)["ok"]
    assert neo4j_store.verify_graph(graph)["ok"]
