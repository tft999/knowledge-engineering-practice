import json
from pathlib import Path

import networkx as nx
from networkx.readwrite import json_graph

from cookkg.models import Recipe
from cookkg.taxonomy import Taxonomy, load_taxonomy


def build_graph(
    recipes: list[Recipe],
    source_commit: str = "test",
    taxonomy: Taxonomy | None = None,
) -> nx.DiGraph:
    taxonomy = taxonomy or load_taxonomy()
    graph = nx.DiGraph(
        dataset="howtocook",
        source_commit=source_commit,
        schema_version=2,
        taxonomy_version=taxonomy.version,
        taxonomy_digest=taxonomy.digest(),
    )
    for recipe in recipes:
        rid = f"r:{recipe.id}"
        graph.add_node(rid, kind="recipe", **recipe.model_dump(mode="json"))
        for use in recipe.ingredients:
            iid = f"i:{use.name}"
            graph.add_node(iid, kind="ingredient", id=use.name, name=use.name)
            relation = {
                "required": "REQUIRES",
                "optional": "OPTIONALLY_USES",
                "pending": "REQUIRES",
            }[use.status]
            graph.add_edge(rid, iid, relation=relation, **use.model_dump(mode="json"))
        for tool in recipe.tools:
            tid = f"t:{tool}"
            graph.add_node(tid, kind="tool", id=tool, name=tool)
            graph.add_edge(rid, tid, relation="REQUIRES_TOOL")
    for membership in taxonomy.memberships:
        if not membership.reviewed:
            continue
        iid = f"i:{membership.ingredient}"
        cid = f"c:{membership.category}"
        graph.add_node(iid, kind="ingredient", id=membership.ingredient, name=membership.ingredient)
        graph.add_node(cid, kind="category", id=membership.category, name=membership.category)
        graph.add_edge(
            iid,
            cid,
            relation="IS_A",
            evidence=[membership.evidence],
            reviewed=True,
        )
    for category in taxonomy.categories:
        if not category.reviewed:
            continue
        child = f"c:{category.child}"
        parent = f"c:{category.parent}"
        graph.add_node(child, kind="category", id=category.child, name=category.child)
        graph.add_node(parent, kind="category", id=category.parent, name=category.parent)
        graph.add_edge(
            child,
            parent,
            relation="SUBCLASS_OF",
            evidence=[category.evidence],
            reviewed=True,
        )
    return graph


def dump_graph(graph: nx.DiGraph, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            json_graph.node_link_data(graph, edges="edges", name="_node_id"),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def load_graph(path: Path) -> nx.DiGraph:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return json_graph.node_link_graph(payload, directed=True, edges="edges", name="_node_id")
