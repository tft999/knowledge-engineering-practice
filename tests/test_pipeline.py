import hashlib
import json

from cookkg.pipeline import build_dataset

GOOD = """# 家常菜的做法

## 必备原料和工具

- 土豆
- 盐

## 操作

1. 土豆加盐炒熟。
"""


def test_build_requires_matching_human_review_hash(tmp_path):
    raw = tmp_path / "raw"
    output = tmp_path / "processed"
    path = raw / "dishes" / "vegetable" / "家常菜.md"
    path.parent.mkdir(parents=True)
    path.write_text(GOOD, encoding="utf-8")
    digest = hashlib.sha256(GOOD.encode()).hexdigest()
    reviews = tmp_path / "reviews.json"
    reviews.write_text(
        json.dumps({"dishes/vegetable/家常菜.md": {"sha256": digest, "approved": True}}),
        encoding="utf-8",
    )

    report = build_dataset(raw, output, "abc", reviews)
    row = json.loads((output / "recipes.jsonl").read_text(encoding="utf-8"))
    assert row["reviewed"] is True
    assert report["reviewed_eligible"] == 1
    assert (output / "graph.json").exists()

    reviews.write_text(
        json.dumps({"dishes/vegetable/家常菜.md": {"sha256": "stale", "approved": True}}),
        encoding="utf-8",
    )
    report = build_dataset(raw, output, "abc", reviews)
    row = json.loads((output / "recipes.jsonl").read_text(encoding="utf-8"))
    assert row["reviewed"] is False
    assert report["stale_reviews"] == 1


def test_review_can_add_remove_and_resolve_ingredients(tmp_path):
    raw = tmp_path / "raw"
    output = tmp_path / "processed"
    path = raw / "dishes" / "vegetable" / "家常菜.md"
    path.parent.mkdir(parents=True)
    path.write_text(GOOD, encoding="utf-8")
    digest = hashlib.sha256(GOOD.encode()).hexdigest()
    reviews = tmp_path / "reviews.json"
    reviews.write_text(
        json.dumps(
            {
                "dishes/vegetable/家常菜.md": {
                    "sha256": digest,
                    "approved": True,
                    "remove_ingredients": ["盐"],
                    "add_ingredients": [{"name": "食用油", "status": "required"}],
                }
            }
        ),
        encoding="utf-8",
    )
    build_dataset(raw, output, "abc", reviews)
    row = json.loads((output / "recipes.jsonl").read_text(encoding="utf-8"))
    assert [(item["name"], item["status"]) for item in row["ingredients"]] == [
        ("土豆", "required"),
        ("食用油", "required"),
    ]


def test_build_reports_skipped_templates_and_missing_sections(tmp_path):
    raw = tmp_path / "raw"
    output = tmp_path / "processed"
    (raw / "dishes/template/x").mkdir(parents=True)
    (raw / "dishes/template/x/x.md").write_text(GOOD, encoding="utf-8")
    (raw / "dishes/broken").mkdir(parents=True)
    (raw / "dishes/broken/x.md").write_text("# X 的做法", encoding="utf-8")
    reviews = tmp_path / "reviews.json"
    reviews.write_text("{}", encoding="utf-8")
    report = build_dataset(raw, output, "abc", reviews)
    assert report["scanned"] == 2
    assert report["skipped"] == 1
    assert report["ineligible"] == 1
