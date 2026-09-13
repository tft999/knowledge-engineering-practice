# 最终阶段离线验收记录（2026-09-13）

## 本次已验收

| 项目 | 结果 |
| --- | --- |
| 固定 HowToCook 全量构建 | 扫描 370，排除模板 1，正式人工审核可用 10 |
| Evidence 索引 | 121 chunks，SHA-256 `f7ac97dba7104b9042d0473279284b0400159767710d60575586bc92f2ff6fe4` |
| Python 测试 | 118 passed，2 个需在线 Neo4j 的测试 skipped |
| Ruff | passed |
| Vitest | 19 passed |
| TypeScript 与 Vite 生产构建 | passed |
| Playwright Mock | 桌面和平板共 4 passed |
| Playwright 真实 FastAPI | 菜单与层级排除流程 1 passed |

测试覆盖 Evidence 稳定性和审核门禁、四检索器、查询路由、固定参数化 Cypher、引用重试、
无证据拒答、API 合约、Neo4j Evidence 幂等写入，以及菜单和问答浏览器流程。

## 尚未验收

- v2 的 100 道记录当前是机器草稿，人工确认数为 0；正式图仍为 10 道人工审核菜谱。
- 本机本次没有连接真实 Neo4j，因此 Evidence 在线导入、全文索引及重复导入须在组员数据库复验。
- 本次没有配置真实模型服务；API 使用假模型通过集成测试，页面使用明确标识的 Mock 数据通过测试。
- 100 条人工评测题尚未签字，不能生成或宣称最终 Recall@5、答案和引用指标。

上述三项完成后，按 [评测协议](../evaluation-protocol.md)运行固定命令并把原始结果提交到
`data/evaluation/final` 对应的可审阅成果目录，再签署最终验收。
