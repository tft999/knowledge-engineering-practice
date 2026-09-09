import hashlib
import json
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from cookkg.data_models import validate_recipe_id
from cookkg.models import IngredientStatus
from cookkg.parser import parse_recipe


class AddedIngredient(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    status: IngredientStatus = "required"

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("食材名称不能为空")
        return clean


class ReviewRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    approved: bool
    reviewed_on: date
    ingredient_status: dict[str, IngredientStatus] = Field(default_factory=dict)
    add_ingredients: list[AddedIngredient] = Field(default_factory=list)
    remove_ingredients: list[str] = Field(default_factory=list)
    add_tools: list[str] = Field(default_factory=list)
    remove_tools: list[str] = Field(default_factory=list)

    @field_validator(
        "remove_ingredients", "add_tools", "remove_tools", mode="after"
    )
    @classmethod
    def validate_names(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value for value in cleaned):
            raise ValueError("名称不能为空")
        return cleaned

    @field_validator("ingredient_status", mode="after")
    @classmethod
    def validate_status_names(
        cls, values: dict[str, IngredientStatus]
    ) -> dict[str, IngredientStatus]:
        if any(not name.strip() for name in values):
            raise ValueError("食材名称不能为空")
        return {name.strip(): status for name, status in values.items()}


def load_review_records(path: Path) -> dict[str, ReviewRecord]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("审核文件顶层必须是对象")
    records: dict[str, ReviewRecord] = {}
    for recipe_id, value in payload.items():
        if not isinstance(recipe_id, str):
            raise ValueError(f"非法菜谱 ID：{recipe_id}")
        validate_recipe_id(recipe_id)
        records[recipe_id] = ReviewRecord.model_validate(value)
    return records


def _verify_source(raw: Path, commit: str) -> None:
    marker = raw / ".cookkg-source.json"
    if not marker.exists():
        raise RuntimeError("原始数据缺少 CookKG 来源清单")
    manifest = json.loads(marker.read_text(encoding="utf-8"))
    if manifest.get("commit") != commit:
        raise RuntimeError("原始数据提交不匹配")


def build_review_queue(
    raw: Path, reviews_path: Path, commit: str, limit: int = 20
) -> list[dict]:
    _verify_source(raw, commit)
    reviews = load_review_records(reviews_path)
    queue: list[dict] = []
    for path in sorted((raw / "dishes").rglob("*.md")):
        relative = path.relative_to(raw).as_posix()
        text = path.read_text(encoding="utf-8")
        result = parse_recipe(text, relative, commit)
        if result.skipped:
            continue
        review = reviews.get(relative)
        if review and review.approved and review.sha256 == result.recipe.source_hash:
            continue
        queue.append(
            {
                "recipe_id": relative,
                "name": result.recipe.name,
                "issues": result.issues,
                "sha256": result.recipe.source_hash,
                "source_path": str(path.resolve()),
                "source_url": result.recipe.source_url,
                "ingredients": [
                    ingredient.model_dump(mode="json")
                    for ingredient in result.recipe.ingredients
                ],
                "tools": result.recipe.tools,
            }
        )
    queue.sort(
        key=lambda item: (
            0 if item["issues"] else 1,
            len(item["issues"]),
            item["recipe_id"],
        )
    )
    return queue[:limit]


def check_reviews(raw: Path, reviews_path: Path, commit: str) -> dict:
    _verify_source(raw, commit)
    reviews = load_review_records(reviews_path)
    stale: list[str] = []
    missing: list[str] = []
    for recipe_id, record in reviews.items():
        path = (raw / recipe_id).resolve()
        if not path.is_relative_to(raw.resolve()):
            raise ValueError(f"非法菜谱路径：{recipe_id}")
        if not path.is_file():
            missing.append(recipe_id)
            continue
        digest = hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
        if digest != record.sha256:
            stale.append(recipe_id)
    result = {
        "review_count": len(reviews),
        "approved_count": sum(record.approved for record in reviews.values()),
        "matching_hashes": len(reviews) - len(stale) - len(missing),
        "stale_reviews": stale,
        "missing_recipes": missing,
        "ok": not stale and not missing,
    }
    return result
