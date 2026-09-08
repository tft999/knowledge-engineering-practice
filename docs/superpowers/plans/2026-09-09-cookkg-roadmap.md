# CookKG v0.2—v1.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把已完成的离线原型扩展为可演示、可评测的知识图谱与 GraphRAG 菜单规划系统。

**Architecture:** 保留标准 Recipe JSONL 作为唯一数据交换格式，以 Neo4j 持久化图关系，
FastAPI 暴露领域能力，React 提供中文界面。硬约束始终由确定性规划器执行；检索器只提供
证据，LLM 只根据证据组织答案。

**Tech Stack:** Python 3.13、Pydantic、NetworkX、Neo4j、FastAPI、pytest、React、
TypeScript、Vite、Vitest、Playwright、Neo4j GraphRAG Python、可配置的 OpenAI 兼容模型。

---

## 里程碑与顺序

| 里程碑 | 交付物 | 进入条件 | 完成条件 |
| --- | --- | --- | --- |
| M1 数据扩充 | 审核 CLI 与 100 道菜 | v0.1 已完成 | 100 道哈希有效菜谱可推荐 |
| M2 Web 演示 | FastAPI＋React | M1 数据契约稳定 | 浏览器完成核心故事 |
| M3 GraphRAG | 四检索器＋引用回答 | M2 API 稳定、Neo4j 可用 | 问答返回可验证证据 |
| M4 实验答辩 | 基线、消融、报告 | M3 功能冻结 | 一键生成实验结果与演示材料 |

不要并行修改标准数据契约和 GraphRAG 索引。每个里程碑在前一里程碑通过验收后开始。

## Task 1：审核工作流与 100 道菜谱

**Files:**

- Create: `src/cookkg/review.py`
- Modify: `src/cookkg/cli.py`, `src/cookkg/resources/reviewed_recipes.json`
- Test: `tests/test_review.py`, `tests/test_cli.py`

- [ ] **Step 1: 定义审核模型并写失败测试**

定义 `ReviewRecord`：`sha256`、`approved`、`reviewed_on`、`ingredient_status`、
`add_ingredients`、`remove_ingredients`、`add_tools`、`remove_tools`。测试拒绝未知字段、非法状态、
空食材名和非 SHA-256 值。

```python
def test_review_record_rejects_invalid_status():
    with pytest.raises(ValidationError):
        ReviewRecord(
            sha256="a" * 64,
            approved=True,
            reviewed_on=date(2026, 9, 9),
            ingredient_status={"盐": "requird"},
        )
```

- [ ] **Step 2: 实现审核队列命令**

新增 `cookkg review-queue --limit 20 --json`，按“有问题优先、问题数量少、稳定 ID”输出待审核
菜谱、抽取结果、原文路径和问题。新增 `cookkg review-check`，验证全部审核哈希和字段。

```json
{"recipe_id":"dishes/example.md","issues":["ingredient_only_in_steps:盐"],"sha256":"..."}
```

- [ ] **Step 3: 完成 100 道人工审核**

每道菜逐份对照“必备原料、计算、操作”，确定工具、必需项、可选项和解析遗漏。审核记录必须
包含审核日期；禁止用批量 `approved=true` 代替阅读。每增加 20 道运行一次：

```powershell
.venv/Scripts/cookkg build
.venv/Scripts/cookkg review-check
.venv/Scripts/python -m pytest -q
```

- [ ] **Step 4: M1 验收并提交**

验收：`reviewed_eligible >= 100`、`stale_reviews == 0`、审核检查退出 0、全部测试与 Ruff 通过。
提交信息：`feat: expand validated recipe knowledge base`。

## Task 2：FastAPI 领域接口

**Files:**

- Create: `src/cookkg/api.py`, `src/cookkg/services.py`
- Modify: `pyproject.toml`
- Test: `tests/test_api.py`

- [ ] **Step 1: 写 API 契约测试**

接口固定为：

```text
GET  /api/health
POST /api/v1/recommendations
GET  /api/v1/recipes/{recipe_id}
GET  /api/v1/graph/neighborhood?recipe_id=...&limit=30
GET  /api/v1/reviews/queue?limit=20
```

测试 1—3 道菜、非法 `count`、负数 `max_buy`、编码后的含斜杠 recipe ID、无解响应和来源字段。
请求体复用 `RecommendRequest`；无解仍返回 HTTP 200 和空 `plans`，输入非法返回 422，找不到
菜谱返回 404。

- [ ] **Step 2: 注入图谱服务**

