import json
import shutil
import tempfile
import urllib.request
import zipfile
from importlib.resources import files
from pathlib import Path

from cookkg.graph import build_graph, dump_graph
from cookkg.models import IngredientUse, Recipe
from cookkg.normalize import normalize_ingredient
from cookkg.parser import parse_recipe


def source_config() -> dict:
    path = files("cookkg").joinpath("resources/sources.json")
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_dataset(destination: Path, force: bool = False) -> dict:
    config = source_config()
    marker = destination / ".cookkg-source.json"
    if marker.exists() and not force:
        current = json.loads(marker.read_text(encoding="utf-8"))
        if current.get("commit") == config["commit"]:
            return current
        raise RuntimeError("数据目录来自其他提交；使用 --force 明确替换")
    with tempfile.TemporaryDirectory(prefix="cookkg-") as temporary:
        archive = Path(temporary) / "source.zip"
        urllib.request.urlretrieve(config["archive_url"], archive)
        unpacked = Path(temporary) / "unpacked"
        with zipfile.ZipFile(archive) as package:
            for member in package.infolist():
                candidate = (unpacked / member.filename).resolve()
                if unpacked.resolve() not in candidate.parents and candidate != unpacked.resolve():
                    raise RuntimeError("数据压缩包包含不安全路径")
            package.extractall(unpacked)
        roots = [entry for entry in unpacked.iterdir() if entry.is_dir()]
        if len(roots) != 1 or not (roots[0] / "dishes").is_dir():
            raise RuntimeError("HowToCook 压缩包结构不符合预期")
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(roots[0], destination)
    manifest = {
        **config,
        "recipe_markdown_count": len(list((destination / "dishes").rglob("*.md"))),
    }
    marker.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def load_reviews(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_dataset(raw: Path, output: Path, commit: str, reviews_path: Path) -> dict:
    reviews = load_reviews(reviews_path)
    results = []
    stale_reviews = 0
    for path in sorted((raw / "dishes").rglob("*.md")):
        relative = path.relative_to(raw).as_posix()
        result = parse_recipe(path.read_text(encoding="utf-8"), relative, commit)
        review = reviews.get(relative)
        if review and review.get("approved"):
            if review.get("sha256") == result.recipe.source_hash:
                result.recipe.reviewed = True
                overrides = review.get("ingredient_status", {})
                for ingredient in result.recipe.ingredients:
                    if ingredient.name in overrides:
                        ingredient.status = overrides[ingredient.name]
                removed = {
                    normalize_ingredient(name) for name in review.get("remove_ingredients", [])
                }
                result.recipe.ingredients = [
                    ingredient
                    for ingredient in result.recipe.ingredients
                    if ingredient.name not in removed
                ]
                existing = {ingredient.name for ingredient in result.recipe.ingredients}
                for addition in review.get("add_ingredients", []):
                    name = normalize_ingredient(addition["name"])
                    if name not in existing:
                        result.recipe.ingredients.append(
                            IngredientUse(
                                name=name,
                                status=addition.get("status", "required"),
                                evidence=[f"human-review:{relative}"],
                            )
                        )
                        existing.add(name)
            else:
                stale_reviews += 1
                result.issues.append("stale_review")
        results.append(result)

    recipes: list[Recipe] = [result.recipe for result in results if not result.skipped]
    output.mkdir(parents=True, exist_ok=True)
    jsonl = "\n".join(recipe.model_dump_json() for recipe in recipes)
    (output / "recipes.jsonl").write_text(jsonl + ("\n" if jsonl else ""), encoding="utf-8")
    dump_graph(build_graph(recipes, commit), output / "graph.json")
    report = {
        "source_commit": commit,
        "scanned": len(results),
        "skipped": sum(result.skipped for result in results),
        "ineligible": sum(not result.recipe.eligible and not result.skipped for result in results),
        "with_issues": sum(bool(result.issues) and not result.skipped for result in results),
        "reviewed_eligible": sum(
            recipe.reviewed
            and recipe.eligible
            and all(item.status != "pending" for item in recipe.ingredients)
            for recipe in recipes
        ),
        "stale_reviews": stale_reviews,
        "issues": [
            {"recipe_id": result.recipe.id, "issues": result.issues}
            for result in results
            if result.issues
        ],
    }
    (output / "quality-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def load_recipes(path: Path) -> list[Recipe]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [Recipe.model_validate_json(line) for line in lines]
