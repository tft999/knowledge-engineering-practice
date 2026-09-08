import hashlib
import re

from cookkg.models import IngredientUse, ParseResult, Recipe
from cookkg.normalize import normalize_ingredient

TOOL_NAMES = {"锅", "炒锅", "汤锅", "碗", "盘子", "菜刀", "砧板", "烤箱", "空气炸锅", "微波炉"}
STEP_ONLY_CANDIDATES = {"食用油", "盐", "糖", "醋", "生抽", "老抽", "清水", "水", "葱", "姜", "蒜"}


def _sections(text: str) -> dict[str, list[tuple[int, str]]]:
    result: dict[str, list[tuple[int, str]]] = {}
    current = "intro"
    for number, line in enumerate(text.splitlines(), 1):
        match = re.match(r"^##\s+(.+?)\s*$", line)
        if match:
            current = match.group(1)
            result.setdefault(current, [])
        else:
            result.setdefault(current, []).append((number, line))
    return result


def _find_section(sections: dict[str, list[tuple[int, str]]], keyword: str):
    return next((lines for title, lines in sections.items() if keyword in title), None)


def parse_recipe(text: str, path: str, commit: str) -> ParseResult:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    title = re.search(r"^#\s+(.+?)(?:的做法)?\s*$", text, re.MULTILINE)
    name = title.group(1) if title else path.rsplit("/", 1)[-1].removesuffix(".md")
    source_url = f"https://github.com/Anduin2017/HowToCook/blob/{commit}/{path}"
    category = path.split("/")[1] if len(path.split("/")) > 2 else "unknown"
    recipe = Recipe(
        id=path, name=name, category=category, source_url=source_url, source_hash=digest
    )
    if path.startswith("dishes/template/"):
        return ParseResult(recipe=recipe, issues=["template"], skipped=True)

    sections = _sections(text)
    ingredient_lines = _find_section(sections, "必备原料")
    calculation_lines = _find_section(sections, "计算") or []
    operation_lines = _find_section(sections, "操作") or []
    issues: list[str] = []
    if ingredient_lines is None:
        recipe.eligible = False
        issues.append("missing_ingredients_section")
        return ParseResult(recipe=recipe, issues=issues)

    calculation_values: list[tuple[int, str]] = []
    for number, line in calculation_lines:
        if re.match(r"^\s*[-*]\s+", line):
            raw = re.sub(r"^\s*[-*]\s+", "", line).strip()
            calculation_values.append((number, raw))

    known: set[str] = set()
    for number, line in ingredient_lines:
        if not re.match(r"^\s*[-*]\s+", line):
            continue
        raw = re.sub(r"^\s*[-*]\s+", "", line).strip()
        optional = bool(re.search(r"[（(](?:可选|选用)[）)]", raw))
        name_value = normalize_ingredient(raw)
        if not name_value:
            continue
        if name_value in TOOL_NAMES:
            recipe.tools.append(name_value)
            continue
        known.add(name_value)
        recipe.ingredients.append(
            IngredientUse(
                name=name_value,
                status="optional" if optional else "required",
                quantity_raw=[
                    raw
                    for _, raw in calculation_values
                    if normalize_ingredient(raw).startswith(name_value)
                    or raw.startswith(name_value)
                ],
                evidence=[f"{path}:{number}"],
            )
        )

    for candidate in sorted(STEP_ONLY_CANDIDATES):
        name_value = normalize_ingredient(candidate)
        matches = [(number, raw) for number, raw in calculation_values if raw.startswith(candidate)]
        raw_values = [raw for _, raw in matches]
        if raw_values and name_value not in known:
            recipe.ingredients.append(
                IngredientUse(
                    name=name_value,
                    status="pending",
                    quantity_raw=raw_values,
                    evidence=[f"{path}:{number}" for number, _ in matches],
                )
            )
            known.add(name_value)
            issues.append(f"ingredient_only_in_calculation:{name_value}")

    operation_text = "\n".join(line for _, line in operation_lines)
    recipe.steps = operation_text
    for candidate in sorted(STEP_ONLY_CANDIDATES):
        canonical = normalize_ingredient(candidate)
        if candidate in operation_text and canonical not in known:
            evidence = [
                f"{path}:{number}"
                for number, line in operation_lines
                if candidate in line
            ]
            recipe.ingredients.append(
                IngredientUse(name=canonical, status="pending", evidence=evidence)
            )
            known.add(canonical)
            issues.append(f"ingredient_only_in_steps:{canonical}")

    difficulty = re.search(r"预估烹饪难度[：:]\s*([★☆]+)", text)
    recipe.difficulty = difficulty.group(1).count("★") if difficulty else None
    if not recipe.ingredients:
        recipe.eligible = False
        issues.append("empty_ingredients")
    return ParseResult(recipe=recipe, issues=issues)
