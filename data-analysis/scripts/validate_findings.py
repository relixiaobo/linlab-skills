#!/usr/bin/env python3
"""Validate a findings ledger TSV for evidence, verification, and caveats."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


REQUIRED = ["id", "claim", "computation", "evidence", "verification", "caveat", "status"]
VALID_STATUSES = {"verified", "refuted", "needs_followup"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("--json", action="store_true", help="Print JSON result")
    args = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []

    with args.ledger.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        fields = reader.fieldnames or []
        missing = [field for field in REQUIRED if field not in fields]
        if missing:
            errors.append(f"Missing required columns: {', '.join(missing)}")
        rows = list(reader)

    if not rows:
        warnings.append("Ledger has no findings.")

    for idx, row in enumerate(rows, start=2):
        row_id = row.get("id") or f"line {idx}"
        for field in REQUIRED:
            if field in fields and not (row.get(field) or "").strip():
                errors.append(f"{row_id}: empty {field}")
        status = (row.get("status") or "").strip()
        if status and status not in VALID_STATUSES:
            errors.append(f"{row_id}: invalid status {status}")
        if status == "verified":
            if len((row.get("evidence") or "").strip()) < 10:
                warnings.append(f"{row_id}: verified finding has thin evidence")
            if len((row.get("verification") or "").strip()) < 10:
                warnings.append(f"{row_id}: verified finding has thin verification")

    result = {"ok": not errors, "errors": errors, "warnings": warnings, "rows": len(rows)}

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("OK" if result["ok"] else "FAILED")
        for error in errors:
            print(f"ERROR: {error}")
        for warning in warnings:
            print(f"WARNING: {warning}")

    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

