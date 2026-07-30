# XLSX Operations

XLSX files are ZIP packages of workbook parts, worksheets, relationships,
styles, shared strings, tables, charts, comments, drawings, calculation chain,
and content types. Treat them as structured packages, not as single flat files.

## Inspect First

Use:

```bash
python3 scripts/workbook_tool.py inspect input.xlsx --out report.json
```

Read the report for:

- sheet names, dimensions, hidden state, and protection
- formula counts and formula error markers
- named ranges
- tables and autofilters
- data validation
- comments, merged cells, hyperlinks, and external relationships
- charts, drawings, pivots, macros, and unsupported features
- calculation mode and stale calculation risks

For formula workbooks, prefer a real recalculation pass before delivery:

```bash
python3 scripts/workbook_tool.py recalc input.xlsx --output recalculated.xlsx --out recalc-report.json
```

This command uses LibreOffice when available and then runs the same package
inspection on the recalculated file. If LibreOffice is unavailable, use Excel,
Google Sheets, or another real spreadsheet engine when possible; otherwise
state that only structural formula checks were possible.

## Editing Rules

- Preserve `xl/workbook.xml`, styles, shared strings, table parts,
  relationships, comments, drawings, charts, pivots, and calculation settings
  unless the edit intentionally changes them.
- Do not drop workbook features merely because a library cannot round-trip them.
- Prefer stable anchors: sheet name, table name, named range, header name,
  row/column coordinate, or unique cell label plus nearby context.
- Avoid blind global find/replace in worksheet XML.
- Repack the ZIP with original internal path names when doing package-level
  repairs.
- Verify by opening, recalculating, exporting, rendering, or re-inspecting when
  possible.

## Tool Selection

- XlsxWriter: strong for creating new XLSX files, formatting, charts, tables,
  validation, comments, and memory-efficient generation. It is not for editing
  existing XLSX files.
- openpyxl: useful for reading/editing many XLSX files, formulas as formulas,
  styles, tables, and validation; verify feature preservation for charts,
  pivots, macros, and complex files.
- ExcelJS: useful for JavaScript workbook creation/editing and style/table
  workflows; verify unsupported features before using it on complex templates.
- SheetJS: useful for broad spreadsheet data extraction and generation; treat
  advanced styling/pivot/formula behavior as capability-dependent.
- calamine/python-calamine: useful for fast read-only extraction across Excel
  and ODS formats; not an editing path.

## Package Risks

Common failure modes:

- formulas overwritten by cached values
- formulas left stale because the workbook was not recalculated
- formula errors missed because only the package XML was inspected
- named ranges broken or changed scope
- external links missing or unintended
- tables resized incorrectly
- data validation dropped
- charts/pivots not updated after data range changes
- hidden sheets carrying undocumented logic
- protected sheets preventing intended user input
- CSV export losing leading zeroes, dates, or precision
