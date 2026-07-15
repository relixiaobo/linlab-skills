#!/usr/bin/env python3
"""Second deterministic Judge Adapter used to verify per-case routing."""

from __future__ import annotations

import json
import os
from pathlib import Path


def main() -> None:
    if os.environ.get("EVAL_JUDGE_ADAPTER_ID") != "fixture-secondary":
        raise RuntimeError("wrong Judge Adapter identity")
    if os.environ.get("EVAL_JUDGE_PROTOCOL_VERSION") != "1.0":
        raise RuntimeError("wrong Judge Adapter protocol")
    config = json.loads(os.environ["EVAL_JUDGE_CONFIG"])
    oracle = json.loads(Path(os.environ["EVAL_ORACLE_FILE"]).read_text(encoding="utf-8"))
    result = json.loads(Path(os.environ["EVAL_RESULT_FILE"]).read_text(encoding="utf-8"))
    route_ok = result["route"]["primary_skill"] in oracle["expected"]["route"][
        "acceptable_primary_skills"
    ]
    artifact_ok = any(item["path"] == "artifact.txt" for item in result["artifacts"])
    value = float(config["score"]) if route_ok and artifact_ok else 0.0

    evidence_dir = Path(os.environ["EVAL_JUDGE_EVIDENCE_DIR"])
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / "secondary-evidence.json").write_text(
        json.dumps({"route_ok": route_ok, "artifact_ok": artifact_ok}) + "\n",
        encoding="utf-8",
    )
    judgment = {
        "scores": [
            {
                "criterion_id": "route-and-output",
                "value": value,
                "passed": value >= 0.75,
                "rationale": "Secondary fixture Judge Adapter result.",
                "evidence": ["secondary-evidence.json"],
            }
        ],
        "failure_tags": [] if route_ok else ["route-error"],
        "summary": "secondary fixture judge completed",
    }
    Path(os.environ["EVAL_JUDGE_RESULT_FILE"]).write_text(
        json.dumps(judgment) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
