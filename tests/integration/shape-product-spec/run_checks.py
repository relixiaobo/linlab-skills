#!/usr/bin/env python3
"""Deterministic integration checks for the product-spec inspection tool."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests" / "fixtures" / "shape-product-spec"
SPEC_CHECK = ROOT / "skills" / "shape-product-spec" / "scripts" / "spec_check.py"


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def check_spec_script() -> list[str]:
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="product_spec_test_") as temp:
        output_dir = Path(temp)
        good_out = output_dir / "good-product-spec-report.json"
        bad_out = output_dir / "bad-product-spec-report.json"

        good = run([
            sys.executable,
            str(SPEC_CHECK),
            "inspect",
            str(FIXTURES / "good_product_spec.md"),
            "--out",
            str(good_out),
        ])
        if good.returncode != 0:
            errors.append(
                f"good product spec should pass: {good.stderr.strip() or good.stdout[-1000:]}"
            )
        else:
            report = load_json(good_out)
            counts = report.get("summary", {}).get("stable_id_counts", {})
            if counts.get("FR", 0) < 2 or counts.get("AC", 0) < 4 or counts.get("EVD", 0) < 2:
                errors.append("good product spec report missed expected FR/AC/EVD IDs")
            if counts.get("CON", 0) < 2 or counts.get("OPT", 0) < 2 or counts.get("TRD", 0) < 1:
                errors.append("good product spec report missed expected constraint/option/tradeoff IDs")
            groups = report.get("sections", {}).get("groups", {})
            for group in ("flows", "evidence", "constraints"):
                if not groups.get(group):
                    errors.append(f"good product spec report missed {group} section")

        bad = run([
            sys.executable,
            str(SPEC_CHECK),
            "inspect",
            str(FIXTURES / "bad_product_spec.md"),
            "--out",
            str(bad_out),
        ])
        if bad.returncode == 0:
            errors.append("bad product spec should fail spec_check")
        else:
            report = load_json(bad_out)
            joined = "\n".join(report.get("findings", {}).get("errors", []))
            if "Duplicate stable IDs" not in joined or "placeholder" not in joined.lower():
                errors.append("bad product spec did not report duplicate IDs and placeholders")
    return errors


def main() -> int:
    errors = check_spec_script()
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, indent=2))
        return 1
    print(json.dumps({"ok": True, "fixture_dir": str(FIXTURES.relative_to(ROOT))}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
