import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cookkg.api import create_app
from cookkg.data_backend import build_backend_projection, compatibility_reason
from cookkg.data_models import DataRecipe
from cookkg.data_pipeline import build_v2
from cookkg.graph import dump_graph
from cookkg.recommend import RecommendRequest, expand_exclusions, recommend


def recipe(**updates):
    value = dict(schema_version="2.0", id="dishes/test/菜.md", name="菜", category="test",
        source_hash="a" * 64, source_commit="b" * 40, source_url="https://example.test/source",
        annotation_hash="c" * 64, method="ai_assisted", author="Codex",
        ingredients=[dict(use_id="u1", id="小米椒", surface="小米椒",
            requirement="required", review_state="pending", resource_kind="food",
            evidence=[dict(line=3, text="- 小米椒")])], tools=[], choice_groups=[], issues=[],
        notes=[], steps="炒。", review_state="pending", human_approval=None,
        strict_eligible=False, difficulty=2)
    value.update(updates)
    return DataRecipe.model_validate(value)


def ontology():
    return dict(schema_version="2.0", categories=["辣椒类", "蔬菜类"],
                ingredients={"小米椒": {"resource_kind": "food"}}, aliases=[],
                relations=[dict(type="IS_A", child="小米椒", parent="辣椒类",
                                review_state="pending", basis="fixture"),
                           dict(type="SUBCLASS_OF", child="辣椒类", parent="蔬菜类",
                                review_state="pending", basis="fixture")])


def test_projection_is_loss_aware_and_supports_category_alias():
    graph, report = build_backend_projection([recipe()], ontology())
    attrs = graph.nodes["r:dishes/test/菜.md"]
    assert not attrs["reviewed"]
    assert attrs["integration_eligible"] and report["integration_eligible"] == 1
    expanded, paths = expand_exclusions(graph, {"辣椒"})
    assert "小米椒" in expanded
    assert paths["小米椒"] == ["i:小米椒", "c:辣椒类"]
    result = recommend(graph, RecommendRequest(exclude={"辣椒"}))
    assert not result.plans and result.excluded_ingredients == ["小米椒", "辣椒"]


@pytest.mark.parametrize("updates,reason", [
    ({"issues": [dict(code="x", detail="x", evidence=[dict(line=3, text="- 小米椒")])]},
     "source_or_annotation_issue"),
    ({"ingredients": [dict(use_id="u1", id="小米椒", surface="小米椒",
        requirement="unknown", review_state="pending", resource_kind="food",
        evidence=[dict(line=3, text="- 小米椒")])]}, "unknown_ingredient_relation"),
    ({"ingredients": [dict(use_id="u1", id="小米椒", surface="小米椒",
        requirement="one_of", review_state="pending", group_id="g", resource_kind="food",
        evidence=[dict(line=3, text="- 小米椒")])],
      "choice_groups": [dict(id="g", member_ids=["u1"], min_select=1, max_select=1,
                              is_open=True, evidence=[dict(line=3, text="- 小米椒")])]},
     "open_choice_group"),
])
def test_projection_refuses_semantic_loss(updates, reason):
    record = recipe(**updates)
    assert compatibility_reason(record) == reason
    graph, _ = build_backend_projection([record], ontology())
    assert not graph.nodes[f"r:{record.id}"]["integration_eligible"]


def test_household_water_is_not_projected_as_a_shopping_ingredient():
    water = dict(use_id="w", id="水", surface="水", requirement="required",
                 review_state="pending", resource_kind="household_resource",
                 evidence=[dict(line=4, text="- 水")])
    value = recipe().model_dump(mode="json")
    value["ingredients"].append(water)
    graph, _ = build_backend_projection([DataRecipe.model_validate(value)], ontology())
    assert "i:水" not in graph


def test_closed_choice_group_is_projected_and_prefers_stock_member():
    ingredients = [
        dict(use_id="u1", id="牛奶", surface="牛奶", requirement="one_of",
             review_state="pending", group_id="g", resource_kind="food",
             evidence=[dict(line=3, text="- 牛奶或豆浆")]),
        dict(use_id="u2", id="豆浆", surface="豆浆", requirement="one_of",
             review_state="pending", group_id="g", resource_kind="food",
             evidence=[dict(line=3, text="- 牛奶或豆浆")]),
    ]
    group = dict(id="g", member_ids=["u1", "u2"], min_select=1, max_select=1,
                 evidence=[dict(line=3, text="- 牛奶或豆浆")])
    record = recipe(ingredients=ingredients, choice_groups=[group])

    assert compatibility_reason(record) is None
    graph, report = build_backend_projection([record], ontology())
    assert report["integration_eligible"] == 1
    assert graph.edges[f"r:{record.id}", "i:牛奶"]["group_id"] == "g"

    result = recommend(graph, RecommendRequest(have={"豆浆"}, max_buy=0))
    assert result.plans[0].to_buy == []
    assert result.plans[0].covered == ["豆浆"]


def test_projected_graph_loads_in_real_fastapi_contract(tmp_path):
    graph, _ = build_backend_projection([recipe()], ontology())
    path = tmp_path / "graph.json"
    dump_graph(graph, path)
    with TestClient(create_app(path)) as client:
        health = client.get("/api/health").json()
        assert health["reviewed_recipes"] == 0
        assert health["integration_eligible_recipes"] == health["available_recipes"] == 1
        assert "review_policy" not in health
        response = client.get("/api/v1/recipes/dishes/test/菜.md")
        assert response.status_code == 200 and response.json()["difficulty"] == 2


def test_shipped_hundred_build_exports_backend_compatibility(tmp_path):
    raw = Path("data/raw/howtocook")
    build_v2(raw, tmp_path)
    report = json.loads((tmp_path / "backend-compatibility.json").read_text(encoding="utf-8"))
    review = json.loads((tmp_path / "technical-review.json").read_text(encoding="utf-8"))
    assert report["total_recipes"] == 100
    assert 0 < report["integration_eligible"] < 100
    assert "human_reviewed" not in review and "course_human_approval" not in review

    with TestClient(create_app(tmp_path / "backend-graph.json")) as client:
        health = client.get("/api/health").json()
        assert health["available_recipes"] == report["integration_eligible"]
        response = client.post(
            "/api/v1/recommendations",
            json={
                "have": ["鸡蛋", "洋葱", "面包片"],
                "pantry": ["盐", "食用油", "黄油", "料酒"],
                "exclude": ["辣椒"],
                "count": 2,
                "max_buy": 2,
                "limit": 5,
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["plans"]
        assert all(
            recipe["id"] in report["eligible_recipe_ids"]
            for plan in body["plans"]
            for recipe in plan["recipes"]
        )
        assert all(
            recipe["name"] != "小炒肉"
            for plan in body["plans"]
            for recipe in plan["recipes"]
        )
        recipe_id = body["plans"][0]["recipes"][0]["id"]
        assert client.get(f"/api/v1/recipes/{recipe_id}").status_code == 200
        assert client.get(
            "/api/v1/graph/neighborhood", params={"recipe_id": recipe_id}
        ).status_code == 200
