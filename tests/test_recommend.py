import pytest
from pydantic import ValidationError

from cookkg.graph import build_graph
from cookkg.models import IngredientUse, Recipe
from cookkg.recommend import RecommendRequest, recommend


def recipe(path, name, required, optional=()):
    return Recipe(
        id=path,
        name=name,
        category="test",
        source_url=f"https://example/{path}",
        source_hash="hash",
        reviewed=True,
        ingredients=[IngredientUse(name=x, status="required") for x in required]
        + [IngredientUse(name=x, status="optional") for x in optional],
    )


RECIPES = [
    recipe("a.md", "番茄蛋", ["西红柿", "鸡蛋", "盐"], ["葱"]),
    recipe("b.md", "土豆蛋", ["土豆", "鸡蛋", "盐"], ["辣椒"]),
    recipe("c.md", "辣椒肉", ["辣椒", "猪肉"]),
]


def test_shared_missing_ingredient_is_counted_once_and_sort_is_stable():
    result = recommend(
        build_graph(RECIPES),
        RecommendRequest(have={"西红柿", "土豆"}, pantry={"盐"}, count=2, max_buy=1),
    )
    assert result.plans[0].recipe_ids == ["a.md", "b.md"]
    assert result.plans[0].to_buy == ["鸡蛋"]
    assert result.plans[0].covered == ["土豆", "西红柿"]


def test_excluded_required_rejects_and_excluded_optional_is_omitted():
    result = recommend(
        build_graph(RECIPES),
        RecommendRequest(have={"西红柿", "鸡蛋"}, pantry={"盐"}, exclude={"葱"}),
    )
    assert result.plans[0].omitted_optional == ["葱"]

    no_meat = recommend(
        build_graph(RECIPES),
        RecommendRequest(have={"辣椒"}, exclude={"猪肉"}),
    )
    assert all("c.md" not in plan.recipe_ids for plan in no_meat.plans)


def test_no_solution_does_not_relax_constraints():
    result = recommend(
        build_graph(RECIPES), RecommendRequest(have=set(), count=3, max_buy=0)
    )
    assert result.plans == []
    assert result.reason == "没有满足当前约束的菜单组合"


def test_unreviewed_or_pending_recipe_is_not_recommended():
    pending = recipe("p.md", "待核验", ["豆腐"])
    pending.ingredients[0].status = "pending"
    pending.reviewed = False
    result = recommend(build_graph([pending]), RecommendRequest(have={"豆腐"}))
    assert result.plans == []


def test_ranking_matches_independent_exhaustive_enumeration():
    graph = build_graph(RECIPES)
    request = RecommendRequest(have={"西红柿"}, pantry={"盐"}, count=2, max_buy=4)
    result = recommend(graph, request)

    expected = []
    for left in range(len(RECIPES)):
        for right in range(left + 1, len(RECIPES)):
            pair = [RECIPES[left], RECIPES[right]]
            required = {
                item.name
                for current in pair
                for item in current.ingredients
                if item.status == "required"
            }
            to_buy = required - request.have - request.pantry
            covered = required & request.have
            ids = sorted(current.id for current in pair)
            expected.append((len(to_buy), -len(covered), tuple(ids), ids))
    expected.sort()
    assert [plan.recipe_ids for plan in result.plans] == [item[3] for item in expected[:5]]


def test_category_exclusion_filters_descendants_and_returns_path_explanation():
    pepper = recipe("pepper.md", "小炒肉", ["小米椒", "猪肉"])
    safe = recipe("safe.md", "番茄蛋", ["西红柿", "鸡蛋"])

    result = recommend(
        build_graph([pepper, safe]),
        RecommendRequest(have={"小米椒", "猪肉", "西红柿", "鸡蛋"}, exclude={"辣椒"}),
    )

    assert [item.id for item in result.plans[0].recipes] == ["safe.md"]
    assert {"辣椒", "小米椒", "朝天椒", "青椒"} <= set(result.excluded_ingredients)
    explanation = result.explanations[0]
    assert explanation.kind == "excluded_required"
    assert [node.label for node in explanation.path] == ["小炒肉", "小米椒", "辣椒"]


def test_normalized_available_and_excluded_inputs_conflict():
    with pytest.raises(ValidationError, match="归一化后同时出现在可用与排除条件"):
        RecommendRequest(have={"番茄"}, exclude={"西红柿"})


def test_plan_ids_and_ranks_are_stable():
    graph = build_graph(RECIPES)
    request = RecommendRequest(have={"西红柿"}, pantry={"盐"}, count=2, max_buy=4)

    first = recommend(graph, request)
    second = recommend(graph, request)

    assert [plan.id for plan in first.plans] == [plan.id for plan in second.plans]
    assert [plan.rank for plan in first.plans] == list(range(1, len(first.plans) + 1))
    assert first.normalized_input.have == ["西红柿"]
