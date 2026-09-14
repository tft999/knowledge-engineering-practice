import hashlib
import json
from collections import Counter
from functools import lru_cache
from importlib.resources import files
from itertools import combinations
from typing import Literal

import networkx as nx
from pydantic import BaseModel, Field, field_validator, model_validator

from cookkg.normalize import normalize_ingredient


def _canon(values: set[str]) -> set[str]:
    return {normalize_ingredient(value) for value in values if value.strip()}


def recipe_is_available(attrs: dict) -> bool:
    return bool(attrs.get("reviewed") or attrs.get("integration_eligible"))


class RecommendRequest(BaseModel):
    have: set[str] = Field(default_factory=set)
    pantry: set[str] = Field(default_factory=set)
    exclude: set[str] = Field(default_factory=set)
    count: int = 1
    max_buy: int = 99
    limit: int = 5

    @field_validator("count")
    @classmethod
    def valid_count(cls, value: int) -> int:
        if not 1 <= value <= 3:
            raise ValueError("count 必须在 1 到 3 之间")
        return value

    @model_validator(mode="after")
    def normalize_and_reject_conflicts(self):
        self.have = _canon(self.have)
        self.pantry = _canon(self.pantry)
        self.exclude = _canon(self.exclude)
        conflict = (self.have | self.pantry) & self.exclude
        if conflict:
            names = "、".join(sorted(conflict))
            raise ValueError(f"{names} 归一化后同时出现在可用与排除条件")
        return self


class RecipeSummary(BaseModel):
    id: str
    name: str
    source_url: str


class ExplanationNode(BaseModel):
    id: str
    label: str
    kind: Literal["recipe", "ingredient", "category", "tool"]


class ExplanationEdge(BaseModel):
    source: str
    target: str
    relation: Literal["REQUIRES", "OPTIONALLY_USES", "IS_A", "SUBCLASS_OF"]
    evidence: list[str] = Field(default_factory=list)


class Explanation(BaseModel):
    id: str
    kind: Literal["excluded_required", "omitted_optional", "normalization"]
    message: str
    path: list[ExplanationNode]
    edges: list[ExplanationEdge]


class NormalizedInput(BaseModel):
    have: list[str]
    pantry: list[str]
    exclude: list[str]


class DiversitySummary(BaseModel):
    categories: list[str]
    repeated_core_ingredients: list[str]
    same_category_pairs: int
    max_ingredient_similarity: float
    category_count: int
    summary: str


class MenuPlan(BaseModel):
    id: str
    rank: int
    recipes: list[RecipeSummary]
    to_buy: list[str]
    covered: list[str]
    omitted_optional: list[str]
    diversity: DiversitySummary

    @property
    def recipe_ids(self) -> list[str]:
        return [recipe.id for recipe in self.recipes]

    @property
    def source_urls(self) -> list[str]:
        return [recipe.source_url for recipe in self.recipes]


class RecommendResult(BaseModel):
    plans: list[MenuPlan]
    reason: str | None = None
    candidate_count: int = 0
    normalized_input: NormalizedInput
    excluded_ingredients: list[str] = Field(default_factory=list)
    explanations: list[Explanation] = Field(default_factory=list)


@lru_cache(maxsize=1)
def _neutral_ingredients() -> frozenset[str]:
    resource = files("cookkg").joinpath("resources/diversity.json")
    payload = json.loads(resource.read_text(encoding="utf-8"))
    return frozenset(payload["neutral_ingredients"])


def _diversity_summary(
    graph: nx.DiGraph, nodes: list[str], required_sets: list[set[str]]
) -> DiversitySummary:
    core_sets = [required - _neutral_ingredients() for required in required_sets]
    counts = Counter(ingredient for required in core_sets for ingredient in required)
    repeated = sorted(name for name, count in counts.items() if count > 1)
    categories = sorted({str(graph.nodes[node].get("category") or "unknown") for node in nodes})
    category_values = [str(graph.nodes[node].get("category") or "unknown") for node in nodes]
    same_category_pairs = sum(
        1 for left, right in combinations(category_values, 2) if left == right
    )
    similarities = []
    for left, right in combinations(core_sets, 2):
        union = left | right
        similarities.append(len(left & right) / len(union) if union else 0.0)
    maximum = max(similarities, default=0.0)
    if not repeated and same_category_pairs == 0:
        summary = "菜品类别不同，且没有重复核心食材"
    elif repeated:
        summary = f"重复核心食材：{'、'.join(repeated)}"
    else:
        summary = "部分菜品属于相同类别"
    return DiversitySummary(
        categories=categories,
        repeated_core_ingredients=repeated,
        same_category_pairs=same_category_pairs,
        max_ingredient_similarity=round(maximum, 4),
        category_count=len(categories),
        summary=summary,
    )


