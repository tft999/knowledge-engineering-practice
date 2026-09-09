"""Validate source-bound annotations and export the version 2 knowledge graph."""

import hashlib
import json
from collections import Counter
from importlib.resources import files
from pathlib import Path
from urllib.parse import quote

import networkx as nx

from cookkg.data_models import Annotation, Approvals, DataRecipe, validate_recipe_id
from cookkg.pipeline import source_config
from cookkg.review import _verify_source


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def resource_json(name: str) -> dict:
    return json.loads(files("cookkg").joinpath(f"resources/{name}").read_text(encoding="utf-8"))


def source_text(raw: Path, recipe_id: str) -> str:
    validate_recipe_id(recipe_id)
    path = (raw / recipe_id).resolve()
    if not path.is_relative_to(raw.resolve()):
        raise ValueError(f"Source escapes root: {recipe_id}")
    return path.read_text(encoding="utf-8")


def validate_evidence(annotation: Annotation, text: str) -> None:
    if hashlib.sha256(text.encode("utf-8")).hexdigest() != annotation.source_hash:
        raise ValueError(f"Stale source hash: {annotation.id}")
    lines = text.splitlines()
    objects = [*annotation.ingredients, *annotation.tools,
               *annotation.choice_groups, *annotation.issues]
    for obj in objects:
        for evidence in obj.evidence:
            if evidence.line > len(lines) or lines[evidence.line - 1] != evidence.text:
                raise ValueError(f"Evidence mismatch: {annotation.id}:{evidence.line}")
    for use in annotation.ingredients:
        if not any(use.surface in e.text for e in use.evidence):
            raise ValueError(f"Surface absent from evidence: {annotation.id}/{use.id}")
        if any(q not in {e.text for e in use.evidence} for q in use.quantity_raw):
            raise ValueError(f"Quantity not grounded: {annotation.id}/{use.id}")
        known_evidence = {(e.line, e.text) for e in use.evidence}
        for observation in [*use.quantities, *use.forms]:
            e = observation.evidence
            if (e.line, e.text) not in known_evidence:
                raise ValueError(f"Observation evidence mismatch: {annotation.id}/{use.id}")
        for quantity in use.quantities:
            if quantity.evidence.text not in use.quantity_raw:
                raise ValueError(f"Structured quantity lacks raw quantity: {annotation.id}")
            if quantity.scope == "combined" and not set(quantity.member_ids) <= {
                u.id for u in annotation.ingredients
            }:
                raise ValueError("Combined quantity references unknown ingredients")


