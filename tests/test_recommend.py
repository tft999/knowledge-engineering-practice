import pytest
from pydantic import ValidationError

from cookkg.graph import build_graph
from cookkg.models import IngredientUse, Recipe
from cookkg.recommend import RecommendRequest, recommend


def recipe(path, name, required, optional=(), category="test"):
    return Recipe(
        id=path,
        name=name,
        category=category,
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


def test_balanced_ranking_matches_independent_exhaustive_enumeration():
    graph = build_graph(RECIPES)
    request = RecommendRequest(have={"西红柿"}, pantry={"盐"}, count=2, max_buy=4)
    result = recommend(graph, request)

    expected = []
    neutral = {"盐", "食用油"}
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
            core_sets = [
                {
                    item.name
                    for item in current.ingredients
                    if item.status == "required" and item.name not in neutral
                }
                for current in pair
            ]
            repeated = len(core_sets[0] & core_sets[1])
            same_category = int(pair[0].category == pair[1].category)
            union = core_sets[0] | core_sets[1]
            similarity = len(core_sets[0] & core_sets[1]) / len(union) if union else 0
            expected.append(
                (
                    repeated,
                    same_category,
                    similarity,
                    len(to_buy),
                    -len(covered),
                    tuple(ids),
                    ids,
                )
            )
    expected.sort()
    assert result.plans[0].recipe_ids == expected[0][6]
    assert {tuple(plan.recipe_ids) for plan in result.plans} == {
        tuple(item[6]) for item in expected
    }


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


def test_balanced_ranking_avoids_repeating_core_ingredient():
    graph = build_graph(
        [
            recipe("egg-a.md", "煎蛋", ["鸡蛋"], category="breakfast"),
            recipe("egg-b.md", "蒸蛋", ["鸡蛋"], category="breakfast"),
            recipe("tofu.md", "烧豆腐", ["豆腐"], category="vegetable_dish"),
        ]
    )

    result = recommend(
        graph,
        RecommendRequest(have={"鸡蛋", "豆腐"}, count=2, max_buy=0),
    )

    assert result.plans[0].recipe_ids != ["egg-a.md", "egg-b.md"]
    assert result.plans[0].diversity.repeated_core_ingredients == []
    assert result.plans[0].diversity.category_count == 2


def test_neutral_flavorings_do_not_make_dishes_similar():
    graph = build_graph(
        [
            recipe("tofu.md", "烧豆腐", ["豆腐", "盐", "食用油"]),
            recipe("potato.md", "炒土豆", ["土豆", "盐", "食用油"]),
        ]
    )

    result = recommend(
        graph,
        RecommendRequest(
            have={"豆腐", "土豆", "盐", "食用油"}, count=2, max_buy=0
        ),
    )

    diversity = result.plans[0].diversity
    assert diversity.repeated_core_ingredients == []
    assert diversity.max_ingredient_similarity == 0


def test_returned_plans_reduce_reuse_across_top_results():
    graph = build_graph(
        [
            recipe("a.md", "菜A", ["甲"], category="a"),
            recipe("b.md", "菜B", ["乙"], category="b"),
            recipe("c.md", "菜C", ["丙"], category="c"),
            recipe("d.md", "菜D", ["丁"], category="d"),
        ]
    )

    result = recommend(
        graph,
        RecommendRequest(have={"甲", "乙", "丙", "丁"}, count=2, max_buy=0, limit=3),
    )

    assert result.plans[0].recipe_ids == ["a.md", "b.md"]
    assert result.plans[1].recipe_ids == ["c.md", "d.md"]


def test_condiment_recipes_are_not_treated_as_standalone_dishes():
    graph = build_graph(
        [
            recipe("a-syrup.md", "糖浆", ["糖"], category="condiment"),
            recipe("z-soup.md", "蔬菜汤", ["白菜"], category="soup"),
        ]
    )

    result = recommend(
        graph,
        RecommendRequest(have={"糖", "白菜"}, count=1, max_buy=0),
    )

    assert result.plans[0].recipe_ids == ["z-soup.md"]


def test_top_results_do_not_repeat_a_dominant_core_ingredient():
    graph = build_graph(
        [
            recipe("a-egg.md", "煎蛋", ["鸡蛋"], category="breakfast"),
            recipe("b-egg.md", "蒸蛋", ["鸡蛋"], category="breakfast"),
            recipe("c-tofu.md", "豆腐", ["豆腐"], category="vegetable_dish"),
            recipe("d-potato.md", "土豆", ["土豆"], category="vegetable_dish"),
            recipe("e-fish.md", "鱼", ["鱼肉"], category="aquatic"),
            recipe("f-rice.md", "米饭", ["大米"], category="staple"),
        ]
    )
    result = recommend(
        graph,
        RecommendRequest(
            have={"鸡蛋", "豆腐", "土豆", "鱼肉", "大米"},
            count=2,
            max_buy=0,
            limit=2,
        ),
    )

    first_names = {recipe.name for recipe in result.plans[0].recipes}
    second_names = {recipe.name for recipe in result.plans[1].recipes}
    assert "煎蛋" in first_names
    assert "蒸蛋" not in second_names
