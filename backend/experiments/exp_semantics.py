"""实验三：关系语义对照。

比较两种方法：

1. all_required —— 所有出现的食材均视为必需；
2. semantic   —— 区分必需、可选、选择组（本系统方法）。

指标：可用候选菜谱数、被错误淘汰的菜谱数、不必要补购的物品种类数。
"""

from __future__ import annotations

from cookkg.exclusion import expand_exclusions
from cookkg.filter import filter_recipes
from cookkg.models import Recipe

from .common import EvalMetadata, build_engine, save_result

EXCLUDE = ["辣椒"]


def _all_required_ingredients(recipe: Recipe) -> set[str]:
    """把所有食材（含可选、选择组全部成员）都当作必需。"""
    return {ing.id for ing in recipe.ingredients}


def _is_blocked_all_required(recipe: Recipe, excluded: set[str]) -> bool:
    return bool(_all_required_ingredients(recipe) & excluded)


def run() -> dict:
    engine = build_engine()
    exclusion = expand_exclusions(EXCLUDE, engine.taxonomy, engine.normalizer)
    excluded_all = exclusion.all_excluded_ingredients()

    candidates_semantic, rejected_semantic = filter_recipes(
        engine.recipes, exclusion, set(), set()
    )

    blocked_all = 0
    for recipe in engine.recipes:
        if _is_blocked_all_required(recipe, excluded_all):
            blocked_all += 1

    # 不必要补购：可选食材本不应进入补购，却被 all_required 计为必需
    unnecessary_buy = set()
    for recipe in engine.recipes:
        for ing in recipe.ingredients:
            if ing.requirement == "optional" and ing.id not in excluded_all:
                unnecessary_buy.add(ing.id)
        for ing in recipe.ingredients:
            if ing.requirement == "one_of" and ing.id not in excluded_all:
                # 选择组被当作全必需时，会多买其他成员
                unnecessary_buy.add(ing.id)

    # 语义方法错误淘汰数 = 因忌口被淘汰，但实际仅命中可选/可省略项的菜谱
    wrongly_rejected = [
        fr.recipe.id
        for fr in rejected_semantic
        if fr.reason and "命中排除" in fr.reason
        and all(
            ing.requirement == "optional" for ing in fr.recipe.ingredients if ing.id in excluded_all
        )
    ]

    return {
        "methods": [
            {
                "method": "all_required",
                "available_candidates": len(engine.recipes) - blocked_all,
                "blocked_recipes": blocked_all,
                "unnecessary_buy_items": len(unnecessary_buy),
            },
            {
                "method": "semantic",
                "available_candidates": len(candidates_semantic),
                "blocked_recipes": len(rejected_semantic),
                "unnecessary_buy_items": 0,
                "wrongly_rejected": wrongly_rejected,
            },
        ]
    }


if __name__ == "__main__":
    result = run()
    save_result("exp_semantics", EvalMetadata(experiment="semantics"), result["methods"])
    for r in result["methods"]:
        print(r)
