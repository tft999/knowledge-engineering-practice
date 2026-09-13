"""Deterministic question routing for planning and GraphRAG retrieval."""

from typing import Literal

from pydantic import BaseModel

RouteTarget = Literal["planner", "vector", "vector_cypher", "hybrid", "hybrid_cypher"]


class RouteDecision(BaseModel):
    target: RouteTarget
    reason: str


def route_question(question: str) -> RouteDecision:
    text = question.strip().lower()
    planner_terms = ("不吃", "排除", "补购", "最多买", "几道菜", "做两道", "做三道")
    if any(term in text for term in planner_terms):
        return RouteDecision(target="planner", reason="问题包含库存、忌口、菜数或补购约束")
    cross_terms = ("哪些菜", "都使用", "共同", "需要什么工具", "为什么不推荐")
    if any(term in text for term in cross_terms):
        return RouteDecision(target="hybrid_cypher", reason="问题需要跨菜谱或跨实体关系检索")
    relation_terms = ("属于什么", "什么类别", "有什么食材", "需要哪些食材", "关系")
    if any(term in text for term in relation_terms):
        return RouteDecision(target="vector_cypher", reason="问题需要从文本证据扩展到图谱关系")
    semantic_terms = ("清淡", "下饭", "快手", "简单", "早餐", "午餐", "晚餐")
    recipe_terms = ("炒", "汤", "饭", "面", "蛋", "肉")
    if any(term in text for term in semantic_terms) and any(term in text for term in recipe_terms):
        return RouteDecision(target="hybrid", reason="问题同时包含语义描述和明确菜谱线索")
    return RouteDecision(target="vector", reason="问题主要询问单道菜的原文事实或步骤")
