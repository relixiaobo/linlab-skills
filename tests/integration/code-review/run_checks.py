#!/usr/bin/env python3
"""Static regression gate for code-review eval fixtures.

This does not grade a model's review output. It guarantees the review scenarios
are usable: fixture files exist, expected finding anchors resolve to real lines,
and the before/after diff actually introduces the behavior the eval asks a
reviewer to catch.
"""

from __future__ import annotations

import difflib
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

        after_files = [Path(rel) for rel in item.get("files", []) if rel.endswith("after.py")]
        before_files = [Path(rel) for rel in item.get("files", []) if rel.endswith("before.py")]
        if len(after_files) != 1 or len(before_files) != 1:
            errors.append(f"{eval_id}: expected one before.py and one after.py fixture")
            continue
        before = ROOT / before_files[0]
        after = ROOT / after_files[0]
        diff = "\n".join(difflib.unified_diff(
            before.read_text(encoding="utf-8").splitlines(),
            after.read_text(encoding="utf-8").splitlines(),
            fromfile=str(before_files[0]),
            tofile=str(after_files[0]),
            lineterm="",
        ))
        if 'extra={"headers": headers}' not in diff:
            errors.append(f"{eval_id}: diff does not introduce header logging")
        if "Authorization" not in after.read_text(encoding="utf-8"):
            errors.append(f"{eval_id}: after fixture does not contain Authorization data")

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
            if "logger.info" not in line or "headers" not in line:
                errors.append(f"{eval_id}: expected finding line is not the introduced logging call")
            if int(finding.get("minimum_confidence", 0)) < 80:
                errors.append(f"{eval_id}: expected finding confidence threshold must be >= 80")

    if errors:
        print(json.dumps({"ok": False, "errors": errors}, indent=2))
        return 1
    print(json.dumps({"ok": True, "eval_file": str(EVALS.relative_to(ROOT))}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
