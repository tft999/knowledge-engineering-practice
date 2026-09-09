"""CookKG 算法与后端模块。

本包负责：输入归一化、忌口图推理、菜谱硬约束过滤、多菜联合补购优化、
推荐解释生成，以及对外提供的 FastAPI 接口。

模块边界（见 team-roles.md）：
- 算法模块不直接解析 Markdown，只读取数据模块产出的标准数据；
- UI 不复制推荐规则，以后端返回结果为准。
"""

from __future__ import annotations

from .engine import RecommendationEngine
from .loader import DataBundle, load_aliases, load_all, load_recipes, load_taxonomy
from .models import (
    ChoiceGroup,
    Explanation,
    IngredientUse,
    MenuPlan,
    NormalizedInput,
    PlanRecipe,
    Recipe,
    RecommendRequest,
    RecommendResponse,
    TaxonomyEdge,
)

__version__ = "0.2.0"

__all__ = [
    "RecommendationEngine",
    "DataBundle",
    "load_all",
    "load_aliases",
    "load_recipes",
    "load_taxonomy",
    "ChoiceGroup",
    "Explanation",
    "IngredientUse",
    "MenuPlan",
    "NormalizedInput",
    "PlanRecipe",
    "Recipe",
    "RecommendRequest",
    "RecommendResponse",
    "TaxonomyEdge",
    "__version__",
]
