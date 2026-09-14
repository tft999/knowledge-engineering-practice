"""Controlled natural-language orchestration for CookKG tools."""

import json
import re
from typing import Literal

import networkx as nx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from cookkg.answering import AnswerService, Citation
from cookkg.evidence import RetrieverName
from cookkg.llm import LlmClient, LlmUnavailableError
from cookkg.normalize import aliases, normalize_ingredient
from cookkg.recommend import RecommendRequest, RecommendResult, recommend
from cookkg.router import route_question


class AgentRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=5, ge=1, le=10)


class NormalizedTerm(BaseModel):
    raw: str
    canonical: str
    field: Literal["have", "pantry", "exclude"]
    source: Literal["exact", "alias", "entity_linker", "category_linker"]


class ToolTrace(BaseModel):
    tool: Literal["plan_menu", "answer_knowledge"]
    status: Literal["success", "empty"]
    summary: str


class AgentResponse(BaseModel):
    mode: Literal["help", "planner", "graphrag", "clarification"]
    answer: str
    route_reason: str
    normalized_terms: list[NormalizedTerm] = Field(default_factory=list)
    tool_trace: list[ToolTrace] = Field(default_factory=list)
    recommendation: RecommendResult | None = None
    citations: list[Citation] = Field(default_factory=list)
    retriever: RetrieverName | None = None
    insufficient_evidence: bool = False
    clarification_question: str | None = None


class AgentArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    have: list[str] = Field(default_factory=list)
    pantry: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)
    count: int | None = Field(default=None, ge=1, le=3)
    max_buy: int | None = Field(default=None, ge=0, le=20)


class AgentAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["plan_menu", "answer_knowledge"]
    arguments: AgentArguments = Field(default_factory=AgentArguments)
    reason: str = Field(min_length=1, max_length=200)


_CONVERSATIONAL_ALIASES = {
    "蛋": "鸡蛋",
    "辣": "辣椒",
    "辣的": "辣椒",
    "辣味": "辣椒",
}
_GREETING = re.compile(r"^(你好|您好|嗨|hello|hi)([，,。.!！?？\s].*)?$", re.IGNORECASE)
_HELP_TERMS = ("你能做什么", "怎么使用", "使用帮助", "帮助")


def _agent_prompt(question: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "你是CookKG的受控路由器，只能选择plan_menu或answer_knowledge。"
                "涉及已有食材、常备调料、忌口、排除、菜数、补购或搭配时选择plan_menu；"
                "菜谱步骤、用量、实体关系和原因解释选择answer_knowledge。"
                "只输出JSON：{\"action\":...,\"arguments\":{\"have\":[],"
                "\"pantry\":[],\"exclude\":[],\"count\":null,\"max_buy\":null},"
                "\"reason\":...}。保留用户原词，不要输出代码或Cypher。"
            ),
        },
        {"role": "user", "content": question},
    ]


def _json_object(raw: str) -> dict:
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not match:
        raise ValueError("模型没有返回JSON对象")
    value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise ValueError("模型动作必须是对象")
    return value


def _clean_term(raw: str) -> str:
    value = raw.strip().strip("，,。；;！!？?")
    value = re.sub(r"^(?:大约|大概)?[一二两三四五六七八九十百\d]+(?:个|颗|只|份|根|片)?", "", value)
    return value.strip()


