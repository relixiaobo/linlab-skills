#!/usr/bin/env python3
"""Invalid Judge Adapter that mutates Agent output for boundary testing."""

from __future__ import annotations

import json
import os
from pathlib import Path


def main() -> None:
    output_dir = Path(os.environ["EVAL_OUTPUT_DIR"])
    (output_dir / "artifact.txt").write_text("mutated by judge\n", encoding="utf-8")
    judgment = {
        "scores": [
            {
                "criterion_id": "route-and-output",
                "value": 1.0,
                "passed": True,
                "rationale": "The fixture would otherwise pass.",
                "evidence": ["artifact.txt"],
            }
        ],
        "failure_tags": [],
        "summary": "invalid mutating judge completed",
    }
    Path(os.environ["EVAL_JUDGE_RESULT_FILE"]).write_text(
        json.dumps(judgment) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
