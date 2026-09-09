from typing import Literal

import networkx as nx
from pydantic import BaseModel, Field

from cookkg.normalize import normalize_ingredient
from cookkg.recommend import expand_exclusions, recipe_is_available

PUBLIC_RELATIONS = {
    "REQUIRES",
    "OPTIONALLY_USES",
    "ONE_OF",
    "IS_A",
    "SUBCLASS_OF",
    "REQUIRES_TOOL",
}


class RecipeIngredient(BaseModel):
    name: str
    requirement: Literal["required", "optional", "one_of"]
    quantity_raw: list[str]


class RecipeDetail(BaseModel):
    id: str
    name: str
    source_url: str
    category: str
    difficulty: int | None
    ingredients: list[RecipeIngredient]
    steps: str


class GraphNode(BaseModel):
    id: str
    label: str
    kind: Literal["recipe", "ingredient", "category", "tool"]
    excluded: bool = False


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relation: Literal[
        "REQUIRES",
        "OPTIONALLY_USES",
        "ONE_OF",
        "IS_A",
        "SUBCLASS_OF",
        "REQUIRES_TOOL",
    ]
    evidence: list[str] = Field(default_factory=list)
    excluded: bool = False


class GraphNeighborhood(BaseModel):
    recipe_id: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class CookKgService:
    def __init__(self, graph: nx.DiGraph):
        self.graph = graph

    def _recipe_node(self, recipe_id: str) -> str:
        node = f"r:{recipe_id}"
        if node not in self.graph:
            raise KeyError(recipe_id)
        attrs = self.graph.nodes[node]
        uses = [
            edge
            for _, target, edge in self.graph.out_edges(node, data=True)
            if self.graph.nodes[target].get("kind") == "ingredient"
        ]
        if (
            attrs.get("kind") != "recipe"
            or not recipe_is_available(attrs)
            or not attrs.get("eligible", True)
            or any(edge.get("status") == "pending" for edge in uses)
        ):
            raise KeyError(recipe_id)
        return node

    def reviewed_recipe_count(self) -> int:
        return sum(
            bool(attrs.get("kind") == "recipe" and attrs.get("reviewed"))
            for _, attrs in self.graph.nodes(data=True)
        )

    def integration_eligible_recipe_count(self) -> int:
        count = 0
        for _, attrs in self.graph.nodes(data=True):
            if (
                attrs.get("kind") != "recipe"
                or not attrs.get("integration_eligible")
                or attrs.get("reviewed")
            ):
                continue
            try:
                self._recipe_node(attrs["id"])
            except KeyError:
                continue
            count += 1
        return count

    def available_recipe_count(self) -> int:
        return self.reviewed_recipe_count() + self.integration_eligible_recipe_count()

    def recipe_detail(self, recipe_id: str) -> RecipeDetail:
        node = self._recipe_node(recipe_id)
        attrs = self.graph.nodes[node]
        ingredients = []
        for _, target, edge in self.graph.out_edges(node, data=True):
            if self.graph.nodes[target].get("kind") != "ingredient":
                continue
            status = edge.get("status")
            if status not in {"required", "optional", "one_of"}:
                continue
            ingredients.append(
                RecipeIngredient(
                    name=self.graph.nodes[target]["name"],
                    requirement=status,
                    quantity_raw=edge.get("quantity_raw", []),
                )
            )
        ingredients.sort(key=lambda item: (item.requirement, item.name))
        return RecipeDetail(
            id=attrs["id"],
            name=attrs["name"],
            source_url=attrs["source_url"],
            category=attrs.get("category", "unknown"),
            difficulty=attrs.get("difficulty"),
            ingredients=ingredients,
            steps=attrs.get("steps", ""),
        )

    def neighborhood(
        self, recipe_id: str, limit: int = 30, exclude: set[str] | None = None
    ) -> GraphNeighborhood:
        recipe_node = self._recipe_node(recipe_id)
        selected = [recipe_node]
        direct = sorted(
            self.graph.successors(recipe_node),
            key=lambda node: (
                self.graph.nodes[node].get("kind", ""),
                self.graph.nodes[node].get("name", node),
            ),
        )
        for node in direct:
            if len(selected) >= limit:
                break
            selected.append(node)

        queue = [
            node for node in selected if self.graph.nodes[node].get("kind") == "ingredient"
        ]
        while queue and len(selected) < limit:
            current = queue.pop(0)
            for neighbor in sorted(self.graph.successors(current)):
                relation = self.graph.edges[current, neighbor].get("relation")
                if relation not in {"IS_A", "SUBCLASS_OF"} or neighbor in selected:
                    continue
                selected.append(neighbor)
                queue.append(neighbor)
                if len(selected) >= limit:
                    break

        normalized_exclude = {
            normalize_ingredient(name) for name in (exclude or set()) if name.strip()
        }
        _, paths = expand_exclusions(self.graph, normalized_exclude)
        excluded_nodes: set[str] = set()
        excluded_edges: set[tuple[str, str]] = set()
        for ingredient, path in paths.items():
            ingredient_node = f"i:{ingredient}"
            if ingredient_node not in direct:
                continue
            full_path = [recipe_node, *path]
            excluded_nodes.update(path)
            excluded_edges.update(zip(full_path, full_path[1:]))

        selected_set = set(selected)
        nodes = [
            GraphNode(
                id=node,
                label=self.graph.nodes[node]["name"],
                kind=self.graph.nodes[node]["kind"],
                excluded=node in excluded_nodes,
            )
            for node in selected
        ]
        edges = []
        for source, target, attrs in self.graph.edges(data=True):
            if source not in selected_set or target not in selected_set:
                continue
            relation = attrs.get("relation")
            if relation not in PUBLIC_RELATIONS:
                continue
            edges.append(
                GraphEdge(
                    id=f"{source}|{relation}|{target}",
                    source=source,
                    target=target,
                    relation=relation,
                    evidence=attrs.get("evidence", []),
                    excluded=(source, target) in excluded_edges,
                )
            )
        edges.sort(key=lambda edge: edge.id)
        return GraphNeighborhood(recipe_id=recipe_id, nodes=nodes, edges=edges)