def validate_ontology(ontology: dict, ingredient_ids: set[str], raw: Path | None = None) -> None:
    if ontology.get("schema_version") != "2.0":
        raise ValueError("Unsupported ontology version")
    categories = ontology["categories"]
    if len(set(categories)) != len(categories):
        raise ValueError("Duplicate category")
    known = set(categories)
    nodes = set(ontology["ingredients"])
    if not ingredient_ids <= nodes:
        raise ValueError(f"Unregistered ingredients: {sorted(ingredient_ids - nodes)}")
    seen = set()
    graphs = {kind: nx.DiGraph() for kind in ("IS_A", "SUBCLASS_OF", "HAS_COMPONENT")}
    for relation in ontology["relations"]:
        kind, child, parent = relation["type"], relation["child"], relation["parent"]
        if kind not in graphs:
            raise ValueError(f"Unsupported ontology relation: {kind}")
        key = (kind, child, parent)
        if key in seen or child == parent:
            raise ValueError("Duplicate or self ontology relation")
        seen.add(key)
        expected_child = known if kind == "SUBCLASS_OF" else nodes
        expected_parent = nodes if kind == "HAS_COMPONENT" else known
        if child not in expected_child or parent not in expected_parent:
            raise ValueError(f"Dangling ontology relation: {key}")
        if relation.get("review_state") not in {"pending", "confirmed"}:
            raise ValueError("Ontology review state required")
        if not relation.get("basis"):
            raise ValueError("Ontology basis required")
        if kind == "HAS_COMPONENT":
            if not relation.get("evidence") or not relation.get("recipe_id"):
                raise ValueError("Components require recipe evidence")
            if raw is not None:
                text = source_text(raw, relation["recipe_id"])
                sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
                if sha != relation.get("source_hash"):
                    raise ValueError("Stale component source")
                lines = text.splitlines()
                for e in relation["evidence"]:
                    if not 1 <= e["line"] <= len(lines) or lines[e["line"] - 1] != e["text"]:
                        raise ValueError("Component evidence mismatch")
        graphs[kind].add_edge(child, parent)
    if any(not nx.is_directed_acyclic_graph(g) for g in graphs.values()):
        raise ValueError("Cyclic ontology")
    aliases = ontology["aliases"]
    seen_aliases = set()
    for alias in aliases:
        key = (alias["scope"], alias["alias"])
        if key in seen_aliases or alias["canonical"] not in nodes:
            raise ValueError("Ambiguous or dangling alias")
        if not alias.get("basis") or alias.get("review_state") not in {"pending", "confirmed"}:
            raise ValueError("Alias basis and review state required")
        if raw is not None:
            alias_text = source_text(raw, alias["scope"])
            alias_lines = alias_text.splitlines()
            evidence = alias.get("evidence", [])
            if not evidence or not any(alias["alias"] in e["text"] for e in evidence):
                raise ValueError("Alias needs source evidence containing its surface")
            for e in evidence:
                if (not 1 <= e["line"] <= len(alias_lines)
                        or alias_lines[e["line"] - 1] != e["text"]):
                    raise ValueError("Alias evidence mismatch")
        seen_aliases.add(key)


def build_graph(recipes: list[dict], ontology: dict, commit: str) -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph(schema_version="2.0", dataset="howtocook-v2", source_commit=commit)
    for category in sorted(ontology["categories"]):
        graph.add_node(f"c:{category}", kind="IngredientCategory", name=category)
    for name, attrs in sorted(ontology["ingredients"].items()):
        graph.add_node(f"i:{name}", kind="Ingredient", name=name, **attrs)
    for recipe in recipes:
        rid = f"r:{recipe['id']}"
        graph.add_node(rid, kind="Recipe", **{k: v for k, v in recipe.items()
                       if k not in {"ingredients", "tools", "choice_groups"}})
        for group in recipe["choice_groups"]:
            gid = f"g:{recipe['id']}:{group['id']}"
            attrs = {**group, "group_kind": group["kind"], "kind": "ChoiceGroup"}
            graph.add_node(gid, name=group["id"], **attrs)
            graph.add_edge(rid, gid, key=f"group:{group['id']}", type="HAS_CHOICE_GROUP")
        for use in recipe["ingredients"]:
            kind = {"required": "REQUIRES", "optional": "OPTIONALLY_USES",
                    "one_of": "ONE_OF", "unknown": "UNRESOLVED_USE"}[use["requirement"]]
            graph.add_edge(rid, f"i:{use['id']}", key=use["use_id"], type=kind, **use)
        for use in recipe["tools"]:
            tid = f"t:{use['id']}"
            graph.add_node(tid, kind="Tool", name=use["id"])
            kind = {"required": "REQUIRES_TOOL", "optional": "OPTIONAL_TOOL",
                    "one_of": "TOOL_OPTION"}[use["requirement"]]
            graph.add_edge(rid, tid, key=use["use_id"], type=kind, **use)
    for relation in ontology["relations"]:
        kind = relation["type"]
        left = "c:" if kind == "SUBCLASS_OF" else "i:"
        right = "i:" if kind == "HAS_COMPONENT" else "c:"
        graph.add_edge(left + relation["child"], right + relation["parent"], key=kind, **relation)
    return graph


