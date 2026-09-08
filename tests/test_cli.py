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
    assert json.loads(result.output)["plans"][0]["recipes"] == ["土豆菜"]


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
