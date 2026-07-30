#!/usr/bin/env python3
"""Run a read-only SQL query against a database URL (DATABASE_URL by default).

Mirrors query_duckdb.py for real databases. It refuses mutating SQL, opens a
best-effort read-only transaction, and never commits. This is an accident
guardrail, not a substitute for a genuinely read-only database account.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from _sqlsafe import UnsafeSQLError, assert_safe
from _tableio import render

try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import SQLAlchemyError
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "sqlalchemy is required for database access: pip install sqlalchemy "
        "(plus a driver, e.g. psycopg2-binary for Postgres or pymysql for MySQL)"
    ) from exc

try:
    import pandas as pd
except ImportError as exc:  # pragma: no cover
    raise SystemExit("pandas is required: pip install pandas") from exc


# Best-effort per-engine statement to force a read-only session.
READ_ONLY_SETUP = {
    "postgresql": "set transaction read only",
    "mysql": "set session transaction read only",
}


def redact(url: str) -> str:
    """Hide credentials when echoing the connection target."""
    if "@" in url and "://" in url:
        scheme, rest = url.split("://", 1)
        return f"{scheme}://***@{rest.split('@', 1)[1]}"
    return url


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=os.environ.get("DATABASE_URL"), help="SQLAlchemy URL (default: $DATABASE_URL)")
    parser.add_argument("--sql")
    parser.add_argument("--sql-file", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--format", choices=["markdown", "csv", "json"], default="markdown")
    parser.add_argument("--max-rows", type=int, default=1000, help="Truncate output to this many rows")
    args = parser.parse_args()

    if not args.url:
        raise SystemExit("No database URL. Pass --url or set DATABASE_URL.")
    if not args.sql and not args.sql_file:
        raise SystemExit("Provide --sql or --sql-file")
    sql = args.sql if args.sql is not None else args.sql_file.read_text(encoding="utf-8")
    try:
        assert_safe(sql)
    except UnsafeSQLError as exc:
        raise SystemExit(str(exc)) from exc

    engine = create_engine(args.url)
    backend = engine.url.get_backend_name()
    try:
        with engine.connect() as conn:
            transaction = conn.begin()
            try:
                setup = READ_ONLY_SETUP.get(backend)
                if setup:
                    try:
                        conn.execute(text(setup))
                    except SQLAlchemyError:
                        pass  # not all engines/permissions support it; guard stays in assert_safe
                df = pd.read_sql(text(sql), conn)
            finally:
                transaction.rollback()  # never commit
    finally:
        engine.dispose()

    truncated = len(df) > args.max_rows
    if truncated:
        df = df.head(args.max_rows)
    output = render(df, args.format)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output, encoding="utf-8")
        print(f"Wrote {args.out} ({len(df)} rows from {redact(args.url)})")
    else:
        print(output)
    if truncated:
        print(f"\n[truncated to {args.max_rows} rows; add LIMIT/aggregation to the query for full results]")


if __name__ == "__main__":
    main()
