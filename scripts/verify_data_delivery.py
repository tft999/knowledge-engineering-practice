"""Run from the repository root after installing .[dev]; optional live Neo4j checks."""

import argparse
import json
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from uuid import uuid4

from cookkg.data_neo4j import QUERIES, import_v2, run_queries_v2, verify_v2
from cookkg.data_pipeline import build_v2, write_json


class ReviewPage(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.refs, self.approvals = set(), set(), []
        self.in_script = False
        self.script = ""

    def handle_starttag(self, tag, pairs):
        attrs = dict(pairs)
        if "id" in attrs:
            assert attrs["id"] not in self.ids
            self.ids.add(attrs["id"])
        if tag == "a" and attrs.get("href", "").startswith("#"):
            self.refs.add(attrs["href"][1:])
        if tag == "input" and attrs.get("class") == "approve":
            self.approvals.append(attrs)
        if tag == "script":
            self.in_script = True

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_script = False

    def handle_data(self, data):
        if self.in_script:
            self.script += data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--neo4j", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("data/processed/v2"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = args.output.resolve()
    if not out.is_relative_to(root):
        raise ValueError("Verification output must stay inside this repository")
    repeat = out.parent / "v2-repeat"
    report = build_v2(root / "data/raw/howtocook", out)
    second = build_v2(root / "data/raw/howtocook", repeat)
    names = sorted(p.name for p in repeat.iterdir() if p.is_file())
    assert report == second
    assert all((out / name).read_bytes() == (repeat / name).read_bytes() for name in names)
    page = ReviewPage()
    page.feed((out / "review-100.html").read_text(encoding="utf-8"))
    assert page.refs <= page.ids
    assert len(page.approvals) == 100 and all("checked" not in a for a in page.approvals)
    node = shutil.which("node")
    if node:
        script = out / "review-script.js"
        script.write_text(page.script, encoding="utf-8")
        subprocess.run([node, "--check", str(script)], check=True, capture_output=True)
    subprocess.run([sys.executable, "-m", "ruff", "check", "src", "tests", "scripts"],
                   cwd=root, check=True)
    subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                    "--basetemp", str(out.parent / f"test-tmp-{uuid4().hex}"),
                    "--junitxml", str(out / "tests.xml")], cwd=root, check=True)
    suites = ET.parse(out / "tests.xml").getroot().findall("testsuite")
    counts = {name: sum(int(s.get(name, "0")) for s in suites)
              for name in ("tests", "failures", "errors", "skipped")}
    live = dict(status="not_run")
    graph = json.loads((out / "graph.json").read_text(encoding="utf-8"))
    if args.neo4j:
        if counts["skipped"]:
            raise ValueError("Live verification requested but some tests were skipped")
        first = import_v2(graph)
        assert first == import_v2(graph)
        verification = verify_v2(graph)
        assert verification["ok"]
        queries = run_queries_v2(graph)
        assert queries["ok"]
        live = dict(status="passed", repeated_import_identical=True,
                    comparison=verification, query_checks=len(queries["checks"]))
        write_json(out / "neo4j-queries.json", queries)
        cypher = ("// Pending source-grounded AI drafts; not human-confirmed strict data.\n"
                  f":param scope => '{first['scope']}';\n\n")
        cypher += "\n\n".join(f"// {key}\n{query};" for key, query in QUERIES.items())
        (out / "representative-queries.cypher").write_text(cypher + "\n", encoding="utf-8")
    validation = dict(python=sys.version.split()[0], tests=counts, ruff="passed",
        project_base=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root,
                                             text=True).strip(),
        source_commit=report["source_commit"], graph_hash=report["graph_hash"],
        ontology_hash=report["ontology_hash"], repeated_build_identical=True,
        deterministic_files=len(names), neo4j=live,
        review_html=dict(valid_internal_links=len(page.refs), broken_internal_links=0,
                         prechecked_approvals=0, javascript_syntax="passed" if node else "not_run",
                         visual_verification="not_run: browser policy blocks local file URLs"),
        semantic_accuracy="not_measured_without_independent_human_gold_data")
    write_json(out / "validation-results.json", validation)
    print(json.dumps(validation, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
