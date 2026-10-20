#!/usr/bin/env python3
"""Static regression gate for code-review eval fixtures.

This does not grade a model's review output. It checks that fixture files exist,
comparison snapshots differ, and expected findings resolve to their source lines.
Behavioral evaluation must run the prompts without exposing expected findings.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
EVALS = ROOT / "tests" / "fixtures" / "code-review" / "evals.json"


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def line_at(path: Path, line_no: int) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    if line_no < 1 or line_no > len(lines):
        raise IndexError(f"{path}:{line_no} outside file with {len(lines)} lines")
    return lines[line_no - 1]


def main() -> int:
    errors: list[str] = []
    data = load_json(EVALS)
    if data.get("skill_name") != "code-review":
        errors.append("evals.json skill_name must be code-review")
    evals = data.get("evals")
    if not isinstance(evals, list) or not evals:
        errors.append("evals.json must contain non-empty evals")

    for item in evals or []:
        eval_id = item.get("id", "<missing-id>")
        for key in ["name", "prompt", "files", "expected_findings"]:
            if key not in item:
                errors.append(f"{eval_id}: missing {key}")
        if "$code-review" not in item.get("prompt", ""):
            errors.append(f"{eval_id}: prompt must invoke $code-review")
        for rel in item.get("files", []):
            if not (ROOT / rel).exists():
                errors.append(f"{eval_id}: missing fixture {rel}")

        change = item.get("change")
        before_lines = []
        if change:
            before = ROOT / change["before"]
            after = ROOT / change["after"]
            if not before.is_file() or not after.is_file():
                errors.append(f"{eval_id}: missing comparison snapshot")
                continue
            before_lines = before.read_text(encoding="utf-8").splitlines()
            if before_lines == after.read_text(encoding="utf-8").splitlines():
                errors.append(f"{eval_id}: comparison snapshots are identical")

        for finding in item.get("expected_findings", []):
            rel_file = finding.get("file")
            line_no = finding.get("line")
            if not rel_file or not isinstance(line_no, int):
                errors.append(f"{eval_id}: expected finding missing file/line")
                continue
            try:
                line = line_at(ROOT / rel_file, line_no)
            except Exception as exc:
                errors.append(f"{eval_id}: {exc}")
                continue
            anchor = finding.get("anchor")
            if not anchor or anchor != line.strip():
                errors.append(f"{eval_id}: expected finding anchor does not match {rel_file}:{line_no}")
            if change and finding.get("relationship") == "introduced":
                if rel_file != change["after"] or anchor in [value.strip() for value in before_lines]:
                    errors.append(f"{eval_id}: introduced finding is not new in the after snapshot")

    if errors:
        print(json.dumps({"ok": False, "errors": errors}, indent=2))
        return 1
    print(json.dumps({"ok": True, "eval_file": str(EVALS.relative_to(ROOT)), "cases": len(evals)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
