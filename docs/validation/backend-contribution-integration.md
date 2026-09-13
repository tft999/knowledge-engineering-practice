# 98K12WQ 后端贡献整合记录（2026-09-13）

## 收到的提交

远端 `main` 通过 PR #1 合入 `daa1a1e`，新增独立 `backend/` 草案。该目录包含层级忌口、
选择组、联合补购、FastAPI、29 个测试和三组小样本实验。整合前在该目录运行测试，结果为
`29 passed`。

## 与正式实现的对应关系

| 队员草案 | 正式位置 | 处理 |
| --- | --- | --- |
| 忌口层级与解释 | `src/cookkg/taxonomy.py`、`exclusion.py` | 正式实现已覆盖 |
| 选择组与联合补购 | `src/cookkg/recommend.py` | 正式实现已覆盖且已接真实图 |
| FastAPI | `src/cookkg/api.py` | 正式实现已覆盖并增加 GraphRAG API |
| 三组基线实验 | `docs/evaluation-protocol.md` | 保留实验设计，最终改用人工冻结评测集 |
| 9 道演示数据 | 正式固定 HowToCook 数据 | 不进入正式图，避免把样例当人工审核数据 |

`backend/README.md` 明确把自身定义为“独立并存、尚未合并”的 v0.2 草案，并要求完成整合后
删除该目录。最终版本执行这一约定：Git 历史完整保留原提交和评审依据，工作树只保留根目录
`src/cookkg` 作为唯一后端，避免 Python 包名、端口、接口和运行说明冲突。

## 最终验证

- 队员原草案：29 passed；
- 正式根后端：120 passed，2 skipped（在线 Neo4j）；
- Web：19 passed，生产构建通过；
- 浏览器：Mock 桌面/平板 4 passed，真实 FastAPI 1 passed。
