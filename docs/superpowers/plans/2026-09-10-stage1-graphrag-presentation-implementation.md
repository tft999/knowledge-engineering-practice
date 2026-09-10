# CookKG 第一阶段 GraphRAG 汇报 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 制作一份以老师的 GraphRAG 三组件框架为起点、能在四分钟内讲清 CookKG 数据、图谱模式、架构、实例和阶段边界的 7 页 PPT。

**Architecture:** 使用现有 Artifact Tool 演示文稿工程重新编排内容。前三页建立 GraphRAG 定位和数据可信度，中间两页解释图谱模式与系统架构，最后两页用真实结果和计划收束。所有数字来自第一阶段整合验收记录。

**Tech Stack:** JavaScript ES modules、`@oai/artifact-tool`、Microsoft YaHei、PowerPoint PPTX、Markdown 讲稿。

---

### Task 1: 准备可核验的汇报内容

**Files:**
- Read: `课程要求.pptx`
- Read: `docs/validation/stage1-integration.md`
- Read: `docs/superpowers/specs/2026-09-10-stage1-graphrag-presentation-design.md`
- Modify: `.ppt-build/build-graphrag-deck.mjs`

- [ ] **Step 1: 冻结事实表**

在构建脚本顶部定义固定来源提交、扫描数、严格审核数、v2 草稿数、实体关系统计和测试数。不得在多个页面重复手写不同数字。

- [ ] **Step 2: 定义 7 页叙事结构**

按设计规范依次创建课题定位、GraphRAG 选择、数据构建、实体关系、系统架构、运行实例和阶段计划。

- [ ] **Step 3: 检查阶段口径**

搜索“GraphRAG”“人工审核”“100 道”“53 道”，确认每次出现都能区分当前能力、技术联调草稿和后续工作。

### Task 2: 构建可编辑图表和页面

**Files:**
- Create: `.ppt-build/build-graphrag-deck.mjs`
- Create: `deliverables/CookKG_第一阶段汇报_GraphRAG版.pptx`

- [ ] **Step 1: 实现通用版式函数**

实现标题、页脚、文本、圆角框、状态标记和连接线函数，统一字体、字号、边距和色彩。

- [ ] **Step 2: 构建 GraphRAG 技术选择图**

用三个连续模块展示知识图谱构建、图约束检索和知识注入，分别标记“已完成”和“下一阶段”。

- [ ] **Step 3: 构建数据流程与图谱模式**

数据页明确显示固定提交和三层数据状态；本体页用可编辑节点和关系线展示五类实体与六类核心关系。

- [ ] **Step 4: 构建总体架构图**

用上下两条路径区分离线建图和在线推荐，以虚线延伸未来的 HybridCypher 和 LLM 知识注入。

- [ ] **Step 5: 构建实例与计划页**

实例页同时展示类别忌口路径和联合补购结果；计划页按数据审核、评测、检索器和 LLM 的依赖顺序排列。

- [ ] **Step 6: 导出并运行最终器**

运行 Artifact Tool 最终器，要求 7 页、16:9、Microsoft YaHei、无布局警告，并保存独立验收报告。

### Task 3: 编写四分钟逐页讲稿

**Files:**
- Create: `deliverables/CookKG_第一阶段汇报_GraphRAG版讲稿.md`

- [ ] **Step 1: 按页写口语稿**

每页只解释一个核心问题，按 15、35、40、45、50、40、35 秒分配，总时长为 260 秒以内，并预留换页时间。

- [ ] **Step 2: 增加答辩口径**

写明老师追问“为什么算 GraphRAG”“为什么不用 LLM 判硬约束”“100 道是否审核完成”时的简短回答。

- [ ] **Step 3: 核对页面与讲稿**

逐页确认讲稿提到的数字、关系和组件都能在对应页面看到，不靠额外口头补充才能理解。

### Task 4: 视觉和内容验收

**Files:**
- Inspect: `deliverables/CookKG_第一阶段汇报_GraphRAG版.pptx`
- Inspect: `.ppt-build/graphrag-rendered/slide-*.png`

- [ ] **Step 1: 运行结构和布局检查**

确认 PPTX 包完整、7 页、所有标题适配、Microsoft YaHei 使用一致、没有对象越界或重叠。

- [ ] **Step 2: 渲染全部页面**

以至少 1.5 倍比例渲染 7 页，逐页检查文字大小、连接线方向、状态标签和数据层级。

- [ ] **Step 3: 做事实复核**

将页面数字与 `docs/validation/stage1-integration.md` 对照；确认没有把 v2 草稿写成严格审核数据，也没有把 HybridCypher 和 LLM 写成已完成。

- [ ] **Step 4: 交付**

提供最终 PPTX、讲稿和设计规范路径，并说明当前 Neo4j 在线验证和完整 GraphRAG 的实际边界。
