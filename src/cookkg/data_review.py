"""Offline source review pages. No approvals are preselected or fabricated."""

import html
import json
from pathlib import Path


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def compare_annotations(first: dict, second: dict) -> dict:
    """Compare two source-identical label sets; disagreement is not an accuracy score."""
    from cookkg.data_models import Annotation

    if first["source_commit"] != second["source_commit"]:
        raise ValueError("The two annotations use different source commits")
    left = [Annotation.model_validate(a) for a in first["annotations"]]
    right = [Annotation.model_validate(a) for a in second["annotations"]]
    if len({a.id for a in left}) != len(left) or len({a.id for a in right}) != len(right):
        raise ValueError("Duplicate recipe IDs in comparison")
    right_by_id = {a.id: a for a in right}
    if {a.id for a in left} != set(right_by_id):
        raise ValueError("Both reviewers must annotate the same recipes")

    def signature(annotation):
        uses = {u.use_id: u for u in [*annotation.ingredients, *annotation.tools]}
        groups = {g.id: (g.kind, tuple(sorted(uses[i].id for i in g.member_ids)),
                         g.min_select, g.max_select, g.is_open) for g in annotation.choice_groups}
        return dict(ingredients=sorted((u.id, u.requirement, u.resource_kind,
                                        str(groups.get(u.group_id)), tuple(u.quantity_raw),
                                        json.dumps([q.model_dump(mode="json")
                                                    for q in u.quantities],
                                                   ensure_ascii=False, sort_keys=True),
                                        json.dumps([f.model_dump(mode="json") for f in u.forms],
                                                   ensure_ascii=False, sort_keys=True))
                                       for u in annotation.ingredients),
                    tools=sorted((u.id, u.requirement, str(groups.get(u.group_id)))
                                 for u in annotation.tools),
                    issues=sorted(i.detail for i in annotation.issues))

    rows = []
    for a in sorted(left, key=lambda a: a.id):
        b = right_by_id[a.id]
        if a.source_hash != b.source_hash:
            raise ValueError(f"Source hash differs: {a.id}")
        sa, sb = signature(a), signature(b)
        different = [key for key in sa if sa[key] != sb[key]]
        rows.append(dict(recipe_id=a.id, differing_fields=different,
                         first=sa if different else None, second=sb if different else None))
    distinct_humans = bool(left) and all(
        a.method == b.method == "human" and a.author.strip() and b.author.strip()
        and a.author != b.author for a in left for b in [right_by_id[a.id]])
    return dict(recipe_count=len(rows),
                same_recipe_count=sum(not r["differing_fields"] for r in rows),
                declared_distinct_human_authors=distinct_humans,
                note="Authorship is self-declared. This comparison neither proves independence "
                     "nor substitutes for team adjudication; agreement is not accuracy.",
                recipes=rows)


STYLE = """
body{font-family:system-ui,'Microsoft YaHei',sans-serif;background:#f4f5f0;color:#19322d;
margin:0;line-height:1.6}header{background:#143f36;color:white;padding:28px 5%}
main{max-width:1450px;margin:auto;padding:24px}h1{margin:0}input,button{font:inherit;
padding:8px;margin:4px}button{background:#17664f;color:white;border:0;border-radius:6px}
.toolbar{position:sticky;top:0;background:#f4f5f0;padding:10px;z-index:1;
border-bottom:1px solid #ccc}
article{background:white;padding:22px;margin:22px 0;border-radius:10px;border:1px solid #d3dcd5}
.columns{display:grid;grid-template-columns:1fr 1fr;gap:24px}.source{max-height:720px;overflow:auto;
font-family:Consolas,monospace;background:#f8faf8;padding:14px;white-space:pre-wrap;font-size:13px}
.line:target{background:#fff0a0}.line{display:block}.num{color:#687970;display:inline-block;min-width:32px}
table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;padding:7px;
border-bottom:1px solid #dde3df;vertical-align:top}.issue{background:#fff4d6;padding:10px}
.small{font-size:13px;color:#597269}.badge{padding:3px 8px;background:#e9f0e8;border-radius:20px}
a{color:#086850}header a{color:#c1efd9}textarea{width:100%;min-height:250px}
@media(max-width:900px){.columns{grid-template-columns:1fr}.toolbar{position:static}}
"""


def quantity_cell(use: dict) -> str:
    amounts = "<br>".join(f'{esc(q["raw"])} [{esc(q["kind"])}; {esc(q["scope"])}]'
                          for q in use["quantities"])
    forms = esc("、".join(f["form"] for f in use["forms"]) or "未明确记录")
    return f'<td>{amounts}<br><span class="small">形态：{forms}</span></td>'


