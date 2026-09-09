from pathlib import Path

import networkx as nx
import pytest
from fastapi.testclient import TestClient

from cookkg.api import create_app
from cookkg.graph import build_graph, dump_graph
from cookkg.models import IngredientUse, Recipe


def recipe(path: str, name: str, ingredients: list[IngredientUse], tools=()) -> Recipe:
    return Recipe(
        id=path,
        name=name,
        category="test",
        source_url=f"https://example/{path}",
        source_hash="hash",
        difficulty=2,
        reviewed=True,
        ingredients=ingredients,
        tools=list(tools),
        steps="切好后炒熟。",
    )


@pytest.fixture
def graph_path(tmp_path: Path) -> Path:
    recipes = [
        recipe(
            "dishes/meat/小炒肉.md",
            "小炒肉",
            [
                IngredientUse(
                    name="小米椒",
                    status="required",
                    quantity_raw=["小米椒 2 个"],
                    evidence=["ingredients:1"],
                ),
                IngredientUse(name="猪肉", status="required", quantity_raw=["猪肉 200g"]),
            ],
            tools=["炒锅"],
        ),
        recipe(
            "dishes/egg/番茄蛋.md",
            "番茄蛋",
            [
                IngredientUse(name="西红柿", status="required"),
                IngredientUse(name="鸡蛋", status="required"),
                IngredientUse(name="葱", status="optional"),
            ],
        ),
        recipe(
            "dishes/pending.md",
            "待核验菜",
            [IngredientUse(name="未知配料", status="pending")],
        ),
    ]
    path = tmp_path / "graph.json"
    dump_graph(build_graph(recipes, source_commit="fixture"), path)
    return path


def test_health_reports_loaded_graph_metadata(graph_path):
    with TestClient(create_app(graph_path)) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["source_commit"] == "fixture"
    assert response.json()["schema_version"] == 2
    assert response.json()["reviewed_recipes"] == 2


def test_recommendation_returns_frontend_contract_and_hierarchy_explanation(graph_path):
    with TestClient(create_app(graph_path)) as client:
        response = client.post(
            "/api/v1/recommendations",
            json={
                "have": ["小米椒", "猪肉", "番茄", "鸡蛋"],
                "pantry": [],
                "exclude": ["辣椒"],
                "count": 1,
                "max_buy": 0,
                "limit": 5,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["plans"][0]["recipes"][0]["id"] == "dishes/egg/番茄蛋.md"
    assert "小米椒" in body["excluded_ingredients"]
    assert [node["label"] for node in body["explanations"][0]["path"]] == [
        "小炒肉",
        "小米椒",
        "辣椒",
    ]
    assert [edge["relation"] for edge in body["explanations"][0]["edges"]] == [
        "REQUIRES",
        "IS_A",
    ]
    assert body["explanations"][0]["edges"][0]["evidence"] == ["ingredients:1"]
    assert body["explanations"][0]["edges"][1]["evidence"]
    assert "recipe_ids" not in body["plans"][0]


def test_normalized_conflict_and_numeric_bounds_return_422(graph_path):
    with TestClient(create_app(graph_path)) as client:
        conflict = client.post(
            "/api/v1/recommendations",
            json={
                "have": ["番茄"],
                "pantry": [],
                "exclude": ["西红柿"],
                "count": 1,
                "max_buy": 0,
                "limit": 5,
            },
        )
        invalid = client.post(
            "/api/v1/recommendations",
            json={"have": [], "pantry": [], "exclude": [], "count": 4, "max_buy": 21},
        )

    assert conflict.status_code == 422
    assert invalid.status_code == 422


def test_recipe_path_and_neighborhood_exclusion_highlight(graph_path):
    with TestClient(create_app(graph_path)) as client:
        detail = client.get("/api/v1/recipes/dishes/meat/小炒肉.md")
        neighborhood = client.get(
            "/api/v1/graph/neighborhood",
            params=[("recipe_id", "dishes/meat/小炒肉.md"), ("limit", "30"), ("exclude", "辣椒")],
        )

    assert detail.status_code == 200
    assert detail.json()["ingredients"][0]["requirement"] == "required"
    assert neighborhood.status_code == 200
    body = neighborhood.json()
    assert {node["kind"] for node in body["nodes"]} == {
        "recipe",
        "ingredient",
        "category",
        "tool",
    }
    highlighted = {node["label"] for node in body["nodes"] if node["excluded"]}
    assert {"小米椒", "辣椒"} <= highlighted
    assert any(edge["relation"] == "REQUIRES_TOOL" for edge in body["edges"])
    assert any(edge["evidence"] for edge in body["edges"] if edge["relation"] == "IS_A")


def test_missing_or_stale_graph_fails_during_lifespan(tmp_path):
    with pytest.raises(RuntimeError, match="cookkg build"):
        with TestClient(create_app(tmp_path / "missing.json")):
            pass

    stale = nx.DiGraph(dataset="howtocook", source_commit="old")
    path = tmp_path / "stale.json"
    dump_graph(stale, path)
    with pytest.raises(RuntimeError, match="cookkg build"):
        with TestClient(create_app(path)):
            pass

    graph = build_graph([], source_commit="fixture")
    graph.graph["taxonomy_digest"] = "different-resource"
    mismatched = tmp_path / "mismatched.json"
    dump_graph(graph, mismatched)
    with pytest.raises(RuntimeError, match="cookkg build"):
        with TestClient(create_app(mismatched)):
            pass


def test_cors_preflight_allows_local_vite(graph_path):
    with TestClient(create_app(graph_path)) as client:
        response = client.options(
            "/api/v1/recommendations",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