def _category_path(graph: nx.DiGraph, ingredient: str, category: str) -> list[str] | None:
    start, target = f"i:{ingredient}", f"c:{category}"
    if start not in graph or target not in graph:
        return None
    queue: list[tuple[str, list[str]]] = [(start, [start])]
    visited = {start}
    while queue:
        current, path = queue.pop(0)
        if current == target:
            return path
        next_nodes = []
        for neighbor in graph.successors(current):
            relation = graph.edges[current, neighbor].get("relation")
            if relation in {"IS_A", "SUBCLASS_OF"} and neighbor not in visited:
                next_nodes.append(neighbor)
        for neighbor in sorted(next_nodes):
            visited.add(neighbor)
            queue.append((neighbor, [*path, neighbor]))
    return None


def expand_exclusions(
    graph: nx.DiGraph, exclude: set[str]
) -> tuple[set[str], dict[str, list[str]]]:
    expanded = set(exclude)
    paths: dict[str, list[str]] = {}
    category_aliases = graph.graph.get("category_aliases", {})
    ingredients = sorted(
        attrs["name"]
        for _, attrs in graph.nodes(data=True)
        if attrs.get("kind") == "ingredient"
    )
    for ingredient in ingredients:
        if ingredient in exclude:
            paths[ingredient] = [f"i:{ingredient}"]
            continue
        for category in sorted(exclude):
            category = category_aliases.get(category, category)
            path = _category_path(graph, ingredient, category)
            if path:
                expanded.add(ingredient)
                paths[ingredient] = path
                break
    return expanded, paths


def _explanation_path(
    graph: nx.DiGraph, recipe_node: str, path: list[str]
) -> list[ExplanationNode]:
    return [
        ExplanationNode(
            id=node,
            label=graph.nodes[node]["name"],
            kind=graph.nodes[node]["kind"],
        )
        for node in [recipe_node, *path]
    ]


def _explanation_edges(
    graph: nx.DiGraph, recipe_node: str, path: list[str]
) -> list[ExplanationEdge]:
    nodes = [recipe_node, *path]
    return [
        ExplanationEdge(
            source=source,
            target=target,
            relation=graph.edges[source, target]["relation"],
            evidence=graph.edges[source, target].get("evidence", []),
        )
        for source, target in zip(nodes, nodes[1:])
    ]


def _plan_id(recipe_ids: list[str]) -> str:
    digest = hashlib.sha256("\0".join(recipe_ids).encode("utf-8")).hexdigest()[:16]
    return f"plan-{digest}"


def _resolve_choice_groups(
    recipe_attrs: dict,
    uses: list[tuple[str, dict]],
    available: set[str],
    expanded_exclude: set[str],
) -> tuple[set[str], set[str]] | None:
    """Choose the minimum required members of each closed food choice group."""
    by_group: dict[str, list[str]] = {}
    for name, edge in uses:
        if edge.get("status") == "one_of" and edge.get("group_id"):
            by_group.setdefault(edge["group_id"], []).append(name)

    required: set[str] = set()
    omitted: set[str] = set()
    for group in sorted(recipe_attrs.get("choice_groups", []), key=lambda item: item["id"]):
        members = sorted(by_group.get(group["id"], []))
        allowed = [name for name in members if name not in expanded_exclude]
        omitted.update(set(members) & expanded_exclude)
        minimum = group["min_select"]
        if len(allowed) < minimum:
            return None
        chosen = sorted(allowed, key=lambda name: (name not in available, name))[:minimum]
        required.update(chosen)
    return required, omitted


