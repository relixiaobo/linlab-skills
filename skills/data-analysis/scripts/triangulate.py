#!/usr/bin/env python3
"""Triangulation & reasonableness checks — confirmative (specification) verification.

These verify the SPECIFICATION of an analysis, not its computation. Recomputing a
number a second way (DuckDB <-> pandas) catches implementation bugs but agrees with
itself on a wrong metric / grain / filter — the right answer to the wrong question.
Each check here appeals to an INDEPENDENT reference frame — a known total, the
universe size, the claimed grain, the stated window, an independent magnitude
estimate, a conservation law — so it can catch specification errors recomputation
cannot. Run in VALIDATE, after the Definition Contract is set.

A check is only as good as the independence of its reference. A reference produced
by the same reasoning that did the analysis is NOT independent (mark reconcile
--source estimate and it will say so). Prefer an external/authoritative source, a
prior certified figure, or a raw row count.

Exit code is 1 on FLAG (and 0 on PASS/WARN) so a check can gate a pipeline.

Subcommands:
  reconcile  agg(data.column) must tie to a known --expected total
  coverage   distinct --key entities vs an expected --universe size
  grain      one row == one unit: --key must be unique (no duplication / fan-out)
  window     --date values must fall within --start/--end; flags partial coverage
  magnitude  --value within --orders orders of magnitude (and same sign) as --expected
  parts      sum(data.part-col) must equal --whole (conservation)

Examples:
  python3 triangulate.py reconcile --data orders.csv --column amount --agg sum --expected 104700 --source external
  python3 triangulate.py reconcile --data orders.csv --agg rows --expected 18204     # row count
  python3 triangulate.py coverage  --data orders.csv --key customer_id --universe 5000000
  python3 triangulate.py grain     --data orders.csv --key order_id
  python3 triangulate.py window    --data orders.csv --date order_date --start 2024-01-01 --end 2024-06-30
  python3 triangulate.py magnitude --value 104700 --expected 100000 --orders 1
  python3 triangulate.py parts     --data drivers.csv --part-col contribution --whole 16200 --tol 0.02
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _tableio import read_table  # noqa: E402

try:
    import pandas as pd
except ImportError as exc:  # pragma: no cover
    raise SystemExit("pandas is required: pip install pandas") from exc


def rel_diff(a: float, b: float) -> float:
    denom = max(abs(a), abs(b))
    return 0.0 if denom == 0 else abs(a - b) / denom


# --- checks: each returns a result dict with a "verdict" of PASS / WARN / FLAG ---

def check_reconcile(args) -> dict:
    df = read_table(args.data)
    if args.agg == "rows":
        computed = float(len(df))
        label = "rows"
    else:
        if not args.column:
            raise SystemExit(f"--column is required for --agg {args.agg}")
        if args.column not in df.columns:
            raise SystemExit(f"Column not found: {args.column}")
        col = df[args.column]
        computed = float({
            "sum": col.sum,
            "mean": col.mean,
            "count": lambda: col.notna().sum(),  # NON-NULL values (use --agg rows for row count)
            "nunique": col.nunique,
        }[args.agg]())
        label = f"{args.agg}({args.column})"
    diff = rel_diff(computed, args.expected)
    verdict = "PASS" if diff <= args.tol else "FLAG"
    msg = (f"{label} = {computed:,.6g} vs expected {args.expected:,.6g} "
           f"(rel diff {diff:.2%}, tol {args.tol:.2%})")
    if verdict == "FLAG":
        msg += " — does not reconcile; likely a filter/population/grain difference"
    if args.source == "estimate":
        msg += "  [reference is a self-estimate, NOT independent — confirm against an external source]"
    return {
        "check": "reconcile", "verdict": verdict, "agg": args.agg, "column": args.column,
        "computed": computed, "expected": args.expected, "rel_diff": round(diff, 6),
        "tolerance": args.tol, "source": args.source, "message": msg,
    }


def check_coverage(args) -> dict:
    df = read_table(args.data)
    if args.key not in df.columns:
        raise SystemExit(f"Key not found: {args.key}")
    distinct = int(df[args.key].nunique())
    cov = distinct / args.universe if args.universe else 0.0
    verdict = "PASS" if cov >= args.min_coverage else "FLAG"
    msg = (f"{distinct:,} distinct {args.key} of an expected {args.universe:,.0f} "
           f"({cov:.1%} coverage, min {args.min_coverage:.0%})")
    if verdict == "FLAG":
        msg += f" — {1 - cov:.1%} of the universe is missing; is that expected?"
    return {
        "check": "coverage", "verdict": verdict, "key": args.key, "distinct": distinct,
        "universe": args.universe, "coverage": round(cov, 4),
        "min_coverage": args.min_coverage, "message": msg,
    }


def check_grain(args) -> dict:
    df = read_table(args.data)
    keys = [k.strip() for k in args.key.split(",")]
    missing = [k for k in keys if k not in df.columns]
    if missing:
        raise SystemExit(f"Grain key(s) not found: {', '.join(missing)}")
    rows = len(df)
    null_keys = int(df[keys].isna().any(axis=1).sum())  # NULL keys silently drop from joins/aggregations
    # dropna=False so null rows form their own group instead of vanishing and distorting the count
    sizes = df.groupby(keys, dropna=False).size()
    distinct = int(len(sizes))
    dup_factor = rows / distinct if distinct else float("inf")
    dup_keys = int((sizes > 1).sum())
    if dup_factor > 1.0 + 1e-9:
        verdict = "FLAG"
    elif null_keys > 0:
        verdict = "WARN"
    else:
        verdict = "PASS"
    msg = f"{rows:,} rows / {distinct:,} distinct [{', '.join(keys)}] = {dup_factor:.3g}x"
    if dup_factor > 1.0 + 1e-9:
        msg += f" — {dup_keys:,} key(s) repeat; aggregates over this grain will inflate"
    else:
        msg += " — one row per unit, grain holds"
    if null_keys > 0:
        msg += f"; {null_keys:,} row(s) have a NULL key (these drop silently from joins/aggregations)"
    return {
        "check": "grain", "verdict": verdict, "key": keys, "rows": rows,
        "distinct_keys": distinct, "dup_factor": round(dup_factor, 4),
        "duplicated_keys": dup_keys, "null_keys": null_keys, "message": msg,
    }


def check_window(args) -> dict:
    df = read_table(args.data)
    if args.date not in df.columns:
        raise SystemExit(f"Date column not found: {args.date}")
    # utc=True + drop tz: handles mixed/naive/tz-aware columns without a tz-compare crash
    dates = pd.to_datetime(df[args.date], errors="coerce", utc=True).dt.tz_localize(None)
    n_unparsed = int(dates.isna().sum())
    start = pd.to_datetime(args.start)
    end = pd.to_datetime(args.end)
    if dates.notna().sum() == 0:
        return {"check": "window", "verdict": "FLAG", "date": args.date,
                "message": f"no parseable dates in {args.date} ({n_unparsed:,} unparseable)"}
    actual_min, actual_max = dates.min(), dates.max()
    outside = int(((dates < start) | (dates > end)).sum())
    partial = (actual_min > start) or (actual_max < end)
    if outside > 0:
        verdict = "FLAG"
    elif partial or n_unparsed > 0:
        verdict = "WARN"
    else:
        verdict = "PASS"
    msg = f"data spans {actual_min.date()}..{actual_max.date()} vs stated {start.date()}..{end.date()} (compared in UTC)"
    if outside:
        msg += f" — {outside:,} rows fall OUTSIDE the stated window"
    elif partial:
        msg += " — data does not cover the full window (partial period)"
    if n_unparsed:
        msg += f"; {n_unparsed:,} unparseable dates"
    return {
        "check": "window", "verdict": verdict, "date": args.date,
        "stated_start": str(start.date()), "stated_end": str(end.date()),
        "actual_min": str(actual_min.date()), "actual_max": str(actual_max.date()),
        "rows_outside": outside, "unparsed_dates": n_unparsed, "message": msg,
    }


def check_magnitude(args) -> dict:
    if args.value == 0 or args.expected == 0:
        raise SystemExit("magnitude check needs non-zero --value and --expected")
    ratio = args.value / args.expected
    sign_flip = (args.value > 0) != (args.expected > 0)  # a flipped sign is a specification error
    log_dist = abs(math.log10(abs(ratio)))
    verdict = "FLAG" if (sign_flip or log_dist > args.orders) else "PASS"
    msg = (f"{args.value:,.6g} vs independent estimate {args.expected:,.6g} = {ratio:.3g}x "
           f"({log_dist:.2f} orders of magnitude off, allowed {args.orders})")
    if sign_flip:
        msg += " — SIGN MISMATCH: result and estimate have opposite signs"
    elif verdict == "FLAG":
        msg += " — off by orders of magnitude; suspect grain / population / double-count"
    return {
        "check": "magnitude", "verdict": verdict, "value": args.value, "expected": args.expected,
        "ratio": round(ratio, 4), "orders_off": round(log_dist, 3), "orders_allowed": args.orders,
        "sign_flip": sign_flip, "message": msg,
    }


def check_parts(args) -> dict:
    df = read_table(args.data)
    if args.part_col not in df.columns:
        raise SystemExit(f"Column not found: {args.part_col}")
    total = float(df[args.part_col].sum())
    diff = rel_diff(total, args.whole)
    verdict = "PASS" if diff <= args.tol else "FLAG"
    msg = (f"sum({args.part_col}) = {total:,.6g} vs whole {args.whole:,.6g} "
           f"(rel diff {diff:.2%}, tol {args.tol:.2%})")
    if verdict == "FLAG":
        msg += " — parts do not sum to the whole; a slice is missing or double-counted"
    return {
        "check": "parts", "verdict": verdict, "part_col": args.part_col, "sum_parts": total,
        "whole": args.whole, "rel_diff": round(diff, 6), "tolerance": args.tol, "message": msg,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", action="store_true", help="emit the result as JSON")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("reconcile"); p.set_defaults(fn=check_reconcile)
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--column", help="required unless --agg rows")
    p.add_argument("--agg", choices=["sum", "mean", "count", "nunique", "rows"], default="sum",
                   help="'count' = non-null values; 'rows' = row count")
    p.add_argument("--expected", type=float, required=True)
    p.add_argument("--tol", type=float, default=0.01)
    p.add_argument("--source", choices=["external", "prior", "raw_count", "estimate", "unknown"],
                   default="unknown", help="where the reference came from; 'estimate' is flagged as non-independent")

    p = sub.add_parser("coverage"); p.set_defaults(fn=check_coverage)
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--key", required=True)
    p.add_argument("--universe", type=float, required=True)
    p.add_argument("--min-coverage", type=float, default=0.9, dest="min_coverage")

    p = sub.add_parser("grain"); p.set_defaults(fn=check_grain)
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--key", required=True, help="grain key column(s), comma-separated")

    p = sub.add_parser("window"); p.set_defaults(fn=check_window)
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--date", required=True)
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)

    p = sub.add_parser("magnitude"); p.set_defaults(fn=check_magnitude)
    p.add_argument("--value", type=float, required=True)
    p.add_argument("--expected", type=float, required=True, help="independent Fermi estimate")
    p.add_argument("--orders", type=float, default=1.0)

    p = sub.add_parser("parts"); p.set_defaults(fn=check_parts)
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--part-col", required=True, dest="part_col")
    p.add_argument("--whole", type=float, required=True)
    p.add_argument("--tol", type=float, default=0.01)

    args = parser.parse_args()
    result = args.fn(args)

    if args.json:
        print(json.dumps(result))
    else:
        print(f"[{result['verdict']}] {result['message']}")
    sys.exit(1 if result["verdict"] == "FLAG" else 0)


if __name__ == "__main__":
    main()
