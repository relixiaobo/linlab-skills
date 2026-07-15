"""Shared evidence helpers for domain Judge Adapters."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from evals.runners.codex_exec_adapter import parse_jsonl_best_effort


def anonymized_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": result.get("status"),
        "route": result.get("route"),
        "usage": result.get("usage"),
        "artifacts": result.get("artifacts"),
        "model": (result.get("executor") or {}).get("model"),
    }


def trace_summary(output_dir: Path) -> dict[str, Any]:
    event_path = output_dir / "trace" / "codex-events.jsonl"
    if not event_path.is_file():
        return {"event_counts": {}, "items": []}
    events, diagnostics = parse_jsonl_best_effort(
        event_path.read_text(encoding="utf-8", errors="replace")
    )
    counts: dict[str, int] = {}
    items: list[dict[str, Any]] = []
    for event in events:
        event_type = str(event.get("type", "unknown"))
        counts[event_type] = counts.get(event_type, 0) + 1
        item = event.get("item")
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type == "command_execution":
            items.append(
                {
                    "type": item_type,
                    "command": item.get("command", ""),
                    "status": item.get("status", ""),
                }
            )
        elif item_type in {"agent_message", "file_change", "error"}:
            items.append(
                {
                    "type": item_type,
                    "text": item.get("text") or item.get("message") or "",
                    "status": item.get("status", ""),
                }
            )
    summary: dict[str, Any] = {"event_counts": counts, "items": items[-200:]}
    if diagnostics:
        summary["parse_diagnostics"] = diagnostics
    return summary
