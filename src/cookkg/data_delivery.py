"""Reproducible review queue, full-source audit and backend evaluation inputs."""

import math
import re
from collections import Counter
from pathlib import Path

from cookkg.data_pipeline import digest, source_text, write_json
from cookkg.parser import parse_recipe


def resolution_kind(detail: str) -> tuple[str, str]:
    if re.search(r"计算.*\d|6g|76g|明显可疑", detail):
        return "source_conflict", "保留两处原文数值；不能选一个数值冒充已裁决结果。"
    if any(word in detail for word in ("没有", "未出现在", "缺实际", "未说明", "缺实际")):
        return "missing_or_conflicting_step", "核对所有章节；证据不足则保留unknown，排除严格推荐。"
    if any(word in detail for word in ("品牌", "SKU", "配料表", "成分")):
        return "product_or_scope_unknown", "保留商品粒度，成分标为未披露；不得根据名称补写成分。"
    if any(word in detail for word in ("品种", "具体指", "具体食材", "地域")):
        return "identity_unknown", "保留原称呼，不能擅自合并具体食材；需要团队明确采购实体。"
    return "branch_or_optional_scope", "选定原文支持的做法并记录依据，或保留问题及严格排除。"


def source_audit(raw: Path, commit: str, reviewed_ids: set[str]) -> dict:
    rows = []
    for path in sorted((raw / "dishes").rglob("*.md")):
        recipe_id = path.relative_to(raw).as_posix()
        parsed = parse_recipe(source_text(raw, recipe_id), recipe_id, commit)
        rows.append(dict(id=recipe_id, source_hash=parsed.recipe.source_hash,
                         skipped=parsed.skipped, parser_issues=parsed.issues,
                         in_curated_batch=recipe_id in reviewed_ids))
    return dict(source_commit=commit, scanned=len(rows),
                non_template=sum(not r["skipped"] for r in rows),
                curated=sum(r["in_curated_batch"] for r in rows), recipes=rows,
                note="Full fixed-source scan. Parser output is preannotation, not human review.")


def write_delivery_pack(output: Path, recipes: list[dict], ontology: dict,
                        raw: Path, report: dict) -> None:
    queue, evaluation = [], []
    relations = {r["child"]: r["parent"] for r in ontology["relations"]
                 if r["type"] == "IS_A"}
    for index, recipe in enumerate(recipes):
        for issue in recipe["issues"]:
            kind, action = resolution_kind(issue["detail"])
            queue.append(dict(id=digest([recipe["id"], issue])[:16], recipe_id=recipe["id"],
                              source_hash=recipe["source_hash"],
                              annotation_hash=recipe["annotation_hash"],
                              issue=issue, category=kind, proposed_action=action,
                              disposition="excluded_from_strict", decision=None,
                              decided_by=None, decided_on=None))
        # A reproducible spread of exact/category exclusions and pantry/stock cases.
        food = [u for u in recipe["ingredients"] if u["resource_kind"] == "food"]
        target = food[index % len(food)] if food else None
        exclude = ([relations.get(target["id"], target["id"])] if index % 2
                   else [target["id"]]) if target else []
        have = [u["id"] for u in food[:index % 4]]
        evaluation.append(dict(id=f"data-eval-{index + 1:03d}", recipe_id=recipe["id"],
            source_hash=recipe["source_hash"], annotation_hash=recipe["annotation_hash"],
            request=dict(have=have, pantry=["盐", "食用油"] if index % 3 == 0 else [],
                         exclude=exclude, count=index % 3 + 1, max_buy=index % 6, limit=5),
            question="全局菜单应满足这些输入条件；重点检查所列菜谱的处理与来源解释。",
            expected=None, human_reviewed=False,
            draft_reference=dict(ingredient_uses=recipe["ingredients"],
                                 choice_groups=recipe["choice_groups"])))
    write_json(output / "source-audit.json", source_audit(
        raw, report["source_commit"], {r["id"] for r in recipes}))
    write_json(output / "issue-resolution-queue.json", dict(
        source_commit=report["source_commit"], recipes_with_issues=report["recipes_with_issues"],
        issue_count=len(queue), categories=dict(Counter(r["category"] for r in queue)),
        note="Suggested handling, not human adjudications. No decision or signature is prefilled.",
        issues=queue))
    write_json(output / "evaluation-100-draft.json", dict(
        source_commit=report["source_commit"], seed=0,
        generation="Deterministic sorted recipe order; no random sampling.",
        ontology_hash=report["ontology_hash"], graph_hash=report["graph_hash"],
        status="Draft inputs for team evaluation; expected outputs need independent human review.",
        cases=evaluation))
    write_json(output / "team-review.blank.json", dict(
        standard_version=None, standard_approved_by=[], interface_approved_by=[],
        pilot_adjudicator=None, pilot_adjudicated_on=None, pilot_comparison=None,
        pilot_resolutions=[], cross_reviews=[], integration_evidence=None,
        report_and_rehearsal_evidence=None))


def acceptance_report(report: dict, recipes: list[dict], team: dict | None = None) -> dict:
    """Report actual completion, including requirements that code cannot sign for people."""
    team = team or {}
    by_id = {r["id"]: r for r in recipes}
    valid_cross = set()
    for review in team.get("cross_reviews", []):
        r = by_id.get(review.get("recipe_id"))
        if (r and review.get("primary_annotator") and review.get("reviewer")
                and review["reviewer"] != review["primary_annotator"]
                and review.get("source_hash") == r["source_hash"]
                and review.get("annotation_hash") == r["annotation_hash"]
                and review.get("reviewed_on") and review.get("outcome") == "approved"):
            valid_cross.add(r["id"])
    comparison = team.get("pilot_comparison") or {}
    pilot = bool(comparison.get("recipe_count") == 20
                 and comparison.get("declared_distinct_human_authors")
                 and team.get("pilot_adjudicator") and team.get("pilot_adjudicated_on")
                 and (comparison.get("same_recipe_count") == 20
                      or len(team.get("pilot_resolutions", [])) >=
                      20 - comparison.get("same_recipe_count", 0)))
    checks = dict(
        hundred_source_bound_drafts=report["source_hashes_validated"] >= 100,
        hundred_human_reviewed=report["human_confirmed"] >= 100,
        strict_dataset_available=report["strict_eligible"] > 0,
        strict_data_has_no_pending=all(
            r["review_state"] == "confirmed" and not r["issues"]
            and all(u["review_state"] == "confirmed" and u["requirement"] != "unknown"
                    for u in r["ingredients"])
            for r in recipes if r["strict_eligible"]),
        first_twenty_independent_and_adjudicated=pilot,
        cross_review_ten_percent=len(valid_cross) >= math.ceil(len(recipes) * 0.1),
        standard_agreed=bool(team.get("standard_version") == "1.0"
                             and len(set(team.get("standard_approved_by", [])) - {""}) >= 3),
        interface_agreed=len(set(team.get("interface_approved_by", [])) - {""}) >= 3,
        integrated_with_backend=bool(team.get("integration_evidence")),
        report_and_rehearsal=bool(team.get("report_and_rehearsal_evidence")),
    )
    return dict(complete=all(checks.values()), checks=checks,
                incomplete=[name for name, ok in checks.items() if not ok],
                valid_cross_reviews=len(valid_cross),
                note="Team review records are self-declared evidence. This is not proof of "
                     "independent human work or a semantic accuracy measurement.")
