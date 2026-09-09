import json
import os
from uuid import uuid4

import pytest
from neo4j import GraphDatabase

from cookkg.data_neo4j import import_v2, snapshot_rows, verify_v2


@pytest.mark.integration
def test_live_v2_roundtrip_idempotence_scope_and_corruption(monkeypatch):
    names = ("URI", "USERNAME", "PASSWORD")
    if not all(os.getenv(f"NEO4J_TEST_{name}") for name in names):
        pytest.skip("Set NEO4J_TEST_URI/USERNAME/PASSWORD for a real Neo4j integration test")
    for name in names:
        monkeypatch.setenv(f"NEO4J_{name}", os.environ[f"NEO4J_TEST_{name}"])
    database = os.getenv("NEO4J_TEST_DATABASE", "neo4j")
    monkeypatch.setenv("NEO4J_DATABASE", database)
    payload = dict(metadata=dict(dataset=f"test-v2-{uuid4().hex}", source_commit="fixture",
                                 schema_version="2.0"),
                   nodes=[dict(node_id="r:菜", properties=dict(kind="Recipe", name="菜",
                                    strict_eligible=False, review_state="pending",
                                    steps="保留中文与证据", source_hash="a" * 64)),
                          dict(node_id="i:蛋", properties=dict(kind="Ingredient", name="蛋")),
                          dict(node_id="c:蛋类", properties=dict(kind="IngredientCategory",
                                                                 name="蛋类")),
                          dict(node_id="g:1", properties=dict(kind="ChoiceGroup", name="g1",
                                            group_kind="food", min_select=0, max_select=1,
                                            is_open=False)),
                          dict(node_id="t:锅", properties=dict(kind="Tool", name="锅"))],
                   edges=[dict(source="r:菜", target="i:蛋", key="u1", properties=dict(
                                type="REQUIRES", requirement="required", review_state="pending")),
                          dict(source="r:菜", target="i:蛋", key="u2", properties=dict(
                                type="ONE_OF", requirement="one_of", group_id="g1",
                                evidence=[dict(line=3, text="- 蛋（可选）  ")],
                                quantity_raw=["1个"])),
                          dict(source="r:菜", target="g:1", key="g1", properties=dict(
                                type="HAS_CHOICE_GROUP")),
                          dict(source="r:菜", target="t:锅", key="t1", properties=dict(
                                type="REQUIRES_TOOL")),
                          dict(source="i:蛋", target="c:蛋类", key="IS_A", properties=dict(
                                type="IS_A", review_state="pending"))])
    second = json.loads(json.dumps(payload))
    second["metadata"]["source_commit"] = "second"
    scopes = [snapshot_rows(p)[0] for p in (payload, second)]
    uri, user, password = (os.environ[f"NEO4J_TEST_{n}"] for n in names)
    with GraphDatabase.driver(uri, auth=(user, password)) as driver:
        try:
            first = import_v2(payload)
            assert verify_v2(payload)["ok"]
            assert import_v2(payload) == first
            assert verify_v2(payload)["ok"]
            import_v2(second)
            import_v2(payload)
            assert verify_v2(second)["ok"]
            with driver.session(database=database) as session:
                row = session.run(
                    "MATCH (r:CookKGV2:Recipe {scope:$scope})-[e:ONE_OF]->(i:Ingredient) "
                    "RETURN r.name AS recipe,i.name AS ingredient,e.group_id AS choice",
                    scope=scopes[0]).single()
                assert dict(row) == dict(recipe="菜", ingredient="蛋", choice="g1")
                session.run("MATCH (n:CookKGV2 {scope:$scope,node_id:'r:菜'}) "
                            "SET n.strict_eligible=true", scope=scopes[0]).consume()
            bad = verify_v2(payload)
            assert not bad["ok"] and not bad["nodes_match"] and bad["edges_match"]
            import_v2(payload)
            with driver.session(database=database) as session:
                session.run("MATCH (:CookKGV2 {scope:$scope})-[e:ONE_OF]->() "
                            "SET e.group_id='incorrect'", scope=scopes[0]).consume()
            bad = verify_v2(payload)
            assert not bad["ok"] and bad["nodes_match"] and not bad["edges_match"]
        finally:
            with driver.session(database=database) as session:
                session.run("MATCH (n:CookKGV2) WHERE n.scope IN $scopes DETACH DELETE n",
                            scopes=scopes).consume()
                session.run("MATCH (n:CookKGV2Snapshot) WHERE n.scope IN $scopes DELETE n",
                            scopes=scopes).consume()
