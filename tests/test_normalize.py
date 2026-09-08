from cookkg.normalize import normalize_ingredient


def test_confirmed_alias_is_normalized():
    assert normalize_ingredient("番茄") == "西红柿"


def test_distinct_sauces_are_not_merged():
    assert normalize_ingredient("生抽") == "生抽"
    assert normalize_ingredient("老抽") == "老抽"


def test_quantity_and_optional_suffix_are_removed():
    assert normalize_ingredient("土豆 2 个（可选）") == "土豆"
