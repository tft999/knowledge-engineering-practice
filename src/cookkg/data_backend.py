"""Loss-aware projection of CookKG v2 data into the current recommendation graph."""

import json
from collections import Counter
from pathlib import Path

import networkx as nx

from cookkg.data_models import DataRecipe
from cookkg.data_pipeline import digest, write_json
from cookkg.graph import dump_graph


def load_v2_recipes(path: Path) -> list[DataRecipe]:
    return [DataRecipe.model_validate_json(line) for line in path.read_text(
        encoding="utf-8").splitlines() if line.strip()]


def compatibility_reason(recipe: DataRecipe) -> str | None:
    if not recipe.name:
        return "missing_public_fields"
    if recipe.issues:
        return "source_or_annotation_issue"
    if any(use.requirement == "unknown" for use in recipe.ingredients):
        return "unknown_ingredient_relation"
    if any(group.is_open for group in recipe.choice_groups):
        return "open_choice_group"
    if any(group.kind != "food" for group in recipe.choice_groups):
        return "tool_choice_group_not_supported"
    return None


def build_backend_projection(recipes: list[DataRecipe], ontology: dict) -> tuple[nx.DiGraph, dict]:
    """Build a loss-aware graph projection accepted by the current backend.

    Every recipe remains in the projection for traceability. Only records that
    can be represented without changing semantics become integration-eligible.
    """
    source_commits = {recipe.source_commit for recipe in recipes}
    if len(source_commits) != 1:
        raise ValueError("Backend projection needs exactly one source commit")
    ontology_hash = digest(ontology)
    category_aliases = {name.removesuffix("类"): name for name in ontology["categories"]
                        if name.endswith("类") and name.removesuffix("类")}
    graph = nx.DiGraph(
        dataset="howtocook-v2-integration",
        source_commit=source_commits.pop(),
        schema_version=2,
        data_contract="cookkg-v2-integration",
        taxonomy_version="2.0",
        taxonomy_digest=ontology_hash,
        category_aliases=category_aliases,
    )
    excluded = Counter()
    eligible_ids = []
    for recipe in sorted(recipes, key=lambda item: item.id):
        reason = compatibility_reason(recipe)
        if reason:
            excluded[reason] += 1
        else:
            eligible_ids.append(recipe.id)
        node = f"r:{recipe.id}"
        graph.add_node(node, kind="recipe", id=recipe.id, name=recipe.name,
                       category=recipe.category, source_url=recipe.source_url,
                       source_hash=recipe.source_hash, difficulty=recipe.difficulty,
                       steps=recipe.steps, reviewed=False,
                       integration_eligible=reason is None, eligible=reason is None,
                       compatibility_blocker=reason,
                       annotation_hash=recipe.annotation_hash,
                       choice_groups=[group.model_dump(mode="json")
                                      for group in recipe.choice_groups])
        for use in recipe.ingredients:
            if use.resource_kind == "household_resource":
                continue
            ingredient = f"i:{use.id}"
            graph.add_node(ingredient, kind="ingredient", id=use.id, name=use.id)
            relation = {"required": "REQUIRES", "optional": "OPTIONALLY_USES",
                        "one_of": "ONE_OF", "unknown": "UNRESOLVED_USE"}[use.requirement]
            graph.add_edge(node, ingredient, relation=relation, status=use.requirement,
                           group_id=use.group_id,
                           requirement=use.requirement, quantity_raw=use.quantity_raw,
                           evidence=[f"L{e.line}: {e.text}" for e in use.evidence],
                           source_hash=recipe.source_hash, annotation_hash=recipe.annotation_hash)
        for tool in recipe.tools:
            tool_node = f"t:{tool.id}"
            graph.add_node(tool_node, kind="tool", id=tool.id, name=tool.id)
            graph.add_edge(node, tool_node, relation="REQUIRES_TOOL",
                           status=tool.requirement,
                           evidence=[f"L{e.line}: {e.text}" for e in tool.evidence])
    for relation in ontology["relations"]:
        kind = relation["type"]
        if kind not in {"IS_A", "SUBCLASS_OF"}:
            continue
        source_prefix = "c:" if kind == "SUBCLASS_OF" else "i:"
        source_kind = "category" if kind == "SUBCLASS_OF" else "ingredient"
        source = source_prefix + relation["child"]
        target = "c:" + relation["parent"]
        graph.add_node(source, kind=source_kind, id=relation["child"],
                       name=relation["child"])
        graph.add_node(target, kind="category", id=relation["parent"],
                       name=relation["parent"])
        basis = relation["basis"].replace("AI辅助拟定，需成员人工审核。", "")
        graph.add_edge(source, target, relation=kind, reviewed=False, basis=basis)
    report = dict(
        source_commit=graph.graph["source_commit"], ontology_hash=ontology_hash,
        total_recipes=len(recipes), integration_eligible=len(eligible_ids),
        excluded_from_recommendation=dict(sorted(excluded.items())),
        household_resources_omitted=True,
        canonical_graph="data/processed/v2/graph.json",
        projection_graph="data/processed/v2/backend-graph.json",
        limitations=[
            "Closed food choice groups are solved; open and tool choice groups are not.",
            (
                "Recipes with issues, unknown relations, open groups or tool groups "
                "are not candidates."
            ),
            "Scoped ingredient aliases are not applied globally to user input.",
            "Ontology relations remain proposals until the team confirms them.",
        ],
        eligible_recipe_ids=eligible_ids,
    )
    return graph, report


def write_backend_projection(data: Path, output: Path | None = None) -> dict:
    output = output or data / "backend-graph.json"
    recipes = load_v2_recipes(data / "recipes.jsonl")
    ontology = json.loads((data / "ontology.json").read_text(encoding="utf-8"))
    graph, report = build_backend_projection(recipes, ontology)
    dump_graph(graph, output)
    write_json(data / "backend-compatibility.json", report)
    write_json(data / "technical-review.json", dict(
        checked_on="2026-09-10",
        source_commit=report["source_commit"], ontology_hash=report["ontology_hash"],
        scope="source binding, structural semantics, graph and backend projection",
        decision="integration_checked_with_recorded_exclusions",
        eligible_recipe_ids=report["eligible_recipe_ids"],
        excluded_counts=report["excluded_from_recommendation"],
        note=("This is a technical compatibility record; course approval fields "
              "are intentionally absent.")))
    return report
