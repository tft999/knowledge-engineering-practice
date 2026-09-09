from cookkg.data_delivery import acceptance_report, resolution_kind


def test_technical_build_cannot_claim_course_completion():
    result = acceptance_report(dict(source_hashes_validated=100, human_confirmed=0,
                                    strict_eligible=0), [])
    assert not result["complete"]
    assert "hundred_human_reviewed" in result["incomplete"]
    assert "first_twenty_independent_and_adjudicated" in result["incomplete"]


def test_cross_review_is_distinct_and_bound_to_current_hashes():
    recipe = dict(id="dishes/a.md", source_hash="a" * 64, annotation_hash="b" * 64,
                  review_state="pending", strict_eligible=False)
    report = dict(source_hashes_validated=1, human_confirmed=0, strict_eligible=0)
    review = dict(recipe_id=recipe["id"], primary_annotator="A", reviewer="A",
                  source_hash=recipe["source_hash"], annotation_hash=recipe["annotation_hash"],
                  reviewed_on="2026-09-09", outcome="approved")
    team = dict(cross_reviews=[review])
    assert acceptance_report(report, [recipe], team)["valid_cross_reviews"] == 0
    review["reviewer"] = "B"
    assert acceptance_report(report, [recipe], team)["valid_cross_reviews"] == 1
    review["annotation_hash"] = "c" * 64
    assert acceptance_report(report, [recipe], team)["valid_cross_reviews"] == 0


def test_source_ambiguity_is_not_replaced_with_a_guessed_amount():
    kind, action = resolution_kind("白砂糖计算26g，步骤分别18g、50g、8g共76g。")
    assert kind == "source_conflict" and "不能" in action


def test_public_ui_contract_has_no_unknown_requirement():
    from pathlib import Path

    # Inspect the newly fetched frontend contract; it has no pending/unknown DTO option.
    text = (Path(__file__).parents[1] / "web/src/api/types.ts").read_text(encoding="utf-8")
    ingredient_type = text.split("export type RecipeIngredient =", 1)[1].split("};", 1)[0]
    assert '"required" | "optional" | "one_of"' in ingredient_type
