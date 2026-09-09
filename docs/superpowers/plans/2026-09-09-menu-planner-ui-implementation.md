# CookKG Menu Planner UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建带模拟 API、菜单结果、菜谱详情和知识图谱抽屉的 CookKG 单页规划器。

**Architecture:** `web/` 是独立 React/Vite 应用。组件只依赖前端领域类型和 `CookKgApi`，模拟实现与 HTTP 实现可由环境变量切换；服务端状态由 React 原生状态和 AbortController 管理。

**Tech Stack:** React、TypeScript、Vite、Tailwind CSS、Radix Dialog、React Flow、Vitest、Testing Library、Playwright、pnpm。

---

## Task 1：工程骨架与契约

- [ ] 建立 Vite、TypeScript、Tailwind、Vitest 和 Playwright 配置。
- [ ] 先编写 API 解析失败测试，再实现领域类型、运行时校验、HTTP 客户端和错误类型。
- [ ] 建立可配置延迟和场景的模拟 `CookKgApi`。
- [ ] 提交 `feat: scaffold CookKG web client`。

## Task 2：标签表单

- [ ] 先测试 Enter、逗号、去重、Backspace 和跨字段冲突。
- [ ] 实现可访问的 `IngredientTagInput` 和 `PlannerForm`。
- [ ] 实现空表单、默认数值和一键演示示例。
- [ ] 提交 `feat: add menu constraint form`。

## Task 3：推荐结果与菜谱详情

- [ ] 先测试摘要、方案排名、补购、覆盖、可选省略、来源和无解/错误状态。
- [ ] 实现提交取消、请求状态和重试。
- [ ] 先测试详情按需读取和局部失败，再实现详情展开。
- [ ] 提交 `feat: present explainable menu plans`。

## Task 4：知识图谱抽屉

- [ ] 先测试抽屉开关、菜谱切换、节点类型和失败状态。
- [ ] 实现 Radix 右侧抽屉和 React Flow 确定性布局。
- [ ] 实现关系样式、节点选择、适应视图和焦点恢复。
- [ ] 提交 `feat: visualize recipe graph explanations`。

## Task 5：响应式、无障碍与端到端验证

- [ ] 完成桌面双栏和平板单栏样式。
- [ ] 验证键盘、焦点、状态文本和安全外链。
- [ ] 实现 Playwright 核心演示流程与 1440×900、768×1024 视口检查。
- [ ] 运行 `pnpm test`、`pnpm build`、`pnpm e2e` 和后端回归测试。
- [ ] 更新 README 启动说明并提交 `docs: document CookKG web workflow`。
