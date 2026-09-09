"""忌口推理（排除集合扩展）测试。"""

from cookkg.exclusion import expand_exclusions


def test_category_excludes_descendant_ingredients(engine):
    result = expand_exclusions(["辣椒"], engine.taxonomy, engine.normalizer)
    assert "小米椒" in result.excluded_ingredients
    assert "朝天椒" in result.excluded_ingredients
    assert "青椒" in result.excluded_ingredients
    assert "辣椒" in result.excluded_categories
    # 类别名本身作为字面兜底，命中菜谱中以“辣椒”为食材名的项
    assert "辣椒" in result.excluded_literals


def test_subcategory_descendants(engine):
    # 辣椒 SUBCLASS_OF 蔬菜，蔬菜的后代类别包含辣椒，但辣椒的后代食材不在蔬菜下
    result = expand_exclusions(["蔬菜"], engine.taxonomy, engine.normalizer)
    # 蔬菜类别下的直接食材（西红柿、土豆）
    assert "西红柿" in result.excluded_ingredients
    assert "土豆" in result.excluded_ingredients


def test_specific_ingredient_exact(engine):
    result = expand_exclusions(["小米椒"], engine.taxonomy, engine.normalizer)
    assert result.excluded_ingredients == {"小米椒"}


def test_alias_normalization_before_expansion(engine):
    result = expand_exclusions(["马铃薯"], engine.taxonomy, engine.normalizer)
    # “马铃薯”归一化为“土豆”，命中蔬菜类别下的食材
    assert "土豆" in result.excluded_ingredients


def test_component_expansion(engine_component):
    result = expand_exclusions(
        ["辣椒"], engine_component.taxonomy, engine_component.normalizer, use_component=True
    )
    # 豆瓣酱 HAS_COMPONENT 辣椒，成分扩展后应被排除
    assert "豆瓣酱" in result.excluded_ingredients


def test_component_expansion_disabled_by_default(engine):
    result = expand_exclusions(["辣椒"], engine.taxonomy, engine.normalizer)
    assert "豆瓣酱" not in result.excluded_ingredients


def test_unknown_literal_fallback(engine):
    result = expand_exclusions(["某种神秘食材"], engine.taxonomy, engine.normalizer)
    assert result.excluded_literals == {"某种神秘食材"}
