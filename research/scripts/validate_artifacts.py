#!/usr/bin/env python3
"""Validate a research artifact directory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, List, Set


REQUIRED = ["route.txt", "plan.md", "sources.jsonl", "claims.jsonl", "audit.md", "report.md"]


def read_jsonl(path: Path) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{lineno}: invalid JSONL: {exc}") from exc
    return rows


def ids(rows: Iterable[Dict[str, object]]) -> Set[str]:
    return {str(row.get("id")) for row in rows if row.get("id")}


def validate(path: Path) -> List[str]:
    errors: List[str] = []
    for name in REQUIRED:
        if not (path / name).exists():
            errors.append(f"missing required file: {name}")

    if errors:
        return errors

    try:
        sources = read_jsonl(path / "sources.jsonl")
        claims = read_jsonl(path / "claims.jsonl")
    except ValueError as exc:
        return [str(exc)]

    source_ids = ids(sources)
    claim_ids = ids(claims)

    for row in sources:
        if not row.get("id"):
            errors.append("source row missing id")
        if not (row.get("url") or row.get("identifier")):
            errors.append(f"source {row.get('id', '?')} missing url or identifier")
        if row.get("tier") not in {None, "S", "A", "B", "C"}:
            errors.append(f"source {row.get('id', '?')} has invalid tier")

    for row in claims:
        claim_id = row.get("id", "?")
        if not row.get("id"):
            errors.append("claim row missing id")
        if not row.get("claim"):
            errors.append(f"claim {claim_id} missing claim text")
        for sid in row.get("source_ids", []) or []:
            if str(sid) not in source_ids:
                errors.append(f"claim {claim_id} references missing source id {sid}")

    report = (path / "report.md").read_text(encoding="utf-8")
    if claim_ids and "Sources" not in report and "sources" not in report.lower():
        errors.append("report.md should include a sources section")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact_dir")
    args = parser.parse_args()
    artifact_dir = Path(args.artifact_dir)
    errors = validate(artifact_dir)
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, indent=2))
        return 1
    print(json.dumps({"ok": True, "artifact_dir": str(artifact_dir)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
