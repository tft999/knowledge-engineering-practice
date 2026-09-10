"""菜谱硬约束过滤。

对每道菜谱执行：

- 严格推荐准入检查（审核状态、无 unknown/pending、无开放选择组）；
- 必需食材命中排除集合 -> 淘汰菜谱；
- 可选食材命中排除集合 -> 保留菜谱并省略该项；
- 选择组按组约束判断：必需组可用成员不足时淘汰，否则优先选择库存/常备成员。

补购集合按 ``Required(r) - Have - Pantry`` 计算，库存利用按 ``Required(r) ∩ Have`` 计算。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .exclusion import ExclusionResult
from .models import Explanation, IngredientUse, Omission, Recipe

# 关系名，用于解释展示
_REL_REQUIRED = "REQUIRES"
_REL_OPTIONAL = "OPTIONALLY_USES"
_REL_ONE_OF = "ONE_OF"


@dataclass
class FilteredRecipe:
    """一道菜谱的过滤结果。"""

    recipe: Recipe
    retained: bool
    required: set[str] = field(default_factory=set)  # 解析后的必需食材（含选择组选中）
    omitted: list[Omission] = field(default_factory=list)  # 因忌口省略的可选食材
    buy: set[str] = field(default_factory=set)  # 单菜补购
    used_have: set[str] = field(default_factory=set)  # 单菜利用的库存食材
    reason: str | None = None  # 淘汰原因
    explanations: list[Explanation] = field(default_factory=list)


def _hits(ingredient: str, exclusion: ExclusionResult) -> bool:
    """判断食材名是否命中排除集合（含字面兜底）。"""
    return ingredient in exclusion.all_excluded_ingredients()


def _matched(ingredient: str, exclusion: ExclusionResult) -> str:
    """返回命中的排除项名（取路径末节点，兜底为食材自身）。"""
    path = exclusion.ingredient_paths.get(ingredient, [ingredient])
    return path[-1]


def _path(ingredient: str, exclusion: ExclusionResult) -> list[str]:
    return exclusion.ingredient_paths.get(ingredient, [ingredient])


def _omission(ingredient: str, exclusion: ExclusionResult, evidence: list[str]) -> Omission:
    return Omission(
        ingredient=ingredient,
        matched_exclude=_matched(ingredient, exclusion),
        path=_path(ingredient, exclusion),
        evidence=evidence,
    )


def _explain(
    recipe: Recipe,
    ingredient: str,
    exclusion: ExclusionResult,
    relation: str,
    verdict: str,
    reason: str,
    evidence: list[str],
) -> Explanation:
    return Explanation(
        recipe_id=recipe.id,
        recipe_name=recipe.name,
        verdict=verdict,  # type: ignore[arg-type]
        relation=relation,
        path=[recipe.name, *_path(ingredient, exclusion)],
        matched_exclude=_matched(ingredient, exclusion),
        reason=reason,
        evidence=evidence,
    )


def _admission_reject(reason: str) -> str:
    return reason


def _check_admission(recipe: Recipe) -> str | None:
    """返回严格推荐准入不通过的原因，通过则返回 None。"""
    if recipe.review_state != "confirmed":
        return "菜谱未通过人工审核"
    groups = {g.group_id: g for g in recipe.groups}
    for ing in recipe.ingredients:
        if ing.requirement == "unknown":
            return f"食材 '{ing.id}' 需求语义未知"
        if ing.review_state != "confirmed":
            return f"食材关系 '{ing.id}' 未通过人工审核"
        if ing.requirement == "one_of":
            group = groups.get(ing.group_id) if ing.group_id else None
            if group is None:
                return f"选择组 '{ing.group_id}' 定义缺失"
    for group in recipe.groups:
        if group.open_group:
            return f"选择组 '{group.group_id}' 为开放选择组，算法尚未支持"
        if group.min_select > group.max_select:
            return f"选择组 '{group.group_id}' 约束非法"
    return None


def _resolve_groups(
    recipe: Recipe,
    exclusion: ExclusionResult,
    have: set[str],
    pantry: set[str],
) -> tuple[set[str], list[Omission], list[Explanation], str | None]:
    """解析选择组，返回 (选中的必需食材, 省略项, 解释, 淘汰原因)。"""
    groups = {g.group_id: g for g in recipe.groups}
    # 按 group_id 聚合成员
    members_by_group: dict[str, list[IngredientUse]] = {}
    for ing in recipe.ingredients:
        if ing.requirement == "one_of" and ing.group_id:
            members_by_group.setdefault(ing.group_id, []).append(ing)

    required: set[str] = set()
    omitted: list[Omission] = []
    explanations: list[Explanation] = []
    stock = have | pantry

    for group_id, group in groups.items():
        members = members_by_group.get(group_id, [])
        available = [m for m in members if not _hits(m.id, exclusion)]
        blocked = [m for m in members if _hits(m.id, exclusion)]

        if group.requirement == "required_one_of":
            if len(available) < group.min_select:
                reason = f"必需选择组 '{group_id}' 可用成员不足"
                for m in blocked:
                    explanations.append(
                        _explain(
                            recipe,
                            m.id,
                            exclusion,
                            _REL_ONE_OF,
                            "omitted",
                            "选择组选项因忌口不可用",
                            m.evidence,
                        )
                    )
                return set(), omitted, explanations, reason
            # 优先库存/常备，其余按字典序，保证结果可复现
            in_stock = sorted([m.id for m in available if m.id in stock])
            others = sorted([m.id for m in available if m.id not in stock])
            chosen = (in_stock + others)[: group.min_select]
            required |= set(chosen)
            for m in blocked:
                explanations.append(
                    _explain(
                        recipe,
                        m.id,
                        exclusion,
                        _REL_ONE_OF,
                        "omitted",
                        "选择组选项因忌口不可用",
                        m.evidence,
                    )
                )
        else:  # optional_one_of：整组可选，命中排除则省略，不产生补购
            for m in blocked:
                omitted.append(_omission(m.id, exclusion, m.evidence))
                explanations.append(
                    _explain(
                        recipe,
                        m.id,
                        exclusion,
                        _REL_ONE_OF,
                        "omitted",
                        "可选选择组选项因忌口省略",
                        m.evidence,
                    )
                )

    return required, omitted, explanations, None


def filter_recipe(
    recipe: Recipe,
    exclusion: ExclusionResult,
    have: set[str],
    pantry: set[str],
) -> FilteredRecipe:
    """过滤单道菜谱。"""
    result = FilteredRecipe(recipe=recipe, retained=False)

    admission_reason = _check_admission(recipe)
    if admission_reason is not None:
        result.reason = admission_reason
        return result

    group_required, group_omitted, group_explanations, group_reject = _resolve_groups(
        recipe, exclusion, have, pantry
    )
    if group_reject is not None:
        result.reason = group_reject
        result.explanations = group_explanations
        result.omitted = group_omitted
        return result

    required: set[str] = set(group_required)
    omitted: list[Omission] = list(group_omitted)
    explanations: list[Explanation] = list(group_explanations)

    for ing in recipe.ingredients:
        if ing.requirement != "required" and ing.requirement != "optional":
            continue
        if not _hits(ing.id, exclusion):
            if ing.requirement == "required":
                required.add(ing.id)
            continue

        # 命中排除
        if ing.requirement == "required":
            result.reason = f"必需食材 '{ing.id}' 命中排除项 '{_matched(ing.id, exclusion)}'"
            result.explanations = explanations + [
                _explain(
                    recipe,
                    ing.id,
                    exclusion,
                    _REL_REQUIRED,
                    "excluded",
                    result.reason,
                    ing.evidence,
                )
            ]
            return result
        # optional 命中 -> 省略
        omitted.append(_omission(ing.id, exclusion, ing.evidence))
        explanations.append(
            _explain(
                recipe,
                ing.id,
                exclusion,
                _REL_OPTIONAL,
                "omitted",
                f"可选食材 '{ing.id}' 因忌口省略",
                ing.evidence,
            )
        )

    result.required = required
    result.omitted = omitted
    result.explanations = explanations
    result.buy = required - have - pantry
    result.used_have = required & have
    result.retained = True
    return result


def filter_recipes(
    recipes: list[Recipe],
    exclusion: ExclusionResult,
    have: set[str],
    pantry: set[str],
) -> tuple[list[FilteredRecipe], list[FilteredRecipe]]:
    """过滤所有菜谱，返回 (候选, 被淘汰)。"""
    candidates: list[FilteredRecipe] = []
    rejected: list[FilteredRecipe] = []
    for recipe in recipes:
        filtered = filter_recipe(recipe, exclusion, have, pantry)
        if filtered.retained:
            candidates.append(filtered)
        else:
            rejected.append(filtered)
    return candidates, rejected
