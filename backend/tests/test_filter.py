"""候选过滤测试。"""

from cookkg.exclusion import expand_exclusions
from cookkg.filter import filter_recipe


def _find(engine, recipe_id):
    for r in engine.recipes:
        if r.id == recipe_id:
            return r
    raise AssertionError(f"未找到菜谱 {recipe_id}")


def _exclude(engine, *names):
    return expand_exclusions(list(names), engine.taxonomy, engine.normalizer)


def test_required_conflict_rejects(engine):
    recipe = _find(engine, "dishes/meat_dish/小炒肉.md")
    result = filter_recipe(recipe, _exclude(engine, "辣椒"), set(), set())
    assert not result.retained
    assert "小米椒" in result.reason
    assert any(e.verdict == "excluded" for e in result.explanations)


def test_optional_conflict_omits(engine):
    recipe = _find(engine, "dishes/vegetable_dish/酸辣土豆丝.md")
    result = filter_recipe(recipe, _exclude(engine, "辣椒"), set(), set())
    assert result.retained
    assert [o.ingredient for o in result.omitted] == ["辣椒"]
    assert result.required == {"土豆", "食用油", "盐", "醋"}


def test_optional_kept_when_no_conflict(engine):
    recipe = _find(engine, "dishes/vegetable_dish/酸辣土豆丝.md")
    result = filter_recipe(recipe, _exclude(engine, "香菜"), set(), set())
    assert result.retained
    assert result.omitted == []


def test_required_group_conflict_rejects(engine):
    # 水煮鱼必需选择组含土豆/豆芽/花菜/生菜；排除蔬菜会命中土豆（蔬菜类）
    recipe = _find(engine, "dishes/meat_dish/水煮鱼.md")
    # 只排除“土豆”这一具体食材不足以淘汰整组（还有豆芽等可用）
    r1 = filter_recipe(recipe, _exclude(engine, "土豆"), set(), set())
    assert r1.retained
    # 排除整个蔬菜类别会命中全部成员 -> 淘汰
    r2 = filter_recipe(recipe, _exclude(engine, "蔬菜"), set(), set())
    assert not r2.retained
    assert "可用成员不足" in r2.reason


def test_required_group_prefers_stock(engine):
    recipe = _find(engine, "dishes/meat_dish/水煮鱼.md")
    result = filter_recipe(recipe, _exclude(engine), {"土豆"}, {"盐"})
    assert result.retained
    assert "土豆" in result.required  # 库存中的成员优先选中
    assert result.buy == {"草鱼", "食用油"}  # 土豆用库存，无需补购


def test_optional_group_omits_blocked(engine):
    # 蛋炒饭可选选择组：灯影牛肉丝/午餐肉/腊肠；排除腊肠只省略该成员，不影响菜谱
    recipe = _find(engine, "dishes/staple/蛋炒饭.md")
    result = filter_recipe(recipe, _exclude(engine, "腊肠"), set(), set())
    assert result.retained
    assert "腊肠" in [o.ingredient for o in result.omitted]


def test_pending_recipe_rejected(engine):
    recipe = _find(engine, "dishes/meat_dish/麻婆豆腐.md")
    result = filter_recipe(recipe, _exclude(engine), set(), set())
    assert not result.retained
    assert "未通过人工审核" in result.reason
