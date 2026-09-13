import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from neo4j import GraphDatabase
from pydantic import Field

from cookkg.answering import (
    AnswerRequest,
    AnswerResponse,
    AnswerService,
    PlannerQuestionError,
)
from cookkg.evidence import build_evidence_from_graph, load_evidence
from cookkg.graph import load_graph
from cookkg.llm import LlmClient, LlmUnavailableError, llm_from_env
from cookkg.recommend import RecommendRequest, RecommendResult, recommend
from cookkg.retrieval import Neo4jCypherExpander, build_retrievers
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


def create_app(
    graph_path: Path,
    evidence_path: Path | None = None,
    llm_client: LlmClient | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if not graph_path.is_file():
            raise RuntimeError("CookKG 图谱不存在，请先运行 cookkg build")
        try:
            graph = load_graph(graph_path)
        except Exception as error:
            raise RuntimeError("CookKG 图谱无法读取，请重新运行 cookkg build") from error
        taxonomy = load_taxonomy()
        v2_integration = graph.graph.get("data_contract") == "cookkg-v2-integration"
        if graph.graph.get("schema_version") != 2 or (not v2_integration and (
            graph.graph.get("taxonomy_version") != taxonomy.version
            or graph.graph.get("taxonomy_digest") != taxonomy.digest()
        )):
            raise RuntimeError("CookKG 图谱版本过旧，请重新运行 cookkg build")
        app.state.service = CookKgService(graph)
        evidence = (
            load_evidence(evidence_path)
            if evidence_path is not None and evidence_path.is_file()
            else build_evidence_from_graph(graph)
        )
        app.state.evidence_count = len(evidence)
        app.state.graph_backend = "networkx"
        app.state.neo4j_driver = None
        graph_expander = None
        neo4j_uri = os.getenv("NEO4J_URI", "").strip()
        if neo4j_uri:
            username = os.getenv("NEO4J_USERNAME", "").strip()
            password = os.getenv("NEO4J_PASSWORD", "")
            if not username or not password:
                raise RuntimeError("Neo4j 已启用，但缺少 NEO4J_USERNAME 或 NEO4J_PASSWORD")
            driver = GraphDatabase.driver(neo4j_uri, auth=(username, password))
            try:
                driver.verify_connectivity()
            except Exception as error:
                driver.close()
                raise RuntimeError("Neo4j 已配置但无法连接") from error
            database = os.getenv("NEO4J_DATABASE", "neo4j")
            graph_expander = Neo4jCypherExpander(
                lambda: driver.session(database=database),
                str(graph.graph.get("dataset", "howtocook")),
                str(graph.graph["source_commit"]),
            )
            app.state.neo4j_driver = driver
            app.state.graph_backend = "neo4j"
        app.state.retrievers = build_retrievers(evidence, graph, graph_expander)
        configured_llm = llm_client or llm_from_env()
        app.state.answer_service = (
            AnswerService(app.state.retrievers, configured_llm) if configured_llm else None
        )
        try:
            yield
        finally:
            if app.state.neo4j_driver is not None:
                app.state.neo4j_driver.close()

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
            "integration_eligible_recipes": cookkg.integration_eligible_recipe_count(),
            "available_recipes": cookkg.available_recipe_count(),
            "nodes": graph.number_of_nodes(),
            "edges": graph.number_of_edges(),
            "evidence_chunks": request.app.state.evidence_count,
            "graphrag_ready": request.app.state.answer_service is not None,
            "graph_backend": request.app.state.graph_backend,
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

    @app.post("/api/v1/answers", response_model=AnswerResponse)
    def answers(payload: AnswerRequest, request: Request) -> AnswerResponse:
        answer_service: AnswerService | None = request.app.state.answer_service
        if answer_service is None:
            raise HTTPException(status_code=503, detail="问答模型尚未配置")
        try:
            return answer_service.answer(
                payload.question,
                retriever=payload.retriever,
                top_k=payload.top_k,
            )
        except PlannerQuestionError as error:
            raise HTTPException(status_code=409, detail=str(error)) from None
        except LlmUnavailableError:
            raise HTTPException(status_code=503, detail="问答模型调用失败") from None

    return app
