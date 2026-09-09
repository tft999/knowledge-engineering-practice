"""Create a reviewable local handoff bundle without changing Git history."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

GENERATED_FILES = (
    "technical-review.json",
    "annotation.schema.json",
    "approvals.blank.json",
    "approvals.schema.json",
    "backend-compatibility.json",
    "backend-graph.json",
    "course-acceptance.json",
    "evaluation-100-draft.json",
    "graph.json",
    "issue-resolution-queue.json",
    "neo4j-import.json",
    "networkx.node-link.json",
    "ontology.json",
    "parser-audit.json",
    "pilot-20-blind.html",
    "pilot-20-ids.json",
    "pilot-20-independent.blank.json",
    "quality-report.json",
    "recipe.schema.json",
    "recipes.jsonl",
    "review-100.html",
    "review-script.js",
    "source-audit.json",
    "team-review.blank.json",
    "validation-results.json",
)

DOCS = (
    "docs/data-contract-v2.md",
    "docs/zouyilin06-handoff.md",
    "docs/zouyilin06-report-section.md",
    "docs/validation/zouyilin06-data-v2.md",
)

SOURCE = (
    "src/cookkg/data_backend.py",
    "src/cookkg/data_cli.py",
    "src/cookkg/data_delivery.py",
    "src/cookkg/data_interface.py",
    "src/cookkg/data_models.py",
    "src/cookkg/data_pipeline.py",
    "src/cookkg/data_quantities.py",
    "src/cookkg/data_review.py",
    "src/cookkg/recommend.py",
    "src/cookkg/services.py",
    "src/cookkg/api.py",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("outputs/zouyilin06-final"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    destination = (
        (root / args.output).resolve()
        if not args.output.is_absolute()
        else args.output.resolve()
    )
    destination.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for relative in GENERATED_FILES:
        source = root / "data/processed/v2" / relative
        target = destination / "data/processed/v2" / relative
        if not source.is_file():
            raise FileNotFoundError(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(target)
    for relative in DOCS + SOURCE:
        source = root / relative
        if not source.is_file():
            raise FileNotFoundError(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(target)
    manifest = {
        "project_base": "ed3cf27a1c6f154fb62f4a9b66696a0f48aaef48",
        "source_commit": json.loads(
            (destination / "data/processed/v2/quality-report.json").read_text(
                encoding="utf-8"
            )
        )["source_commit"],
        "files": {
            str(path.relative_to(destination)).replace("\\", "/"): sha256(path)
            for path in copied
        },
    }
    (destination / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    archive = destination.with_suffix(".zip")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(destination.rglob("*")):
            if path.is_file():
                bundle.write(path, path.relative_to(destination).as_posix())
    print(
        json.dumps(
            {"directory": str(destination), "archive": str(archive), "files": len(copied) + 1},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
