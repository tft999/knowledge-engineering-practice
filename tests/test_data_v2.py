import copy
import hashlib
import json
from pathlib import Path

import networkx as nx
import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from cookkg.cli import app
from cookkg.data_models import Annotation, DataRecipe, validate_recipe_id
from cookkg.data_neo4j import snapshot_rows
from cookkg.data_pipeline import (
    build_v2,
    digest,
    graph_from_payload,
    graph_payload,
    resource_json,
    validate_evidence,
    validate_ontology,
    write_json,
)
from cookkg.pipeline import source_config


@pytest.fixture
def case(tmp_path):
    text = ("# 样例的做法\n## 必备原料和工具\n- 鸡蛋 2 个  \n- 油或黄油\n"
            "- 盐（可选）\n- 水\n## 操作\n煮。\n")
    sha = hashlib.sha256(text.encode()).hexdigest()
    recipe_id = "dishes/test/样例.md"
    raw = tmp_path / "raw"
    (raw / "dishes/test").mkdir(parents=True)
    (raw / recipe_id).write_text(text, encoding="utf-8")
    write_json(raw / ".cookkg-source.json", dict(commit=source_config()["commit"]))

    def use(name, line, requirement="required", group=None, surface=None):
        return dict(use_id=name, id=name, surface=surface or name, requirement=requirement,
                    group_id=group, resource_kind="household_resource" if name == "水" else "food",
                    evidence=[dict(line=line, text=text.splitlines()[line - 1])])

    egg = use("鸡蛋", 3)
    egg["quantity_raw"] = ["- 鸡蛋 2 个  "]
    annotation = Annotation.model_validate(dict(id=recipe_id, source_hash=sha,
        ingredients=[egg, use("食用油", 4, "one_of", "g1", "油"),
                     use("黄油", 4, "one_of", "g1"), use("盐", 5, "optional"), use("水", 6)],
        choice_groups=[dict(id="g1", member_ids=["食用油", "黄油"], min_select=1, max_select=1,
                            evidence=[dict(line=4, text="- 油或黄油")])]))
    ontology = dict(schema_version="2.0", categories=["食材"],
                    ingredients={u.id: {} for u in annotation.ingredients},
                    relations=[dict(type="IS_A", child=u.id, parent="食材",
                                    review_state="pending", basis="Test fixture")
                               for u in annotation.ingredients if u.id != "水"], aliases=[])
    annotations_path, ontology_path = tmp_path / "a.json", tmp_path / "o.json"
    write_json(annotations_path, dict(schema_version="2.0", source_commit=source_config()["commit"],
                                     selection="fixture", pilot_ids=[recipe_id],
                                     annotations=[annotation.model_dump(mode="json")]))
    write_json(ontology_path, ontology)
    return dict(raw=raw, output=tmp_path / "output", annotations_path=annotations_path,
                ontology_path=ontology_path), annotation, ontology, text


@pytest.mark.parametrize("path", ["../secret.md", "dishes/../secret.md", "dishes/a\\x.md",
                                  "dishes/C:secret.md", "dishes//x.md", "/dishes/a.md"])
def test_paths_cannot_escape(path):
    with pytest.raises(ValueError):
        validate_recipe_id(path)


def test_evidence_detects_tampering_and_preserves_whitespace(case):
    _, annotation, _, text = case
    validate_evidence(annotation, text)
    assert annotation.ingredients[0].quantity_raw == ["- 鸡蛋 2 个  "]
    with pytest.raises(ValueError, match="Stale source"):
        validate_evidence(annotation, text + "changed")
    altered = annotation.model_copy(deep=True)
    altered.ingredients[0].evidence[0].line = 4
    with pytest.raises(ValueError, match="Evidence mismatch"):
        validate_evidence(altered, text)


@pytest.mark.parametrize("mutation", ["missing_group", "duplicate_use", "bounds", "ai_confirmed",
                                      "oil_as_household", "member_mismatch"])
def test_semantic_guards(case, mutation):
    _, annotation, _, _ = case
    value = annotation.model_dump(mode="json")
    if mutation == "missing_group":
        value["ingredients"][1]["group_id"] = "missing"
    elif mutation == "duplicate_use":
        value["ingredients"].append(value["ingredients"][0])
    elif mutation == "bounds":
        value["choice_groups"][0]["max_select"] = 3
    elif mutation == "ai_confirmed":
        value["ingredients"][0]["review_state"] = "confirmed"
    elif mutation == "oil_as_household":
        value["ingredients"][1]["resource_kind"] = "household_resource"
    else:
        value["choice_groups"][0]["member_ids"] = ["鸡蛋"]
    with pytest.raises(ValidationError):
        Annotation.model_validate(value)


def test_deterministic_build_and_round_trip(case):
    kwargs, _, _, _ = case
    first = build_v2(**kwargs)
    first_bytes = {p.name: p.read_bytes() for p in kwargs["output"].iterdir()}
    assert build_v2(**kwargs) == first
    assert {p.name: p.read_bytes() for p in kwargs["output"].iterdir()} == first_bytes
    assert first["human_confirmed"] == first["strict_eligible"] == 0
    payload = json.loads(first_bytes["graph.json"])
    assert graph_payload(graph_from_payload(payload)) == payload
    graph = graph_from_payload(payload)
    standard = nx.node_link_graph(
        json.loads(first_bytes["networkx.node-link.json"]),
        edges="edges",
        name="node_id",
        key="edge_key",
    )
    assert graph_payload(standard) == payload
    kinds = [e["type"] for *_, e in graph.edges(data=True)]
    assert kinds.count("ONE_OF") == 2 and "OPTIONALLY_USES" in kinds
    recipe = DataRecipe.model_validate_json(first_bytes["recipes.jsonl"])
    assert not recipe.strict_eligible
    assert "食用油" in {u.id for u in recipe.ingredients if u.resource_kind == "food"}


