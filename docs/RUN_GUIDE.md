# CookKG 启动与演示指南

本文命令适用于 Windows PowerShell。所有命令默认从项目目录开始：

```powershell
cd "C:\Users\tft\Desktop\知识工程综合实践\knowledge-engineering-practice"
```

## 1. 汇报前最快启动：演示数据模式

这种方式只启动前端，不需要 Python、FastAPI、Neo4j 或大模型，适合先确认页面和演示流程。

```powershell
cd web
pnpm install
Copy-Item .env.example .env.local -Force
pnpm dev
```

确认 `web/.env.local` 内容为：

```env
VITE_USE_MOCKS=true
VITE_MOCK_SCENARIO=success
VITE_API_BASE_URL=http://localhost:8000
```

浏览器打开：

```text
http://127.0.0.1:5173
```

此时页头显示“演示数据”。菜单规划、图谱抽屉和四类 GraphRAG 问题都能演示，但结果来自固定演示数据。

## 2. 首次准备真实后端

需要 Python 3.13。无需激活虚拟环境，直接使用虚拟环境中的程序可以避免 PowerShell 执行策略问题。

```powershell
cd "C:\Users\tft\Desktop\知识工程综合实践\knowledge-engineering-practice"
python --version
python -m venv .venv
.venv\Scripts\python -m pip install -e .
```

下载固定版本的 HowToCook，并生成 v2 数据、后端图和 Evidence：

```powershell
.venv\Scripts\cookkg fetch
.venv\Scripts\cookkg data-v2 build
```

构建成功后至少应存在：

```text
data/processed/v2/backend-graph.json
data/processed/v2/evidence.jsonl
```

当前项目目录已经有这些文件，重复汇报时可以跳过本节的数据下载和构建。

## 3. 启动真实菜单规划系统

打开第一个 PowerShell 窗口，在项目根目录运行：

```powershell
.venv\Scripts\cookkg serve --v2 --host 127.0.0.1 --port 8000
```

保持窗口运行。浏览器打开以下地址检查后端：

```text
http://127.0.0.1:8000/api/health
http://127.0.0.1:8000/docs
```

也可以在另一个 PowerShell 中检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

正常结果包含：

```text
status: ok
available_recipes: 53
evidence_chunks: 700
graph_backend: networkx
```

如果还没有配置模型，`graphrag_ready` 为 `false`，但菜单规划、菜谱详情和图谱解释仍可使用。

打开第二个 PowerShell 窗口：

```powershell
cd "C:\Users\tft\Desktop\知识工程综合实践\knowledge-engineering-practice\web"
@"
VITE_USE_MOCKS=false
VITE_API_BASE_URL=http://127.0.0.1:8000
"@ | Set-Content .env.local -Encoding utf8
pnpm install
pnpm dev
```

浏览器打开：

```text
http://127.0.0.1:5173
```

页头不应显示“演示数据”。

## 4. 启用真实 GraphRAG 问答

问答接口需要一个兼容 OpenAI `/v1/chat/completions` 协议的模型服务。先启动模型服务，再在启动 FastAPI 的同一个 PowerShell 窗口设置：

```powershell
$env:LLM_BASE_URL="http://localhost:11434/v1"
$env:LLM_MODEL="填写模型名称"
$env:LLM_API_KEY="local"
.venv\Scripts\cookkg serve --v2 --host 127.0.0.1 --port 8000
```

如果使用其他模型服务，将 `LLM_BASE_URL`、`LLM_MODEL` 和 `LLM_API_KEY` 替换成该服务提供的值。

再次访问健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

确认：

```text
graphrag_ready: true
```

然后进入前端“菜谱问答”，依次测试：

```text
空气炸锅面包片要用多少度、烤多久？
洋葱炒鸡蛋需要几个鸡蛋？
小炒肉需要哪些必需食材？
哪些菜都使用鸡蛋？
```

回答应显示检索器名称、路由原因、`[E1]` 引用和固定版本原文链接。

## 5. 推荐的现场演示顺序

### 菜单规划

点击“载入演示示例”，检查输入：

```text
已有：鸡蛋、洋葱、面包片
常备：盐、食用油、黄油、料酒
排除：辣椒
菜数：2
最多补购：2
```

点击“生成菜单方案”，展示：

1. 推荐菜单和联合补购清单；
2. 已覆盖的库存食材；
3. 小炒肉被排除的解释；
4. “查看图谱解释”中的红色命中路径。

### GraphRAG 问答

进入“菜谱问答”，现场问两个问题即可：

```text
空气炸锅面包片要用多少度、烤多久？
哪些菜都使用鸡蛋？
```

第一个问题展示菜谱原文召回，第二个问题展示共享食材图扩展。点击 `[E1]` 和“查看固定版本原文”说明答案可追溯。

## 6. 可选：启用 Neo4j 图扩展

基础演示不要求 Neo4j。未配置 Neo4j 时，后端使用 NetworkX 完成图谱查询。

Neo4j 可用后，在启动后端前设置：

```powershell
$env:NEO4J_URI="bolt://localhost:7687"
$env:NEO4J_USERNAME="neo4j"
$env:NEO4J_PASSWORD="填写密码"
$env:NEO4J_DATABASE="neo4j"
.venv\Scripts\cookkg import-neo4j --v2
.venv\Scripts\cookkg verify-neo4j --v2
.venv\Scripts\cookkg serve --v2
```

健康检查中的 `graph_backend` 应变为 `neo4j`。

## 7. 常见问题

### 提示“图谱不存在”

运行：

```powershell
.venv\Scripts\cookkg fetch
.venv\Scripts\cookkg data-v2 build
```

### 菜单正常，问答返回 503

没有设置模型环境变量，或者模型服务无法访问。检查 `LLM_BASE_URL`、`LLM_MODEL`，并确认健康检查中的 `graphrag_ready` 为 `true`。

### 页面显示“演示数据”

前端仍在模拟模式。把 `web/.env.local` 中的 `VITE_USE_MOCKS` 改为 `false`，然后停止并重新运行 `pnpm dev`。

### 前端无法连接后端

确认后端窗口没有关闭，并访问：

```text
http://127.0.0.1:8000/api/health
```

前端和后端地址最好统一使用 `127.0.0.1`。如果修改了前端端口，需要通过 `COOKKG_CORS_ORIGINS` 配置允许的来源。

### 8000 或 5173 端口被占用

后端可以换成 8001：

```powershell
.venv\Scripts\cookkg serve --v2 --port 8001
```

同时把前端配置改为：

```env
VITE_API_BASE_URL=http://127.0.0.1:8001
```

前端可以换成 5174：

```powershell
pnpm dev -- --port 5174
```

此时还需在启动后端前设置：

```powershell
$env:COOKKG_CORS_ORIGINS="http://127.0.0.1:5174"
```

## 8. 汇报前一分钟检查

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

确认：

- `status` 为 `ok`；
- `available_recipes` 大于 0；
- 前端能打开且没有“服务连接失败”；
- 使用真实数据时页头没有“演示数据”；
- 需要演示问答时，`graphrag_ready` 为 `true`；
- 两个 PowerShell 窗口在汇报期间保持运行。