def write_review_pack(output: Path, recipes: list[dict], sources: dict[str, str],
                      report: dict, pilot_ids: set[str]) -> None:
    articles = []
    for index, recipe in enumerate(recipes):
        refs = lambda evidence: " ".join(  # noqa: E731
            f'<a href="#s{index}l{e["line"]}">L{e["line"]}</a>' for e in evidence)
        rows = "".join(
            f'<tr><td>{esc(u["id"])}<br><span class="small">{esc(u["surface"])}</span></td>'
            f'<td>{esc(u["requirement"])}<br>{esc(u["group_id"] or "")}</td>'
            f'{quantity_cell(u)}'
            f'<td>{refs(u["evidence"])}</td></tr>' for u in recipe["ingredients"])
        tools = "、".join(f'{esc(u["id"])} ({esc(u["requirement"])}) '
                         f'{refs(u["evidence"])}' for u in recipe["tools"])
        issues = "".join(f'<p class="issue">{esc(i["detail"])} {refs(i["evidence"])}</p>'
                         for i in recipe["issues"])
        groups = "".join(f'<li>{esc(g["id"])}: 选 {g["min_select"]}–{g["max_select"]} 项；'
                         f'{"开放候选" if g["is_open"] else "有限候选"}</li>'
                         for g in recipe["choice_groups"])
        source = "".join(f'<span class="line" id="s{index}l{n}"><span class="num">{n}</span>'
                         f'{esc(line)}</span>'
                         for n, line in enumerate(sources[recipe["id"]].splitlines(), 1))
        notes = "".join(f'<li>{esc(note)}</li>' for note in recipe["notes"])
        articles.append(f'''<article data-name="{esc(recipe['name'])}" data-issues="{bool(issues)}">
<h2>{index + 1:03d} · {esc(recipe['name'])} <span class="badge">AI 草稿</span></h2>
<p class="small">{esc(recipe['id'])} · <a href="{esc(recipe['source_url'])}">固定版本原文</a></p>
<div class="columns"><section><table><thead><tr><th>标准名 / 原文称呼</th><th>需求 / 组</th>
<th>用量观察 / 形态</th><th>证据</th></tr></thead><tbody>{rows}</tbody></table>
<p><b>工具：</b>{tools}</p>
<ul>{groups}</ul>{issues}<ul>{notes}</ul>
<label><input type="checkbox" class="approve" data-index="{index}">
我已逐项核对这道菜的原文和标注</label></section><section class="source">{source}</section></div>
</article>''')
    approval_rows = [{key: r[key] for key in ("id", "source_hash", "annotation_hash")}
                     for r in recipes]
    data = json.dumps(approval_rows, ensure_ascii=False).replace("<", "\\u003c")
    page = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CookKG · 100道原文核对</title>
<style>{STYLE}</style><header><h1>CookKG · 数据核对工作台</h1>
<p>{len(recipes)} 道 AI 辅助标注 · {report['human_confirmed']} 道人工确认 ·
{report['recipes_with_issues']} 道待裁决问题 · 来源提交 {esc(report['source_commit'][:12])}</p>
<p>先读原文，再核对需求、选择组、工具和用量。引文与哈希校验不代表语义准确率。</p></header>
<main><p>本页仅导出你实际勾选的审核记录。未解决的问题仍阻止严格推荐。
需要改标注时修改 annotations_v2.json 后重建，再核对新版本。首次20道第二名标注员请打开
<a href="pilot-20-blind.html">独立标注原文包</a>，避免先看此页结论。</p>
<div class="toolbar"><input id="search" placeholder="搜索菜名" aria-label="搜索菜名">
<label><input type="checkbox" id="issues">只显示待裁决</label>
<input id="reviewer" placeholder="实际审核人姓名" aria-label="审核人">
<input id="date" type="date" aria-label="审核日期"><button id="save">导出已勾选审核</button>
<span id="status" role="status"></span></div>{''.join(articles)}</main>
<script>const records={data};
function filter(){{const q=document.querySelector('#search').value.toLowerCase();
document.querySelectorAll('article').forEach(a=>a.hidden=!a.dataset.name.toLowerCase().includes(q)||
(document.querySelector('#issues').checked&&a.dataset.issues!=='True'));}}
document.querySelector('#search').addEventListener('input',filter);
document.querySelector('#issues').addEventListener('change',filter);
document.querySelector('#save').addEventListener('click',()=>{{
const reviewer=document.querySelector('#reviewer').value.trim();
const date=document.querySelector('#date').value;
const chosen=[...document.querySelectorAll('.approve:checked')];
if(!reviewer||!date||!chosen.length){{document.querySelector('#status').textContent='请填写姓名、日期，并逐道核对勾选。';return;}}
const result={{standard_frozen:false,ontology_hash:null,ontology_reviewer:null,
ontology_reviewed_on:null,recipes:{{}}}};
chosen.forEach(el=>{{const r=records[Number(el.dataset.index)];result.recipes[r.id]={{reviewer,
reviewed_on:date,source_hash:r.source_hash,annotation_hash:r.annotation_hash}};}});
const blob=new Blob([JSON.stringify(result,null,2)],{{type:'application/json'}});
const url=URL.createObjectURL(blob);
const a=document.createElement('a');a.href=url;a.download='approvals.json';a.click();
setTimeout(()=>URL.revokeObjectURL(url),1000);
document.querySelector('#status').textContent=
`已导出 ${{chosen.length}} 道实际勾选记录；尚未冻结本体。`;
}});</script></html>'''
    (output / "review-100.html").write_text(page, encoding="utf-8")
    blind = []
    template = []
    for recipe in recipes:
        if recipe["id"] not in pilot_ids:
            continue
        blind.append(f'<article><h2>{esc(recipe["name"])}</h2><p>{esc(recipe["id"])}</p>'
                     f'<pre class="source">{esc(sources[recipe["id"]])}</pre></article>')
        template.append(dict(schema_version="2.0", id=recipe["id"],
                             source_hash=recipe["source_hash"], method="human", author="",
                             ingredients=[], tools=[], choice_groups=[], issues=[], notes=[]))
    (output / "pilot-20-blind.html").write_text(
        f'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>独立标注原文包</title>'
        f'<style>{STYLE}</style><header><h1>前20道 · 独立标注原文包</h1>'
        '<p>第二名成员先独立阅读和标注，完成后再比较第一份。这里不显示第一份结论。</p>'
        f'</header><main>{"".join(blind)}</main></html>', encoding="utf-8")
    (output / "pilot-20-independent.blank.json").write_text(
        json.dumps(dict(schema_version="2.0", source_commit=report["source_commit"],
                        selection="Independent human pilot annotation", pilot_ids=sorted(pilot_ids),
                        annotations=template), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
