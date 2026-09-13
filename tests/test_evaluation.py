import json
from pathlib import Path

import pytest
from test_graphrag import recipe_graph
from typer.testing import CliRunner

from cookkg.cli import app
from cookkg.evaluation import EvaluationCase, evaluate_retrievers, load_evaluation_cases
from cookkg.evidence import build_evidence_from_graph, dump_evidence
from cookkg.graph import dump_graph


def reviewed_case() -> EvaluationCase:
    return EvaluationCase(
        case_id="Q001",
        question="洋葱炒鸡蛋怎么做？",
        expected_recipe_ids=["dishes/egg.md"],
        human_reviewed=True,
    )


def test_evaluation_reports_recall_and_preserves_per_case_results():
    graph = recipe_graph()
    report = evaluate_retrievers(
        [reviewed_case()], build_evidence_from_graph(graph), graph, top_k=3
    )
    assert report["case_count"] == 1
    assert set(report["metrics"]) == {
        "vector", "vector_cypher", "hybrid", "hybrid_cypher"
    }
    assert report["metrics"]["hybrid"]["recall_at_k"] == 1.0
    assert report["results"][0]["case_id"] == "Q001"


def test_final_evaluation_gate_rejects_unreviewed_cases(tmp_path: Path):
    path = tmp_path / "questions.json"
    path.write_text(json.dumps([{
        "case_id": "Q001", "question": "测试",
        "expected_recipe_ids": ["dishes/egg.md"], "human_reviewed": False,
    }], ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="人工审核"):
        load_evaluation_cases(path, require_reviewed=True)


def test_evaluate_cli_writes_json_csv_and_markdown(tmp_path: Path):
    graph = recipe_graph()
    graph_path = tmp_path / "graph.json"
    evidence_path = tmp_path / "evidence.jsonl"
    questions_path = tmp_path / "questions.json"
    output = tmp_path / "evaluation"
    dump_graph(graph, graph_path)
    dump_evidence(build_evidence_from_graph(graph), evidence_path, "fixture")
    questions_path.write_text(
        json.dumps([reviewed_case().model_dump()], ensure_ascii=False), encoding="utf-8"
    )
    result = CliRunner().invoke(app, [
        "evaluate", "--graph", str(graph_path), "--evidence", str(evidence_path),
        "--questions", str(questions_path), "--output", str(output),
    ])
    assert result.exit_code == 0, result.output
    assert (output / "results.jsonl").is_file()
    assert (output / "summary.csv").is_file()
    assert (output / "report.md").is_file()
