"""标准数据加载。

算法模块不直接解析 Markdown，只读取数据模块产出的标准数据。约定文件：

- ``recipes.jsonl``：每行一个 ``Recipe`` 对象；
- ``taxonomy.jsonl``：每行一条 ``TaxonomyEdge`` 对象；
- ``aliases.json``：``{"别名": "标准名"}`` 的别名字典。

文件缺失或无法解析时抛出 :class:`DataLoadError`。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .errors import DataLoadError
from .models import Recipe, TaxonomyEdge


@dataclass
class DataBundle:
    """一次加载得到的完整标准数据。"""

    recipes: list[Recipe] = field(default_factory=list)
    taxonomy: list[TaxonomyEdge] = field(default_factory=list)
    aliases: dict[str, str] = field(default_factory=dict)


def _read_jsonl(path: Path, label: str) -> list[dict]:
    if not path.exists():
        raise DataLoadError(f"{label} 文件不存在: {path}")
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:  # pragma: no cover - 防御性
                raise DataLoadError(f"{label} 第 {line_no} 行不是合法 JSON: {exc}") from exc
    return rows


def load_recipes(path: str | Path) -> list[Recipe]:
    rows = _read_jsonl(Path(path), "recipes")
    try:
        return [Recipe.model_validate(row) for row in rows]
    except Exception as exc:
        raise DataLoadError(f"recipes 数据不符合 Recipe 模型: {exc}") from exc


def load_taxonomy(path: str | Path) -> list[TaxonomyEdge]:
    rows = _read_jsonl(Path(path), "taxonomy")
    try:
        return [TaxonomyEdge.model_validate(row) for row in rows]
    except Exception as exc:
        raise DataLoadError(f"taxonomy 数据不符合 TaxonomyEdge 模型: {exc}") from exc


def load_aliases(path: str | Path) -> dict[str, str]:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DataLoadError(f"aliases 不是合法 JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise DataLoadError("aliases 顶层必须是 JSON 对象")
    return {str(k): str(v) for k, v in data.items()}


def load_all(data_dir: str | Path) -> DataBundle:
    """从目录加载 recipes.jsonl、taxonomy.jsonl 与可选的 aliases.json。"""
    root = Path(data_dir)
    return DataBundle(
        recipes=load_recipes(root / "recipes.jsonl"),
        taxonomy=load_taxonomy(root / "taxonomy.jsonl"),
        aliases=load_aliases(root / "aliases.json"),
    )
