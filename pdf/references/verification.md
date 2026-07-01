# PDF Verification

Approach PDF verification as visual fidelity plus structural preservation.

## Universal Checks

- source of truth is explicit
- page count matches intent
- page sizes, orientation, crop boxes, and rotation are intentional
- metadata changes are intentional
- encryption/password state is intentional
- text extractability matches expectations
- links, bookmarks, annotations, attachments, forms, and signatures are
  preserved or intentionally changed
- final artifact opens or renders with available tools

## Visual Checks

- render representative pages; render every page for short or high-stakes PDFs
- check clipped text, missing glyphs, black boxes, overlap, broken images,
  low-resolution assets, table breaks, margins, headers, and footers
- check first page, last page, all edited pages, all pages with changed
  orientation/size, and random interior pages for long documents

## Extraction Checks

- compare extracted text length and representative paragraphs before/after
  when editing
- verify tables against rendered pages
- keep page references with extracted evidence
- treat empty extraction from image-only pages as an OCR requirement, not as no
  content

## Delivery Report

When emitting JSON, follow `assets/schemas/verification-report.schema.json`.

Include:

- `artifact`: final artifact path
- `outputRoute`: pdf, png-renders, text, csv, json, images, or mixed
- `filesProduced`: produced deliverables
- `sourceFiles`: source PDFs or editable sources
- `checks`: check objects with name, status, tool, and evidence or result
- `issues`: issues found, including fixed issues
- `limitations`: checks not possible in the current environment
- `finalStatus`: passed, warning, or failed
