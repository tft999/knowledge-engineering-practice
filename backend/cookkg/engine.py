"""推荐引擎：编排归一化、忌口推理、候选过滤与联合补购优化。

硬约束判断不依赖 LLM。引擎只读取标准数据，不解析 Markdown。
"""

from __future__ import annotations

from collections import Counter

from .exclusion import ExclusionResult, expand_exclusions
from .filter import FilteredRecipe, filter_recipes
from .models import (
    Explanation,
    NormalizedInput,
    Recipe,
    RecommendRequest,
    RecommendResponse,
    TaxonomyEdge,
)
from .normalization import Normalizer
from .recommend import RecommendOutcome
from .recommend import recommend as optimize
from .taxonomy import Taxonomy


def _is_dietary_reject(reason: str) -> bool:
    """判断淘汰原因是否来自忌口/排除约束（而非数据未就绪）。"""
    return "命中排除" in reason or "可用成员不足" in reason


def _collect_explanations(
    rejected: list[FilteredRecipe], candidates: list[FilteredRecipe]
) -> list[Explanation]:
    """收集淘汰与省略解释，淘汰解释优先，按菜谱 ID 稳定排序。"""
    explanations: list[Explanation] = []
    for fr in sorted(rejected, key=lambda f: f.recipe.id):
        explanations.extend(fr.explanations)
    for fr in sorted(candidates, key=lambda f: f.recipe.id):
        explanations.extend(fr.explanations)
    return explanations


def _no_candidate_reason(rejected: list[FilteredRecipe]) -> str:
    dietary = [fr for fr in rejected if _is_dietary_reject(fr.reason or "")]
    others = [fr for fr in rejected if not _is_dietary_reject(fr.reason or "")]
    if dietary and not others:
        return (
            f"共 {len(rejected)} 道候选菜谱均因忌口冲突被淘汰，无可行候选，"
            "系统不自动放宽排除条件。"
        )
    if not dietary:
        counter = Counter(fr.reason or "未知原因" for fr in others)
        detail = "；".join(f"{r}（{n} 道）" for r, n in counter.most_common(3))
        return f"无通过严格审核的候选菜谱：{detail}。"
    return (
        f"无可行候选：{len(dietary)} 道因忌口冲突被淘汰，"
        f"{len(others)} 道未通过严格审核。"
    )


class RecommendationEngine:
    """菜单推荐引擎。"""

    def __init__(
        self,
        recipes: list[Recipe],
        taxonomy_edges: list[TaxonomyEdge],
        aliases: dict[str, str] | None = None,
        use_component: bool = False,
    ) -> None:
        self.recipes = list(recipes)
        self.normalizer = Normalizer(aliases)
        self.taxonomy = Taxonomy(taxonomy_edges)
        self.use_component = use_component

    def expand_exclusions(self, excludes: list[str]) -> ExclusionResult:
        return expand_exclusions(
            excludes, self.taxonomy, self.normalizer, use_component=self.use_component
        )

    def recommend(self, request: RecommendRequest) -> RecommendResponse:
        """执行完整推荐流程。"""
        # 1. 输入归一化
        have_norm = self.normalizer.normalize_all(request.have)
        pantry_norm = self.normalizer.normalize_all(request.pantry)
        exclude_norm = self.normalizer.normalize_all(request.exclude)
        have = set(have_norm)
        pantry = set(pantry_norm)

        # 2. 排除集合扩展（忌口推理）
        exclusion = self.expand_exclusions(exclude_norm)

        # 3. 候选过滤
        candidates, rejected = filter_recipes(self.recipes, exclusion, have, pantry)

        # 4. 联合补购优化
        outcome: RecommendOutcome = optimize(
            candidates,
            have,
            pantry,
            count=request.count,
            max_buy=request.max_buy,
            limit=request.limit,
        )

        # 5. 组装响应
        reason: str | None = None
        if not candidates:
            reason = _no_candidate_reason(rejected)
        elif not outcome.plans:
            min_buy = outcome.min_buy
            min_buy_text = f"（最少需补购 {min_buy} 种）" if min_buy is not None else ""
            reason = (
                f"候选 {outcome.candidate_count} 道菜中，无法在最多补购 "
                f"{request.max_buy} 种内组合出 {request.count} 道菜的菜单{min_buy_text}。"
                "系统不自动放宽条件。"
            )

        return RecommendResponse(
            plans=outcome.plans,
            reason=reason,
            candidate_count=outcome.candidate_count,
            normalized_input=NormalizedInput(
                have=have_norm, pantry=pantry_norm, exclude=exclude_norm
            ),
            excluded_ingredients=exclusion.sorted_excluded(),
            explanations=_collect_explanations(rejected, candidates),
        )