class AgentService:
    def __init__(
        self,
        graph: nx.DiGraph,
        llm: LlmClient | None,
        answer_service: AnswerService | None,
    ):
        self.graph = graph
        self.llm = llm
        self.answer_service = answer_service
        self.ingredients = {
            str(attrs["name"])
            for _, attrs in graph.nodes(data=True)
            if attrs.get("kind") == "ingredient"
        }
        self.categories = {
            str(attrs["name"])
            for _, attrs in graph.nodes(data=True)
            if attrs.get("kind") == "category"
        }

    def run(self, question: str, top_k: int = 5) -> AgentResponse:
        text = question.strip()
        greeting_request = len(text) <= 12 and "你好" in text
        if greeting_request or _GREETING.match(text) or any(term in text for term in _HELP_TERMS):
            return AgentResponse(
                mode="help",
                answer=(
                    "你好，我可以按库存、忌口、菜数和补购上限规划菜单，也可以查询"
                    "菜谱步骤、用量与食材关系。"
                ),
                route_reason="识别为问候或使用帮助",
            )

        action = self._choose_action(text)
        if action is None:
            return self._clarification("我没有可靠识别这个请求，请换一种方式重新描述。")
        if action.action == "plan_menu":
            return self._plan(action)
        return self._answer(text, top_k, action.reason)

    def _choose_action(self, question: str) -> AgentAction | None:
        if self.llm is not None:
            try:
                raw = self.llm.generate(_agent_prompt(question))
                return AgentAction.model_validate(_json_object(raw))
            except (LlmUnavailableError, ValueError, ValidationError, json.JSONDecodeError):
                pass
        decision = route_question(question)
        if decision.target == "planner":
            try:
                return AgentAction(
                    action="plan_menu",
                    arguments=self._rule_arguments(question),
                    reason=decision.reason,
                )
            except ValidationError:
                return None
        if self.answer_service is not None:
            return AgentAction(action="answer_knowledge", reason=decision.reason)
        return None

    def _rule_arguments(self, question: str) -> AgentArguments:
        count = self._number_before(question, "道")
        max_buy = self._number_after_prefix(question, ("最多买", "最多补购"))
        have = self._segment_terms(
            question,
            r"(?:家里有|我有|已有|现有)",
            r"(?=不吃|不含|不要|排除|常备|做\s*[123一二两三]\s*道|最多|[。.!！?？]|$)",
        )
        pantry = self._segment_terms(
            question,
            r"常备(?:有)?",
            r"(?=不吃|不含|不要|排除|做\s*[123一二两三]\s*道|最多|[。.!！?？]|$)",
        )
        exclude = self._segment_terms(
            question,
            r"(?:不吃|不含|不要|排除)",
            r"(?=做\s*[123一二两三]\s*道|最多|[，,。；;.!！?？]|$)",
        )
        return AgentArguments(
            have=have,
            pantry=pantry,
            exclude=exclude,
            count=count,
            max_buy=max_buy,
        )

    @staticmethod
    def _segment_terms(text: str, prefix: str, boundary: str) -> list[str]:
        match = re.search(rf"{prefix}\s*(.+?){boundary}", text)
        if not match:
            return []
        return [
            value.strip()
            for value in re.split(r"和|与|及|、|，|,", match.group(1))
            if value.strip()
        ]

    @staticmethod
    def _number_before(text: str, suffix: str) -> int | None:
        match = re.search(rf"([123一二两三])\s*{suffix}", text)
        return AgentService._number(match.group(1)) if match else None

    @staticmethod
    def _number_after_prefix(text: str, prefixes: tuple[str, ...]) -> int | None:
        joined = "|".join(re.escape(item) for item in prefixes)
        match = re.search(rf"(?:{joined})\s*([0-9一二两三四五六七八九十]+)", text)
        return AgentService._number(match.group(1)) if match else None

    @staticmethod
    def _number(value: str) -> int:
        numbers = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
                   "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
        return numbers.get(value, int(value) if value.isdigit() else 0)

    def _link(
        self, raw: str, field: Literal["have", "pantry", "exclude"]
    ) -> NormalizedTerm | None:
        cleaned = _clean_term(raw)
        conversational = _CONVERSATIONAL_ALIASES.get(cleaned)
        candidate = conversational or normalize_ingredient(cleaned)
        candidate = self.graph.graph.get("category_aliases", {}).get(candidate, candidate)
        if candidate not in self.ingredients and candidate not in self.categories:
            return None
        if conversational:
            source = "category_linker" if candidate in self.categories else "entity_linker"
        elif candidate != cleaned and cleaned in aliases():
            source = "alias"
        elif candidate in self.categories:
            source = "category_linker"
        else:
            source = "exact"
        return NormalizedTerm(
            raw=raw, canonical=candidate, field=field, source=source
        )

    def _plan(self, action: AgentAction) -> AgentResponse:
        linked: list[NormalizedTerm] = []
        unknown: list[str] = []
        for field in ("have", "pantry", "exclude"):
            for raw in getattr(action.arguments, field):
                item = self._link(raw, field)
                if item is None:
                    unknown.append(raw)
                else:
                    linked.append(item)
        if unknown:
            return self._clarification(
                f"我无法把“{'、'.join(unknown)}”唯一对应到知识图谱实体，请换成更明确的食材名称。"
            )
        values = {
            field: {item.canonical for item in linked if item.field == field}
            for field in ("have", "pantry", "exclude")
        }
        conflict = (values["have"] | values["pantry"]) & values["exclude"]
        if conflict:
            return self._clarification(
                f"{'、'.join(sorted(conflict))}同时出现在可用和排除条件中，请确认保留哪一个。"
            )
        count = action.arguments.count or 2
        max_buy = action.arguments.max_buy if action.arguments.max_buy is not None else 2
        result = recommend(
            self.graph,
            RecommendRequest(
                have=values["have"],
                pantry=values["pantry"],
                exclude=values["exclude"],
                count=count,
                max_buy=max_buy,
                limit=5,
            ),
        )
        status = "success" if result.plans else "empty"
        return AgentResponse(
            mode="planner",
            answer=f"已按{count}道菜、最多补购{max_buy}种进行均衡规划。",
            route_reason=action.reason,
            normalized_terms=linked,
            tool_trace=[
                ToolTrace(
                    tool="plan_menu",
                    status=status,
                    summary="完成类别排除、联合补购和多样性排序",
                )
            ],
            recommendation=result,
        )

    def _answer(self, question: str, top_k: int, reason: str) -> AgentResponse:
        if self.answer_service is None:
            raise LlmUnavailableError("问答模型尚未配置")
        result = self.answer_service.answer(question, retriever="auto", top_k=top_k)
        return AgentResponse(
            mode="graphrag",
            answer=result.answer,
            route_reason=reason or result.route_reason,
            tool_trace=[
                ToolTrace(
                    tool="answer_knowledge",
                    status="empty" if result.insufficient_evidence else "success",
                    summary=f"使用{result.retriever}检索并检查引用",
                )
            ],
            citations=result.citations,
            retriever=result.retriever,
            insufficient_evidence=result.insufficient_evidence,
        )

    @staticmethod
    def _clarification(question: str) -> AgentResponse:
        return AgentResponse(
            mode="clarification",
            answer="需要补充或修改输入后才能继续。",
            route_reason="实体或工具动作未通过受控校验",
            clarification_question=question,
        )
