import json as json_module
import sys
from importlib.resources import files
from pathlib import Path
from typing import Annotated

import typer

from cookkg.graph import load_graph
from cookkg.pipeline import build_dataset, fetch_dataset, source_config
from cookkg.recommend import RecommendRequest, recommend

app = typer.Typer(help="HowToCook 食材知识图谱与约束菜单规划")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
DEFAULT_RAW = Path("data/raw/howtocook")
DEFAULT_PROCESSED = Path("data/processed")


def _items(value: str) -> set[str]:
    return {item.strip() for item in value.replace("，", ",").split(",") if item.strip()}


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
    review_path = reviews or Path(str(files("cookkg").joinpath("resources/reviewed_recipes.json")))
    try:
        report = build_dataset(raw, output, config["commit"], review_path)
    except Exception as error:
        typer.echo(f"构建失败：{error}", err=True)
        raise typer.Exit(1) from error
    typer.echo(json_module.dumps(report, ensure_ascii=False, indent=2))


def recommend_command(
    graph: Annotated[Path, typer.Option("--graph")] = DEFAULT_PROCESSED / "graph.json",
    have: Annotated[str, typer.Option("--have")] = "",
    pantry: Annotated[str, typer.Option("--pantry")] = "",
    exclude: Annotated[str, typer.Option("--exclude")] = "",
    count: Annotated[int, typer.Option("--count", min=1, max=3)] = 1,
    max_buy: Annotated[int, typer.Option("--max-buy", min=0)] = 99,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """根据库存与限制生成菜单方案。"""
    try:
        result = recommend(
            load_graph(graph),
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
        typer.echo(f"方案 {index}：{'、'.join(plan.recipes)}")
        typer.echo(f"补购：{'、'.join(plan.to_buy) if plan.to_buy else '无需补购'}")
        typer.echo(f"已覆盖：{'、'.join(plan.covered) if plan.covered else '无'}")
        if plan.omitted_optional:
            typer.echo(f"省略可选项：{'、'.join(plan.omitted_optional)}")
        for source in plan.source_urls:
            typer.echo(f"来源：{source}")


app.command("recommend")(recommend_command)


@app.command("import-neo4j")
def import_neo4j(
    graph: Annotated[Path, typer.Option("--graph")] = DEFAULT_PROCESSED / "graph.json",
) -> None:
    """幂等导入当前图谱快照到 Neo4j。"""
    from cookkg.neo4j_store import import_graph

    try:
        result = import_graph(load_graph(graph))
    except Exception as error:
        typer.echo(f"Neo4j 导入失败：{error}", err=True)
        raise typer.Exit(1) from error
    typer.echo(json_module.dumps(result, ensure_ascii=False, indent=2))


@app.command("verify-neo4j")
def verify_neo4j(
    graph: Annotated[Path, typer.Option("--graph")] = DEFAULT_PROCESSED / "graph.json",
) -> None:
    """验证 Neo4j 当前快照与标准图一致。"""
    from cookkg.neo4j_store import verify_graph

    try:
        result = verify_graph(load_graph(graph))
    except Exception as error:
        typer.echo(f"Neo4j 验证失败：{error}", err=True)
        raise typer.Exit(1) from error
    typer.echo(json_module.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("ok"):
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
