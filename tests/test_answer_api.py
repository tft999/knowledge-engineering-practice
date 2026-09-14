from pathlib import Path

from fastapi.testclient import TestClient

from cookkg.api import create_app
from cookkg.graph import build_graph, dump_graph
from cookkg.models import IngredientUse, Recipe


class FakeLlm:
    def generate(self, messages: list[dict[str, str]]) -> str:
        return "鸡蛋需要打散。[E1]"


def graph_path(tmp_path: Path) -> Path:
    recipe = Recipe(
        id="dishes/egg.md",
        name="洋葱炒鸡蛋",
        category="素菜",
        source_url="https://example/dishes/egg.md",
        source_hash="a" * 64,
        reviewed=True,
        ingredients=[IngredientUse(name="鸡蛋", status="required")],
        steps="鸡蛋需要打散。",
    )
    path = tmp_path / "graph.json"
    dump_graph(build_graph([recipe], source_commit="fixture"), path)
    return path


def test_answer_endpoint_exposes_verified_citation_contract(tmp_path: Path):
    with TestClient(create_app(graph_path(tmp_path), llm_client=FakeLlm())) as client:
        response = client.post(
            "/api/v1/answers",
            json={"question": "洋葱炒鸡蛋怎么做？", "retriever": "auto", "top_k": 5},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"].endswith("[E1]")
    assert body["retriever"] == "vector"
    assert body["route_reason"]
    assert body["citations"][0]["evidence_id"] == "E1"
    assert body["citations"][0]["source_url"] == "https://example/dishes/egg.md"
    assert body["insufficient_evidence"] is False


def test_answer_endpoint_reports_missing_model_without_leaking_configuration(tmp_path: Path):
    with TestClient(create_app(graph_path(tmp_path))) as client:
        response = client.post(
            "/api/v1/answers",
            json={"question": "洋葱炒鸡蛋怎么做？", "retriever": "vector", "top_k": 5},
        )

    assert response.status_code == 503
    assert response.json()["detail"] == "问答模型尚未配置"


def test_agent_endpoint_handles_greeting_without_model(tmp_path: Path):
    with TestClient(create_app(graph_path(tmp_path))) as client:
        response = client.post(
            "/api/v1/agent",
            json={"question": "你好", "top_k": 5},
        )

    assert response.status_code == 200
    assert response.json()["mode"] == "help"
