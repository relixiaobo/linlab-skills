# Formula Modeling

## Formula Principles

- Keep formulas live when the workbook is a model.
- Use values only for frozen reports, exports, or immutable source snapshots.
- Prefer named ranges, structured table references, and stable helper columns
  over brittle cell coordinates.
- Keep assumptions out of formulas when they should be user-editable inputs.
- Use check cells for totals, reconciliations, and important outputs.

## Formula Risk Patterns

Flag these before delivery:

- `#REF!`, `#DIV/0!`, `#VALUE!`, `#NAME?`, `#N/A`, or other error literals
- external workbook links such as `[other.xlsx]Sheet1!A1`
- volatile functions such as `NOW`, `TODAY`, `RAND`, `RANDBETWEEN`, `OFFSET`,
  `INDIRECT`, and `INFO`
- formulas copied inconsistently down a repeated range
- formulas pointing into blank source areas
- hidden sheets containing active logic
- circular references unless intentionally documented
- array/dynamic formulas when the target environment may not support them

## Named Ranges

Use named ranges for important inputs and outputs:

- scenario controls
- rates and assumptions
- output metrics
- print/export areas
- validation lists

Names should be descriptive, stable, and scoped intentionally. Avoid names that
collide with cell references or are only meaningful to the author.

## Calculation Verification

Formula evaluation outside Excel is limited. Use the strongest available route:

1. Open/recalculate with Excel, LibreOffice, Google Sheets, or a host spreadsheet
   tool when available.
2. Use a formula evaluator only when its supported function set covers the
   workbook.
3. Independently recompute key outputs with Python/SQL when source data and
   formulas are simple enough.
4. At minimum, inspect formulas, error cells, links, named ranges, and check
   totals; state that full recalculation was not available.

Do not claim formulas were validated merely because the XLSX package opened.
