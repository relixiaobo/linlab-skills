# Spreadsheet Workflow

## Decision Flow

1. Define the workbook purpose, owner, users, and handoff format.
2. Decide source of truth: source-first workbook project, native XLSX, flat
   CSV/TSV/JSON data, or audit report.
3. Extract source data, assumptions, units, date/currency conventions, sheet
   roles, formulas, named ranges, validation, protected ranges, and risks.
4. Choose workbook archetype, sheet roles, and output route.
5. Create a workbook plan before building or editing.
6. Build or edit from the plan.
7. Verify structure, formulas, validation, links, protection, source coverage,
   and format-specific risks.
8. Fix concrete issues and recheck.

## Workbook Plan Schema

When emitting JSON, follow `assets/schemas/workbook-plan.schema.json`.

Capture:

- `title`: workbook title
- `audience`: intended users
- `goal`: decision, calculation, reporting, data entry, or exchange outcome
- `sourceOfTruth`: source-first, native-xlsx, flat-data, google-sheets, or mixed
- `outputRoute`: xlsx, csv, tsv, json, pdf, workbook-spec, or mixed
- `workbookType`: model, tracker, template, report, dashboard, import-export,
  reconciliation, or audit
- `sourceData`: input files, tables, systems, and refresh expectations
- `metadata`: owner, date, version, status, currency, units, timezone, template
- `sheets`: sheet objects with name, purpose, role, inputs, outputs, formulas,
  validation, protection, and notes
- `verificationPlan`: checks to run before delivery

## Creation Pattern

- Separate inputs, assumptions, calculations, outputs, lookup/reference data,
  and documentation.
- Put source data in tables with stable headers before formulas reference it.
- Use named ranges for important user inputs and outputs.
- Use data validation for constrained inputs.
- Use formulas for live calculations; use values only when the output is meant
  to be static.
- Keep formulas readable and copy-safe. Avoid hidden helper logic unless it is
  documented.
- Freeze panes and set filters for workbooks humans will inspect.

## Existing Workbook Pattern

- Inspect workbook package and visible structure before editing.
- Preserve sheet names, formulas, named ranges, tables, validation, charts,
  comments, pivots, macros, external links, and protection unless the user asks
  to change them.
- Do not edit by blind global text replacement in XML.
- Edit source data, named ranges, or stable table coordinates before editing
  scattered formulas.
- Save to a new file unless the user explicitly asks to overwrite.
- Re-inspect and report features preserved, changed, or not verifiable.

## Flat Data Pattern

- Use CSV/TSV only for flat records.
- Preserve header row, delimiter, encoding, units, date formats, and null
  conventions.
- Check duplicate headers, blank rows, formula-injection-like cells, and type
  drift before using a file as source data.
- If a flat file needs formulas, validation, multiple tables, or formatted
  presentation, move to XLSX or a source-first workbook project.

## Delivery Report

When finished, report:

- artifact path
- output route
- source data used
- formulas or workbook features added/changed
- verification performed
- known limitations