`create_app(graph_path: Path) -> FastAPI` 在启动时加载一次图谱，通过应用状态提供只读服务。
启动时图谱缺失则失败并说明先运行 `cookkg build`；请求处理不重复读取文件。

```python
app = create_app(Path("data/processed/graph.json"))
```

- [ ] **Step 3: 实现局部图谱接口**

返回 `nodes` 和 `edges`；只允许从指定菜谱向外获取食材，最多 30 个节点。响应只包含公开字段，
不返回完整步骤或内部 Neo4j key。

- [ ] **Step 4: M2 后端验收并提交**

运行 `pytest tests/test_api.py -q`、全套 pytest 和 Ruff。提交信息：
`feat: expose CookKG domain API`。

## Task 3：React 中文演示界面

**Files:**

- Create: `web/` Vite React TypeScript 应用
- Create: `web/src/api.ts`, `web/src/pages/PlannerPage.tsx`, `web/src/components/PlanResult.tsx`
- Test: `web/src/pages/PlannerPage.test.tsx`, `web/e2e/planner.spec.ts`

- [ ] **Step 1: 建立页面行为测试**

测试用户输入逗号分隔食材、选择 1—3 道菜、设置最多补购、提交后看到菜单、补购清单、库存
覆盖和来源链接；无解时显示原始约束和明确提示，不自动修改表单。

- [ ] **Step 2: 实现单页规划器**

页面只包含四个区域：项目说明、条件输入、候选菜单、当前方案局部图谱。默认菜数 2、最多补购
2，常备与排除为空。所有网络请求集中在 `api.ts`，使用生成的 TypeScript 类型。

- [ ] **Step 3: 加入图谱可视化**

点击菜单方案后请求局部图谱。菜谱节点与食材节点使用不同颜色；必需、可选关系用实线和虚线；
节点文本来自 API，布局只负责展示，不改变数据。

- [ ] **Step 4: 端到端验收并提交**

启动 FastAPI 和 Vite 后运行 Playwright。核心演示必须在 60 秒内完成且无需编辑配置文件。
提交信息：`feat: add menu planning web experience`。

## Task 4：步骤切分、嵌入与索引

**Files:**

- Create: `src/cookkg/chunks.py`, `src/cookkg/indexing.py`, `src/cookkg/models_retrieval.py`
- Modify: `src/cookkg/cli.py`, `pyproject.toml`
- Test: `tests/test_chunks.py`, `tests/test_indexing.py`

- [ ] **Step 1: 定义 Evidence 契约**

```python
class Evidence(BaseModel):
    evidence_id: str
    recipe_id: str
    text: str
    source_url: str
    line_start: int
    line_end: int
    score: float
    retriever: Literal["vector", "vector_cypher", "hybrid", "hybrid_cypher"]
```

测试 ID 稳定、行号有效、来源固定到提交、同一输入重复构建内容一致。

- [ ] **Step 2: 按语义章节切分**

每个原料表和每个操作步骤形成独立 chunk；不跨菜谱、不按固定字符截断步骤。chunk 保存菜谱 ID、
章节、行号和文本。只索引已审核菜谱。

- [ ] **Step 3: 建立索引命令**

新增 `cookkg index`。默认嵌入提供者为配置项 `EMBEDDING_PROVIDER=openai-compatible`，模型名由
`EMBEDDING_MODEL` 指定；测试使用确定性假嵌入器，不发网络请求。索引元数据保存数据提交、审核
文件哈希、嵌入模型和维度，任一变化时拒绝复用旧索引。

- [ ] **Step 4: 索引验收并提交**

验收 100 道审核菜谱全部产生 chunk，无孤立 chunk、无错误来源、重复构建哈希一致。
提交信息：`feat: build traceable recipe evidence index`。

## Task 5：四种检索器与问题路由

**Files:**

- Create: `src/cookkg/retrieval.py`, `src/cookkg/router.py`
- Test: `tests/test_retrieval.py`, `tests/test_router.py`

- [ ] **Step 1: 定义统一检索接口**

```python
class Retriever(Protocol):
    def search(self, query: str, top_k: int = 5) -> list[Evidence]: ...
```

实现 `VectorRetriever`、`VectorCypherRetriever`、`HybridRetriever`、`HybridCypherRetriever`。
所有实现按 `score` 降序、`evidence_id` 升序稳定排序，并去除重复证据。

- [ ] **Step 2: 使用受控图查询**

Cypher 扩展仅使用预定义参数化模板：菜谱到食材、食材到菜谱、菜谱到分类。禁止将用户文本拼入
Cypher。超时、无结果和 Neo4j 不可用分别返回明确错误，不静默改用其他检索器。

- [ ] **Step 3: 实现确定性路由**

