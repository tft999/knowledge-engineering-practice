import hashlib
import json

import pytest

from cookkg.pipeline import build_dataset, fetch_dataset

GOOD = """# 家常菜的做法

## 必备原料和工具

- 土豆
- 盐

## 操作

1. 土豆加盐炒熟。
"""


def mark_source(raw, commit="abc"):
    (raw / ".cookkg-source.json").write_text(
        json.dumps({"commit": commit}), encoding="utf-8"
    )


def test_build_requires_matching_human_review_hash(tmp_path):
    raw = tmp_path / "raw"
    output = tmp_path / "processed"
    path = raw / "dishes" / "vegetable" / "家常菜.md"
    path.parent.mkdir(parents=True)
    path.write_text(GOOD, encoding="utf-8")
    mark_source(raw)
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
    mark_source(raw)
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
                    "add_tools": ["炒锅"],
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
    assert row["tools"] == ["炒锅"]


def test_build_reports_skipped_templates_and_missing_sections(tmp_path):
    raw = tmp_path / "raw"
    output = tmp_path / "processed"
    (raw / "dishes/template/x").mkdir(parents=True)
    (raw / "dishes/template/x/x.md").write_text(GOOD, encoding="utf-8")
    (raw / "dishes/broken").mkdir(parents=True)
    (raw / "dishes/broken/x.md").write_text("# X 的做法", encoding="utf-8")
    mark_source(raw)
    reviews = tmp_path / "reviews.json"
    reviews.write_text("{}", encoding="utf-8")
    report = build_dataset(raw, output, "abc", reviews)
    assert report["scanned"] == 2
    assert report["skipped"] == 1
    assert report["ineligible"] == 1


def test_fetch_never_replaces_an_unmanaged_directory(tmp_path):
    destination = tmp_path / "existing"
    destination.mkdir()
    (destination / "important.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(RuntimeError, match="不是 CookKG 管理的数据目录"):
        fetch_dataset(destination, force=True)
    assert (destination / "important.txt").read_text(encoding="utf-8") == "keep"


def test_build_rejects_missing_or_wrong_source_manifest(tmp_path):
    raw = tmp_path / "raw"
    (raw / "dishes").mkdir(parents=True)
    reviews = tmp_path / "reviews.json"
    reviews.write_text("{}", encoding="utf-8")
    with pytest.raises(RuntimeError, match="来源清单"):
        build_dataset(raw, tmp_path / "out", "abc", reviews)
    mark_source(raw, "wrong")
    with pytest.raises(RuntimeError, match="提交不匹配"):
        build_dataset(raw, tmp_path / "out", "abc", reviews)


def test_build_rejects_invalid_review_status(tmp_path):
    raw = tmp_path / "raw"
    path = raw / "dishes" / "vegetable" / "家常菜.md"
    path.parent.mkdir(parents=True)
    path.write_text(GOOD, encoding="utf-8")
    mark_source(raw)
    reviews = tmp_path / "reviews.json"
    reviews.write_text(
        json.dumps(
            {
                "dishes/vegetable/家常菜.md": {
                    "sha256": hashlib.sha256(GOOD.encode()).hexdigest(),
                    "approved": True,
                    "ingredient_status": {"盐": "requird"},
                }
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="非法食材状态"):
        build_dataset(raw, tmp_path / "out", "abc", reviews)
