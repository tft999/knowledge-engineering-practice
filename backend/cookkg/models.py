"""CookKG 数据模型与接口契约。

本模块定义两类对象：

1. **数据模块 -> 算法模块** 的标准数据对象（数据接口契约）：
   - ``Recipe`` / ``IngredientUse`` / ``ChoiceGroup``：菜谱及其食材关系；
   - ``TaxonomyEdge``：食材层级（IS_A / SUBCLASS_OF / HAS_COMPONENT）。

2. **算法模块对外暴露** 的推荐请求与响应模型（API 契约）：
   - ``RecommendRequest`` / ``RecommendResponse`` 及其子对象。

字段变更必须先更新本模块与 README 中的数据接口契约，再通知其他成员联调。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# 枚举取值
# ---------------------------------------------------------------------------

# 需求语义（requirement）：表示食材在做法中的使用方式
Requirement = Literal["required", "optional", "one_of", "unknown"]

# 审核状态（review_state）：需求语义与审核状态分离保存
ReviewState = Literal["auto", "confirmed", "pending", "rejected"]

# 图谱关系类型
RelationType = Literal["IS_A", "SUBCLASS_OF", "HAS_COMPONENT"]

# ---------------------------------------------------------------------------
# 数据模块 -> 算法模块 的标准数据对象
# ---------------------------------------------------------------------------


class IngredientUse(BaseModel):
    """一条菜谱-食材关系。

    对应图模式中的 ``(Recipe)-[:REQUIRES|OPTIONALLY_USES|ONE_OF]->(Ingredient)``。
    需求语义与审核状态分开保存，不把 ``pending`` 当成一种使用方式。
    """

    id: str = Field(description="审核后的标准食材名称（采购决策粒度）")
    requirement: Requirement = "required"
    review_state: ReviewState = "auto"
    group_id: str | None = Field(
        default=None, description="选择组 ID，仅 requirement='one_of' 时有效"
    )
    quantity_raw: list[str] = Field(default_factory=list, description="原文用量片段")
    evidence: list[str] = Field(
        default_factory=list, description="原文证据位置，如 dishes/xxx.md:20"
    )


class ChoiceGroup(BaseModel):
    """一个食材选择组（对应 ONE_OF 关系组的约束）。

    成员不在此处重复列出，统一从 ``Recipe.ingredients`` 中
    ``requirement == 'one_of'`` 且 ``group_id`` 匹配的条目聚合，避免两份数据不一致。
    """

    group_id: str = Field(description="形如 'recipe-id:group-name'")
    requirement: Literal["required_one_of", "optional_one_of"] = "required_one_of"
    min_select: int = Field(default=1, ge=1, description="至少选择多少项")
    max_select: int = Field(default=1, ge=1, description="至多选择多少项")
    open_group: bool = Field(
        default=False,
        description="列举不完整（比如、等等）时为 True，算法未支持时不能进入严格推荐",
    )


class Recipe(BaseModel):
    """一道菜谱（对应 Recipe 实体）。"""

    id: str = Field(description="HowToCook 仓库相对路径，作为稳定 ID")
    name: str = Field(description="一级标题去掉‘的做法’")
    category: str | None = Field(default=None, description="来源目录，如 meat_dish")
    difficulty: int | None = Field(default=None, description="星级数量，无法确定时为空")
    source_url: str | None = Field(default=None, description="固定到指定提交的原文链接")
    source_hash: str | None = Field(default=None, description="Markdown 内容的 SHA-256")
    review_state: ReviewState = "confirmed"
    groups: list[ChoiceGroup] = Field(default_factory=list, description="选择组约束")
    ingredients: list[IngredientUse] = Field(default_factory=list, description="食材关系")


class TaxonomyEdge(BaseModel):
    """一条食材层级边。

    ``child -> parent`` 的语义由 ``relation`` 决定：
    ``IS_A``（食材 -> 类别）、``SUBCLASS_OF``（类别 -> 类别）、
    ``HAS_COMPONENT``（食材 -> 食材）。
    """

    relation: RelationType
    child: str
    parent: str
    review_state: ReviewState = "confirmed"


# ---------------------------------------------------------------------------
# 推荐请求与响应
# ---------------------------------------------------------------------------


class RecommendRequest(BaseModel):
    """菜单推荐请求。"""

    have: list[str] = Field(default_factory=list, description="已有食材")
    pantry: list[str] = Field(default_factory=list, description="常备调料")
    exclude: list[str] = Field(default_factory=list, description="排除的具体食材或食材类别")
    count: int = Field(default=2, ge=1, le=3, description="计划制作的菜数，1 至 3")
    max_buy: int = Field(default=2, ge=0, description="最多允许补购的食材种类数")
    limit: int = Field(default=5, ge=1, description="返回的方案数上限")


class NormalizedInput(BaseModel):
    """归一化后的用户输入。"""

    have: list[str]
    pantry: list[str]
    exclude: list[str]


class Omission(BaseModel):
    """因忌口被省略的可选食材。"""

    ingredient: str = Field(description="被省略的食材标准名")
    matched_exclude: str = Field(description="命中的排除项")
    path: list[str] = Field(default_factory=list, description="菜谱食材到排除项的图路径")
    evidence: list[str] = Field(default_factory=list, description="原文证据")


class Explanation(BaseModel):
    """一条菜谱保留 / 淘汰 / 省略的解释路径。"""

    recipe_id: str
    recipe_name: str
    verdict: Literal["excluded", "omitted"] = Field(
        description="excluded=菜谱被淘汰，omitted=菜谱保留但省略某食材"
    )
    relation: str = Field(description="命中的菜谱-食材关系，如 REQUIRES / OPTIONALLY_USES")
    path: list[str] = Field(
        default_factory=list, description="节点路径，如 ['小炒肉', '小米椒', '辣椒']"
    )
    matched_exclude: str = Field(description="命中的用户排除项")
    reason: str = Field(description="人类可读的说明")
    evidence: list[str] = Field(default_factory=list, description="原文证据")


class PlanRecipe(BaseModel):
    """方案中的一道菜。"""

    id: str
    name: str
    source_url: str | None = None


class MenuPlan(BaseModel):
    """一个推荐菜单方案。"""

    recipes: list[PlanRecipe]
    buy: list[str] = Field(description="多道菜合并去重后的补购清单")
    used_have: list[str] = Field(description="已利用的库存食材")
    omitted: list[Omission] = Field(default_factory=list, description="被省略的可选食材")
    buy_count: int = Field(description="补购种类数 |Buy(M)|")


class RecommendResponse(BaseModel):
    """菜单推荐响应。"""

    plans: list[MenuPlan]
    reason: str | None = Field(default=None, description="无可行组合时的明确原因")
    candidate_count: int = Field(default=0, description="过滤后候选菜谱数")
    normalized_input: NormalizedInput
    excluded_ingredients: list[str] = Field(
        default_factory=list, description="扩展后的排除食材与类别"
    )
    explanations: list[Explanation] = Field(
        default_factory=list, description="保留 / 淘汰 / 省略的解释路径"
    )
