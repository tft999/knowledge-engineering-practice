import hashlib
import json

import pytest
from pydantic import ValidationError

from cookkg.review import ReviewRecord, build_review_queue, check_reviews


def _write_source(raw, path, text):
    target = raw / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _mark_source(raw, commit="abc"):
    (raw / ".cookkg-source.json").write_text(
        json.dumps({"commit": commit}), encoding="utf-8"
    )


def test_review_record_rejects_invalid_fields():
    valid = {
        "sha256": "a" * 64,
        "approved": True,
        "reviewed_on": "2026-09-09",
    }
    with pytest.raises(ValidationError):
        ReviewRecord.model_validate({**valid, "ingredient_status": {"盐": "requird"}})
    with pytest.raises(ValidationError):
        ReviewRecord.model_validate({**valid, "add_tools": [" "]})
    with pytest.raises(ValidationError):
        ReviewRecord.model_validate({**valid, "sha256": "short"})
    with pytest.raises(ValidationError):
        ReviewRecord.model_validate({**valid, "unexpected": True})


def test_review_queue_prioritizes_fewer_parser_issues(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    _mark_source(raw)
    one_issue = """# 甲的做法

## 必备原料和工具

- 土豆

## 操作

1. 加盐炒熟。
"""
    two_issues = one_issue.replace("加盐", "加盐和糖").replace("# 甲", "# 乙")
    _write_source(raw, "dishes/vegetable/甲.md", one_issue)
    _write_source(raw, "dishes/vegetable/乙.md", two_issues)
    reviews = tmp_path / "reviews.json"
    reviews.write_text("{}", encoding="utf-8")

    queue = build_review_queue(raw, reviews, "abc", 2)

    assert [item["recipe_id"] for item in queue] == [
        "dishes/vegetable/甲.md",
        "dishes/vegetable/乙.md",
    ]
    assert queue[0]["issues"] == ["ingredient_only_in_steps:盐"]
    assert queue[0]["source_path"].endswith("甲.md")


def test_review_queue_skips_current_approved_review(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    _mark_source(raw)
    text = """# 甲的做法

## 必备原料和工具

- 土豆

## 操作

1. 土豆炒熟。
"""
    recipe_id = "dishes/vegetable/甲.md"
    _write_source(raw, recipe_id, text)
    reviews = tmp_path / "reviews.json"
    reviews.write_text(
        json.dumps(
            {
                recipe_id: {
                    "sha256": hashlib.sha256(text.encode()).hexdigest(),
                    "approved": True,
                    "reviewed_on": "2026-09-09",
                }
            }
        ),
        encoding="utf-8",
    )

    assert build_review_queue(raw, reviews, "abc", 20) == []
    assert check_reviews(raw, reviews, "abc")["ok"] is True


def test_review_check_reports_stale_and_missing_sources(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    _mark_source(raw)
    recipe_id = "dishes/vegetable/甲.md"
    _write_source(raw, recipe_id, "changed")
    reviews = tmp_path / "reviews.json"
    reviews.write_text(
        json.dumps(
            {
                recipe_id: {
                    "sha256": "a" * 64,
                    "approved": True,
                    "reviewed_on": "2026-09-09",
                },
                "dishes/vegetable/不存在.md": {
                    "sha256": "b" * 64,
                    "approved": False,
                    "reviewed_on": "2026-09-09",
                },
            }
        ),
        encoding="utf-8",
    )

    result = check_reviews(raw, reviews, "abc")

    assert result["ok"] is False
    assert result["stale_reviews"] == [recipe_id]
    assert result["missing_recipes"] == ["dishes/vegetable/不存在.md"]
