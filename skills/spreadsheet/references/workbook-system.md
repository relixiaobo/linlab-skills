# Workbook System

## Archetypes

Choose the workbook shape that matches the user's job:

- `model`: inputs, assumptions, calculations, scenarios, outputs
- `tracker`: records, status, owners, dates, filters, summaries
- `template`: protected structure, input cells, instructions, validation
- `report`: source data, calculations, formatted output sheets
- `dashboard`: metrics, slicer/filter assumptions, charts, refresh notes
- `import_export`: exact headers, types, required/optional fields, validation
- `reconciliation`: source A, source B, mapping, exceptions, summary
- `audit`: workbook inventory, formulas, links, risks, recommendations

## Sheet Roles

Use explicit sheet roles instead of ad-hoc sheets:

- `README`: purpose, owner, version, refresh instructions, assumptions
- `Inputs`: user-entered inputs and scenario controls
- `SourceData`: imported raw data, one table per source when possible
- `Assumptions`: rates, lookups, constants, units, calendar/currency rules
- `Calculations`: intermediate calculations and helper tables
- `Outputs`: final tables for decisions or handoff
- `Dashboard`: charts and summarized metrics
- `Checks`: reconciliation, totals, error flags, validation status
- `Archive`: frozen snapshots when required

## Source-First Workbooks

For agent-maintained workbooks, keep the workbook reproducible:

- Store a workbook plan/spec near source data and generation scripts.
- Keep raw input data separate from generated XLSX output.
- Use stable sheet names, table names, and named ranges.
- Put generated outputs in a `dist/` or clearly labeled output directory.
- Do not manually edit generated XLSX files unless the user makes the XLSX the
  source of truth.

## Model Design Rules

- Put units and date/currency conventions in headers or README notes.
- Label input cells visually and with comments/notes when useful.
- Avoid formulas that depend on visual position alone when named ranges or
  tables would be clearer.
- Avoid merged cells in data tables; use them only for title blocks or
  presentation areas.
- Keep formulas consistent down columns. Mixed formulas in a repeated region are
  a risk unless intentionally documented.
- Use check totals for key calculations and reconciliations.
- Protect formulas and unlock intended input cells when delivering templates.

## Table Rules

- Use workbook tables for repeated records with shared fields.
- Use unique, stable headers.
- Avoid blank rows inside tables.
- Keep one semantic table per area; do not place unrelated tables side by side
  unless the layout is explicitly a report page.
- For import/export templates, include required/optional status, allowed values,
  examples, and type expectations.
