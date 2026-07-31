# Spreadsheet Verification

Approach verification as a calculation-integrity and workbook-feature pass.

## Universal Checks

- source of truth is clear and available for future revisions
- source data and assumptions are represented faithfully
- sheet roles are clear
- units, dates, currency, timezone, and null conventions are explicit
- input cells and output cells are labeled
- formulas, validation, named ranges, and tables are intentional
- no accidental hidden sheets, broken links, or stale placeholders remain
- final artifact opens or renders when local tools allow it

## XLSX Checks

- inspect package structure with `scripts/workbook_tool.py`
- check sheet dimensions and hidden/protected state
- check formulas, formula errors, volatile functions, and external links
- for formula workbooks, run `scripts/workbook_tool.py recalc` when LibreOffice
  is available, or open/recalculate through Excel, Google Sheets, or another
  real spreadsheet engine
- check named ranges and table ranges
- check data validation, comments, merged cells, hyperlinks, charts, pivots, and
  macros when relevant
- recalculate or independently verify key outputs when possible
- export/render to PDF or screenshots when visual layout matters
- if no real calculation engine is available, list that as a limitation and do
  not describe the workbook as free of formula errors

## CSV/TSV Checks

- inspect flat data with `scripts/table_tool.py`
- check duplicate headers, blank rows, missingness, type guesses, delimiters, and
  formula-injection-like cells
- verify row counts against source expectations
- check leading zeroes, date parsing, precision, and encoding risks

## Delivery Report

When emitting JSON, follow `assets/schemas/verification-report.schema.json`.

Include:

- `artifact`: final artifact path
- `outputRoute`: xlsx, csv, tsv, json, pdf, workbook-spec, or mixed
- `filesProduced`: produced deliverables
- `sourceData`: source inputs used
- `checks`: check objects with name, status, tool, and evidence or result
- `issues`: issues found, including fixed issues
- `limitations`: checks not possible in the current environment
- `finalStatus`: passed, warning, or failed
