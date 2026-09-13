"""命令行入口：离线加载标准数据并执行菜单推荐，或启动 FastAPI 服务。

用法示例：:

    # 离线推荐
    python -m cookkg.cli recommend --data-dir data \\
        --have 鸡蛋,土豆 --pantry 盐,食用油 --exclude 辣椒 \\
        --count 2 --max-buy 2 --limit 5

    # 启动服务
    python -m cookkg.cli serve --data-dir data --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from .engine import RecommendationEngine
from .loader import load_all
from .models import RecommendRequest, RecommendResponse
from .recommend import DEFAULT_CANDIDATE_CAP

app = typer.Typer(help="CookKG 算法与后端命令行工具")


def _split(values: str | None) -> list[str]:
    if not values:
        return []
    return [v.strip() for v in values.split(",") if v.strip()]


def _render_text(resp: RecommendResponse) -> str:
    lines: list[str] = []
    lines.append(f"候选菜谱数：{resp.candidate_count}")
    lines.append(f"排除集合：{'、'.join(resp.excluded_ingredients) or '（无）'}")
    if resp.reason:
        lines.append(f"无解原因：{resp.reason}")
        return "\n".join(lines)
    for i, plan in enumerate(resp.plans, start=1):
        names = "、".join(f"{r.name}({r.id})" for r in plan.recipes)
        lines.append(f"[方案 {i}] {names}")
        lines.append(f"  补购({plan.buy_count} 种)：{'、'.join(plan.buy) or '（无需补购）'}")
        lines.append(f"  利用库存：{'、'.join(plan.used_have) or '（无）'}")
        if plan.omitted:
            lines.append(f"  省略：{'、'.join(o.ingredient for o in plan.omitted)}")
    return "\n".join(lines)


def _build_engine(data_dir: str, use_component: bool) -> RecommendationEngine:
    bundle = load_all(Path(data_dir))
    return RecommendationEngine(
        bundle.recipes, bundle.taxonomy, bundle.aliases, use_component=use_component
    )


@app.command()
def recommend(
    data_dir: Annotated[str, typer.Option(help="标准数据目录，含 recipes.jsonl 等")] = "data",
    have: Annotated[str, typer.Option(help="已有食材，逗号分隔")] = "",
    pantry: Annotated[str, typer.Option(help="常备调料，逗号分隔")] = "",
    exclude: Annotated[str, typer.Option(help="排除的食材或类别，逗号分隔")] = "",
    count: Annotated[int, typer.Option(min=1, max=3, help="菜数 1~3")] = 2,
    max_buy: Annotated[int, typer.Option(min=0, help="最多补购种类")] = 2,
    limit: Annotated[int, typer.Option(min=1, help="返回方案数")] = 5,
    use_component: Annotated[bool, typer.Option(help="启用经审核的成分关系扩展")] = False,
    json_out: Annotated[bool, typer.Option("--json", help="以 JSON 输出")] = False,
    candidate_cap: Annotated[int, typer.Option(help="候选池上限")] = DEFAULT_CANDIDATE_CAP,
) -> None:
    """执行一次菜单推荐。"""
    engine = _build_engine(data_dir, use_component)
    request = RecommendRequest(
        have=_split(have),
        pantry=_split(pantry),
        exclude=_split(exclude),
        count=count,
        max_buy=max_buy,
        limit=limit,
    )
    response = engine.recommend(request)
    if json_out:
        typer.echo(response.model_dump_json(indent=2))
    else:
        typer.echo(_render_text(response))


@app.command()
def serve(
    data_dir: Annotated[str, typer.Option(help="标准数据目录")] = "data",
    host: Annotated[str, typer.Option(help="监听地址")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="监听端口")] = 8000,
    use_component: Annotated[bool, typer.Option(help="启用经审核的成分关系扩展")] = False,
) -> None:
    """启动 FastAPI 服务。"""
    import uvicorn

    from .api import create_app

    engine = _build_engine(data_dir, use_component)
    uvicorn.run(create_app(engine), host=host, port=port)


if __name__ == "__main__":
    app()
