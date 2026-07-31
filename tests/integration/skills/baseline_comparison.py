"""Compare restructure validation output with the Phase 0 baseline."""

from __future__ import annotations

import json
from pathlib import Path


def compare_baseline(
    checks: list[dict],
    baseline_path: Path,
    baseline_id_map: dict[str, str],
    root: Path,
) -> dict:
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    current_status = {item["name"]: item["status"] for item in checks}
    baseline_targets: dict[str, str] = {}
    missing: list[dict] = []
    status_regressions: list[dict] = []

    for item in baseline["checks"]:
        baseline_name = item["name"]
        current_name = baseline_id_map.get(baseline_name, baseline_name)
        expected = "passed" if item["ok"] else "failed"
        actual = current_status.get(current_name)
        baseline_targets[current_name] = expected
        if actual is None:
            missing.append({"baseline": baseline_name, "current": current_name})
        elif expected == "passed" and actual != "passed":
            status_regressions.append({
                "baseline": baseline_name,
                "current": current_name,
                "expected": expected,
                "actual": actual,
            })
        elif expected == "failed" and actual == "skipped":
            status_regressions.append({
                "baseline": baseline_name,
                "current": current_name,
                "expected": expected,
                "actual": actual,
            })

    new_failures = [
        item["name"]
        for item in checks
        if item["status"] == "failed"
        and baseline_targets.get(item["name"]) != "failed"
    ]
    invalid_skips = [
        item["name"]
        for item in checks
        if item["status"] == "skipped"
        and not item["name"].startswith("external-quick-validate:")
    ]
    passed = not (missing or status_regressions or new_failures or invalid_skips)
    try:
        baseline_label = baseline_path.relative_to(root).as_posix()
    except ValueError:
        baseline_label = str(baseline_path)
    return {
        "status": "passed" if passed else "failed",
        "baseline": baseline_label,
        "baseline_check_count": len(baseline["checks"]),
        "current_check_count": len(checks),
        "missing": missing,
        "status_regressions": status_regressions,
        "new_failures": new_failures,
        "invalid_skips": invalid_skips,
    }