库存/忌口/补购问题进入 `planner`；单菜步骤进入 `vector`；食材关联进入 `vector_cypher`；同时
包含精确菜名和描述时进入 `hybrid`；跨菜关联进入 `hybrid_cypher`。路由响应包含选择原因。

- [ ] **Step 4: 检索验收并提交**

为五类意图各准备至少 10 个路由样例；每个检索器用固定小图验证召回与证据来源。
提交信息：`feat: add routed graph and hybrid retrieval`。

## Task 6：带引用的回答服务

**Files:**

- Create: `src/cookkg/answering.py`, `src/cookkg/llm.py`
- Modify: `src/cookkg/api.py`, `.env.example`
- Test: `tests/test_answering.py`, `tests/test_api.py`

- [ ] **Step 1: 定义问答接口**

新增 `POST /api/v1/answers`：

```json
{"question":"洋葱炒鸡蛋如何准备？","retriever":"auto","top_k":5}
```

响应包含 `answer`、`citations`、`retriever`、`route_reason`、`insufficient_evidence`。

- [ ] **Step 2: 实现证据约束提示与引用检查**

模型输入只包含系统指令、用户问题和编号证据。回答引用格式为 `[E1]`。生成后检查所有引用存在，
并检查每个事实句至少有一个引用；失败时重试一次，仍失败则返回证据摘要并标记证据不足。

- [ ] **Step 3: 隔离模型提供者**

`LLMClient.generate(messages) -> str` 是唯一模型边界。配置使用 `LLM_BASE_URL`、`LLM_API_KEY`、
`LLM_MODEL`；测试使用本地假客户端。错误消息不能包含密钥。

- [ ] **Step 4: 问答验收并提交**

测试不存在引用、引用越界、模型超时、无证据和正常回答。提交信息：
`feat: answer recipe questions with verified citations`。

## Task 7：对照实验与消融

**Files:**

- Create: `evaluation/questions.jsonl`, `src/cookkg/evaluation.py`
- Create: `tests/test_evaluation.py`, `docs/evaluation-protocol.md`

- [ ] **Step 1: 建立 100 题评测集**

五类各 20 题：单菜事实、多跳食材关联、库存菜单、排除条件、无答案。每题保存标准答案、必须
证据 ID、禁止食材和问题类型。划分 20 题开发集与 80 题冻结测试集。

- [ ] **Step 2: 实现指标**

计算检索 Recall@5、菜单约束违反率、补购种类数、答案正确率、引用正确率、引用完整率、无答案
识别率、平均延迟和模型调用成本。所有原始逐题结果写入带时间戳的 JSONL。

- [ ] **Step 3: 运行基线与消融**

基线为关键词筛选与普通 Vector RAG；主系统为四种路由检索。消融分别移除食材归一化、图扩展、
全文召回和审核门禁。固定数据版本、问题集、模型、温度、top-k 和随机种子。

- [ ] **Step 4: 生成可复现报告并提交**

`cookkg evaluate --config evaluation/config.json` 生成 CSV 和 Markdown 汇总。报告同时展示改进、退化
和失败案例，不只选择正例。提交信息：`feat: add reproducible CookKG evaluation`。

## Task 8：最终集成、演示与答辩材料

**Files:**

- Modify: `README.md`, `docs/PROJECT.md`
- Create: `docs/demo-script.md`, `docs/final-validation.md`
- Test: 全套后端、前端、端到端和在线 Neo4j 测试

- [ ] **Step 1: 完成一键启动**

提供 Docker Compose 启动 Neo4j、API 和 Web；健康检查依赖真实服务状态。密钥通过未跟踪的 `.env`
注入，镜像和仓库不包含密钥。

- [ ] **Step 2: 编写三分钟演示脚本**

固定演示顺序：库存与忌口输入 → 联合菜单与补购 → 图谱依据 → 菜谱问答与引用 → 对照实验结果。
准备无模型网络时的离线菜单演示，但不得把缓存结果描述成实时模型回答。

- [ ] **Step 3: 最终验证**

```powershell
.venv/Scripts/cookkg fetch
.venv/Scripts/cookkg build
.venv/Scripts/cookkg import-neo4j
.venv/Scripts/cookkg verify-neo4j
.venv/Scripts/python -m pytest -q
.venv/Scripts/ruff check .
pnpm --dir web test
pnpm --dir web exec playwright test
```

- [ ] **Step 4: 完成定义检查并提交**

逐项核对 `docs/PROJECT.md` 的完成定义，记录命令、版本、通过数和仍存限制。提交信息：
`docs: finalize CookKG course delivery`。
