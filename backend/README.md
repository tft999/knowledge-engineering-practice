# CookKG 算法与后端

> 负责成员：`98K12WQ`
>
> 职责：忌口图推理、候选硬约束过滤、多菜联合补购优化、FastAPI、算法测试与评测脚本。

> **本目录与仓库根 `src/cookkg` 的关系**：根目录 `src/cookkg` 是 v0.1 过渡实现
> （`status: required/optional/pending` 单字段、忌口仅精确集合匹配、无 FastAPI）。
> 本目录是 **v0.2 升级草案**（`requirement` 与 `review_state` 分离、忌口层级推理、
> 选择组、FastAPI、评测脚本），为独立并存、尚未合并。待三人共同确认数据模型与
> API 契约后，再合并回 `src/cookkg`，届时删除本目录。

本目录实现 CookKG 的「语义过滤 + 组合优化」闭环，只读取数据模块产出的**标准数据**，
不直接解析 Markdown；硬约束判断不依赖大模型。

## 1. 目录结构

```
code/
├── cookkg/                 # 算法与后端包
│   ├── models.py           # 数据模型与接口契约（Pydantic）
│   ├── normalization.py    # 输入归一化（别名 -> 标准名）
│   ├── taxonomy.py         # 食材层级（NetworkX 有向图）
│   ├── exclusion.py        # 忌口推理：排除集合扩展与解释路径
│   ├── filter.py           # 菜谱硬约束过滤（必需/可选/选择组）
│   ├── recommend.py        # 联合补购优化（组合枚举 + 稳定排序）
│   ├── engine.py           # 推荐引擎：编排上述模块
│   ├── loader.py           # 标准数据加载（recipes/taxonomy/aliases）
│   ├── api.py              # FastAPI 服务
│   ├── cli.py              # Typer 命令行入口
│   └── errors.py           # 自定义异常
├── data/                   # 样例标准数据（演示用）
│   ├── recipes.jsonl       # 菜谱及食材关系
│   ├── taxonomy.jsonl      # 食材层级边
│   └── aliases.json        # 别名字典
├── experiments/            # 三个对照实验脚本
├── tests/                  # pytest 单元与端到端测试
├── pyproject.toml
└── requirements.txt
```

## 2. 数据接口契约（与数据模块联调）

数据模块（`Zouyilin06`）向本模块提供以下标准文件，字段定义见 `cookkg/models.py`：

**`recipes.jsonl`**，每行一个菜谱：

```json
{
  "id": "dishes/example.md",
  "name": "示例菜",
  "category": "meat_dish",
  "difficulty": 2,
  "source_url": "https://github.com/.../dishes/example.md",
  "source_hash": "sha256...",
  "review_state": "confirmed",
  "groups": [
    {"group_id": "dishes/example.md:g1", "requirement": "required_one_of",
     "min_select": 1, "max_select": 1, "open_group": false}
  ],
  "ingredients": [
    {"id": "小米椒", "requirement": "required", "review_state": "confirmed",
     "group_id": null, "quantity_raw": ["小米椒 4 颗"],
     "evidence": ["dishes/example.md:20"]}
  ]
}
```

**`taxonomy.jsonl`**，每行一条层级边（`child -> parent`）：

```json
{"relation": "IS_A", "child": "小米椒", "parent": "辣椒", "review_state": "confirmed"}
{"relation": "SUBCLASS_OF", "child": "辣椒", "parent": "蔬菜", "review_state": "confirmed"}
{"relation": "HAS_COMPONENT", "child": "豆瓣酱", "parent": "辣椒", "review_state": "confirmed"}
```

**`aliases.json`**，别名 -> 标准名：

```json
{"番茄": "西红柿", "马铃薯": "土豆", "蒜末": "蒜"}
```

> 约定：`requirement ∈ {required, optional, one_of, unknown}`；`review_state ∈ {auto, confirmed, pending, rejected}`。
> 只有 `review_state == "confirmed"` 的菜谱、关系和层级边进入严格推荐。
> 字段变更须先更新 `models.py` 与本契约，再通知其他成员。

