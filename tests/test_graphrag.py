from pathlib import Path

import pytest
from typer.testing import CliRunner

from cookkg.answering import AnswerService
from cookkg.cli import app
from cookkg.evidence import Evidence, build_evidence_from_graph, dump_evidence, load_evidence
from cookkg.graph import build_graph, dump_graph
from cookkg.models import IngredientUse, Recipe
from cookkg.retrieval import RETRIEVER_NAMES, Neo4jCypherExpander, build_retrievers
from cookkg.router import route_question


def recipe_graph():
    recipes = [
        Recipe(
            id="dishes/egg.md",
            name="洋葱炒鸡蛋",
            category="素菜",
            source_url="https://example/dishes/egg.md",
            source_hash="a" * 64,
            reviewed=True,
            ingredients=[
                IngredientUse(
                    name="鸡蛋",
                    status="required",
                    quantity_raw=["鸡蛋 2 个"],
                    evidence=["dishes/egg.md:12"],
                ),
                IngredientUse(
                    name="洋葱",
                    status="required",
                    quantity_raw=["洋葱 50 克"],
                    evidence=["dishes/egg.md:13"],
                ),
            ],
            steps="鸡蛋打散。\n洋葱切丝后炒熟。",
        ),
        Recipe(
            id="dishes/pending.md",
            name="未审核菜",
            category="测试",
            source_url="https://example/dishes/pending.md",
            source_hash="b" * 64,
            reviewed=False,
            ingredients=[IngredientUse(name="鸡蛋", status="required")],
            steps="未审核步骤。",
        ),
    ]
    return build_graph(recipes, source_commit="fixture")


def test_evidence_build_is_stable_source_bound_and_review_gated(tmp_path: Path):
    graph = recipe_graph()

    first = build_evidence_from_graph(graph)
    second = build_evidence_from_graph(graph)

    assert first == second
    assert first
    assert {item.recipe_id for item in first} == {"dishes/egg.md"}
    assert all(item.source_url == "https://example/dishes/egg.md" for item in first)
    assert all(item.line_start >= 1 and item.line_end >= item.line_start for item in first)
    assert any("鸡蛋 2 个" in item.text for item in first)
    assert any("洋葱切丝" in item.text for item in first)

    path = tmp_path / "evidence.jsonl"
    metadata = dump_evidence(first, path, source_commit="fixture")
    assert metadata["count"] == len(first)
    assert load_evidence(path) == first


def test_four_retrievers_return_stable_deduplicated_source_evidence():
    graph = recipe_graph()
    evidence = build_evidence_from_graph(graph)
    retrievers = build_retrievers(evidence, graph)

    assert set(retrievers) == set(RETRIEVER_NAMES)
    for name, retriever in retrievers.items():
        result = retriever.search("洋葱炒鸡蛋怎么做", top_k=3)
        assert result
        assert all(item.retriever == name for item in result)
        assert len({item.evidence_id for item in result}) == len(result)
        assert result == sorted(result, key=lambda item: (-item.score, item.evidence_id))
        assert all(item.source_url.startswith("https://example/") for item in result)


def test_graph_expansion_returns_a_recipe_reached_through_shared_ingredient():
    recipes = [
        Recipe(
            id="dishes/seed.md",
            name="鸡蛋做法",
            category="test",
            source_url="https://example/seed",
            source_hash="a" * 64,
            reviewed=True,
            ingredients=[IngredientUse(name="鸡蛋", status="required")],
            steps="把鸡蛋打散。",
        ),
        Recipe(
            id="dishes/related.md",
            name="葱香煎饼",
            category="test",
            source_url="https://example/related",
            source_hash="b" * 64,
            reviewed=True,
            ingredients=[IngredientUse(name="鸡蛋", status="required")],
            steps="加入完全无关措辞并煎熟。",
        ),
    ]
    graph = build_graph(recipes, source_commit="fixture")
    evidence = build_evidence_from_graph(graph)
    retrievers = build_retrievers(evidence, graph)

    base_ids = {
        item.recipe_id for item in retrievers["vector"].search("打散鸡蛋", top_k=2)
    }
    expanded_ids = {
        item.recipe_id
        for item in retrievers["vector_cypher"].search("打散鸡蛋", top_k=2)
    }

    assert "dishes/related.md" not in base_ids
    assert "dishes/related.md" in expanded_ids


