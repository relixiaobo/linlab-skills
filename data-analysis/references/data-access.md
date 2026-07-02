# Data Access

Use the least powerful access path that answers the question.

## Local Files

Preferred order:

1. DuckDB SQL for CSV, Parquet, JSON, and multi-file joins.
2. pandas/polars for profiling, Excel, custom cleaning, and stats.
3. SQLite/DuckDB database files when already present.

Before analysis:

- Detect file type and encoding.
- Confirm sheet name for Excel.
- Profile sample and full shape.
- Treat input files as read-only.
- Write outputs under `analysis_runs/<run_id>/`.

## Read-Only Databases

Before querying:

- Locate connection config without printing secrets.
- Verify the account is read-only when possible.
- Discover schemas/tables/columns before writing SQL.
- Prefer semantic metrics or documented definitions.
- Ask for metric definitions if missing.

Do not run DDL/DML:

- No `CREATE`, `ALTER`, `DROP`, `INSERT`, `UPDATE`, `DELETE`, `MERGE`, `TRUNCATE`, `GRANT`, `REVOKE`, `CALL`, or external export commands unless the user explicitly asks and the environment is safe.

`scripts/query_database.py` runs read-only SQL over `DATABASE_URL` (or `--url`): it rejects mutating statements, opens a best-effort read-only transaction, and never commits. The rejection check (shared with `query_duckdb.py`) is a **guardrail against accidents, not a security sandbox** — for real isolation use a genuinely read-only database account. Prefer that account when one is available.

## Semantic Layer

If a semantic layer or metric catalog exists (`semantic/metrics.yaml`, dbt MetricFlow, Cube, Looker/LookML, AtScale, or similar), inspect it before writing raw metric SQL.

Minimum metric definition (capture a discovered or confirmed metric in `assets/templates/metric_definition.yaml`):

- Name.
- Description.
- Expression.
- Grain.
- Time column.
- Filters.
- Known exclusions.
- Owner/source.

If the analysis discovers a durable business rule, append it to the run notes and ask before promoting it to permanent semantic context.

## Large Data

- Start with schema and sample.
- Use limits for exploratory row output.
- Use aggregate queries for counts and distributions.
- Avoid loading full large tables into memory.
- Save result extracts with row counts and filters in filenames or metadata.

