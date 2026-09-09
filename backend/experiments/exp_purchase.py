"""实验二：联合补购对照。

比较三种选菜策略在相同库存场景下的补购种类数：

1. random  —— 随机选 k 道菜；
2. greedy  —— 逐道选择缺料最少的菜；
3. joint   —— 多道菜联合优化（本系统方法）。

指标：平均补购种类数、库存食材覆盖数、可行菜单比例。

为保证公平，三种策略在**完全相同**的库存场景上评估（先固定随机场景，
再逐策略评估），结果随随机种子一起保存。
"""

from __future__ import annotations

import itertools
import random
from collections.abc import Callable

from cookkg.engine import RecommendationEngine
from cookkg.exclusion import expand_exclusions
from cookkg.filter import filter_recipes

from .common import EvalMetadata, build_engine, save_result

SEED = 42
N_TRIALS = 30
K = 2
MAX_BUY = 5

# 候选库存池：随机抽取一部分作为“已有食材”
INVENTORY_POOL = [
    "鸡蛋",
    "西红柿",
    "土豆",
    "盐",
    "食用油",
    "生抽",
    "蒜",
    "醋",
    "米饭",
    "葱",
    "辣椒",
]


def _make_scenarios(rng: random.Random) -> list[tuple[set[str], set[str]]]:
    """预生成固定库存场景，供所有策略复用。"""
    scenarios = []
    for _ in range(N_TRIALS):
        size = rng.randint(1, len(INVENTORY_POOL))
        have = set(rng.sample(INVENTORY_POOL, size))
        pantry = {"盐", "食用油"} & have
        scenarios.append((have, pantry))
    return scenarios


def _candidates(engine: RecommendationEngine, have: set[str], pantry: set[str]):
    exclusion = expand_exclusions([], engine.taxonomy, engine.normalizer)
    candidates, _ = filter_recipes(engine.recipes, exclusion, have, pantry)
    return candidates


def _metrics_of(combo, have: set[str], pantry: set[str]) -> tuple[int, int]:
    """返回 (补购种类, 库存覆盖种类)。"""
    if not combo:
        return (0, 0)
    required = set().union(*(fr.required for fr in combo))
    return len(required - have - pantry), len(required & have)


def _random_strategy(candidates, have, pantry, rng, k):
    pool = [c for c in candidates if len(c.buy) <= MAX_BUY]
    if len(pool) < k:
        return None
    combo = rng.sample(pool, k)
    return _metrics_of(combo, have, pantry)


def _greedy_strategy(candidates, have, pantry, rng, k):
    del rng  # 贪心无随机性
    chosen = []
    bought: set[str] = set()
    available = list(candidates)
    for _ in range(k):
        available.sort(key=lambda c: (len(c.buy - bought), -len(c.used_have), c.recipe.id))
        if not available:
            return None
        nxt = available.pop(0)
        if len(nxt.buy - bought) > MAX_BUY:
            return None
        chosen.append(nxt)
        bought |= nxt.buy
    required = set().union(*(fr.required for fr in chosen))
    return len(bought), len(required & have)


def _joint_strategy(candidates, have, pantry, rng, k):
    del rng  # 联合优化无随机性
    best: tuple[tuple, tuple[int, int]] | None = None
    for combo in itertools.combinations(candidates, k):
        metrics = _metrics_of(combo, have, pantry)
        if metrics[0] > MAX_BUY:
            continue
        if best is None or (metrics[0], -metrics[1]) < best[0]:
            best = ((metrics[0], -metrics[1]), metrics)
    return best[1] if best is not None else None


def _evaluate(
    strategy: Callable,
    engine: RecommendationEngine,
    scenarios: list[tuple[set[str], set[str]]],
    rng: random.Random,
) -> dict:
    buys: list[int] = []
    covers: list[int] = []
    feasible = 0
    for have, pantry in scenarios:
        candidates = _candidates(engine, have, pantry)
        result = strategy(candidates, have, pantry, rng, K)
        if result is None:
            continue
        feasible += 1
        buys.append(result[0])
        covers.append(result[1])
    return {
        "avg_buy": round(sum(buys) / len(buys), 4) if buys else None,
        "avg_cover": round(sum(covers) / len(covers), 4) if covers else None,
        "feasible_ratio": round(feasible / len(scenarios), 4),
    }


def run() -> list[dict]:
    engine = build_engine()
    scenario_rng = random.Random(SEED)
    scenarios = _make_scenarios(scenario_rng)

    rows = []
    for name, strategy in [
        ("random", _random_strategy),
        ("greedy", _greedy_strategy),
        ("joint", _joint_strategy),
    ]:
        # 每个策略用独立的随机源，但场景序列完全一致，保证公平
        strategy_rng = random.Random(SEED + 1)
        metrics = _evaluate(strategy, engine, scenarios, strategy_rng)
        rows.append({"method": name, **metrics})
    return rows


if __name__ == "__main__":
    rows = run()
    save_result("exp_purchase", EvalMetadata(experiment="purchase"), rows)
    for r in rows:
        print(r)
