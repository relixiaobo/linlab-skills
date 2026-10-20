#!/usr/bin/env python3
"""Minimal Codex CLI double for blind Judge Adapter integration tests."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def option_value(arguments: list[str], name: str) -> str:
    try:
        return arguments[arguments.index(name) + 1]
    except (ValueError, IndexError) as exc:
        raise RuntimeError(f"missing required option: {name}") from exc


def main() -> int:
    arguments = sys.argv[1:]
    if not arguments or arguments[0] != "exec":
        raise RuntimeError("expected the Codex exec subcommand")
    if option_value(arguments, "--sandbox") != "read-only":
        raise RuntimeError("blind judge must use the read-only sandbox")
    disabled = {
        arguments[index + 1]
        for index, value in enumerate(arguments[:-1])
        if value == "--disable"
    }
    if not {"plugins", "multi_agent"}.issubset(disabled):
        raise RuntimeError("blind judge did not disable plugins and multi_agent")
    if any(name.startswith("EVAL_") for name in os.environ):
        raise RuntimeError("evaluation environment leaked into blind judge")

    workspace = Path(option_value(arguments, "--cd"))
    required_workspace_files = [
        "source/prompt.md",
        "agent-result.json",
        "agent-response.md",
        "agent-trace-summary.json",
    ]
    if (workspace / "source/input/orders.csv").is_file():
        artifact_evidence = "artifacts/analysis.md"
        required_workspace_files.extend(
            [
                "source/input/orders.csv",
                "artifacts/analysis.md",
                "artifacts/findings.tsv",
                "source-truth.json",
                "artifact-audit.json",
            ]
        )
    elif (workspace / "source/input/merchant_addon_notes.md").is_file():
        artifact_evidence = "artifacts/product-spec.md"
        required_workspace_files.extend(
            [
                "source/input/merchant_addon_notes.md",
                "artifacts/product-spec.md",
                "spec-check.json",
                "artifact-audit.json",
            ]
        )
    elif (workspace / "source/input/board_notes.md").is_file():
        artifact_evidence = "artifacts/board-memo.md"
        required_workspace_files.extend(
            [
                "source/input/board_notes.md",
                "artifacts/board-memo.md",
                "markdown-inspect.json",
                "artifact-audit.json",
            ]
        )
    elif (workspace / "source/input/policy_draft.md").is_file():
        artifact_evidence = "artifacts/policy-review.md"
        required_workspace_files.extend(
            [
                "source/input/policy_draft.md",
                "artifacts/policy-review.md",
                "markdown-inspect.json",
                "artifact-audit.json",
            ]
        )
    elif (workspace / "source/input/pricing_inputs.csv").is_file():
        artifact_evidence = "workbook-audit.json"
        required_workspace_files.extend(
            [
                "source/input/pricing_inputs.csv",
                "source-inspect.json",
                "source-truth.json",
                "workbook-inspect.json",
                "workbook-audit.json",
                "recalc-report.json",
            ]
        )
    else:
        raise RuntimeError("blind workspace has an unknown domain fixture")
    missing = [
        name for name in required_workspace_files if not (workspace / name).is_file()
    ]
    if missing:
        raise RuntimeError(f"blind workspace is incomplete: {missing}")

    codex_home = Path(os.environ["CODEX_HOME"])
    if not (codex_home / "auth.json").is_file():
        raise RuntimeError("isolated Codex home has no authentication")
    schema_path = Path(option_value(arguments, "--output-schema"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    criterion_ids = schema["properties"]["scores"]["items"]["properties"][
        "criterion_id"
    ]["enum"]
    output_path = Path(option_value(arguments, "--output-last-message"))
    output_path.write_text(
        json.dumps(
            {
                "scores": [
                    {
                        "criterion_id": criterion_id,
                        "value": 0.9,
                        "passed": True,
                        "rationale": "Fixture blind review passed.",
                        "evidence": [artifact_evidence],
                    }
                    for criterion_id in criterion_ids
                ],
                "failure_tags": [],
                "summary": "Fixture model judgment.",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"type": "thread.started", "thread_id": "fixture-thread"}))
    print(
        json.dumps(
            {
                "type": "turn.completed",
                "usage": {"input_tokens": 11, "output_tokens": 7},
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
