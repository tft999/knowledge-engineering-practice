import json
import re
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_stage_one_sample_contains_twenty_traceable_drafts():
    path = ROOT / "docs/annotations/sample-20-zouyilin06-draft.json"
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["state"] == "pending_independent_second_review"
    assert len(payload["recipes"]) == 20
    ids = [recipe["recipe_id"] for recipe in payload["recipes"]]
    assert len(set(ids)) == 20
    assert all(recipe_id.startswith("dishes/") for recipe_id in ids)
    assert all(re.fullmatch(r"[0-9a-f]{64}", recipe["sha256"]) for recipe in payload["recipes"])
    assert all(recipe["decisions"] and recipe["evidence"] for recipe in payload["recipes"])


def test_hierarchy_draft_has_valid_parent_references_and_no_cycles():
    path = ROOT / "src/cookkg/resources/ingredient_hierarchy.draft.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    categories = {category["id"]: category["parent"] for category in payload["categories"]}

    assert categories["食材"] is None
    assert all(parent is None or parent in categories for parent in categories.values())
    for category in categories:
        seen = set()
        current = category
        while current is not None:
            assert current not in seen
            seen.add(current)
            current = categories[current]

    relations = payload["ingredient_is_a"]
    assert len({relation["child"] for relation in relations}) == len(relations)
    assert all(relation["parent"] in categories for relation in relations)
