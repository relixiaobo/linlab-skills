#!/usr/bin/env python3
"""Minimal executor adapter used only by runner unit tests."""

from __future__ import annotations

import json
import os
from pathlib import Path


def main() -> None:
    if "EVAL_ORACLE_FILE" in os.environ:
        raise RuntimeError("oracle leaked into executor environment")
    output_dir = Path(os.environ["EVAL_OUTPUT_DIR"])
    skills_dir = Path(os.environ["EVAL_SKILLS_DIR"])
    result_path = Path(os.environ["EVAL_AGENT_RESULT_FILE"])
    has_skill = (skills_dir / "tiny-skill" / "SKILL.md").is_file()

    response = output_dir / "response.md"
    artifact = output_dir / "artifact.txt"
    response.write_text("Fixture executor completed.\n", encoding="utf-8")
    artifact.write_text("checked fixture result\n", encoding="utf-8")
    result = {
        "status": "completed",
        "response_path": "response.md",
        "artifacts": ["artifact.txt"],
        "traces": [],
        "route": {
            "primary_skill": "tiny-skill" if has_skill else None,
            "selected_skills": ["tiny-skill"] if has_skill else [],
        },
        "usage": {
            "input_tokens": 20 if has_skill else 10,
            "output_tokens": 5,
            "total_tokens": 25 if has_skill else 15,
            "estimated_cost_usd": 0.001 if has_skill else 0.0005,
        },
        "model": {
            "name": "fixture-model",
            "config": {"temperature": 0}
        }
    }
    result_path.write_text(json.dumps(result) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
