# PDF Workflow

## Task Routing

Use the PDF route when the PDF itself is the artifact, evidence, or fixed-layout
deliverable.

Common routes:

- `inspect`: inventory structure, metadata, pages, text/image signals, forms,
  annotations, links, attachments, encryption, and risk markers
- `extract`: produce text, tables, images, citations, or page-coordinate data
- `visual-qa`: render pages and check layout fidelity after export or editing
- `page-ops`: merge, split, rotate, crop, reorder, watermark, encrypt, decrypt,
  repair, optimize, or linearize
- `forms`: fill AcroForm fields or overlay text/checkmarks on non-fillable forms
- `redaction`: permanently remove sensitive content and verify removal
- `ocr`: convert scanned/image PDFs into searchable PDFs
- `create`: generate a new PDF from source content, HTML, Markdown, data, or a
  drawing/layout library

## Source Of Truth

- If a PDF came from DOCX, PPTX, XLSX, Markdown, HTML, LaTeX, or source code and
  content/layout must change, edit the source and regenerate PDF.
- If only a PDF exists, perform PDF-native operations and document limitations.
- If PDF output is only for signoff, keep the editable source next to the PDF.
- If extracting evidence, preserve page numbers and source filenames.

## Inspect-First Flow

1. Run `scripts/pdf_tool.py inspect` on the input.
2. Decide whether the PDF is text-based, image-heavy, encrypted, malformed,
   form-based, or annotation-heavy.
3. Choose a tool path from `tool-selection.md`.
4. Make the change or extraction.
5. Re-inspect the output.
6. Render pages with `scripts/pdf_tool.py render` or another viewer.
7. Report checks, issues, and limitations.

## Handoff

For non-trivial work, keep:

- original PDF path
- final PDF path
- rendered PNGs or screenshots for QA
- extraction outputs, if any
- verification report compatible with
  `assets/schemas/verification-report.schema.json`
