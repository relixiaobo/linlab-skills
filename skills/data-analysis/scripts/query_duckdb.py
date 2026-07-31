#!/usr/bin/env python3
"""Run read-only DuckDB SQL over local files or a DuckDB database."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from _sqlsafe import UnsafeSQLError, assert_safe
from _tableio import render

try:
    import duckdb
except ImportError as exc:  # pragma: no cover
    raise SystemExit("duckdb is required: pip install duckdb") from exc


def parse_alias_path(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise SystemExit(f"Expected alias=path, got: {value}")
    alias, path = value.split("=", 1)
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", alias):
        raise SystemExit(f"Invalid alias: {alias}")
    return alias, Path(path)


def register_file(con: duckdb.DuckDBPyConnection, alias: str, path: Path) -> None:
    suffix = path.suffix.lower()
    path_sql = str(path).replace("'", "''")
    if suffix in {".csv", ".tsv"}:
        delim = "\\t" if suffix == ".tsv" else ","
        con.execute(f"create or replace view {alias} as select * from read_csv_auto('{path_sql}', delim='{delim}')")
    elif suffix in {".parquet", ".pq"}:
        con.execute(f"create or replace view {alias} as select * from read_parquet('{path_sql}')")
    elif suffix in {".json", ".jsonl", ".ndjson"}:
        con.execute(f"create or replace view {alias} as select * from read_json_auto('{path_sql}')")
    else:
        raise SystemExit(f"Unsupported DuckDB file type for {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, help="Optional DuckDB database file")
    parser.add_argument("--file", action="append", default=[], help="Register local file as alias=path")
    parser.add_argument("--sql")
    parser.add_argument("--sql-file", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--format", choices=["markdown", "csv", "json"], default="markdown")
    args = parser.parse_args()

    if not args.sql and not args.sql_file:
        raise SystemExit("Provide --sql or --sql-file")
    sql = args.sql if args.sql is not None else args.sql_file.read_text(encoding="utf-8")
    try:
        assert_safe(sql)
    except UnsafeSQLError as exc:
        raise SystemExit(str(exc)) from exc

    db = str(args.database) if args.database else ":memory:"
    con = duckdb.connect(db, read_only=bool(args.database and args.database.exists()))
    try:
        for item in args.file:
            alias, path = parse_alias_path(item)
            register_file(con, alias, path)
        df = con.execute(sql).fetchdf()
    finally:
        con.close()

    output = render(df, args.format)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output, encoding="utf-8")
        print(f"Wrote {args.out}")
        print(json.dumps({"rows": int(df.shape[0]), "columns": int(df.shape[1])}))
    else:
        print(output)


if __name__ == "__main__":
    main()

