"""Explain changes from the original parser, without treating AI labels as gold data."""

from collections import Counter

from cookkg.parser import parse_recipe


def parser_audit(recipes: list[dict], sources: dict[str, str], commit: str) -> dict:
    rows = []
    codes = Counter()
    for recipe in recipes:
        parsed = parse_recipe(sources[recipe["id"]], recipe["id"], commit)
        old = {u.name: u.status for u in parsed.recipe.ingredients}
        new = {u["id"]: u["requirement"] for u in recipe["ingredients"]}
        changed = [{"name": name, "parser_status": old[name], "draft_requirement": new[name]}
                   for name in sorted(old.keys() & new.keys()) if old[name] != new[name]]
        row = dict(recipe_id=recipe["id"], removed_or_normalized=sorted(old.keys() - new.keys()),
                   added_or_normalized=sorted(new.keys() - old.keys()),
                   changed_requirements=changed, parser_issues=parsed.issues)
        codes.update(issue.split(":", 1)[0] for issue in parsed.issues)
        rows.append(row)
    return dict(note="Differences from parser output, not precision/recall: draft is AI-assisted.",
                compared_recipes=len(rows), parser_issue_counts=dict(sorted(codes.items())),
                recipes_with_changes=sum(bool(r["removed_or_normalized"]
                    or r["added_or_normalized"] or r["changed_requirements"]) for r in rows),
                recipes=rows)