@pytest.mark.parametrize(
    ("question", "target"),
    [
        ("我有鸡蛋，不吃辣椒，做两道菜", "planner"),
        ("洋葱炒鸡蛋怎么做", "vector"),
        ("小米椒属于什么类别", "vector_cypher"),
        ("想吃清淡的洋葱炒鸡蛋", "hybrid"),
        ("哪些菜都使用鸡蛋，它们需要什么工具", "hybrid_cypher"),
        ("为什么不推荐小炒肉", "hybrid_cypher"),
    ],
)
def test_router_is_deterministic_and_explains_choice(question: str, target: str):
    decision = route_question(question)
    assert decision.target == target
    assert decision.reason
    assert route_question(question) == decision


class SequenceLlm:
    def __init__(self, replies: list[str]):
        self.replies = iter(replies)
        self.calls = 0

    def generate(self, messages: list[dict[str, str]]) -> str:
        self.calls += 1
        assert "[E1]" in messages[-1]["content"]
        return next(self.replies)


def test_answer_service_retries_invalid_citations_and_returns_verified_sources():
    graph = recipe_graph()
    retrievers = build_retrievers(build_evidence_from_graph(graph), graph)
    llm = SequenceLlm(["鸡蛋需要打散。", "鸡蛋需要先打散。[E1]"])
    service = AnswerService(retrievers, llm)

    response = service.answer("洋葱炒鸡蛋怎么做", retriever="vector", top_k=3)

    assert llm.calls == 2
    assert response.answer.endswith("[E1]")
    assert response.retriever == "vector"
    assert response.citations[0].evidence_id == "E1"
    assert response.citations[0].record_id
    assert response.citations[0].source_url.startswith("https://example/")
    assert response.insufficient_evidence is False


def test_answer_service_does_not_call_llm_without_evidence():
    llm = SequenceLlm(["不应被调用。[E1]"])
    service = AnswerService(build_retrievers([], recipe_graph()), llm)

    response = service.answer("完全不存在的问题", retriever="vector", top_k=3)

    assert llm.calls == 0
    assert response.insufficient_evidence is True
    assert response.citations == []


def test_evidence_rejects_untraceable_ranges():
    with pytest.raises(ValueError):
        Evidence(
            evidence_id="evidence",
            recipe_id="dishes/example.md",
            text="原文",
            source_url="https://example/dishes/example.md",
            line_start=4,
            line_end=3,
            score=0,
            retriever="vector",
        )


def test_index_cli_writes_reproducible_evidence_and_metadata(tmp_path: Path):
    graph_path = tmp_path / "graph.json"
    output = tmp_path / "evidence.jsonl"
    dump_graph(recipe_graph(), graph_path)

    result = CliRunner().invoke(
        app, ["index", "--graph", str(graph_path), "--output", str(output)]
    )

    assert result.exit_code == 0, result.output
    assert load_evidence(output)
    assert output.with_suffix(".jsonl.meta.json").is_file()
    first = output.read_bytes()
    second = CliRunner().invoke(
        app, ["index", "--graph", str(graph_path), "--output", str(output)]
    )
    assert second.exit_code == 0
    assert output.read_bytes() == first


def test_evidence_snapshot_validation_rejects_stale_or_modified_index(tmp_path: Path):
    path = tmp_path / "evidence.jsonl"
    dump_evidence(build_evidence_from_graph(recipe_graph()), path, "fixture")
    assert load_evidence(path, "fixture")
    with pytest.raises(ValueError, match="snapshot"):
        load_evidence(path, "different")
    path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="snapshot"):
        load_evidence(path, "fixture")


def test_neo4j_expansion_uses_fixed_parameterized_cypher():
    calls = []

    class Session:
        def run(self, query, **parameters):
            calls.append((query, parameters))
            return [{"recipe_id": "dishes/related.md"}]

    user_text = "x') MATCH (n) DETACH DELETE n //"
    related = Neo4jCypherExpander(Session(), "HowToCook", "fixture").related_recipe_ids(
        {user_text}
    )

    assert related == {user_text, "dishes/related.md"}
    query, parameters = calls[0]
    assert user_text not in query
    assert parameters["recipe_ids"] == [user_text]
    assert "$recipe_ids" in query
