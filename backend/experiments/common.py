"""评测脚本公共工具：加载数据、构造引擎、保存结果。

评测结果必须保存数据版本、随机种子与原始输出，确保可重复生成。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from cookkg.engine import RecommendationEngine
from cookkg.loader import load_all

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"


@dataclass
class EvalMetadata:
    """实验元信息，随结果一起保存以保证可复现。"""

    experiment: str
    data_commit: str = "2b19c9e9ee926fd925a68207a57582a338813f9c"
    seed: int = 42
    # 评测数据目录的 recipes/taxonomy/aliases 内容哈希可在需要时追加


def build_engine(use_component: bool = False) -> RecommendationEngine:
    bundle = load_all(DATA_DIR)
    return RecommendationEngine(bundle.recipes, bundle.taxonomy, bundle.aliases, use_component)


def save_result(name: str, metadata: EvalMetadata, rows: list) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"{name}.json"
    payload = {"metadata": asdict(metadata), "rows": rows}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
