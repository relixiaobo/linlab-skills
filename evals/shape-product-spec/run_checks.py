#!/usr/bin/env python3
"""Static and smoke checks for the shape-product-spec skill."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EVALS = ROOT / "evals" / "shape-product-spec" / "evals.json"
WORKSPACE = ROOT / "shape-product-spec-workspace"
SPEC_CHECK = ROOT / "shape-product-spec" / "scripts" / "spec_check.py"


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def check_eval_file() -> list[str]:
    errors: list[str] = []
    data = load_json(EVALS)
    if data.get("skill_name") != "shape-product-spec":
        errors.append("evals.json: skill_name must be shape-product-spec")
    if data.get("skill_path") != "shape-product-spec":
        errors.append("evals.json: skill_path must be shape-product-spec")
    evals = data.get("evals")
    if not isinstance(evals, list) or not evals:
        errors.append("evals.json: missing evals")
        return errors

    seen: set[str] = set()
    for item in evals:
        eval_id = item.get("id")
        if not eval_id:
            errors.append("evals.json: eval missing id")
            continue
        if eval_id in seen:
            errors.append(f"evals.json: duplicate id {eval_id}")
        seen.add(eval_id)
        for key in ["name", "prompt", "expected_skill", "assertions"]:
            if key not in item:
                errors.append(f"evals.json:{eval_id}: missing {key}")
        assertions = item.get("assertions")
        if not isinstance(assertions, list) or not assertions:
            errors.append(f"evals.json:{eval_id}: assertions must be non-empty")
        prompt = item.get("prompt", "")
        if item.get("expected_skill") == "shape-product-spec" and "$shape-product-spec" not in prompt:
            errors.append(f"evals.json:{eval_id}: positive prompt should invoke the skill explicitly")
        for rel in item.get("files", []):
            if not (ROOT / rel).exists():
                errors.append(f"evals.json:{eval_id}: missing file {rel}")
    return errors


def check_spec_script() -> list[str]:
    errors: list[str] = []
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    good_out = WORKSPACE / "good-product-spec-report.json"
    bad_out = WORKSPACE / "bad-product-spec-report.json"

    good = run([
        sys.executable,
        str(SPEC_CHECK),
        "inspect",
        "evals/shape-product-spec/source/good_product_spec.md",
        "--out",
        str(good_out),
    ])
    if good.returncode != 0:
        errors.append(f"good product spec should pass: {good.stderr.strip() or good.stdout[-1000:]}")
    else:
        report = load_json(good_out)
        counts = report.get("summary", {}).get("stable_id_counts", {})
        if counts.get("FR", 0) < 2 or counts.get("AC", 0) < 4 or counts.get("EVD", 0) < 2:
            errors.append("good product spec report missed expected FR/AC/EVD IDs")
        if counts.get("CON", 0) < 2 or counts.get("OPT", 0) < 2 or counts.get("TRD", 0) < 1:
            errors.append("good product spec report missed expected constraint/option/tradeoff IDs")
        if not report.get("sections", {}).get("groups", {}).get("flows"):
            errors.append("good product spec report missed flow section")
        if not report.get("sections", {}).get("groups", {}).get("evidence"):
            errors.append("good product spec report missed evidence section")
        if not report.get("sections", {}).get("groups", {}).get("constraints"):
            errors.append("good product spec report missed constraints/options section")

    bad = run([
        sys.executable,
        str(SPEC_CHECK),
        "inspect",
        "evals/shape-product-spec/source/bad_product_spec.md",
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


def write_forward_test_prompts() -> None:
    data = load_json(EVALS)
    prompts = [
        {
            "id": item["id"],
            "skill_path": data.get("skill_path"),
            "prompt": item["prompt"],
            "files": item.get("files", []),
        }
        for item in data.get("evals", [])
    ]
    out = WORKSPACE / "forward-test-prompts.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"prompts": prompts}, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    errors: list[str] = []
    errors.extend(check_eval_file())
    errors.extend(check_spec_script())
    write_forward_test_prompts()
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, indent=2))
        return 1
    print(json.dumps({"ok": True, "eval_file": str(EVALS.relative_to(ROOT))}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
