# CookKG Implementation Plan

**Goal:** HowToCook 食材知识图谱与约束菜单推荐首轮可复现交付。
**Architecture:** 固定源版本 → 规则解析与人工审核 → 标准 JSONL → 内存图/Neo4j → 组合推荐。
**Tech Stack:** Python 3.13, NetworkX, Pydantic, Typer, Neo4j, pytest, Ruff。

## 工作清单
- [x] 写入设计与计划、配置独立虚拟环境、工程入口和 Git 忽略规则。
- [x] 先编写解析与归一化测试，确认缺失实现失败后实现数据处理。
- [x] 固定提交下载，排除模板；生成来源清单、JSONL、图谱与质量报告。
- [x] 逐份阅读并审核至少 10 道真实菜谱，以源文件哈希保护审核有效性。
- [x] 实现 1—3 道菜推荐、共享缺料去重、可选项与排除项处理。
- [x] 小型人工图与独立穷举结果核对；CLI 提供文本与 JSON 输出。
- [x] 实现 Neo4j 幂等导入与快照验证；离线测试和在线验收分开记录。
- [x] 全量运行、测试与 Ruff，通过后更新 README 与验收报告，阶段性本地提交。

## 验收命令（PowerShell，仓库根目录）
```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -e '.[dev]'
.venv/Scripts/cookkg fetch
.venv/Scripts/cookkg build
.venv/Scripts/cookkg recommend --have '番茄,鸡蛋,土豆' --pantry '食用油,盐' --count 2 --max-buy 2 --json
.venv/Scripts/python -m pytest -q
.venv/Scripts/ruff check .
.venv/Scripts/cookkg import-neo4j
.venv/Scripts/cookkg verify-neo4j
```
数据库命令在 Neo4j 可连接时执行；否则记录具体原因，不能记为通过。
所有已返回推荐必须有来源且满足硬约束；无解应是结构化结果而不是编造菜单。

## 后续
中文页面与图谱展示；向量/图谱/混合检索及真实 LLM 问答；加入规则基线和消融实验。