## 3. API 契约

**请求** `POST /recommend`：

```json
{
  "have": ["鸡蛋", "土豆"],
  "pantry": ["盐", "食用油"],
  "exclude": ["辣椒"],
  "count": 2,
  "max_buy": 2,
  "limit": 5
}
```

**响应**：

```json
{
  "plans": [
    {
      "recipes": [{"id": "dishes/...", "name": "...", "source_url": "..."}],
      "buy": ["..."],
      "used_have": ["..."],
      "omitted": [{"ingredient": "...", "matched_exclude": "...", "path": ["..."]}],
      "buy_count": 1
    }
  ],
  "reason": null,
  "candidate_count": 7,
  "normalized_input": {"have": ["..."], "pantry": ["..."], "exclude": ["..."]},
  "excluded_ingredients": ["辣椒", "小米椒", "朝天椒"],
  "explanations": [{"recipe_id": "...", "verdict": "excluded", "path": ["..."]}]
}
```

健康检查：`GET /health`。

## 4. 运行

```bash
# 安装依赖
pip install -r requirements.txt

# 运行测试
pytest

# 命令行离线推荐（核心演示）
python -m cookkg.cli recommend --data-dir data \
  --have 鸡蛋,土豆,西红柿 --pantry 盐,食用油,生抽 \
  --exclude 辣椒 --count 2 --max-buy 2 --limit 5 --json

# 启动 FastAPI 服务
python -m cookkg.cli serve --data-dir data --host 127.0.0.1 --port 8000

# 运行三个对照实验
python -m experiments.exp_exclusion    # 忌口推理：关键词/别名/层级/成分
python -m experiments.exp_purchase     # 联合补购：随机/贪心/联合优化
python -m experiments.exp_semantics    # 关系语义：全必需 vs 区分语义
```

实验脚本会把结果连同元信息（数据提交、随机种子）写入 `results/`，保证可复现。

## 5. 核心算法说明

- **输入归一化**：已有食材、常备调料、排除条件统一按别名字典归一化（`normalization.py`）。
- **忌口推理**（`exclusion.py`）：排除项若是类别，沿 `SUBCLASS_OF` 找后代类别、沿 `IS_A`
  找下位食材；可选地沿 `HAS_COMPONENT` 找包含它的复合食材（`use_component=True` 开关，
  用于对照实验的「层级 + 成分」方法）。未知名称做字面精确匹配兜底。
- **候选过滤**（`filter.py`）：
  - 必需食材命中排除 -> 淘汰；
  - 可选食材命中排除 -> 保留并省略；
  - 必需选择组可用成员不足 -> 淘汰，否则优先选库存/常备成员；
  - 未审核 / `unknown` / `pending` / 开放选择组 -> 不进入严格推荐。
- **联合补购**（`recommend.py`）：`Buy(M) = Required(M) - Have - Pantry`，
  共享缺料只计一次；单菜候选按补购升序、库存覆盖降序、稳定 ID 截取后枚举组合；
  组合按同样优先级排序，返回前 `limit` 个。

## 6. 当前状态与限制（诚实声明）

- 本目录附带 `data/` 为**演示用样例数据**（9 道菜、11 条层级边），用于验证算法闭环
  与测试。真正用于课程验收的「不少于 100 道人工审核菜谱」由数据模块产出后替换。
- 联合补购只承诺**候选池内**最优（单菜候选截取前 60 道），不保证全局最优；
  这是 `PROJECT.md` 已声明的范围。
- 开放选择组（`open_group=true`）尚未支持，命中即不进入严格推荐。
- 成分推理（`HAS_COMPONENT`）默认关闭，仅在对照实验中显式开启。
- 数量按食材种类计算，不做克数扣减，不换算勺/滴/颗等单位。

## 7. 测试覆盖

`tests/` 覆盖：归一化、忌口扩展（含别名、类别、成分、字面兜底）、候选过滤
（必需/可选/必需选择组/可选选择组/待审核）、联合补购（共享缺料去重、上限约束、
无解说明、排序确定性）、FastAPI 接口（健康检查、推荐、参数校验）。
