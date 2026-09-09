"""输入归一化测试。"""

from cookkg.normalization import Normalizer

ALIASES = {"番茄": "西红柿", "马铃薯": "土豆", "蒜末": "蒜", "蒜瓣": "蒜", "a": "b", "b": "c"}


def test_basic_alias():
    n = Normalizer(ALIASES)
    assert n.normalize("番茄") == "西红柿"
    assert n.normalize("马铃薯") == "土豆"


def test_chain_alias():
    n = Normalizer(ALIASES)
    assert n.normalize("a") == "c"


def test_unknown_unchanged():
    n = Normalizer(ALIASES)
    assert n.normalize("牛肉") == "牛肉"


def test_strip_and_empty():
    n = Normalizer(ALIASES)
    assert n.normalize("  西红柿  ") == "西红柿"
    assert n.normalize("") == ""


def test_normalize_all_dedup_order():
    n = Normalizer(ALIASES)
    assert n.normalize_all(["番茄", "西红柿", "", "马铃薯"]) == ["西红柿", "土豆"]


def test_alias_cycle_terminates():
    n = Normalizer({"x": "y", "y": "x"})
    assert n.normalize("x") in {"x", "y"}
