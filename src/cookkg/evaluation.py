"""Reproducible retrieval evaluation with a human-review gate."""

import csv
import json
from pathlib import Path

import networkx as nx
from pydantic import BaseModel, Field

from cookkg.evidence import Evidence
from cookkg.retrieval import build_retrievers


class EvaluationCase(BaseModel):
    case_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    expected_recipe_ids: list[str] = Field(min_length=1)
    human_reviewed: bool = False


def load_evaluation_cases(path: Path, require_reviewed: bool = True) -> list[EvaluationCase]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("cases", payload.get("items", []))
    cases = [EvaluationCase.model_validate(item) for item in payload]
    if require_reviewed and any(not item.human_reviewed for item in cases):
        raise ValueError("最终评测只允许使用已完成人工审核的题目")
    return cases


def evaluate_retrievers(
    cases: list[EvaluationCase], evidence: list[Evidence], graph: nx.DiGraph, top_k: int = 5
) -> dict:
    retrievers = build_retrievers(evidence, graph)
    rows = []
    totals = {name: 0.0 for name in retrievers}
    for case in sorted(cases, key=lambda item: item.case_id):
        expected = set(case.expected_recipe_ids)
        row = {"case_id": case.case_id, "question": case.question, "retrievers": {}}
        for name, retriever in retrievers.items():
            found = list(
                dict.fromkeys(
                    item.recipe_id for item in retriever.search(case.question, top_k)
                )
            )
            recall = len(expected & set(found)) / len(expected)
            totals[name] += recall
            row["retrievers"][name] = {"recipe_ids": found, "recall": recall}
        rows.append(row)
    denominator = len(cases) or 1
    return {
        "case_count": len(cases),
        "top_k": top_k,
        "metrics": {
            name: {"recall_at_k": round(total / denominator, 6)}
            for name, total in totals.items()
        },
        "results": rows,
    }


def write_evaluation_report(report: dict, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    with (output / "results.jsonl").open("w", encoding="utf-8", newline="\n") as stream:
        for item in report["results"]:
            stream.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
    with (output / "summary.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["retriever", f"recall@{report['top_k']}", "case_count"])
        for name, metrics in report["metrics"].items():
            writer.writerow([name, metrics["recall_at_k"], report["case_count"]])
    lines = [
        "# CookKG 检索评测报告", "", f"- 人工审核题目：{report['case_count']} 条",
        f"- Top K：{report['top_k']}", "", "| 检索器 | Recall@K |", "| --- | ---: |",
    ]
    lines.extend(
        f"| {name} | {metrics['recall_at_k']:.3f} |"
        for name, metrics in report["metrics"].items()
    )
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
