# v0.2 算法与后端 —— 整合说明与字段差异对照

> 负责成员：`98K12WQ`
>
> 本文档说明本目录（`backend/`，v0.2 升级草案）与仓库根 `src/cookkg`（v0.1 过渡实现）
> 的关系、字段差异与整合计划，供三人共同确认数据模型与 API 契约（v1.0）时参考。

## 1. 现状：两套实现并存

| 维度 | `src/cookkg`（v0.1，组长已建） | `backend/`（v0.2，本次提交） |
| --- | --- | --- |
| 需求语义 | `status: required/optional/pending` 单字段 | `requirement: required/optional/one_of/unknown` + 独立 `review_state` |
| 忌口排除 | `required & exclude` 精确集合交集 | 沿层级推理（辣椒 → 小米椒）+ 可选成分推理 |
| 选择组 | 无 | 有（required_one_of / optional_one_of） |
| 解释路径 | 无 | 有（explanation.path + evidence） |
| FastAPI | 无（前端用 mock） | 有 |
| 评测脚本 | 无 | 三个对照实验 |
| 包布局 | `src/` | 平铺 |
| Python 要求 | >=3.13 | >=3.11 |
| 依赖 | networkx / pydantic / typer / neo4j | + fastapi / uvicorn |

v0.2 是对 v0.1 的**升级**，不是替代：`PROJECT.md` 第 6.1 节已把 v0.1 的
`required/optional/pending` 单字段模型定义为「过渡结构」，并要求「v0.2 迁移时必须保持
旧数据可读取」。

## 2. 字段差异对照表（数据模块 & API 契约）

### 2.1 菜谱-食材关系

| 概念 | v0.1 `IngredientUse` | v0.2 `IngredientUse` | 说明 |
| --- | --- | --- | --- |
| 食材名 | `name: str` | `id: str` | 字段名 `name` → `id`，语义不变（采购决策粒度标准名） |
| 需求语义 | `status: required/optional/pending` | `requirement: required/optional/one_of/unknown` | 拆分：`pending` 不再混在需求语义里 |
| 审核状态 | （无独立字段） | `review_state: auto/confirmed/pending/rejected` | 新增，与需求语义分离 |
| 选择组 | （无） | `group_id: str | None` | 新增，仅 `one_of` 时有效 |
| 用量/证据 | `quantity_raw` / `evidence` | 同 | 不变 |

### 2.2 菜谱实体

| 概念 | v0.1 `Recipe` | v0.2 `Recipe` | 说明 |
| --- | --- | --- | --- |
| 审核状态 | `reviewed: bool` | `review_state: auto/confirmed/pending/rejected` | bool → 枚举，语义更细 |
| 准入标记 | `eligible: bool` | （无，由 `_check_admission` 推导） | 是否进严格推荐由算法判定 |
| 选择组 | （无） | `groups: list[ChoiceGroup]` | 新增 |
| 工具 | `tools: list[str]` | （无，暂不参与推荐） | 保留在数据模块，算法不消费 |
| 步骤 | `steps: str` | （无） | 同上 |
| `category` | `str`（必填） | `str | None` | 放宽为可空 |

### 2.3 推荐请求

| 概念 | v0.1 `RecommendRequest` | v0.2 `RecommendRequest` | 说明 |
| --- | --- | --- | --- |
| 集合类型 | `have/pantry/exclude: set[str]` | `list[str]` | set → list（JSON 序列化更友好） |
| 菜数 | `count: int = 1` | `count: int = 2`，`ge=1 le=3` | 默认值统一 |
| 补购上限 | `max_buy: int = 99` | `max_buy: int = 2`，`ge=0` | 默认值统一 |
| 校验方式 | `field_validator` | `Field(ge/le)` | 等价 |

### 2.4 推荐响应

