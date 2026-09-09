# Zouyilin06 — data and knowledge graph handoff

Your part turns recipe text into structured data that the menu-planning algorithm can use.
For example, the graph records that 小炒肉 requires 小米椒, and 小米椒 belongs to 辣椒类.
Your teammate can use that path when a user excludes chili. Your module supplies the facts and evidence;
the algorithm teammate decides which menus satisfy the user's constraints.

## What was built

| Deliverable | Current result |
|---|---|
| Source recipes | 100 real recipes from the fixed HowToCook commit, not invented recipes |
| Annotations | 100 AI-assisted drafts with file hashes, exact line references and quotations |
| Ingredients | 262 distinct names; conservative normalization and 45 scoped alias proposals |
| Quantities/forms | 591 source-bound quantity observations and 75 preparation-form observations |
| Ontology | 46 categories, 259 ingredient-category links, 45 category-parent links |
| Components | 3 explicitly disclosed links for one canned-fish product; a partial ingredient list |
| Choices | 42 food/tool choice groups; alternatives are not all mandatory |
| Graph | 539 nodes and 1,292 relationships, exported for NetworkX and Neo4j |
| Quality | 100 source hashes validated; 39 recipes need adjudication |
| Full source audit | 370 Markdown files scanned; 369 non-template recipes; 100 curated drafts |
| Evaluation | 100 deterministic source-bound inputs; human expected answers remain blank |
| Human review | **0 of these 100 drafts have a recorded human sign-off** |
| Recommendation API projection | **46 recipes eligible; 54 excluded with recorded reasons** |

