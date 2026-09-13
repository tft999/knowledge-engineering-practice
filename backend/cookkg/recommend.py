"""多菜联合补购优化。

目标作用于整组菜单：共享缺料只计算一次。

```text
Buy(M) = Required(M) - Have - Pantry
```

单菜候选按“补购种类升序、库存覆盖数降序、稳定 ID 排序”截取前若干道后枚举组合，
组合按同样优先级排序。系统只承诺候选池内最优。
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable
from dataclasses import dataclass, field

from .filter import FilteredRecipe
from .models import MenuPlan, Omission, PlanRecipe

DEFAULT_CANDIDATE_CAP = 60


@dataclass
class RecommendOutcome:
    """联合补购优化的结果与诊断信息。"""

    plans: list[MenuPlan] = field(default_factory=list)
    candidate_count: int = 0  # 进入组合枚举的候选菜谱数
    min_buy: int | None = None  # 所有 count 组合中的最小补购种类数（不受 max_buy 限制）


def _recipe_sort_key(fr: FilteredRecipe) -> tuple[int, int, str]:
    return (len(fr.buy), -len(fr.used_have), fr.recipe.id)


def _rank_candidates(
    candidates: Iterable[FilteredRecipe], candidate_cap: int
) -> list[FilteredRecipe]:
    """单菜候选排序并截取。"""
    ranked = sorted(candidates, key=_recipe_sort_key)
    return ranked[:candidate_cap]


def _combo_plan(
    combo: tuple[FilteredRecipe, ...], have: set[str], pantry: set[str]
) -> tuple[MenuPlan, set[str]]:
    """计算一个菜单组合的补购、库存覆盖，并构造方案对象。"""
    required_union: set[str] = set()
    omitted_union: dict[str, Omission] = {}
    for fr in combo:
        required_union |= fr.required
        for om in fr.omitted:
            omitted_union.setdefault(om.ingredient, om)

    buy = required_union - have - pantry
    used_have = required_union & have
    plan = MenuPlan(
        recipes=[
            PlanRecipe(
                id=fr.recipe.id,
                name=fr.recipe.name,
                source_url=fr.recipe.source_url,
            )
            for fr in sorted(combo, key=lambda fr: fr.recipe.id)
        ],
        buy=sorted(buy),
        used_have=sorted(used_have),
        omitted=[omitted_union[k] for k in sorted(omitted_union)],
        buy_count=len(buy),
    )
    return plan, buy


def recommend(
    candidates: Iterable[FilteredRecipe],
    have: set[str],
    pantry: set[str],
    count: int,
    max_buy: int,
    limit: int,
    candidate_cap: int = DEFAULT_CANDIDATE_CAP,
) -> RecommendOutcome:
    """从过滤后的候选菜谱中枚举组合，返回满足补购上限的方案（已排序）。

    方案排序键依次为：补购种类最少、库存覆盖最多、菜谱 ID 字典序。
    """
    pool = _rank_candidates(candidates, candidate_cap)
    outcome = RecommendOutcome(candidate_count=len(pool))
    if count > len(pool):
        return outcome

    ranked: list[tuple[tuple, MenuPlan]] = []
    for combo in itertools.combinations(pool, count):
        plan, buy = _combo_plan(combo, have, pantry)
        min_buy = len(buy)
        if outcome.min_buy is None or min_buy < outcome.min_buy:
            outcome.min_buy = min_buy
        if min_buy > max_buy:
            continue
        ids = tuple(sorted(fr.recipe.id for fr in combo))
        ranked.append(((len(buy), -len(plan.used_have), ids), plan))

    ranked.sort(key=lambda item: item[0])
    outcome.plans = [plan for _, plan in ranked[:limit]]
    return outcome
