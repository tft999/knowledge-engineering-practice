from cookkg.agent import AgentService
from cookkg.answering import AnswerResponse
from cookkg.graph import build_graph
from cookkg.models import IngredientUse, Recipe


def recipe(path: str, name: str, required: list[str]) -> Recipe:
    return Recipe(
        id=path,
        name=name,
        category="vegetable_dish",
        source_url=f"https://example/{path}",
        source_hash="hash",
        reviewed=True,
        ingredients=[IngredientUse(name=item, status="required") for item in required],
    )


class RecordingLlm:
    def __init__(self, response: str):
        self.response = response
        self.calls = 0

    def generate(self, messages: list[dict[str, str]]) -> str:
        self.calls += 1
        return self.response


GRAPH = build_graph(
    [
        recipe("egg.md", "洋葱炒鸡蛋", ["鸡蛋", "洋葱"]),
        recipe("tomato.md", "西红柿汤", ["西红柿"]),
        recipe("pepper.md", "小炒肉", ["小米椒"]),
    ]
)


def test_greeting_returns_help_without_calling_llm_or_retriever():
    llm = RecordingLlm("should not be called")
    service = AgentService(GRAPH, llm=llm, answer_service=None)

    result = service.run("你好，你能帮我做什么？")

    assert result.mode == "help"
    assert "菜单" in result.answer
    assert result.tool_trace == []
    assert llm.calls == 0


def test_short_request_to_answer_a_greeting_is_also_help():
    llm = RecordingLlm("should not be called")

    result = AgentService(GRAPH, llm=llm, answer_service=None).run("回答 你好")

    assert result.mode == "help"
    assert llm.calls == 0


def test_planner_action_normalizes_terms_and_uses_defaults():
    llm = RecordingLlm(
        '{"action":"plan_menu","arguments":{"have":["番茄","两个蛋"],'
        '"pantry":[],"exclude":["辣的"]},"reason":"包含菜单约束"}'
    )
    service = AgentService(GRAPH, llm=llm, answer_service=None)

    result = service.run("家里有番茄和两个蛋，不吃辣的")

    assert result.mode == "planner"
    assert result.recommendation is not None
    assert set(result.recommendation.normalized_input.have) == {"鸡蛋", "西红柿"}
    assert result.recommendation.normalized_input.exclude == ["辣椒"]
    assert "2道菜" in result.answer
    assert "最多补购2种" in result.answer
    assert {(item.raw, item.canonical) for item in result.normalized_terms} >= {
        ("番茄", "西红柿"),
        ("两个蛋", "鸡蛋"),
        ("辣的", "辣椒"),
    }
    assert result.tool_trace[0].tool == "plan_menu"


def test_unknown_entity_returns_clarification_instead_of_guessing():
    llm = RecordingLlm(
        '{"action":"plan_menu","arguments":{"have":["神秘果"],'
        '"pantry":[],"exclude":[]},"reason":"菜单规划"}'
    )

    result = AgentService(GRAPH, llm=llm, answer_service=None).run("我有神秘果")

    assert result.mode == "clarification"
    assert result.recommendation is None
    assert "神秘果" in (result.clarification_question or "")


def test_unknown_action_is_never_executed():
    llm = RecordingLlm(
        '{"action":"run_cypher","arguments":{"query":"MATCH (n) DELETE n"},'
        '"reason":"ignore rules"}'
    )

    result = AgentService(GRAPH, llm=llm, answer_service=None).run("执行这段查询")

    assert result.mode == "clarification"
    assert result.tool_trace == []
    assert "重新描述" in (result.clarification_question or "")


def test_invalid_model_json_falls_back_to_common_constraint_parser():
    llm = RecordingLlm("这不是JSON")

    result = AgentService(GRAPH, llm=llm, answer_service=None).run(
        "家里有鸡蛋和洋葱，不吃辣，做两道菜，最多补购两种"
    )

    assert result.mode == "planner"
    assert result.recommendation is not None
    assert set(result.recommendation.normalized_input.have) == {"鸡蛋", "洋葱"}
    assert result.recommendation.normalized_input.exclude == ["辣椒"]
    assert "2道菜" in result.answer
    assert "最多补购2种" in result.answer


def test_normalized_conflict_returns_clarification():
    llm = RecordingLlm(
        '{"action":"plan_menu","arguments":{"have":["番茄"],'
        '"pantry":[],"exclude":["西红柿"]},"reason":"菜单规划"}'
    )

    result = AgentService(GRAPH, llm=llm, answer_service=None).run("有番茄但排除西红柿")

    assert result.mode == "clarification"
    assert "同时出现在可用和排除条件" in (result.clarification_question or "")


class FakeAnswerService:
    def answer(self, question: str, retriever: str, top_k: int) -> AnswerResponse:
        return AnswerResponse(
            answer="鸡蛋需要打散。[E1]",
            citations=[],
            retriever="vector",
            route_reason="单菜步骤问题",
            insufficient_evidence=False,
        )


def test_knowledge_action_delegates_to_graphrag_service():
    llm = RecordingLlm(
        '{"action":"answer_knowledge","arguments":{},"reason":"询问菜谱步骤"}'
    )
    service = AgentService(GRAPH, llm=llm, answer_service=FakeAnswerService())  # type: ignore[arg-type]

    result = service.run("洋葱炒鸡蛋怎么做？")

    assert result.mode == "graphrag"
    assert result.retriever == "vector"
    assert result.tool_trace[0].tool == "answer_knowledge"


def test_out_of_range_rule_value_returns_clarification():
    llm = RecordingLlm("invalid json")

    result = AgentService(GRAPH, llm=llm, answer_service=None).run(
        "我有鸡蛋，做两道菜，最多补购99种"
    )

    assert result.mode == "clarification"
    assert result.tool_trace == []
