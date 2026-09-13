# CookKG 最终评测协议

## 数据冻结

评测前记录 HowToCook 提交、图谱版本、分类资源摘要、Evidence 摘要、模型名、模型参数、
检索 `top_k` 和随机种子。20 条开发题用于修正规则，80 条测试题冻结后不得调参。

每题至少包含 `case_id`、`question`、`expected_recipe_ids` 和 `human_reviewed=true`。
最终命令会拒绝未审核题目。菜单题、单菜步骤题、食材关系题和跨菜谱题应分层统计。

## 对照实验

1. 精确关键词排除 vs 食材类别图谱展开：统计召回率、精确率和硬约束违反率。
2. 逐道贪心 vs 多道菜联合优化：统计平均补购种类及可行率。
3. Vector vs VectorCypher vs Hybrid vs HybridCypher：统计 Recall@5 和延迟。
4. 消融归一化、图扩展、关键词召回、审核门禁：每次只关闭一个模块。

回答由两名成员独立判断正确性、引用正确性、引用完整性和证据不足识别，分歧交组长裁决。
保留逐题 JSONL，汇总 CSV 只能由逐题结果生成。报告同时给出样本数、均值和失败案例，
不把模型不可用、Neo4j 不可用或未人工审核的数据记成通过。

## 运行

```powershell
cookkg index
cookkg evaluate --questions docs/evaluation/questions-100.json --output data/evaluation/final
pytest -q
ruff check .
cd web
pnpm test -- --run
pnpm build
pnpm e2e
```
