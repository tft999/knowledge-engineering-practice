from itertools import combinations

import networkx as nx
from pydantic import BaseModel, Field, field_validator

from cookkg.normalize import normalize_ingredient


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


class MenuPlan(BaseModel):
    recipe_ids: list[str]
    recipes: list[str]
    source_urls: list[str]
    to_buy: list[str]
    covered: list[str]
    omitted_optional: list[str]


class RecommendResult(BaseModel):
    plans: list[MenuPlan]
    reason: str | None = None
    candidate_count: int = 0


def _canon(values: set[str]) -> set[str]:
    return {normalize_ingredient(value) for value in values if value.strip()}


def recommend(graph: nx.DiGraph, request: RecommendRequest) -> RecommendResult:
    have, pantry, exclude = map(_canon, (request.have, request.pantry, request.exclude))
    available = have | pantry
    candidates = []
    for node, attrs in graph.nodes(data=True):
        if (
            attrs.get("kind") != "recipe"
            or not attrs.get("reviewed")
            or not attrs.get("eligible", True)
        ):
            continue
        uses = [
            (graph.nodes[target]["name"], edge)
            for _, target, edge in graph.out_edges(node, data=True)
        ]
        if any(edge["status"] == "pending" for _, edge in uses):
            continue
        required = {name for name, edge in uses if edge["status"] == "required"}
        optional = {name for name, edge in uses if edge["status"] == "optional"}
        if required & exclude:
            continue
        missing = required - available
        covered = required & have
        candidates.append((len(missing), -len(covered), attrs["id"], node, required, optional))
    candidates.sort(key=lambda item: item[:3])
    candidates = candidates[:60]

    ranked = []
    for chosen in combinations(candidates, request.count):
        required = set().union(*(item[4] for item in chosen))
        to_buy = required - available
        if len(to_buy) > request.max_buy:
            continue
        covered = required & have
        ids = sorted(item[2] for item in chosen)
        omitted = set().union(*(item[5] & exclude for item in chosen))
        nodes = sorted((item[3] for item in chosen), key=lambda n: graph.nodes[n]["id"])
        plan = MenuPlan(
            recipe_ids=ids,
            recipes=[graph.nodes[n]["name"] for n in nodes],
            source_urls=[graph.nodes[n]["source_url"] for n in nodes],
            to_buy=sorted(to_buy),
            covered=sorted(covered),
            omitted_optional=sorted(omitted),
        )
        ranked.append((len(to_buy), -len(covered), tuple(ids), plan))
    ranked.sort(key=lambda item: item[:3])
    plans = [item[3] for item in ranked[: request.limit]]
    return RecommendResult(
        plans=plans,
        reason=None if plans else "没有满足当前约束的菜单组合",
        candidate_count=len(candidates),
    )
