from cookkg.graph import build_graph, dump_graph, load_graph
from cookkg.models import IngredientUse, Recipe


def test_graph_round_trip_preserves_lists_and_metadata(tmp_path):
    recipe = Recipe(
        id="dishes/x.md",
        name="测试菜",
        category="test",
        source_url="https://example/x",
        source_hash="abc",
        reviewed=True,
        ingredients=[IngredientUse(name="盐", status="required", quantity_raw=["盐 2g"])],
    )
    graph = build_graph([recipe], source_commit="abc")
    path = tmp_path / "graph.json"
    dump_graph(graph, path)
    restored = load_graph(path)
    assert restored.graph["source_commit"] == "abc"
    assert restored.edges["r:dishes/x.md", "i:盐"]["quantity_raw"] == ["盐 2g"]
