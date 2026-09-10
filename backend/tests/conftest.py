"""测试 fixture：加载样例数据、构造引擎。"""

from __future__ import annotations

from pathlib import Path

import pytest

from cookkg.engine import RecommendationEngine
from cookkg.loader import load_all

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture(scope="session")
def bundle():
    return load_all(DATA_DIR)


@pytest.fixture(scope="session")
def engine(bundle):
    return RecommendationEngine(bundle.recipes, bundle.taxonomy, bundle.aliases)


@pytest.fixture(scope="session")
def engine_component(bundle):
    """启用经审核成分关系扩展的引擎。"""
    return RecommendationEngine(
        bundle.recipes, bundle.taxonomy, bundle.aliases, use_component=True
    )
