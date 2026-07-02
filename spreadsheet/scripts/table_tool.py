#!/usr/bin/env python3
"""Portable flat-table inspection helper for the spreadsheet skill."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

FORMULA_INJECTION_RE = re.compile(r"^[=+\-@]")
INT_RE = re.compile(r"^[+-]?\d+$")
FLOAT_RE = re.compile(r"^[+-]?(?:\d+\.\d*|\d*\.\d+)(?:[eE][+-]?\d+)?$")
DATE_HINT_RE = re.compile(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}$")
LEADING_ZERO_RE = re.compile(r"^0\d+$")


def guess_dialect(sample: str) -> csv.Dialect:
    try:
        return csv.Sniffer().sniff(sample, delimiters=",\t;|")
    except csv.Error:
        return csv.get_dialect("excel")


def classify(values: list[str]) -> str:
    non_empty = [value.strip() for value in values if value.strip() != ""]
    if not non_empty:
        return "empty"
    if any(LEADING_ZERO_RE.match(value) for value in non_empty):
        return "text_with_leading_zero"
    if all(INT_RE.match(value) for value in non_empty):
        return "integer"
    if all(INT_RE.match(value) or FLOAT_RE.match(value) for value in non_empty):
        return "number"
    if all(DATE_HINT_RE.match(value) for value in non_empty):
        return "date"
    if len(set(non_empty)) <= max(20, len(non_empty) * 0.2):
        return "category"
    return "text"


def inspect_table(path: Path, max_rows: int = 10000) -> dict[str, Any]:
    result: dict[str, Any] = {
        "file": str(path),
        "ok": False,
        "errors": [],
        "warnings": [],
        "delimiter": None,
        "encoding": "utf-8",
        "row_count": 0,
        "column_count": 0,
        "headers": [],
        "duplicate_headers": [],
        "blank_header_count": 0,
        "blank_row_count": 0,
        "ragged_row_count": 0,
        "formula_like_cell_count": 0,
        "leading_zero_cell_count": 0,
        "columns": [],
        "sample_limit_reached": False,
    }
    if not path.exists():
        result["errors"].append("file_not_found")
        return result

    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = path.read_text(encoding="latin-1")
            result["encoding"] = "latin-1"
            result["warnings"].append("non_utf8_encoding")
        except UnicodeDecodeError:
            result["errors"].append("could_not_decode")
            return result

    dialect = guess_dialect(text[:8192])
    result["delimiter"] = getattr(dialect, "delimiter", ",")
    rows = list(csv.reader(text.splitlines(), dialect))
    if not rows:
        result["errors"].append("empty_file")
        return result

    headers = [cell.strip() for cell in rows[0]]
    result["headers"] = headers
    result["column_count"] = len(headers)
    header_counts = Counter(header.lower() for header in headers if header)
    result["duplicate_headers"] = sorted(header for header, count in header_counts.items() if count > 1)
    result["blank_header_count"] = sum(1 for header in headers if not header)

    columns = [[] for _ in headers]
    for index, row in enumerate(rows[1:], start=2):
        if index > max_rows + 1:
            result["sample_limit_reached"] = True
            break
        if not row or all(cell.strip() == "" for cell in row):
            result["blank_row_count"] += 1
            continue
        if len(row) != len(headers):
            result["ragged_row_count"] += 1
        for col_index in range(len(headers)):
            value = row[col_index] if col_index < len(row) else ""
            columns[col_index].append(value)
            if FORMULA_INJECTION_RE.match(value.strip()):
                result["formula_like_cell_count"] += 1
            if LEADING_ZERO_RE.match(value.strip()):
                result["leading_zero_cell_count"] += 1
        result["row_count"] += 1

    for header, values in zip(headers, columns):
        non_empty = [value for value in values if value.strip()]
        result["columns"].append({
            "name": header,
            "type_guess": classify(values),
            "non_empty_count": len(non_empty),
            "missing_count": len(values) - len(non_empty),
            "unique_count": len(set(non_empty)),
            "sample_values": non_empty[:5],
        })

    if result["duplicate_headers"]:
        result["warnings"].append("duplicate_headers")
    if result["blank_header_count"]:
        result["warnings"].append("blank_headers")
    if result["blank_row_count"]:
        result["warnings"].append("blank_rows")
    if result["ragged_row_count"]:
        result["warnings"].append("ragged_rows")
    if result["formula_like_cell_count"]:
        result["warnings"].append("formula_like_cells")
    if result["leading_zero_cell_count"]:
        result["warnings"].append("leading_zero_cells")
    result["ok"] = not result["errors"]
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a CSV/TSV-style table.")
    sub = parser.add_subparsers(dest="command", required=True)
    inspect_cmd = sub.add_parser("inspect", help="Inspect table structure.")
    inspect_cmd.add_argument("file")
    inspect_cmd.add_argument("--out", default="-")
    inspect_cmd.add_argument("--max-rows", type=int, default=10000)
    args = parser.parse_args()

    report = inspect_table(Path(args.file), max_rows=args.max_rows)
    data = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out == "-":
        print(data)
    else:
        Path(args.out).write_text(data + "\n", encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
