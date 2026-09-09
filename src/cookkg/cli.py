import json as json_module
import sys
from importlib.resources import files
from pathlib import Path
from typing import Annotated

import typer

from cookkg.data_cli import app as data_app
from cookkg.graph import load_graph
from cookkg.pipeline import build_dataset, fetch_dataset, source_config
from cookkg.recommend import RecommendRequest, recommend
from cookkg.review import build_review_queue, check_reviews

app = typer.Typer(help="HowToCook 食材知识图谱与约束菜单规划")
app.add_typer(data_app, name="data-v2")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
DEFAULT_RAW = Path("data/raw/howtocook")
DEFAULT_PROCESSED = Path("data/processed")
DEFAULT_V2_GRAPH = Path("data/processed/v2/backend-graph.json")


def _default_reviews() -> Path:
    return Path(str(files("cookkg").joinpath("resources/reviewed_recipes.json")))


def _items(value: str) -> set[str]:
    return {item.strip() for item in value.replace("，", ",").split(",") if item.strip()}


def _resolve_graph(graph: Path | None, use_v2: bool) -> Path:
    """Resolve the graph path: explicit --graph wins, else --v2 or default."""
    if graph is not None:
        return graph
    if use_v2:
        return DEFAULT_V2_GRAPH
    return DEFAULT_PROCESSED / "graph.json"


