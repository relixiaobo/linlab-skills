---
name: spreadsheet
description: Create, edit, inspect, validate, or package spreadsheet workbooks and calculable tabular models, including Excel/XLSX, CSV-based workbook sources, Google Sheets-targeted models, formulas, named ranges, data validation, tables, pivots, charts, imports, exports, workbook QA, and spreadsheet-driven templates. Use when the spreadsheet itself is the durable artifact or calculation model, not when a table is merely embedded in a document or slide.
---

# Spreadsheet

## Overview

Build spreadsheets as durable calculation and data-entry artifacts. Treat XLSX,
CSV, JSON, and source scripts as delivery routes selected by model complexity,
editability, formulas, validation, and handoff risk.

Default to source-first workbooks when possible: keep a workbook spec, input
data, and generation script together so another agent can inspect, revise, and
regenerate the XLSX. Use native workbook editing when the user's existing file,
formulas, formatting, comments, data validation, pivots, or template fidelity
are the source of truth.

## Route

1. Identify the job: create workbook, edit workbook, inspect/audit, fix formulas,
   clean/import data, build a template, generate XLSX from source data, export
   CSV, compare workbooks, or package for handoff.
2. Classify the workbook surface:
   - source-first: workbook spec plus data/script remains primary; XLSX is a
     generated deliverable
   - native workbook: edit the existing XLSX/Sheets export directly because
     formulas, styles, validation, comments, or template fidelity are the job
   - tabular exchange: CSV/TSV/JSON/Parquet is the artifact; formulas and
     workbook features are not required
   - audit/QA: inspect a workbook for structure, formulas, ranges, links,
     validation, protection, and calculation risks
3. Extract owner, audience, source data, workbook purpose, sheets, input areas,
   output areas, formulas, assumptions, units, date/currency conventions,
   validation rules, protected ranges, and required handoff format.
4. For existing workbooks, inspect before editing:
   `python3 {baseDir}/scripts/workbook_tool.py inspect path/to/file.xlsx --out report.json`
   when useful. For CSV/TSV inputs, use
   `python3 {baseDir}/scripts/table_tool.py inspect path/to/file.csv --out report.json`.
5. Create a workbook plan before building or editing. If emitting JSON, keep it
   compatible with `{baseDir}/assets/schemas/workbook-plan.schema.json`.
6. Choose the output route:
   - Use XLSX when formulas, formatting, tables, charts, validation, multiple
     sheets, protection, or Excel/Sheets handoff matter.
   - Use CSV/TSV only for flat data exchange with no formulas, styles, merged
     cells, or multi-sheet behavior.
   - Use a workbook spec plus generation script when the workbook will be
     regenerated from data or maintained by agents.
   - Use PDF only for fixed-layout print or signoff after the workbook is stable.
7. Build or edit with appropriate tools:
   - For new XLSX generation, prefer XlsxWriter, openpyxl, ExcelJS, SheetJS, or
     a host spreadsheet tool available in the task environment.
   - For existing XLSX edits, prefer a library or host tool that preserves
     workbook features required by the task. Do not silently drop macros,
     pivots, charts, comments, validation, formulas, named ranges, protection,
     or external links.
   - For formula workbooks, keep calculations as spreadsheet formulas instead
     of hardcoding Python/JS-computed results unless the user asks for a static
     export.
   - For formula evaluation, prefer a real spreadsheet engine: Excel,
     LibreOffice, Google Sheets, or host spreadsheet automation. Use a formula
     evaluator only when its function coverage matches the workbook. Otherwise
     inspect formulas and state calculation limits.
8. Verify before delivering. At minimum check sheet structure, row/column
   bounds, formulas, named ranges, data validation, tables, external links,
   hidden/protected sheets, blank/error hotspots, source data coverage, and
   open/render limits. For workbooks with formulas, recalculate with a real
   spreadsheet engine when available and scan for formula errors.

## References

Load only the reference needed for the current route:

- `references/workflow.md` for planning, creation, editing, and delivery flow.
- `references/workbook-system.md` for workbook archetypes, sheet roles,
  source-first structure, and model design rules.
- `references/formula-modeling.md` for formulas, named ranges, assumptions,
  dependency risks, formula copy patterns, and calculation limits.
- `references/data-intake.md` for CSV/XLSX/JSON imports, column contracts, type
  inference, joins, refresh areas, and source data packaging.
- `references/xlsx-operations.md` for XLSX package inspection, workbook feature
  preservation, and native edit risks.
- `references/verification.md` for workbook QA and delivery reports.

## Scripts

- `python3 {baseDir}/scripts/workbook_tool.py inspect file.xlsx --out report.json`
  inspects XLSX structure, sheets, dimensions, formulas, named ranges, tables,
  validation, comments, links, hidden/protected sheets, merged cells, and risk
  markers.
- `python3 {baseDir}/scripts/workbook_tool.py recalc file.xlsx --output recalculated.xlsx --out report.json`
  recalculates through LibreOffice when `soffice` or `libreoffice` is installed,
  then re-inspects the result. If LibreOffice is unavailable, report the
  limitation and use structural inspection plus targeted formula checks.
- `python3 {baseDir}/scripts/table_tool.py inspect file.csv --out report.json`
  inspects flat CSV/TSV data for dimensions, headers, type guesses, missingness,
  duplicate headers, blank rows, and formula-injection-like cells.

The scripts are portable baseline tools. They do not replace Excel,
LibreOffice, Google Sheets, or formula engines. If local tools can open,
recalculate, render, or export the workbook, use them and keep the same final
verification discipline.

## Quality Bar

- Do not deliver a workbook whose source data, assumptions, units, or date
  windows are unclear.
- Keep source of truth explicit: workbook spec/source script, native XLSX, or
  flat data file.
- Preserve workbook semantics: formulas stay formulas, tables stay tables,
  validation stays validation, named ranges stay named ranges.
- Keep inputs, calculations, outputs, assumptions, and references separated by
  sheet or by clearly labeled ranges.
- Prefer named ranges and structured tables over fragile hard-coded cell
  references for important inputs and outputs.
- Do not silently overwrite formulas with stale cached values.
- Do not claim zero formula errors unless a recalculation or equivalent
  independent formula check was actually performed.
- Do not leave `#REF!`, `#DIV/0!`, `#VALUE!`, broken external links, accidental
  hidden sheets, or unprotected input cells unless intentional and reported.
- State calculation limitations plainly when formula evaluation or visual
  verification is unavailable.