def graph_payload(graph: nx.MultiDiGraph) -> dict:
    return dict(metadata=graph.graph,
                nodes=[dict(node_id=n, properties=a) for n, a in sorted(graph.nodes(data=True))],
                edges=[dict(source=u, target=v, key=k, properties=a)
                       for u, v, k, a in sorted(graph.edges(keys=True, data=True))])


def graph_from_payload(payload: dict) -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph(**payload["metadata"])
    for row in payload["nodes"]:
        graph.add_node(row["node_id"], **row["properties"])
    for row in payload["edges"]:
        if row["source"] not in graph or row["target"] not in graph:
            raise ValueError("Dangling graph endpoint")
        graph.add_edge(row["source"], row["target"], key=row["key"], **row["properties"])
    if len(graph) != len(payload["nodes"]) or graph.number_of_edges() != len(payload["edges"]):
        raise ValueError("Duplicate graph ID")
    return graph


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_v2(raw: Path, output: Path, annotations_path: Path | None = None,
             ontology_path: Path | None = None, approvals_path: Path | None = None) -> dict:
    config = source_config()
    commit = config["commit"]
    _verify_source(raw, commit)
    bundle = (json.loads(annotations_path.read_text(encoding="utf-8")) if annotations_path
              else resource_json("annotations_v2.json"))
    ontology = (json.loads(ontology_path.read_text(encoding="utf-8")) if ontology_path
                else resource_json("ontology_v2.json"))
    if bundle["source_commit"] != commit or bundle["schema_version"] != "2.0":
        raise ValueError("Annotation source/version mismatch")
    annotations = [Annotation.model_validate(a) for a in bundle["annotations"]]
    if len({a.id for a in annotations}) != len(annotations):
        raise ValueError("Duplicate recipe annotation")
    approvals = (Approvals.model_validate_json(approvals_path.read_text(encoding="utf-8"))
                 if approvals_path else Approvals())
    if set(approvals.recipes) - {a.id for a in annotations}:
        raise ValueError("Approval refers to an unknown recipe")
    validate_ontology(ontology, {u.id for a in annotations for u in a.ingredients}, raw)
    ontology_hash = digest(ontology)
    if approvals.ontology_hash and approvals.ontology_hash != ontology_hash:
        raise ValueError("Stale ontology approval")
    ontology_confirmed = bool(approvals.standard_frozen and approvals.ontology_hash)
    classified = {r["child"] for r in ontology["relations"] if r["type"] == "IS_A"}
    sources, recipes = {}, []
    for annotation in annotations:
        text = source_text(raw, annotation.id)
        validate_evidence(annotation, text)
        sources[annotation.id] = text
        payload = annotation.model_dump(mode="json")
        annotation_hash = digest(payload)
        approval = approvals.recipes.get(annotation.id)
        if approval and (approval.source_hash != annotation.source_hash
                         or approval.annotation_hash != annotation_hash):
            raise ValueError(f"Stale approval: {annotation.id}")
        confirmed = approval is not None
        recipe = dict(payload, annotation_hash=annotation_hash, source_commit=commit,
                      name=text.splitlines()[0].lstrip("# ").removesuffix("的做法"),
                      category=annotation.id.split("/")[1],
                      source_url=f"{config['homepage']}/blob/{commit}/{quote(annotation.id)}",
                      review_state="confirmed" if confirmed else "pending",
                      human_approval=approval.model_dump(mode="json") if approval else None)
        from cookkg.parser import parse_recipe

        recipe["difficulty"] = parse_recipe(text, annotation.id, commit).recipe.difficulty
        # Claims from the source remain original text, never inferred nutrition facts.
        recipe["steps"] = text.split("## 操作", 1)[-1].split("## 附加内容", 1)[0].strip()
        if confirmed:
            for use in [*recipe["ingredients"], *recipe["tools"]]:
                use["review_state"] = "confirmed"
        recipe["strict_eligible"] = bool(confirmed and ontology_confirmed
            and not annotation.issues and not any(g.is_open for g in annotation.choice_groups)
            and all(u.requirement != "unknown" for u in annotation.ingredients)
            and all(u.resource_kind == "household_resource" or u.id in classified
                    for u in annotation.ingredients))
        recipes.append(DataRecipe.model_validate(recipe).model_dump(mode="json"))
    recipes.sort(key=lambda r: r["id"])
    effective_ontology = json.loads(json.dumps(ontology))
    if ontology_confirmed:
        for relation in [*effective_ontology["relations"], *effective_ontology["aliases"]]:
            relation["review_state"] = "confirmed"
    graph = build_graph(recipes, effective_ontology, commit)
    payload = graph_payload(graph)
    from cookkg.data_audit import parser_audit

    audit = parser_audit(recipes, sources, commit)
    report = dict(schema_version="2.0", source_commit=commit, annotation_count=len(recipes),
                  selection=bundle["selection"], pilot_count=len(bundle["pilot_ids"]),
                  source_hashes_validated=len(recipes),
                  human_confirmed=sum(r["review_state"] == "confirmed" for r in recipes),
                  strict_eligible=sum(r["strict_eligible"] for r in recipes),
                  recipes_with_issues=sum(bool(r["issues"]) for r in recipes),
                  categories=dict(sorted(Counter(r["category"] for r in recipes).items())),
                  ingredient_uses=sum(len(r["ingredients"]) for r in recipes),
                  quantity_observations=dict(Counter(q["kind"] for r in recipes
                      for u in r["ingredients"] for q in u["quantities"])),
                  preparation_observations=sum(len(u["forms"]) for r in recipes
                                                for u in r["ingredients"]),
                  unique_ingredients=len(ontology["ingredients"]),
                  requirement_counts=dict(Counter(u["requirement"] for r in recipes
                                                  for u in r["ingredients"])),
                  choice_groups=sum(len(r["choice_groups"]) for r in recipes),
                  graph_nodes=len(graph), graph_edges=graph.number_of_edges(),
                  node_types=dict(Counter(a["kind"] for _, a in graph.nodes(data=True))),
                  edge_types=dict(Counter(a["type"] for *_, a in graph.edges(data=True))),
                  graph_hash=digest(payload), ontology_hash=ontology_hash,
                  parser_comparison_changed_recipes=audit["recipes_with_changes"],
                  unclassified_ingredients=ontology.get("unclassified", []),
                  accuracy="Not measured: no independent adjudicated human reference set.",
                  review_status="AI-assisted drafts; human course sign-off remains outstanding."
                  if not all(r["review_state"] == "confirmed" for r in recipes)
                  else "Human confirmed")
    # All validations complete before writing any deliverable.
    output.mkdir(parents=True, exist_ok=True)
    (output / "recipes.jsonl").write_text("".join(canonical_json(r) + "\n" for r in recipes),
                                           encoding="utf-8")
    for name, obj in {"graph.json": payload, "neo4j-import.json": payload,
                      "networkx.node-link.json": nx.node_link_data(
                          graph, edges="edges", name="node_id", key="edge_key"
                      ),
                      "ontology.json": effective_ontology, "quality-report.json": report,
                      "parser-audit.json": audit,
                      "annotation.schema.json": Annotation.model_json_schema(),
                      "recipe.schema.json": DataRecipe.model_json_schema(),
                      "approvals.schema.json": Approvals.model_json_schema(),
                      "approvals.blank.json": Approvals().model_dump(mode="json"),
                      "pilot-20-ids.json": bundle["pilot_ids"]}.items():
        write_json(output / name, obj)
    from cookkg.data_review import write_review_pack

    write_review_pack(output, recipes, sources, report, set(bundle["pilot_ids"]))
    from cookkg.data_delivery import acceptance_report, write_delivery_pack

    write_delivery_pack(output, recipes, effective_ontology, raw, report)
    write_json(output / "course-acceptance.json", acceptance_report(report, recipes))
    from cookkg.data_backend import write_backend_projection

    write_backend_projection(output)
    return report
