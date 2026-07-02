# Data Intake

Use this before building or auditing a workbook from source data.

## Intake Contract

For each source, record:

- original path or URL
- format and encoding
- row count and column count
- header row and duplicate headers
- date/currency/unit conventions
- null conventions
- filters or extraction limits
- refresh expectation

## File Routes

- CSV/TSV: inspect delimiter, encoding, headers, blank rows, missingness, type
  guesses, and formula-injection-like cells.
- XLSX/XLSM/XLSB/ODS: inspect sheets, dimensions, formulas, tables, validation,
  hidden sheets, external links, and comments before extraction.
- JSON/Parquet: flatten only when the target workbook has a clear table shape.
- Folder/ZIP: inventory files first; import only relevant sources.

## Column Contracts

For import templates and recurring reports, define a column contract:

```markdown
| Column | Required | Type | Allowed values | Example | Notes |
| --- | --- | --- | --- | --- | --- |
| order_id | yes | text | unique | A1001 | preserve leading zeroes |
| order_date | yes | date | ISO date | 2026-07-01 | timezone: Asia/Shanghai |
| amount | yes | decimal | >= 0 | 120.50 | currency: USD |
```

## Safety

- Preserve leading zeroes for IDs and codes.
- Do not let spreadsheet software auto-convert IDs, large integers, dates, or
  gene-like strings unintentionally.
- Treat cells starting with `=`, `+`, `-`, or `@` in external CSV data as
  possible formula injection when exporting to spreadsheets.
- Keep raw source data immutable when building source-first workbook projects.