The first 20 recipes came from the earlier review queue. The remaining 80 were selected from short
recipes across eight categories so that the work covered more than breakfast and desserts.
This is a convenience sample, not a random evaluation benchmark. The source is
[HowToCook at commit 2b19c9e9ee926fd925a68207a57582a338813f9c](https://github.com/Anduin2017/HowToCook/tree/2b19c9e9ee926fd925a68207a57582a338813f9c).

## Open these files first

Run `cookkg data-v2 build`, then open `data/processed/v2/review-100.html` in your browser.
It places each annotation beside its original recipe. Clicking a line reference jumps to the evidence.
Search for **空气炸锅面包片** for a simple first example: bread is the ingredient, and the air fryer is a tool.

The delivered folder also contains actual Neo4j screenshots: `neo4j-hierarchy.png` and
`neo4j-choices.png`. The first illustrates the chili hierarchy; the second shows that cooking wine,
rum and beer are alternatives in 芥末黄油罗氏虾. The screenshot does not imply human approval of the data.

`recipes.jsonl` is the main handoff to the algorithm teammate. Each line is one recipe.
`networkx.node-link.json` is the standard NetworkX node-link format. `graph.json` and
`neo4j-import.json` contain the same canonical graph with full source properties.

`issue-resolution-queue.json` separates 44 issues into source conflicts, missing steps,
identity/product uncertainty, and optional/branch scope. Proposed handling is included, while every
human decision, name and date remains blank. `evaluation-100-draft.json` provides the required 100
evaluation inputs without inventing expected answers.

## What still requires your team

1. **Human review of the 100 recipes.** Check the proposed labels against the source. Do not tick a
   recipe simply because its hash passed. The 61 recipes without recorded issues are still AI drafts.
2. **Resolve the 39 flagged recipes.** Some contain inconsistent quantities, missing steps, unclear
   optional scope or alternate cooking methods. For example, 芋泥雪媚娘 lists 26g sugar in one section
   but uses 18g + 50g + 8g in the steps. This conflict is preserved, not silently corrected.
3. **Independent first-20 review and team adjudication.** The other annotator should use
   `pilot-20-blind.html` and `pilot-20-independent.blank.json` before reading the first annotator's
   conclusions. The leader resolves disagreements and records the agreed standard.
4. **Confirm the ontology and interface.** All new ontology/alias proposals are pending. 有盐牛油 and
   红萝卜 remain unclassified because the names need clarification. The team must agree on v2 before
   the backend switches to it.

These are the remaining course acceptance requirements, not completed activities. I cannot supply
another student's independent judgment or sign the team's agreement on their behalf.

## How to record real review

The review page starts with every checkbox unchecked and the reviewer/date blank. After actually
checking a recipe, tick that recipe and enter the real reviewer name and date. Export `approvals.json`.
The export includes only selected recipes and binds them to both source and annotation hashes.

If a label needs correction, edit the corresponding record in `src/cookkg/resources/annotations_v2.json`,
then rebuild and review again. Keep exact source quotations and source hashes. Edit ontology proposals
in `src/cookkg/resources/ontology_v2.json`. Changing either invalidates earlier hash-bound approval.

Two completed annotation bundles can be compared with:

```powershell
.venv-data/Scripts/cookkg data-v2 compare --first reviewer-a.json --second reviewer-b.json
```

The comparison reports disagreements and self-declared authorship. It does not prove independence
or measure accuracy. Validate edited bundles against the actual source with `data-v2 build --annotations`.
Once the leader has genuinely frozen the standard and checked the ontology, fill the ontology reviewer,
date and `ontology_hash` (from `quality-report.json`) in the approval file and set `standard_frozen` true.

```powershell
.venv-data/Scripts/cookkg data-v2 build --approvals approvals.json
```

A recipe only becomes `strict_eligible` when its human approval is current, the standard and ontology
are confirmed, it has no unresolved issue or open choice, and its food ingredients are classified.
Approval alone does not erase a recorded conflict. Unresolved issues must be adjudicated and the
annotation updated with a written rationale before final approval.

## Reproduce the technical result

Use Python 3.13 or newer. On a new machine create a virtual environment, install `.[dev]`, and run
`cookkg fetch` to download the fixed source. On this computer `.venv-data` is already configured.
From the repository root:

```powershell
.venv-data/Scripts/cookkg data-v2 build
.venv-data/Scripts/python -m pytest -q
.venv-data/Scripts/ruff check src tests
.venv-data/Scripts/python scripts/verify_data_delivery.py
```

For a running Neo4j instance, set the four `NEO4J_*` variables using your own connection configuration:

```powershell
.venv-data/Scripts/cookkg data-v2 neo4j-import
.venv-data/Scripts/cookkg data-v2 neo4j-import
.venv-data/Scripts/cookkg data-v2 neo4j-verify
.venv-data/Scripts/cookkg data-v2 neo4j-queries
```

Live tests use `NEO4J_TEST_URI`, `NEO4J_TEST_USERNAME`, `NEO4J_TEST_PASSWORD` and optionally
`NEO4J_TEST_DATABASE`; without them the live tests are explicitly skipped.
This work was tested on actual Neo4j Community 5.26.30 using a temporary instance bound to localhost.

```python
import json
import networkx as nx

with open("data/processed/v2/networkx.node-link.json", encoding="utf-8") as source:
    graph = nx.node_link_graph(
        json.load(source), edges="edges", name="node_id", key="edge_key"
    )
assert graph.is_multigraph()
```

## Tell the algorithm teammate

The current project base is `ed3cf27`, which includes the recommendation API and menu-planner UI. Read
`docs/data-contract-v2.md`, `backend-compatibility.json`, and the exported `recipe.schema.json`.
The canonical graph keeps all v2 semantics; the API consumes `backend-graph.json`, where
`integration_eligible` is an explicit compatibility gate. Keep tools out of groceries, exclude household
water from shopping, and do not silently treat unknown relations or choice groups as ordinary required ingredients.

`cookkg.data_interface.recipe_detail` maps a strict recipe into the new UI `RecipeDetail` shape. The compatibility
projection and API integration are implemented in `cookkg.data_backend`; recommendation ranking remains the
algorithm teammate's responsibility.

No message or code has been sent to teammates or pushed to GitHub. The work is local and uncommitted
in the integrated checkout `knowledge-engineering-practice-integrated`.

## Your short presentation explanation

“我负责把 HowToCook 的 Markdown 菜谱整理为有来源证据的结构化数据，并构建食材知识图谱。
数据模型区分必需、可选、选择组、工具和家庭资源；审核状态单独保存。每条标注绑定原文哈希和
行号，避免旧审核覆盖新文本。图谱包含菜谱、食材、类别、工具和选择组，NetworkX 与 Neo4j
由同一份标准数据生成。用量分为精确量、范围、公式、定性描述和未解析上下文；联合总量不会
错误分到每个食材。我们通过重复构建、重复导入、完整属性回读和代表性查询验证数据一致性。
目前交付的是100道AI辅助校读草稿；最终人工审核与双人标注裁决仍需实际完成。”

Accuracy has not been measured against an independent human gold set. Passing code, hash and graph
consistency checks verifies the pipeline; it does not establish a percentage of correct food labels.
