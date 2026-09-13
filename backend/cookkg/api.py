"""FastAPI 服务。

UI 只调用本接口，不复制推荐规则。后端负责保证硬约束正确。
"""

from __future__ import annotations

from fastapi import FastAPI

from .engine import RecommendationEngine
from .models import RecommendRequest, RecommendResponse


def create_app(engine: RecommendationEngine) -> FastAPI:
    """以给定引擎构建 FastAPI 应用。"""
    app = FastAPI(
        title="CookKG",
        version="0.2.0",
        description="基于食材层级知识图谱与约束优化的可解释家庭菜单规划系统 API",
    )

    @app.get("/health", tags=["meta"])
    def health() -> dict:
        return {"status": "ok", "recipes": len(engine.recipes)}

    @app.post("/recommend", response_model=RecommendResponse, tags=["recommend"])
    def recommend(request: RecommendRequest) -> RecommendResponse:
        """菜单推荐：输入已有食材、常备调料、排除项、菜数与补购上限。"""
        return engine.recommend(request)

    return app
