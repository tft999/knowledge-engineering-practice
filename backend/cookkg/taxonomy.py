"""食材层级：基于 NetworkX 的有向图。

边方向统一为 ``child -> parent``：

- ``IS_A``：食材 -> 食材类别；
- ``SUBCLASS_OF``：子类别 -> 父类别；
- ``HAS_COMPONENT``：复合食材 -> 成分食材（经审核的有限成分关系）。

只加载 ``review_state == 'confirmed'`` 的边，未确认的关系不参与推理。
"""

from __future__ import annotations

from collections.abc import Iterable

import networkx as nx

from .models import TaxonomyEdge


class Taxonomy:
    """食材层级查询对象。"""

    def __init__(self, edges: Iterable[TaxonomyEdge]) -> None:
        self.graph: nx.DiGraph = nx.DiGraph()
        self._ingredients: set[str] = set()
        self._categories: set[str] = set()

        for edge in edges:
            if edge.review_state != "confirmed":
                continue
            self.graph.add_edge(edge.child, edge.parent, relation=edge.relation)
            if edge.relation == "IS_A":
                self._ingredients.add(edge.child)
                self._categories.add(edge.parent)
            elif edge.relation == "SUBCLASS_OF":
                self._categories.add(edge.child)
                self._categories.add(edge.parent)
            elif edge.relation == "HAS_COMPONENT":
                self._ingredients.add(edge.child)
                self._ingredients.add(edge.parent)

    # -- 节点类型 -----------------------------------------------------------

    def is_category(self, name: str) -> bool:
        return name in self._categories

    def is_ingredient(self, name: str) -> bool:
        return name in self._ingredients

    def node_kind(self, name: str) -> str:
        """返回 'ingredient' / 'category' / 'unknown'。"""
        if self.is_category(name):
            return "category"
        if self.is_ingredient(name):
            return "ingredient"
        return "unknown"

    # -- 沿指定关系反向遍历 ------------------------------------------------

    def _ancestors(self, node: str, relation: str) -> set[str]:
        """返回所有经指定关系边能到达 node 的节点（即 node 的 'child' 祖先）。"""
        result: set[str] = set()
        stack = [node]
        while stack:
            cur = stack.pop()
            for pred in self.graph.predecessors(cur):
                if self.graph[pred][cur].get("relation") == relation and pred not in result:
                    result.add(pred)
                    stack.append(pred)
        return result

    # -- 类别层级 -----------------------------------------------------------

    def category_descendants(self, category: str, include_self: bool = True) -> set[str]:
        """某类别的所有后代类别（沿 SUBCLASS_OF 向下）。"""
        descendants = self._ancestors(category, "SUBCLASS_OF")
        if include_self:
            descendants.add(category)
        return descendants

    def ingredients_of(self, categories: Iterable[str]) -> set[str]:
        """所有 IS_A 指向这些类别的食材。"""
        result: set[str] = set()
        for cat in categories:
            result |= self._ancestors(cat, "IS_A")
        return result

    def ingredient_categories(self, ingredient: str) -> set[str]:
        """某食材直接 IS_A 指向的类别。"""
        return {
            parent
            for parent in self.graph.successors(ingredient)
            if self.graph[ingredient][parent].get("relation") == "IS_A"
        }

    # -- 成分关系 -----------------------------------------------------------

    def containing_ingredients(self, component: str) -> set[str]:
        """所有经 HAS_COMPONENT 声明包含 component 的复合食材。"""
        return self._ancestors(component, "HAS_COMPONENT")

    def components_of(self, ingredient: str) -> set[str]:
        """某复合食材经 HAS_COMPONENT 声明的成分。"""
        return {
            parent
            for parent in self.graph.successors(ingredient)
            if self.graph[ingredient][parent].get("relation") == "HAS_COMPONENT"
        }
