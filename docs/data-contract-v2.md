# CookKG 数据接口 v2（完整图谱契约与兼容投影）

v2 是数据负责人的完整交付接口；`graph.json` 是保留选择组、未决关系和证据的规范图谱。
当前推荐 API 使用同一构建生成的 `backend-graph.json` 兼容投影，并通过 `backend-compatibility.json`
记录每道菜是否可无损表示。第一阶段整合后的后端支持封闭食材选择组，共有 53 道草稿
可用于技术联调；35 道来源或标注问题、8 道缺少公开菜名、4 道工具选择组被明确阻断。
这些记录均未完成课程人工审核，不能进入默认严格数据。

## 字段与边界

- `schema_version` 固定为 `2.0`；来源固定到提交 SHA 和规范化换行后的 UTF-8 内容 SHA-256。
- `requirement`: `required / optional / one_of / unknown`；与 `review_state` 独立。
- `review_state`: `pending / confirmed`。未完成课程审核的记录仍为 `pending`。
- 每个食材使用关系包含标准 `id`、稳定 `use_id`、来源称呼 `surface`、原文行号及逐字引文。
- `quantity_raw` 保存原文用量行；`quantities` 保存来源绑定的逐条观察：
  `exact`（数值与原单位）、`range`（上下限）、`adjustable`（基础量与调整量）、
  `formula`（原公式，不求值）、`qualitative`（适量等）、`unparsed`（保留上下文）。
  `scope=combined` 的数值属于 `member_ids` 的组合总量，不能分配给每个成员。
  `scope=context` 禁止填写数值，避免把配料总量、商品规格或其他食材数量错误归属。
  多条观察可能是不同步骤、不同章节或同一物品的个数/重量，禁止直接相加。
- `forms` 保存有逐字来源的加工形态；没有证据时为空，不默认填“原粒”。
  姜片、葱花等采购名称与形态分开；油种、葱种、带盐/无盐等差异保留。
- `difficulty` 为来源星级，无法确定为 null。新增字段参与标注摘要，旧审批会失效。
- 工具在独立 `tools` 数组；水是 `household_resource`，保留为图节点但不计补购。
- `choice_groups` 保存候选使用关系的 ID、`min_select`、`max_select`、`is_open` 和证据。
  同一食材可出现在不同组；用 MultiDiGraph 避免普通 DiGraph 覆盖关系。
- 开放选择、依赖可选步骤的材料、原文矛盾写入 `issues`，保守阻止严格推荐。
- 备选做法未完全展开时，在 `issues` 中说明；不能将所有备选食材并入必需集合。
- 只做保守同义归一化；鱼种、油种、糖种、带盐/无盐、完整/加工形态保留差异。
- 分类是项目检索本体，不是营养学或生物学权威分类。成分仅记录原文明确披露的关系，
  不能从产品名称猜配料，也不能据此作食物过敏安全保证。

## 图模式

节点：`Recipe`、`Ingredient`、`IngredientCategory`、`Tool`、`ChoiceGroup`。

关系：`REQUIRES`、`OPTIONALLY_USES`、`ONE_OF`、`UNRESOLVED_USE`、`REQUIRES_TOOL`、
`OPTIONAL_TOOL`、`TOOL_OPTION`、`HAS_CHOICE_GROUP`、`IS_A`、`SUBCLASS_OF`、`HAS_COMPONENT`。
选择成员边以 `group_id` 对应选择组节点，组的成员 ID 必须与边一致。
层级和成分边必须无环；关系保留审核状态、依据和来源。

## 审核与发布

`data-v2 build` 校验源提交、全部哈希、逐字引文、选择组引用、唯一 ID 与本体后生成完整草稿包。
`strict_eligible` 只有在该菜的人工确认、整份本体人工确认、规范冻结均有效，且没有未决问题时才为真。
人工确认通过独立 `approvals.json` 提供：姓名、日期、源哈希及完整标注摘要，修改标注后确认失效。
确认文件必须由实际审核人填写；本仓库不会预填他人的签名。
前 20 道仍需两名成员独立标注、组长裁决；仅验证 JSON 不等于完成此流程。
随后菜谱需交叉复核不少于10%。`team-review.blank.json` 提供空白团队记录，
每条 cross_reviews 至少填写 recipe_id、primary_annotator、reviewer、reviewed_on、
source_hash、annotation_hash 和 outcome（通过时为 approved）。不能自我交叉复核。

构建产物包含质量统计、机器可读 schema、可离线打开的原文核对页面、NetworkX 图、Neo4j JSON 导入包。
图导入按数据集、源提交和接口版本隔离，在单次事务内替换同一作用域；重复导入结果应完全一致。
原始数据和生成图谱仍不提交 Git；只提交代码、轻量标注与验证记录。

## 与新前端对接

本次核对的项目基线是 `ed3cf27`，其中 web/src/api/types.ts 的 RecipeDetail 包含
id、name、source_url、category、difficulty、ingredients 和 steps。
`cookkg.data_interface.recipe_detail` 提供严格数据适配；当前 API 通过 `data_backend` 投影把可兼容草稿
映射为同一 `RecipeDetail` 形状，并在健康检查中分别报告审核数量和兼容可用数量。
详情可保留水来解释做法，购物逻辑必须依据 resource_kind 排除家庭资源。

本体中的篇内别名以 scope 限定来源菜谱，不能直接作为全局用户输入词典。
例如一篇菜谱把“小葱”简称“葱”，不表示其他菜谱的所有葱都应该合并到小葱。
