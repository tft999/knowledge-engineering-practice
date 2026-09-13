"""Evidence-constrained question answering with citation verification."""

import re
from typing import Literal

from pydantic import BaseModel, Field

from cookkg.evidence import Evidence, RetrieverName
from cookkg.llm import LlmClient
from cookkg.retrieval import Retriever
from cookkg.router import route_question


class AnswerRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    retriever: Literal["auto", "vector", "vector_cypher", "hybrid", "hybrid_cypher"] = "auto"
    top_k: int = Field(default=5, ge=1, le=10)


class Citation(BaseModel):
    evidence_id: str
    record_id: str
    recipe_id: str
    text: str
    source_url: str
    line_start: int
    line_end: int


class AnswerResponse(BaseModel):
    answer: str
    citations: list[Citation]
    retriever: RetrieverName
    route_reason: str
    insufficient_evidence: bool


class PlannerQuestionError(ValueError):
    pass


def _prompt(
    question: str, evidence: list[Evidence], correction: bool = False
) -> list[dict[str, str]]:
    numbered = "\n".join(
        f"[E{index}] {item.text}\n来源：{item.source_url}，行 {item.line_start}-{item.line_end}"
        for index, item in enumerate(evidence, 1)
    )
    correction_text = (
        "上一次回答的引用不合格。每个事实句末尾必须包含一个或多个有效引用，如 [E1]。"
        if correction
        else ""
    )
    return [
        {
            "role": "system",
            "content": (
                "你是 CookKG 菜谱问答助手。只能使用给定证据回答，不得补充证据外事实。"
                "每个事实句末尾必须引用 [E1] 形式的证据。证据不足时明确说明。"
            ),
        },
        {
            "role": "user",
            "content": f"{correction_text}\n问题：{question}\n证据：\n{numbered}".strip(),
        },
    ]


def _references(answer: str) -> list[int]:
    return [int(value) for value in re.findall(r"\[E(\d+)\]", answer)]


def _valid_answer(answer: str, evidence_count: int) -> bool:
    references = _references(answer)
    out_of_range = any(index < 1 or index > evidence_count for index in references)
    if not answer.strip() or not references or out_of_range:
        return False
    compact = re.sub(r"\s+", "", answer)
    covered = "".join(
        re.findall(r"[^。！？!?]+[。！？!?]?(?:\[E\d+\])+", compact)
    )
    return covered == compact


class AnswerService:
    def __init__(self, retrievers: dict[RetrieverName, Retriever], llm: LlmClient):
        self.retrievers = retrievers
        self.llm = llm

    def answer(
        self,
        question: str,
        retriever: Literal["auto", "vector", "vector_cypher", "hybrid", "hybrid_cypher"] = "auto",
        top_k: int = 5,
    ) -> AnswerResponse:
        if retriever == "auto":
            decision = route_question(question)
            if decision.target == "planner":
                raise PlannerQuestionError("该问题包含菜单硬约束，请使用菜单规划器")
            selected: RetrieverName = decision.target
            reason = decision.reason
        else:
            selected = retriever
            reason = "用户指定检索器"
        evidence = self.retrievers[selected].search(question, top_k)
        if not evidence:
            return AnswerResponse(
                answer="没有检索到足够的菜谱证据。",
                citations=[],
                retriever=selected,
                route_reason=reason,
                insufficient_evidence=True,
            )
        answer = ""
        for attempt in range(2):
            answer = self.llm.generate(_prompt(question, evidence, correction=attempt == 1)).strip()
            if _valid_answer(answer, len(evidence)):
                break
        if not _valid_answer(answer, len(evidence)):
            summary = "\n".join(f"[E{i}] {item.text}" for i, item in enumerate(evidence, 1))
            return AnswerResponse(
                answer=f"模型回答未通过引用检查。检索证据如下：\n{summary}",
                citations=[self._citation(i, item) for i, item in enumerate(evidence, 1)],
                retriever=selected,
                route_reason=reason,
                insufficient_evidence=True,
            )
        used = sorted(set(_references(answer)))
        return AnswerResponse(
            answer=answer,
            citations=[self._citation(index, evidence[index - 1]) for index in used],
            retriever=selected,
            route_reason=reason,
            insufficient_evidence=False,
        )

    @staticmethod
    def _citation(index: int, item: Evidence) -> Citation:
        return Citation(
            evidence_id=f"E{index}",
            record_id=item.evidence_id,
            recipe_id=item.recipe_id,
            text=item.text,
            source_url=item.source_url,
            line_start=item.line_start,
            line_end=item.line_end,
        )