| 概念 | v0.1 | v0.2 | 说明 |
| --- | --- | --- | --- |
| 方案 | `MenuPlan` | `MenuPlan` | 结构见下 |
| 无解原因 | `reason: str | None` | 同 | 不变 |
| 候选数 | `candidate_count: int` | 同 | 不变 |
| 归一化回显 | （无） | `normalized_input` | 新增 |
| 排除扩展 | （无） | `excluded_ingredients` | 新增 |
| 解释 | （无） | `explanations: list[Explanation]` | 新增 |

**`MenuPlan` 字段对照（重点）**：

| v0.1 `MenuPlan` | v0.2 `MenuPlan` | 说明 |
| --- | --- | --- |
| `recipe_ids: list[str]` | `recipes: list[PlanRecipe]` | 三个平行 list 合并为结构化对象 |
| `recipes: list[str]`（菜名） | 同上 `PlanRecipe.name` | 同上 |
| `source_urls: list[str]` | 同上 `PlanRecipe.source_url` | 同上 |
| `to_buy: list[str]` | `buy: list[str]` | 重命名 |
| `covered: list[str]` | `used_have: list[str]` | 重命名 |
| `omitted_optional: list[str]` | `omitted: list[Omission]` | 字符串 → 结构化（含路径/证据） |
| （无） | `buy_count: int` | 新增，冗余存补购种类数 |

### 2.5 新增对象（v0.1 完全没有）

- `ChoiceGroup`：选择组约束（`group_id` / `requirement` / `min_select` / `max_select` / `open_group`）。
- `TaxonomyEdge`：食材层级边（`IS_A` / `SUBCLASS_OF` / `HAS_COMPONENT`）。
- `NormalizedInput` / `Omission` / `Explanation` / `PlanRecipe`：解释与展示用。

## 3. 需要三人共同确认的待决项

1. **字段名最终版**：`to_buy` vs `buy`、`covered` vs `used_have`、`name` vs `id`、
   `omitted_optional` vs `omitted`。建议以 v0.2 为准（语义更清晰、结构化），
   但需组长（前端已消费 v0.1 字段）与数据模块确认。
2. **taxonomy 层级数据的归属**：v0.2 的忌口层级推理需要 `taxonomy.jsonl`（食材 IS_A/SUBCLASS_OF
   关系）。这份数据应由数据模块（`Zouyilin06`）产出；`backend/data/taxonomy.jsonl`
   目前是演示用样例，需替换。
3. **旧数据兼容**：`PROJECT.md` 要求「v0.2 迁移时保持旧数据可读取」。合并时需在
   `models.py` 加一个从 v0.1 `status/reviewed` 到 v0.2 `requirement/review_state`
   的迁移函数，保证已审核的 `reviewed_recipes.json` 不丢。
4. **包布局统一**：v0.2 平铺布局应并入 `src/cookkg/`，与 v0.1 的 `src/` 布局一致。
5. **Python 与依赖**：`>=3.13` 还是 `>=3.11`；是否把 `fastapi`/`uvicorn` 加进主依赖。

## 4. 建议的整合顺序（阶段二/三协作）

1. 三人确认上述待决项，冻结 API v1 与数据模型 v1。
2. 数据模块产出 taxonomy 层级数据 + 100 道审核菜谱（替换 `backend/data/` 样例）。
3. 算法层把 `exclusion/taxonomy/filter/api` 并入 `src/cookkg/`，`recommend.py` 升级为层级推理，
   `parser/pipeline/neo4j_store` 仍由数据模块维护。
4. 组长前端从 mock 切换到真实 FastAPI，三方联调。
5. 删除 `backend/` 目录，`src/cookkg` 成为唯一实现。

## 5. 本分支交付物（可 review）

- `backend/cookkg/`：12 个模块，忌口推理 + 过滤 + 联合补购 + FastAPI + CLI。
- `backend/tests/`：29 个测试，`cd backend && pytest` 全通过。
- `backend/experiments/`：三个对照实验脚本（忌口推理 / 联合补购 / 关系语义）。
- `backend/data/`：演示用样例标准数据（9 道菜 + 17 条层级边 + 6 条别名）。
- `backend/README.md`：完整接口契约与运行说明。
- `backend/汇报.md`：逐文件详细说明。
