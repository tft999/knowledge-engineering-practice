import json
from pathlib import Path
from typing import Annotated

import typer

from cookkg.data_neo4j import import_v2, run_queries_v2, verify_v2
from cookkg.data_pipeline import build_v2, write_json
from cookkg.data_review import compare_annotations

app = typer.Typer(help="v2 数据交付：原文证据、选择组、本体与类型化图谱")


@app.command("backend-export")
def backend_export(
    data: Annotated[Path, typer.Option()] = Path("data/processed/v2"),
    output: Annotated[Path | None, typer.Option()] = None,
) -> None:
    """生成当前推荐后端可读取的AI审核投影，并报告被排除的语义。"""
    from cookkg.data_backend import write_backend_projection

    try:
        result = write_backend_projection(data, output)
    except (ValueError, OSError, KeyError) as error:
        typer.echo(f"v2 backend export failed: {error}", err=True)
        raise typer.Exit(1) from error
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@app.command("acceptance")
def acceptance(
    data: Annotated[Path, typer.Option()] = Path("data/processed/v2"),
    team_review: Annotated[Path | None, typer.Option()] = None,
) -> None:
    """检查课程交付要求；未完成人工审核/联调时返回非零状态。"""
    from cookkg.data_delivery import acceptance_report

    try:
        report = json.loads((data / "quality-report.json").read_text(encoding="utf-8"))
        recipes = [json.loads(line) for line in (data / "recipes.jsonl").read_text(
            encoding="utf-8").splitlines() if line.strip()]
        team = json.loads(team_review.read_text(encoding="utf-8")) if team_review else None
        result = acceptance_report(report, recipes, team)
        write_json(data / "course-acceptance.json", result)
    except (ValueError, OSError, KeyError, TypeError) as error:
        typer.echo(f"v2 acceptance check failed: {error}", err=True)
        raise typer.Exit(1) from error
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["complete"]:
        raise typer.Exit(1)


@app.command("compare")
def compare(
    first: Annotated[Path, typer.Option()],
    second: Annotated[Path, typer.Option()],
    output: Annotated[Path, typer.Option()] = Path("data/processed/v2/adjudication.json"),
) -> None:
    """比较相同源版本的两份标注，输出分歧供组长裁决。"""
    try:
        report = compare_annotations(json.loads(first.read_text(encoding="utf-8")),
                                     json.loads(second.read_text(encoding="utf-8")))
        output.parent.mkdir(parents=True, exist_ok=True)
        write_json(output, report)
    except (ValueError, OSError, KeyError) as error:
        typer.echo(f"v2 comparison failed: {error}", err=True)
        raise typer.Exit(1) from error
    typer.echo(json.dumps(dict(recipe_count=report["recipe_count"],
                               same_recipe_count=report["same_recipe_count"], output=str(output)),
                          ensure_ascii=False))


@app.command("build")
def build(
    raw: Annotated[Path, typer.Option()] = Path("data/raw/howtocook"),
    output: Annotated[Path, typer.Option()] = Path("data/processed/v2"),
    annotations: Annotated[Path | None, typer.Option()] = None,
    ontology: Annotated[Path | None, typer.Option()] = None,
    approvals: Annotated[Path | None, typer.Option()] = None,
) -> None:
    """核验全部来源与标注，生成 JSONL、图、本体和离线人工核对包。"""
    try:
        result = build_v2(raw, output, annotations, ontology, approvals)
    except (ValueError, OSError, RuntimeError, KeyError) as error:
        typer.echo(f"v2 build failed: {error}", err=True)
        raise typer.Exit(1) from error
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@app.command("neo4j-import")
def neo4j_import(
    graph: Annotated[Path, typer.Option()] = Path("data/processed/v2/neo4j-import.json"),
) -> None:
    """事务化导入v2类型化图谱；仅替换该数据集/提交/接口版本。"""
    try:
        payload = json.loads(graph.read_text(encoding="utf-8"))
        result = import_v2(payload)
    except (ValueError, OSError, RuntimeError, KeyError) as error:
        typer.echo(f"v2 import failed: {error}", err=True)
        raise typer.Exit(1) from error
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@app.command("neo4j-verify")
def neo4j_verify(
    graph: Annotated[Path, typer.Option()] = Path("data/processed/v2/neo4j-import.json"),
) -> None:
    """逐项比较Neo4j中的节点、边、属性与本地图谱。"""
    try:
        result = verify_v2(json.loads(graph.read_text(encoding="utf-8")))
    except (ValueError, OSError, RuntimeError, KeyError) as error:
        typer.echo(f"v2 verification failed: {error}", err=True)
        raise typer.Exit(1) from error
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ok"]:
        raise typer.Exit(1)


@app.command("neo4j-queries")
def neo4j_queries(
    graph: Annotated[Path, typer.Option()] = Path("data/processed/v2/neo4j-import.json"),
    output: Annotated[Path, typer.Option()] = Path("data/processed/v2/neo4j-queries.json"),
) -> None:
    """执行首批100道的六个代表性查询并与NetworkX比较。"""
    try:
        result = run_queries_v2(json.loads(graph.read_text(encoding="utf-8")))
        output.parent.mkdir(parents=True, exist_ok=True)
        write_json(output, result)
    except (ValueError, OSError, RuntimeError, KeyError, StopIteration) as error:
        typer.echo(f"v2 query check failed: {error}", err=True)
        raise typer.Exit(1) from error
    typer.echo(json.dumps(dict(ok=result["ok"], output=str(output)), ensure_ascii=False))
    if not result["ok"]:
        raise typer.Exit(1)
