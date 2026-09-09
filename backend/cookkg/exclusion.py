"""忌口推理：把用户排除项扩展到受影响的食材集合并生成解释路径。

排除条件不能只做字符串匹配：排除“辣椒”时应沿食材层级识别“小米椒、朝天椒”
等下位食材。本模块完成三类扩展：

1. 类别排除：沿 ``SUBCLASS_OF`` 找后代类别，再沿 ``IS_A`` 找这些类别下的食材；
2. 具体食材排除：直接加入该食材，可选地沿 ``HAS_COMPONENT`` 找包含它的复合食材；
3. 字面兜底：名称不在层级图中时，保留原名做精确字符串匹配。

不根据“辣味”等模糊口味自动推断具体食材。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx

from .normalization import Normalizer
from .taxonomy import Taxonomy


@dataclass
class ExclusionResult:
    """排除集合扩展结果。"""

    # 所有应被排除的食材名（含类别后代食材、成分扩展结果）
    excluded_ingredients: set[str] = field(default_factory=set)
    # 被排除的类别名（含后代类别）
    excluded_categories: set[str] = field(default_factory=set)
    # 未在图谱中命中的字面排除项，做精确字符串匹配兜底
    excluded_literals: set[str] = field(default_factory=set)
    # 食材名 -> 到排除项的图路径（用于解释），如 {"小米椒": ["小米椒", "辣椒"]}
    ingredient_paths: dict[str, list[str]] = field(default_factory=dict)
    # 每个排除项 -> 扩展出的食材名（有序，供展示 excluded_ingredients）
    detail: dict[str, list[str]] = field(default_factory=dict)

    def all_excluded_ingredients(self) -> set[str]:
        """判断菜谱食材是否命中时使用的完整集合。"""
        return self.excluded_ingredients | self.excluded_literals

    def sorted_excluded(self) -> list[str]:
        """合并排除类别与食材，供响应 excluded_ingredients 使用（稳定排序）。"""
        merged = sorted(
            self.excluded_categories | self.excluded_ingredients | self.excluded_literals
        )
        return merged


def _path_to(taxonomy: Taxonomy, node: str, target: str) -> list[str]:
    """返回 node 沿边方向到 target 的最短路径，失败时退化为 [node, target]。"""
    try:
        return nx.shortest_path(taxonomy.graph, source=node, target=target)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return [node, target]


def expand_exclusions(
    excludes: list[str],
    taxonomy: Taxonomy,
    normalizer: Normalizer,
    use_component: bool = False,
) -> ExclusionResult:
    """归一化并扩展用户排除项。

    ``use_component`` 为 True 时，额外沿经审核的 HAS_COMPONENT 关系扩展，
    用于忌口推理对照实验的“层级 + 成分”方法。
    """
    result = ExclusionResult()

    for raw in excludes:
        name = normalizer.normalize(raw)
        if not name:
            continue

        kind = taxonomy.node_kind(name)

        if kind == "category":
            categories = taxonomy.category_descendants(name, include_self=True)
            ingredients = taxonomy.ingredients_of(categories)
            result.excluded_categories |= categories
            result.excluded_ingredients |= ingredients
            # 类别名本身也按字面兜底：菜谱中若直接以类别名作为食材，同样命中
            result.excluded_literals.add(name)
            for ing in ingredients:
                result.ingredient_paths.setdefault(ing, _path_to(taxonomy, ing, name))
            expanded = ingredients | {name}
            result.detail[name] = sorted(expanded)
            # 成分扩展：类别名本身及其下位食材若被某复合食材声明为成分，复合食材也应排除
            if use_component:
                _extend_components(result, taxonomy, ingredients | {name})

        elif kind == "ingredient":
            result.excluded_ingredients.add(name)
            result.ingredient_paths.setdefault(name, [name])
            result.detail[name] = [name]
            if use_component:
                _extend_components(result, taxonomy, {name})

        else:
            # 未知名称：字面精确匹配兜底，不做层级推断
            result.excluded_literals.add(name)
            result.detail[name] = [name]

    return result


def _extend_components(
    result: ExclusionResult, taxonomy: Taxonomy, ingredients: set[str]
) -> None:
    """沿 HAS_COMPONENT 反向扩展：排除包含这些成分的复合食材。"""
    for ing in ingredients:
        for composite in taxonomy.containing_ingredients(ing):
            if composite in result.excluded_ingredients:
                continue
            result.excluded_ingredients.add(composite)
            # composite HAS_COMPONENT ing
            result.ingredient_paths.setdefault(composite, [composite, ing])
            result.detail.setdefault(ing, []).append(composite)
