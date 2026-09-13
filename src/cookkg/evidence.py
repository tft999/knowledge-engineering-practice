"""Traceable text evidence used by CookKG retrieval and answering."""

import hashlib
import json
import re
from pathlib import Path
from typing import Literal, Self

import networkx as nx
from pydantic import BaseModel, ConfigDict, Field, model_validator

RetrieverName = Literal["vector", "vector_cypher", "hybrid", "hybrid_cypher"]


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(min_length=1)
    recipe_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    score: float = 0.0
    retriever: RetrieverName = "vector"
    section: Literal["ingredient", "step"] = "step"

    @model_validator(mode="after")
    def valid_range(self) -> Self:
        if self.line_end < self.line_start:
            raise ValueError("line_end must not precede line_start")
        return self


def _stable_id(recipe_id: str, section: str, ordinal: int, text: str) -> str:
    payload = "\0".join([recipe_id, section, str(ordinal), text]).encode("utf-8")
    return f"ev:{hashlib.sha256(payload).hexdigest()[:20]}"


def _line_number(values: list[str], default: int) -> int:
    for value in values:
        match = re.search(r":(\d+)(?::|$)", value)
        if match:
            return int(match.group(1))
    return default


def build_evidence_from_graph(graph: nx.DiGraph) -> list[Evidence]:
    """Create deterministic evidence chunks from public, reviewed recipe nodes."""
    result: list[Evidence] = []
    recipe_nodes = sorted(
        (
            (node, attrs)
            for node, attrs in graph.nodes(data=True)
            if attrs.get("kind") == "recipe"
            and attrs.get("reviewed")
            and attrs.get("eligible", True)
        ),
        key=lambda item: item[1].get("id", item[0]),
    )
    for node, attrs in recipe_nodes:
        uses = sorted(
            (
                (target, edge)
                for _, target, edge in graph.out_edges(node, data=True)
                if graph.nodes[target].get("kind") == "ingredient"
                and edge.get("status") in {"required", "optional", "one_of"}
            ),
            key=lambda item: (graph.nodes[item[0]].get("name", item[0]), item[0]),
        )
        if any(edge.get("status") == "pending" for _, _, edge in graph.out_edges(node, data=True)):
            continue
        for ordinal, (target, edge) in enumerate(uses, 1):
            name = graph.nodes[target].get("name", target)
            quantity = "、".join(edge.get("quantity_raw", [])) or name
            relation = {
                "required": "必需食材",
                "optional": "可选食材",
                "one_of": "选择组食材",
            }[edge["status"]]
            chunk = f"菜谱“{attrs['name']}”的{relation}：{quantity}。"
            line = _line_number(edge.get("evidence", []), ordinal)
            result.append(
                Evidence(
                    evidence_id=_stable_id(attrs["id"], "ingredient", ordinal, chunk),
                    recipe_id=attrs["id"],
                    text=chunk,
                    source_url=attrs["source_url"],
                    line_start=line,
                    line_end=line,
                    section="ingredient",
                )
            )
        step_lines = [part.strip() for part in attrs.get("steps", "").splitlines() if part.strip()]
        for ordinal, step in enumerate(step_lines, 1):
            chunk = f"菜谱“{attrs['name']}”的操作步骤：{step}"
            locations = attrs.get("step_evidence", [])
            line = _line_number(
                locations[ordinal - 1 : ordinal],
                1,
            )
            result.append(
                Evidence(
                    evidence_id=_stable_id(attrs["id"], "step", ordinal, chunk),
                    recipe_id=attrs["id"],
                    text=chunk,
                    source_url=attrs["source_url"],
                    line_start=line,
                    line_end=line,
                    section="step",
                )
            )
    return sorted(result, key=lambda item: item.evidence_id)


def dump_evidence(items: list[Evidence], path: Path, source_commit: str) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(item.model_dump_json() for item in items)
    path.write_text(body + ("\n" if body else ""), encoding="utf-8")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    metadata = {
        "schema_version": 1,
        "source_commit": source_commit,
        "count": len(items),
        "sha256": digest,
    }
    path.with_suffix(path.suffix + ".meta.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return metadata


def load_evidence(path: Path) -> list[Evidence]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return [
        Evidence.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