def test_human_approval_binds_both_content_hashes(case, tmp_path):
    kwargs, annotation, ontology, _ = case
    approvals = dict(standard_frozen=True, ontology_hash=digest(ontology),
                     ontology_reviewer="Fixture ontology reviewer",
                     ontology_reviewed_on="2026-09-09",
                     recipes={annotation.id: dict(reviewer="Fixture reviewer",
                         reviewed_on="2026-09-09", source_hash=annotation.source_hash,
                         annotation_hash=digest(annotation.model_dump(mode="json")))})
    path = tmp_path / "approvals.json"
    write_json(path, approvals)
    report = build_v2(**kwargs, approvals_path=path)
    assert report["human_confirmed"] == report["strict_eligible"] == 1
    from cookkg.data_interface import recipe_detail

    recipe = json.loads((kwargs["output"] / "recipes.jsonl").read_text(encoding="utf-8"))
    detail = recipe_detail(recipe)
    assert detail["ingredients"][0]["name"] == "鸡蛋"
    assert "difficulty" in detail and detail["id"] == recipe["id"]
    approvals["recipes"][annotation.id]["annotation_hash"] = "0" * 64
    write_json(path, approvals)
    with pytest.raises(ValueError, match="Stale approval"):
        build_v2(**kwargs, approvals_path=path)


def test_pending_data_cannot_be_exposed_as_an_approved_ui_recipe(case):
    from cookkg.data_interface import recipe_detail

    kwargs, _, _, _ = case
    build_v2(**kwargs)
    record = json.loads((kwargs["output"] / "recipes.jsonl").read_text(encoding="utf-8"))
    with pytest.raises(ValueError, match="strict public"):
        recipe_detail(record)


def test_delivery_outputs_are_traceable_and_do_not_fabricate_review(case):
    kwargs, _, _, _ = case
    build_v2(**kwargs)
    out = kwargs["output"]
    audit = json.loads((out / "source-audit.json").read_text(encoding="utf-8"))
    assert audit["scanned"] == audit["curated"] == 1
    evaluation = json.loads((out / "evaluation-100-draft.json").read_text(encoding="utf-8"))
    assert len(evaluation["cases"]) == 1
    assert evaluation["cases"][0]["expected"] is None
    assert not evaluation["cases"][0]["human_reviewed"]
    result = CliRunner().invoke(app, ["data-v2", "acceptance", "--data", str(out)])
    assert result.exit_code == 1 and '"complete": false' in result.output


def test_ontology_rejects_cycles_dangling_and_unproven_components(case):
    _, _, ontology, _ = case
    for relation in [dict(type="SUBCLASS_OF", child="食材", parent="食材"),
                     dict(type="IS_A", child="未知", parent="食材"),
                     dict(type="HAS_COMPONENT", child="黄油", parent="盐")]:
        broken = copy.deepcopy(ontology)
        broken["relations"].append(dict(relation, review_state="pending", basis="fixture"))
        with pytest.raises(ValueError):
            validate_ontology(broken, {"鸡蛋"})


def test_shipped_hundred_annotations_are_honest_and_consistent():
    bundle = resource_json("annotations_v2.json")
    records = [Annotation.model_validate(a) for a in bundle["annotations"]]
    assert len(records) == len({a.id for a in records}) == 100
    assert len(bundle["pilot_ids"]) == 20
    assert all(a.method == "ai_assisted" for a in records)
    validate_ontology(resource_json("ontology_v2.json"),
                      {u.id for a in records for u in a.ingredients})
    by_name = {Path(a.id).stem: a for a in records}
    tuna = by_name["金枪鱼酱三明治"]
    assert "水" not in {u.id for u in tuna.ingredients}
    optional = {u.id for u in by_name["凉拌莴笋"].ingredients if u.requirement == "optional"}
    assert "萝卜" in optional
    assert any("76g" in issue.detail for issue in by_name["芋泥雪媚娘"].issues)


def test_neo4j_rejects_untyped_payload_before_connecting(case):
    kwargs, _, _, _ = case
    build_v2(**kwargs)
    payload = json.loads((kwargs["output"] / "graph.json").read_text(encoding="utf-8"))
    scope, nodes, edges = snapshot_rows(payload)
    assert all(n["scope"] == scope for n in nodes)
    assert len({e["properties"]["key"] for e in edges}) == len(edges)
    payload["edges"][0]["properties"]["type"] = "BAD` CYPHER"
    with pytest.raises(ValueError):
        snapshot_rows(payload)


def test_v2_cli_reports_source_failure_without_traceback(tmp_path):
    result = CliRunner().invoke(app, ["data-v2", "build", "--raw", str(tmp_path)])
    assert result.exit_code == 1
    assert "v2 build failed" in result.output


def test_comparison_uses_semantics_and_does_not_claim_human_review(case):
    from cookkg.data_review import compare_annotations

    kwargs, _, _, _ = case
    first = json.loads(kwargs["annotations_path"].read_text(encoding="utf-8"))
    second = copy.deepcopy(first)
    second["annotations"][0]["ingredients"][0]["use_id"] = "another-stable-id"
    result = compare_annotations(first, second)
    assert result["same_recipe_count"] == 1
    assert not result["declared_distinct_human_authors"]
    second["annotations"][0]["ingredients"][3]["requirement"] = "required"
    assert compare_annotations(first, second)["same_recipe_count"] == 0
    second["annotations"][0]["source_hash"] = "a" * 64
    with pytest.raises(ValueError, match="Source hash differs"):
        compare_annotations(first, second)
