import pytest
from pydantic import ValidationError

from cookkg.graph import build_graph
from cookkg.models import IngredientUse, Recipe
from cookkg.taxonomy import CategoryRelation, Membership, Taxonomy


def test_build_graph_adds_reviewed_taxonomy_and_tools():
    recipe = Recipe(
        id="pepper.md",
        name="辣椒菜",
        category="meat_dish",
        source_url="https://example/pepper.md",
        source_hash="hash",
        reviewed=True,
        ingredients=[IngredientUse(name="小米椒", status="required")],
        tools=["炒锅"],
    )

    graph = build_graph([recipe], source_commit="fixture")

    assert graph.graph["schema_version"] == 2
    assert graph.graph["taxonomy_version"] == "1.0"
    assert len(graph.graph["taxonomy_digest"]) == 64
    assert graph.nodes["c:辣椒"]["kind"] == "category"
    assert graph.nodes["t:炒锅"]["kind"] == "tool"
    assert graph.edges["i:小米椒", "c:辣椒"]["relation"] == "IS_A"
    assert graph.edges["c:辣椒", "c:蔬菜"]["relation"] == "SUBCLASS_OF"
    assert graph.edges["r:pepper.md", "t:炒锅"]["relation"] == "REQUIRES_TOOL"
    assert graph.edges["r:pepper.md", "i:小米椒"]["relation"] == "REQUIRES"


def test_dumped_taxonomy_contains_only_reviewed_relations():
    taxonomy = Taxonomy(
        version="1.0",
        memberships=[
            Membership(
                ingredient="小米椒",
                category="辣椒",
                reviewed=True,
                evidence="reviewed",
            ),
            Membership(
                ingredient="未审核椒",
                category="辣椒",
                reviewed=False,
                evidence="pending review",
            ),
        ],
    )
    graph = build_graph([], source_commit="fixture", taxonomy=taxonomy)

    assert ("i:小米椒", "c:辣椒") in graph.edges
    assert ("i:未审核椒", "c:辣椒") not in graph.edges


def test_reviewed_taxonomy_rejects_cycles_with_multiple_parents():
    def relation(child, parent):
        return CategoryRelation(
            child=child,
            parent=parent,
            reviewed=True,
            evidence="reviewed",
        )

    with pytest.raises(ValidationError, match="不能包含循环"):
        Taxonomy(
            version="1.0",
            categories=[relation("A", "C"), relation("A", "B"), relation("C", "A")],
        )