@app.command()
def fetch(
    destination: Annotated[Path, typer.Option("--destination")] = DEFAULT_RAW,
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """下载固定提交的 HowToCook 数据。"""
    try:
        manifest = fetch_dataset(destination, force)
    except Exception as error:
        typer.echo(f"下载失败：{error}", err=True)
        raise typer.Exit(1) from error
    typer.echo(json_module.dumps(manifest, ensure_ascii=False, indent=2))


@app.command()
def build(
    raw: Annotated[Path, typer.Option("--raw")] = DEFAULT_RAW,
    output: Annotated[Path, typer.Option("--output")] = DEFAULT_PROCESSED,
    reviews: Annotated[Path | None, typer.Option("--reviews")] = None,
) -> None:
    """解析、审核并建立标准数据与内存图。"""
    config = source_config()
    review_path = reviews or _default_reviews()
    try:
        report = build_dataset(raw, output, config["commit"], review_path)
    except Exception as error:
        typer.echo(f"构建失败：{error}", err=True)
        raise typer.Exit(1) from error
    typer.echo(json_module.dumps(report, ensure_ascii=False, indent=2))


def recommend_command(
    graph: Annotated[Path | None, typer.Option("--graph")] = None,
    use_v2: Annotated[bool, typer.Option("--v2")] = False,
    have: Annotated[str, typer.Option("--have")] = "",
    pantry: Annotated[str, typer.Option("--pantry")] = "",
    exclude: Annotated[str, typer.Option("--exclude")] = "",
    count: Annotated[int, typer.Option("--count", min=1, max=3)] = 1,
    max_buy: Annotated[int, typer.Option("--max-buy", min=0)] = 99,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """根据库存与限制生成菜单方案。"""
    graph_path = _resolve_graph(graph, use_v2)
    try:
        result = recommend(
            load_graph(graph_path),
            RecommendRequest(
                have=_items(have),
                pantry=_items(pantry),
                exclude=_items(exclude),
                count=count,
                max_buy=max_buy,
            ),
        )
    except Exception as error:
        typer.echo(f"推荐失败：{error}", err=True)
        raise typer.Exit(1) from error
    if json_output:
        typer.echo(result.model_dump_json(indent=2))
        return
    if not result.plans:
        typer.echo(result.reason)
        return
    for index, plan in enumerate(result.plans, 1):
        typer.echo(f"方案 {index}：{'、'.join(recipe.name for recipe in plan.recipes)}")
        typer.echo(f"补购：{'、'.join(plan.to_buy) if plan.to_buy else '无需补购'}")
        typer.echo(f"已覆盖：{'、'.join(plan.covered) if plan.covered else '无'}")
        if plan.omitted_optional:
            typer.echo(f"省略可选项：{'、'.join(plan.omitted_optional)}")
        for recipe in plan.recipes:
            typer.echo(f"来源：{recipe.source_url}")


app.command("recommend")(recommend_command)


@app.command("review-queue")
def review_queue_command(
    raw: Annotated[Path, typer.Option("--raw")] = DEFAULT_RAW,
    reviews: Annotated[Path | None, typer.Option("--reviews")] = None,
    limit: Annotated[int, typer.Option("--limit", min=1)] = 20,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """列出优先人工复核的菜谱和自动抽取结果。"""
    try:
        queue = build_review_queue(
            raw, reviews or _default_reviews(), source_config()["commit"], limit
        )
    except Exception as error:
        typer.echo(f"生成审核队列失败：{error}", err=True)
        raise typer.Exit(1) from error
    if json_output:
        typer.echo(json_module.dumps(queue, ensure_ascii=False, indent=2))
        return
    if not queue:
        typer.echo("没有待审核菜谱")
        return
    for item in queue:
        typer.echo(f"{item['recipe_id']}｜{item['name']}")
        typer.echo(f"  问题：{'、'.join(item['issues']) if item['issues'] else '无自动问题'}")
        typer.echo(f"  SHA-256：{item['sha256']}")
        typer.echo(f"  原文：{item['source_path']}")


@app.command("review-check")
def review_check_command(
    raw: Annotated[Path, typer.Option("--raw")] = DEFAULT_RAW,
    reviews: Annotated[Path | None, typer.Option("--reviews")] = None,
) -> None:
    """验证审核记录字段、源文件和内容哈希。"""
    try:
        result = check_reviews(raw, reviews or _default_reviews(), source_config()["commit"])
    except Exception as error:
        typer.echo(f"审核检查失败：{error}", err=True)
        raise typer.Exit(1) from error
    typer.echo(json_module.dumps(result, ensure_ascii=False, indent=2))
    if not result["ok"]:
        raise typer.Exit(1)


@app.command()
def serve(
    graph: Annotated[Path | None, typer.Option("--graph")] = None,
    use_v2: Annotated[bool, typer.Option("--v2")] = False,
    host: Annotated[str, typer.Option("--host")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", min=1, max=65535)] = 8000,
) -> None:
    """启动 CookKG FastAPI 服务。"""
    import uvicorn

    from cookkg.api import create_app

    uvicorn.run(create_app(_resolve_graph(graph, use_v2)), host=host, port=port)


@app.command("import-neo4j")
def import_neo4j(
    graph: Annotated[Path | None, typer.Option("--graph")] = None,
    use_v2: Annotated[bool, typer.Option("--v2")] = False,
) -> None:
    """幂等导入当前图谱快照到 Neo4j。"""
    from cookkg.neo4j_store import import_graph

    try:
        result = import_graph(load_graph(_resolve_graph(graph, use_v2)))
    except Exception as error:
        typer.echo(f"Neo4j 导入失败：{error}", err=True)
        raise typer.Exit(1) from error
    typer.echo(json_module.dumps(result, ensure_ascii=False, indent=2))


@app.command("verify-neo4j")
def verify_neo4j(
    graph: Annotated[Path | None, typer.Option("--graph")] = None,
    use_v2: Annotated[bool, typer.Option("--v2")] = False,
) -> None:
    """验证 Neo4j 当前快照与标准图一致。"""
    from cookkg.neo4j_store import verify_graph

    try:
        result = verify_graph(load_graph(_resolve_graph(graph, use_v2)))
    except Exception as error:
        typer.echo(f"Neo4j 验证失败：{error}", err=True)
        raise typer.Exit(1) from error
    typer.echo(json_module.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("ok"):
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
