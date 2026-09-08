from cookkg.parser import parse_recipe

TEXT = """# 西红柿炒鸡蛋的做法

家常菜。

预估烹饪难度：★★

## 必备原料和工具

- 番茄
- 鸡蛋
- 糖（可选）
- 锅

## 计算

- 西红柿 = 1 个 * 份数
- 鸡蛋 = 2 个 * 份数

## 操作

1. 放入食用油，炒鸡蛋。
2. 加入西红柿。
"""


def test_parse_recipe_extracts_and_cross_checks_sections():
    result = parse_recipe(TEXT, "dishes/vegetable/西红柿炒鸡蛋.md", "abc")

    assert result.recipe.name == "西红柿炒鸡蛋"
    assert result.recipe.category == "vegetable"
    assert result.recipe.difficulty == 2
    assert [(item.name, item.status) for item in result.recipe.ingredients] == [
        ("西红柿", "required"),
        ("鸡蛋", "required"),
        ("糖", "optional"),
        ("食用油", "pending"),
    ]
    assert result.recipe.tools == ["锅"]
    assert "ingredient_only_in_steps:食用油" in result.issues
    assert result.recipe.ingredients[0].quantity_raw == ["西红柿 = 1 个 * 份数"]
    assert result.recipe.source_url.endswith("/blob/abc/dishes/vegetable/西红柿炒鸡蛋.md")


def test_missing_ingredient_section_is_not_silently_accepted():
    result = parse_recipe("# 空菜的做法\n\n## 操作\n\n1. 开火", "dishes/x.md", "abc")
    assert result.recipe.eligible is False
    assert "missing_ingredients_section" in result.issues


def test_template_path_is_skipped():
    result = parse_recipe(TEXT, "dishes/template/示例菜/示例菜.md", "abc")
    assert result.skipped is True
    assert "template" in result.issues


def test_calculation_only_ingredient_is_pending():
    text = """# 测试菜的做法

## 必备原料和工具
- 土豆
## 计算
- 食用油 10ml
## 操作
1. 土豆煮熟
"""
    result = parse_recipe(text, "dishes/test.md", "abc")
    assert ("食用油", "pending") in [
        (ingredient.name, ingredient.status) for ingredient in result.recipe.ingredients
    ]
    assert "ingredient_only_in_calculation:食用油" in result.issues
