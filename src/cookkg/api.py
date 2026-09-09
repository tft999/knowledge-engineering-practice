import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import Field

from cookkg.graph import load_graph
from cookkg.recommend import RecommendRequest, RecommendResult, recommend
from cookkg.services import CookKgService, GraphNeighborhood, RecipeDetail
from cookkg.taxonomy import load_taxonomy


class ApiRecommendationRequest(RecommendRequest):
    count: int = Field(default=2, ge=1, le=3)
    max_buy: int = Field(default=2, ge=0, le=20)
    limit: int = Field(default=5, ge=1, le=5)


def _cors_origins() -> list[str]:
    configured = os.getenv("COOKKG_CORS_ORIGINS")
    if configured:
        return [origin.strip() for origin in configured.split(",") if origin.strip()]
    return ["http://localhost:5173", "http://127.0.0.1:5173"]


def create_app(graph_path: Path) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if not graph_path.is_file():
            raise RuntimeError("CookKG 图谱不存在，请先运行 cookkg build")
        try:
            graph = load_graph(graph_path)
        except Exception as error:
            raise RuntimeError("CookKG 图谱无法读取，请重新运行 cookkg build") from error
        taxonomy = load_taxonomy()
        if (
            graph.graph.get("schema_version") != 2
            or graph.graph.get("taxonomy_version") != taxonomy.version
        ):
            raise RuntimeError("CookKG 图谱版本过旧，请重新运行 cookkg build")
        app.state.service = CookKgService(graph)
        yield

    app = FastAPI(title="CookKG API", version="0.2.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    def service(request: Request) -> CookKgService:
        return request.app.state.service

    @app.get("/api/health")
    def health(request: Request) -> dict:
        cookkg = service(request)
        graph = cookkg.graph
        return {
            "status": "ok",
            "dataset": graph.graph.get("dataset"),
            "source_commit": graph.graph["source_commit"],
            "schema_version": graph.graph["schema_version"],
            "taxonomy_version": graph.graph["taxonomy_version"],
            "reviewed_recipes": cookkg.reviewed_recipe_count(),
            "nodes": graph.number_of_nodes(),
            "edges": graph.number_of_edges(),
        }

    @app.post("/api/v1/recommendations", response_model=RecommendResult)
    def recommendations(payload: ApiRecommendationRequest, request: Request) -> RecommendResult:
        return recommend(service(request).graph, payload)

    @app.get("/api/v1/recipes/{recipe_id:path}", response_model=RecipeDetail)
    def recipe_detail(recipe_id: str, request: Request) -> RecipeDetail:
        try:
            return service(request).recipe_detail(recipe_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="没有找到可用菜谱") from None

    @app.get("/api/v1/graph/neighborhood", response_model=GraphNeighborhood)
    def graph_neighborhood(
        request: Request,
        recipe_id: str,
        limit: int = Query(default=30, ge=1, le=30),
        exclude: list[str] = Query(default=[]),
    ) -> GraphNeighborhood:
        try:
            return service(request).neighborhood(recipe_id, limit, set(exclude))
        except KeyError:
            raise HTTPException(status_code=404, detail="没有找到可用菜谱图谱") from None

    return app
