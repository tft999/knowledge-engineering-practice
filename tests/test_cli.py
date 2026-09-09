import json

from typer.testing import CliRunner

from cookkg.cli import app
from cookkg.graph import build_graph, dump_graph
from cookkg.models import IngredientUse, Recipe


def test_recommend_json_command(tmp_path):
    recipe = Recipe(
        id="dishes/x.md",
        name="土豆菜",
        category="test",
        source_url="https://example/x",
        source_hash="abc",
        reviewed=True,
        ingredients=[
            IngredientUse(name="土豆", status="required"),
            IngredientUse(name="盐", status="required"),
        ],
    )
    graph_path = tmp_path / "graph.json"
    dump_graph(build_graph([recipe]), graph_path)
    result = CliRunner().invoke(
        app,
        [
            "recommend",
            "--graph",
            str(graph_path),
            "--have",
            "土豆",
            "--pantry",
            "盐",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["plans"][0]["recipes"] == [
        {"id": "dishes/x.md", "name": "土豆菜", "source_url": "https://example/x"}
    ]


def test_recommend_text_includes_source_and_shopping_list(tmp_path):
    recipe = Recipe(
        id="dishes/x.md",
        name="土豆菜",
        category="test",
        source_url="https://example/x",
        source_hash="abc",
        reviewed=True,
        ingredients=[IngredientUse(name="土豆", status="required")],
    )
    graph_path = tmp_path / "graph.json"
    dump_graph(build_graph([recipe]), graph_path)
    result = CliRunner().invoke(app, ["recommend", "--graph", str(graph_path)])
    assert result.exit_code == 0
    assert "补购：土豆" in result.output
    assert "https://example/x" in result.output


def test_verify_command_fails_when_snapshot_does_not_match(tmp_path, monkeypatch):
    recipe = Recipe(
        id="dishes/x.md",
        name="土豆菜",
        category="test",
        source_url="https://example/x",
        source_hash="abc",
        reviewed=True,
        ingredients=[IngredientUse(name="土豆", status="required")],
    )
    graph_path = tmp_path / "graph.json"
    dump_graph(build_graph([recipe]), graph_path)
    monkeypatch.setattr("cookkg.neo4j_store.verify_graph", lambda graph: {"ok": False})
    result = CliRunner().invoke(app, ["verify-neo4j", "--graph", str(graph_path)])
    assert result.exit_code == 1
    assert '"ok": false' in result.output


def test_serve_starts_fastapi_with_selected_graph(tmp_path, monkeypatch):
    graph_path = tmp_path / "graph.json"
    called = {}

    def fake_run(app, *, host, port):
        called.update(app=app, host=host, port=port)

    monkeypatch.setattr("uvicorn.run", fake_run)
    result = CliRunner().invoke(
        app,
        ["serve", "--graph", str(graph_path), "--host", "127.0.0.1", "--port", "8123"],
    )

    assert result.exit_code == 0, result.output
    assert called["host"] == "127.0.0.1"
    assert called["port"] == 8123
