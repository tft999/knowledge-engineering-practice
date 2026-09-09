# CookKG：家庭菜单规划

知识工程综合实践课程项目。项目使用 [HowToCook](https://github.com/Anduin2017/HowToCook)
的固定版本构建食材知识图谱，根据已有食材、常备调料和排除项推荐 1—3 道菜，
并以“联合菜单所需补购食材种类最少”为主要优化目标。

当前版本已经打通固定数据构建、知识图谱推理、联合菜单推荐、FastAPI 和 React 页面。
向量检索和 LLM 问答安排在后续阶段，本项目当前不称为 GraphRAG 系统。

项目的完整问题定义、用户故事、创新边界、总体架构和课程完成标准见
[项目定义与总体架构](docs/PROJECT.md)。后续工作已拆分为数据扩充、Web 演示、GraphRAG 和
实验答辩四个阶段，详见 [v0.2—v1.0 实施计划](docs/superpowers/plans/2026-09-09-cookkg-roadmap.md)。

当前小组讨论形成的联合课题定义、实体关系规则和职责安排见：

- [问题定义与知识图谱初步标注规范](docs/problem-and-annotation-standard.md)
- [小组成员分工](docs/team-roles.md)

## 快速开始

需要 Python 3.13。以下命令在仓库根目录运行：

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -e '.[dev]'
.venv/Scripts/cookkg fetch
.venv/Scripts/cookkg build
.venv/Scripts/cookkg recommend --have '鸡蛋,洋葱,面包片' `
  --pantry '盐,食用油,黄油,料酒' --exclude '辣椒' --count 2 --max-buy 2
.venv/Scripts/cookkg serve
```

加上 `--json` 可获得结构化结果。原始数据、标准 JSONL、NetworkX 图和质量报告
分别写入 `data/raw/howtocook` 与 `data/processed`，这些生成文件不会提交到 Git。

系统默认不假定油盐齐全。`--have` 表示希望消耗的现有食材，`--pantry` 表示常备
但不计入覆盖率的调料，`--exclude` 可以是具体食材或审核过的食材类别。补购按食材种类计算，
不判断克数是否充足。默认 API 地址为 `http://127.0.0.1:8000`，接口文档位于 `/docs`。

## Web 演示界面

`web/` 提供桌面优先、兼容平板的 React 单页菜单规划器。默认使用明确标识的演示数据；
切换环境变量后可连接真实 FastAPI，展示联合补购结果、菜谱详情和红色忌口推理路径。

```powershell
cd web
pnpm install
Copy-Item .env.example .env.local
pnpm dev
```

真实联调时先在仓库根目录执行 `cookkg build` 和 `cookkg serve`，再将 `web/.env.local`
设置为：

```env
VITE_USE_MOCKS=false
VITE_API_BASE_URL=http://localhost:8000
```

生产构建和测试命令：

```powershell
pnpm test
pnpm build
pnpm e2e
pnpm e2e:real
```

`e2e` 使用模拟数据；`e2e:real` 自动启动真实 FastAPI 和 Vite，并要求已经生成
`data/processed/graph.json`。端到端测试默认使用本机 Google Chrome。

前端设计与实施说明见[菜单规划器 UI 设计](docs/superpowers/specs/2026-09-09-menu-planner-ui-design.md)
和[实施计划](docs/superpowers/plans/2026-09-09-menu-planner-ui-implementation.md)。

## 数据质量门禁

数据源固定为 HowToCook 提交
`2b19c9e9ee926fd925a68207a57582a338813f9c`。规则解析会扫描全库并报告跨章节不一致；
严格推荐只使用 `reviewed_recipes.json` 中人工审核且 SHA-256 仍匹配的菜谱。
上游文件变化会使审核自动失效，避免旧审核覆盖新内容。

当前提交包含 10 道人工审核菜谱和版本化人工食材分类。规则解析结果中的 `pending` 食材、
未审核菜谱和结构不完整菜谱不会进入推荐；只有分类资源中 `reviewed=true` 的关系参与推理。

审核人员可以生成稳定的待审核队列并检查现有审核记录：

```powershell
.venv/Scripts/cookkg review-queue --limit 20
.venv/Scripts/cookkg review-queue --limit 20 --json
.venv/Scripts/cookkg review-check
```

`review-queue` 按“存在解析问题、问题数量较少、稳定菜谱 ID”的顺序选择样本，并显示原文
路径、内容哈希、解析问题和预抽取结果。`review-check` 会验证审核字段、菜谱路径和 SHA-256。
Zouyilin06 的首批 20 道 AI 辅助标注草稿位于
[`docs/annotations/sample-20-zouyilin06-draft.json`](docs/annotations/sample-20-zouyilin06-draft.json)，
食材层级草案位于
[`src/cookkg/resources/ingredient_hierarchy.draft.json`](src/cookkg/resources/ingredient_hierarchy.draft.json)。
二者都需要第二名标注人员独立复核，不会直接进入严格推荐。

## Zouyilin06 的 v2 数据与图谱交付

新增独立的 v2 数据管线：100 道真实 HowToCook 菜谱的 AI 辅助校读标注、262 个食材名称、
选择组、工具、类别、结构化用量、加工形态和逐行证据。100 道均通过源哈希与逐字引文校验，
**目前人工确认数为 0**；
39 道含待裁决问题，不能把机器校验通过说成“100 道人工审核完成”。
完整 v2 图谱保留全部语义；另生成与当前推荐 API 兼容的 `backend-graph.json`，仅将 46 道无语义阻断的
菜谱标为兼容可用，39 道问题菜谱和 15 道含选择组菜谱明确排除。接口联调已在本地完成，人工课程签字仍为 0。

```powershell
.venv/Scripts/cookkg data-v2 build
.venv/Scripts/cookkg data-v2 neo4j-import
.venv/Scripts/cookkg data-v2 neo4j-verify
.venv/Scripts/cookkg data-v2 neo4j-queries
.venv/Scripts/cookkg data-v2 acceptance
```

本次工作环境使用 `.venv-data/Scripts/`，其中 Python 版本为 3.13.15。
Neo4j 命令使用 `NEO4J_URI / NEO4J_USERNAME / NEO4J_PASSWORD / NEO4J_DATABASE` 环境变量。
构建产物位于 `data/processed/v2/`：`recipes.jsonl`、`networkx.node-link.json`、`graph.json`、`backend-graph.json`、
`neo4j-import.json`、本体、JSON Schema、质量报告、全源扫描、问题裁决队列、100 条评测输入草稿、
旧解析器差异报告、兼容性报告、技术核对记录和 `review-100.html`。`acceptance` 会在人工审核、双人标注、交叉复核、
接口确认或联调证据缺失时返回非零状态，防止把技术准备误报为课程任务完成。

请从 [数据模块交接说明](docs/zouyilin06-handoff.md) 开始；
详细字段见 [v2 数据契约](docs/data-contract-v2.md)，
真实数据库测试结果见 [数据与图谱验收记录](docs/validation/zouyilin06-data-v2.md)。

## Neo4j

复制 `.env.example` 中的变量到当前 shell 环境，然后执行：

```powershell
.venv/Scripts/cookkg import-neo4j
.venv/Scripts/cookkg verify-neo4j
```

导入使用 CookKG 专用标签、数据集与源提交命名空间，并采用幂等写入；不会清除其他数据。
本机没有可连接的 Neo4j 时，离线功能仍可使用，数据库验收会明确报告失败原因。

## 验证

```powershell
.venv/Scripts/python -m pytest -q
.venv/Scripts/ruff check .
```

详细设计见 [设计文档](docs/superpowers/specs/2026-09-08-cook-graph-design.md)，执行记录见
[实施计划](docs/superpowers/plans/2026-09-08-cook-graph-implementation.md)和
[首轮验收记录](docs/validation/initial-validation.md)。

## 数据许可

菜谱来自 Anduin2017/HowToCook，源仓库声明为 Unlicense。生成结果保留固定提交来源链接，
便于追溯原文。CookKG 自身的许可尚未由课程小组指定。
