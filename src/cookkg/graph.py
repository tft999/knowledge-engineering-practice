import json
from pathlib import Path

import networkx as nx
from networkx.readwrite import json_graph

from cookkg.models import Recipe


def build_graph(recipes: list[Recipe], source_commit: str = "test") -> nx.DiGraph:
    graph = nx.DiGraph(dataset="howtocook", source_commit=source_commit)
    for recipe in recipes:
        rid = f"r:{recipe.id}"
        graph.add_node(rid, kind="recipe", **recipe.model_dump(mode="json"))
        for use in recipe.ingredients:
            iid = f"i:{use.name}"
            graph.add_node(iid, kind="ingredient", id=use.name, name=use.name)
            graph.add_edge(rid, iid, **use.model_dump(mode="json"))
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
