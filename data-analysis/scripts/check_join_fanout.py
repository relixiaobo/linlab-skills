#!/usr/bin/env python3
"""Check cardinality, NULL-key drops, unmatched keys, and fan-out before joining two local files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    import duckdb
except ImportError as exc:  # pragma: no cover
    raise SystemExit("duckdb is required: pip install duckdb") from exc


def parse_alias_path(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise SystemExit(f"Expected alias=path, got: {value}")
    alias, path = value.split("=", 1)
    return alias, Path(path)


def relation_sql(path: Path) -> str:
    suffix = path.suffix.lower()
    escaped = str(path).replace("'", "''")
    if suffix in {".csv", ".tsv"}:
        delim = "\\t" if suffix == ".tsv" else ","
        return f"read_csv_auto('{escaped}', delim='{delim}')"
    if suffix in {".parquet", ".pq"}:
        return f"read_parquet('{escaped}')"
    if suffix in {".json", ".jsonl", ".ndjson"}:
        return f"read_json_auto('{escaped}')"
    raise SystemExit(f"Unsupported file type: {path}")


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def classify_cardinality(left_unique: bool, right_unique: bool) -> str:
    if left_unique and right_unique:
        return "1:1"
    if left_unique and not right_unique:
        return "1:N (one left row matches many right rows)"
    if not left_unique and right_unique:
        return "N:1 (many left rows match one right row)"
    return "N:N (many-to-many — aggregate one side to its key grain before joining)"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--left", required=True, help="alias=path for left table")
    parser.add_argument("--right", required=True, help="alias=path for right table")
    parser.add_argument("--left-key", required=True)
    parser.add_argument("--right-key", required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    left_alias, left_path = parse_alias_path(args.left)
    right_alias, right_path = parse_alias_path(args.right)
    left_rel = relation_sql(left_path)
    right_rel = relation_sql(right_path)
    lk = quote_ident(args.left_key)
    rk = quote_ident(args.right_key)

    con = duckdb.connect(":memory:")
    metrics = con.execute(
        f"""
        with
        l as (select * from {left_rel}),
        r as (select * from {right_rel}),
        lk as (select {lk} as k from l),
        rk as (select {rk} as k from r)
        select
          (select count(*) from l) as left_rows,
          (select count(distinct k) from lk where k is not null) as left_distinct,
          (select count(*) from lk where k is null) as left_nulls,
          (select count(*) from r) as right_rows,
          (select count(distinct k) from rk where k is not null) as right_distinct,
          (select count(*) from rk where k is null) as right_nulls,
          (select count(*) from l join r on l.{lk} = r.{rk}) as inner_rows,
          (select count(*) from l left join r on l.{lk} = r.{rk}) as left_join_rows,
          (select count(distinct k) from lk
             where k is not null and k not in (select k from rk where k is not null)) as left_unmatched_keys,
          (select count(distinct k) from rk
             where k is not null and k not in (select k from lk where k is not null)) as right_unmatched_keys,
          (select max(c) from (select count(*) as c from l group by {lk})) as max_left_fanout,
          (select max(c) from (select count(*) as c from r group by {rk})) as max_right_fanout
        """
    ).fetchone()
    con.close()

    (left_rows, left_distinct, left_nulls, right_rows, right_distinct, right_nulls,
     inner_rows, left_join_rows, left_unmatched_keys, right_unmatched_keys,
     max_left_fanout, max_right_fanout) = metrics

    left_dup_key_rows = left_rows - left_distinct - left_nulls
    right_dup_key_rows = right_rows - right_distinct - right_nulls
    left_unique = left_dup_key_rows == 0
    right_unique = right_dup_key_rows == 0
    ratio = (inner_rows / left_rows) if left_rows else None
    left_rows_dropped_by_inner = left_join_rows - inner_rows

    warnings: list[str] = []
    if ratio is not None and ratio > 1.05:
        warnings.append(
            f"Inner join inflates rows {left_rows} -> {inner_rows} (ratio {ratio:.2f}). "
            "Summing a left-table measure after this join double-counts; aggregate to grain first."
        )
    if left_nulls:
        warnings.append(f"{left_nulls} left rows have a NULL join key and are dropped by inner/right joins.")
    if right_nulls:
        warnings.append(f"{right_nulls} right rows have a NULL join key and are dropped by inner/left joins.")
    if left_unmatched_keys:
        warnings.append(f"{left_unmatched_keys} distinct left keys have no match on the right (inner join drops their rows).")
    if right_unmatched_keys:
        warnings.append(f"{right_unmatched_keys} distinct right keys have no match on the left.")
    if not left_unique and not right_unique:
        warnings.append("Many-to-many join: aggregate one side to its key grain before joining.")

    result = {
        "left": {
            "alias": left_alias, "path": str(left_path), "key": args.left_key,
            "rows": left_rows, "distinct_keys": left_distinct, "null_keys": left_nulls,
            "duplicate_key_rows": left_dup_key_rows, "unmatched_keys": left_unmatched_keys,
            "max_fanout_per_key": max_left_fanout, "unique_key": left_unique,
        },
        "right": {
            "alias": right_alias, "path": str(right_path), "key": args.right_key,
            "rows": right_rows, "distinct_keys": right_distinct, "null_keys": right_nulls,
            "duplicate_key_rows": right_dup_key_rows, "unmatched_keys": right_unmatched_keys,
            "max_fanout_per_key": max_right_fanout, "unique_key": right_unique,
        },
        "cardinality": classify_cardinality(left_unique, right_unique),
        "join": {
            "inner_rows": inner_rows,
            "left_join_rows": left_join_rows,
            "left_rows_dropped_by_inner_join": left_rows_dropped_by_inner,
            "join_to_left_row_ratio": ratio,
        },
        "fanout_risk": ratio is not None and ratio > 1.05,
        "warnings": warnings,
    }

    output = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output, encoding="utf-8")
        print(f"Wrote {args.out}")
    print(output)


if __name__ == "__main__":
    main()