def recommend(graph: nx.DiGraph, request: RecommendRequest) -> RecommendResult:
    have, pantry, exclude = request.have, request.pantry, request.exclude
    available = have | pantry
    expanded_exclude, exclusion_paths = expand_exclusions(graph, exclude)
    candidates = []
    explanations: list[tuple[str, str, Explanation]] = []
    for node, attrs in graph.nodes(data=True):
        if (
            attrs.get("kind") != "recipe"
            or not recipe_is_available(attrs)
            or not attrs.get("eligible", True)
            or attrs.get("category") == "condiment"
        ):
            continue
        uses = [
            (graph.nodes[target]["name"], edge)
            for _, target, edge in graph.out_edges(node, data=True)
            if graph.nodes[target].get("kind") == "ingredient"
        ]
        if any(edge.get("status") == "pending" for _, edge in uses):
            continue
        required = {name for name, edge in uses if edge.get("status") == "required"}
        optional = {name for name, edge in uses if edge.get("status") == "optional"}
        resolved_groups = _resolve_choice_groups(
            attrs, uses, available, expanded_exclude
        )
        if resolved_groups is None:
            continue
        group_required, group_omitted = resolved_groups
        required |= group_required
        rejected = sorted(required & expanded_exclude)
        if rejected:
            for ingredient in rejected:
                path = exclusion_paths.get(ingredient, [f"i:{ingredient}"])
                explanations.append(
                    (
                        attrs["id"],
                        ingredient,
                        Explanation(
                            id=f"exclude:{attrs['id']}:{ingredient}",
                            kind="excluded_required",
                            message=f"{attrs['name']} 必需使用{ingredient}；该食材命中排除条件。",
                            path=_explanation_path(graph, node, path),
                            edges=_explanation_edges(graph, node, path),
                        ),
                    )
                )
            continue
        missing = required - available
        covered = required & have
        candidates.append(
            (len(missing), -len(covered), attrs["id"], node, required, optional, group_omitted)
        )
    candidates.sort(key=lambda item: item[:3])
    candidate_count = len(candidates)
    candidates = candidates[:60]

    ranked = []
    for chosen in combinations(candidates, request.count):
        required = set().union(*(item[4] for item in chosen))
        to_buy = required - available
        if len(to_buy) > request.max_buy:
            continue
        covered = required & have
        ids = sorted(item[2] for item in chosen)
        omitted = set().union(
            *((item[5] & expanded_exclude) | item[6] for item in chosen)
        )
        nodes = sorted((item[3] for item in chosen), key=lambda node: graph.nodes[node]["id"])
        required_by_node = {item[3]: item[4] for item in chosen}
        diversity = _diversity_summary(
            graph, nodes, [required_by_node[node] for node in nodes]
        )
        core_ingredients = frozenset(
            set().union(*(required_by_node[node] for node in nodes))
            - _neutral_ingredients()
        )
        plan = MenuPlan(
            id=_plan_id(ids),
            rank=0,
            recipes=[
                RecipeSummary(
                    id=graph.nodes[node]["id"],
                    name=graph.nodes[node]["name"],
                    source_url=graph.nodes[node]["source_url"],
                )
                for node in nodes
            ],
            to_buy=sorted(to_buy),
            covered=sorted(covered),
            omitted_optional=sorted(omitted),
            diversity=diversity,
        )
        ranked.append(
            (
                len(diversity.repeated_core_ingredients),
                diversity.same_category_pairs,
                diversity.max_ingredient_similarity,
                len(to_buy),
                -len(covered),
                tuple(ids),
                plan,
                core_ingredients,
            )
        )
    ranked.sort(key=lambda item: item[:6])
    pool = [(item[6], item[7], index) for index, item in enumerate(ranked[:30])]
    selected: list[tuple[MenuPlan, frozenset[str], int]] = []
    if pool:
        selected.append(pool.pop(0))
    while pool and len(selected) < request.limit:
        selected_ids = [set(plan.recipe_ids) for plan, _, _ in selected]
        selected_cores = [core for _, core, _ in selected]

        def selection_key(
            item: tuple[MenuPlan, frozenset[str], int]
        ) -> tuple[int, int, int, int]:
            plan, core, base_rank = item
            return (
                max(len(set(plan.recipe_ids) & ids) for ids in selected_ids),
                max(len(core & selected_core) for selected_core in selected_cores),
                len(plan.diversity.repeated_core_ingredients),
                base_rank,
            )

        pool.sort(key=selection_key)
        selected.append(pool.pop(0))
    plans = [plan for plan, _, _ in selected]
    for rank, plan in enumerate(plans, 1):
        plan.rank = rank
    explanations.sort(key=lambda item: item[:2])
    return RecommendResult(
        plans=plans,
        reason=None if plans else "没有满足当前约束的菜单组合",
        candidate_count=candidate_count,
        normalized_input=NormalizedInput(
            have=sorted(have), pantry=sorted(pantry), exclude=sorted(exclude)
        ),
        excluded_ingredients=sorted(expanded_exclude),
        explanations=[item[2] for item in explanations[:5]],
    )
