import pytest
from pydantic import ValidationError

from cookkg.data_models import Quantity
from cookkg.data_quantities import observe_forms, observe_quantities


def amounts(text, name="盐", names=None):
    return observe_quantities(text, 1, [name], names or {name: [name]}, name)


@pytest.mark.parametrize("text,expected", [
    ("- 盐 500g", dict(kind="exact", value=500, unit="g")),
    ("* 盐 1-2g", dict(kind="range", minimum=1, maximum=2)),
    ("* 盐 1g-2g", dict(kind="range", minimum=1, maximum=2)),
    ("- 盐 10±5g", dict(kind="adjustable", value=10, adjustment=5)),
    ("- 盐 10g（按口味加减±5g）", dict(kind="adjustable", value=10, adjustment=5)),
    ("- 盐 适量", dict(kind="qualitative", value=None)),
    ("- 盐 份数 * 12ml", dict(kind="formula", value=None)),
    ("- 盐 每份 1g", dict(kind="formula", value=None)),
    ("- 盐 1/2 勺", dict(kind="formula", value=None)),
    ("- 盐 少于5g以内", dict(kind="unparsed", value=None)),
])
def test_quantity_semantics(text, expected):
    result = amounts(text)
    assert len(result) == 1
    for key, value in expected.items():
        assert result[0][key] == value


def test_shared_total_never_assigned_to_each_ingredient():
    names = {name: [name] for name in ["葱", "姜", "蒜"]}
    for name in names:
        result = amounts("- 葱、姜、蒜共15g", name, names)
        assert result[0]["scope"] == "combined"
        assert set(result[0]["member_ids"]) == set(names)


def test_temperature_and_other_ingredients_cannot_become_amounts():
    assert [q["value"] for q in amounts("- 水 100°C，1500ml", "水")] == [1500]
    names = {"盐": ["盐"], "糖": ["糖"]}
    assert amounts("- 盐2g糖5g", names=names)[0]["kind"] == "unparsed"
    assert amounts("- 糖5g", names=names)[0]["kind"] == "unparsed"
    assert amounts("- 配料总重100克以内")[0]["kind"] == "unparsed"
    assert amounts("- 洋葱 50g", "洋葱", {"洋葱": ["洋葱"], "葱": ["葱"]})[0]["value"] == 50
    assert amounts("- 蚝油 5ml", "蚝油", {"蚝油": ["蚝油"], "油": ["油"]})[0]["value"] == 5
    assert amounts("- 米（金龙鱼30元5kg的就行）", "米")[0]["kind"] == "unparsed"


def test_forms_are_local_and_not_inferred_from_unrelated_steps():
    names = {"蒜": ["蒜"], "姜": ["姜"]}
    evidence = [dict(line=1, text="- 蒜切末，姜切片"), dict(line=2, text="- 蒜不要切碎")]
    forms = observe_forms(evidence, ["蒜"], names, "蒜")
    assert [f["form"] for f in forms] == ["切末"]


def test_quantity_rejects_ungrounded_or_impossible_values():
    item = amounts("- 盐 1-2g")[0]
    item["minimum"] = 3
    with pytest.raises(ValidationError):
        Quantity.model_validate(item)
    item = amounts("- 盐 5g")[0]
    item["value"] = 500
    with pytest.raises(ValidationError, match="differs"):
        Quantity.model_validate(item)
    item = amounts("- 盐 5g")[0]
    item["raw"] = "500g"
    with pytest.raises(ValidationError):
        Quantity.model_validate(item)
