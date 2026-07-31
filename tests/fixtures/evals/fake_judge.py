#!/usr/bin/env python3
"""Minimal post-run judge used only by runner unit tests."""

from __future__ import annotations

import json
import os
from pathlib import Path


def main() -> None:
    oracle = json.loads(Path(os.environ["EVAL_ORACLE_FILE"]).read_text(encoding="utf-8"))
    result = json.loads(Path(os.environ["EVAL_RESULT_FILE"]).read_text(encoding="utf-8"))
    expected = oracle["expected"]["route"]["acceptable_primary_skills"]
    route_ok = result["route"]["primary_skill"] in expected
    artifact_ok = any(item["path"] == "artifact.txt" for item in result["artifacts"])
    value = 1.0 if route_ok and artifact_ok else 0.0
    judge_result = {
        "scores": [
            {
                "criterion_id": "route-and-output",
                "value": value,
                "passed": value == 1.0,
                "rationale": "Fixture route and artifact protocol check.",
                "evidence": ["result.route", "result.artifacts"]
            }
        ],
        "failure_tags": [] if route_ok else ["route-error"],
        "summary": "fixture judge completed"
    }
    Path(os.environ["EVAL_JUDGE_RESULT_FILE"]).write_text(
        json.dumps(judge_result) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
