#!/usr/bin/env python3
"""Inspect Markdown product spec artifacts for readiness risks."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
ID_RE = re.compile(r"\b(OBJ|CON|OPT|TRD|EVD|DEC|HYP|ASM|FLOW|STORY|SCREEN|FR|NFR|BR|AC|EC|SM|A|OQ)-(\d+)\b")
DEF_ID_RE = re.compile(r"(?m)^(?:#{1,6}\s+|\s*[-*]\s+)?(?:\*\*)?\b(OBJ|CON|OPT|TRD|EVD|DEC|HYP|ASM|FLOW|STORY|SCREEN|FR|NFR|BR|AC|EC|SM|A|OQ)-(\d+)\b(?:\*\*)?\s*:")
AC_RE = re.compile(
    r"\b(Given\b.+\bWhen\b.+\bThen\b|When\b.+\bshall\b|If\b.+\bshall\b|While\b.+\bshall\b|Where\b.+\bshall\b|The\b.+\bshall\b)",
    re.IGNORECASE,
)
PLACEHOLDER_RE = re.compile(
    r"(\bTODO\b|\bTBD\b|\bFIXME\b|\?\?\?|<[^>\n]+>|\[(?:Product|Feature|Name|Role|Step|Specific|Term|State)[^\]\n]*\]|ACTION REQUIRED|PLACEHOLDER)",
    re.IGNORECASE,
)
CLARIFICATION_RE = re.compile(r"\[(?:NEEDS CLARIFICATION|OPEN QUESTION|ASSUMPTION):", re.IGNORECASE)
VAGUE_RE = re.compile(
    r"\b(fast|simple|easy|intuitive|robust|secure|scalable|seamless|user-friendly|gracefully|efficient|optimized)\b",
    re.IGNORECASE,
)
IMPLEMENTATION_RE = re.compile(
    r"\b(database|postgres|mysql|redis|mongodb|sql|api endpoint|endpoint|react|vue|next\.js|lambda|s3|kafka|microservice|schema|table|column|field name|backend|frontend)\b",
    re.IGNORECASE,
)

SECTION_GROUPS = {
    "purpose": ["purpose", "reader", "overview", "introduction"],
    "decision": ["decision"],
    "constraints": ["objective", "constraint", "tradeoff", "option", "clean-slate", "brownfield", "minimum acceptable"],
    "evidence": ["evidence", "assumption", "hypothesis"],
    "problem": ["problem", "goal", "job", "user"],
    "scope": ["scope", "non-goal", "out of scope", "in scope"],
    "flows": ["flow", "journey", "scenario"],
    "requirements": ["requirement", "story", "business rule", "validation"],
    "prototype": ["prototype", "screen", "ui copy", "interaction"],
    "edge_cases": ["edge", "failure", "error", "recovery"],
    "acceptance": ["acceptance", "criteria", "done"],
    "open_questions": ["open question", "assumption"],
}


@dataclass
class Heading:
    level: int
    title: str
    line: int


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def headings(lines: list[str]) -> list[Heading]:
    found: list[Heading] = []
    for idx, line in enumerate(lines, start=1):
        match = HEADING_RE.match(line)
        if match:
            found.append(Heading(len(match.group(1)), match.group(2).strip(), idx))
    return found


def section_hits(found: list[Heading]) -> dict[str, bool]:
    titles = [h.title.lower() for h in found]
    hits: dict[str, bool] = {}
    for group, needles in SECTION_GROUPS.items():
        hits[group] = any(any(needle in title for needle in needles) for title in titles)
    return hits


def line_matches(pattern: re.Pattern[str], lines: list[str]) -> list[dict[str, str | int]]:
    matches = []
    for idx, line in enumerate(lines, start=1):
        if pattern.search(line):
            matches.append({"line": idx, "text": line.strip()[:240]})
    return matches


def duplicate_ids(text: str) -> list[str]:
    counts: dict[str, int] = {}
    for match in DEF_ID_RE.finditer(text):
        item = f"{match.group(1)}-{match.group(2)}"
        counts[item] = counts.get(item, 0) + 1
    return sorted(item for item, count in counts.items() if count > 1)


def id_inventory(text: str) -> dict[str, list[str]]:
    inventory: dict[str, set[str]] = {}
    for kind, number in ID_RE.findall(text):
        inventory.setdefault(kind, set()).add(f"{kind}-{number}")
    return {kind: sorted(values, key=lambda value: int(value.split("-")[1])) for kind, values in sorted(inventory.items())}


def inspect_markdown(path: Path) -> dict:
    text = read_text(path)
    lines = text.splitlines()
    found_headings = headings(lines)
    hits = section_hits(found_headings)
    ids = id_inventory(text)
    duplicated = duplicate_ids(text)
    placeholders = line_matches(PLACEHOLDER_RE, lines)
    clarifications = line_matches(CLARIFICATION_RE, lines)
    vague = line_matches(VAGUE_RE, lines)
    implementation_terms = line_matches(IMPLEMENTATION_RE, lines)
    ac_lines = line_matches(AC_RE, lines)

    errors: list[str] = []
    warnings: list[str] = []

    if not found_headings:
        errors.append("No Markdown headings found.")
    if placeholders:
        errors.append(f"Found {len(placeholders)} placeholder/TODO-like marker(s).")
    if duplicated:
        errors.append(f"Duplicate stable IDs found: {', '.join(duplicated)}.")
    if not ids.get("FR") and not ids.get("BR") and not ids.get("NFR") and not ids.get("STORY"):
        errors.append("No FR/BR/NFR/STORY requirement or story IDs found.")
    if not ids.get("AC") and not ac_lines:
        errors.append("No acceptance criteria detected.")

    for group in ["purpose", "scope", "flows", "requirements"]:
        if not hits[group]:
            warnings.append(f"Missing or unclear section group: {group}.")
    if not hits["decision"]:
        warnings.append("Decision summary is not clearly sectioned.")
    if not hits["constraints"]:
        warnings.append("Objective, constraints, options, or tradeoffs are not clearly sectioned.")
    if not hits["evidence"]:
        warnings.append("Evidence, assumptions, or hypotheses are not clearly sectioned.")
    if not hits["edge_cases"]:
        warnings.append("Edge cases or failure/recovery states are not clearly sectioned.")
    if clarifications:
        warnings.append(f"Found {len(clarifications)} assumption/open-question clarification marker(s); ensure they are intentional.")
    if vague:
        warnings.append(f"Found {len(vague)} vague quality term(s); verify each has observable criteria.")
    if implementation_terms:
        warnings.append(f"Found {len(implementation_terms)} possible implementation-detail term(s); verify they are constraints or suggestions.")

    return {
        "ok": not errors,
        "path": str(path),
        "summary": {
            "line_count": len(lines),
            "heading_count": len(found_headings),
            "stable_id_counts": {kind: len(values) for kind, values in ids.items()},
            "acceptance_criteria_count": max(len(ids.get("AC", [])), len(ac_lines)),
            "placeholder_count": len(placeholders),
            "warning_count": len(warnings),
            "error_count": len(errors),
        },
        "sections": {
            "headings": [{"level": h.level, "title": h.title, "line": h.line} for h in found_headings],
            "groups": hits,
        },
        "ids": ids,
        "findings": {
            "errors": errors,
            "warnings": warnings,
            "placeholders": placeholders[:50],
            "clarification_markers": clarifications[:50],
            "vague_terms": vague[:50],
            "implementation_terms": implementation_terms[:50],
            "acceptance_criteria_lines": ac_lines[:100],
        },
    }


def inspect_command(args: argparse.Namespace) -> int:
    path = Path(args.file)
    if not path.exists():
        print(json.dumps({"ok": False, "errors": [f"missing file: {path}"]}, indent=2))
        return 1
    report = inspect_markdown(path)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect", help="inspect a Markdown product spec artifact")
    inspect.add_argument("file", help="Markdown file to inspect")
    inspect.add_argument("--out", help="optional JSON report path")
    inspect.set_defaults(func=inspect_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
