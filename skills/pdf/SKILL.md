---
name: pdf
description: Create, edit, inspect, extract from, repair, render, OCR, combine, split, rotate, redact, fill, validate, or package PDF artifacts. Use when a .pdf file is the primary input or output, when fixed-layout page fidelity matters, when scanned PDFs or form fields are involved, or when another skill exports PDF and needs PDF-level rendering or QA. Do not use for drafting documents, slides, or spreadsheets when their editable source remains the primary artifact.
metadata:
  author: lin
  version: "0.1.0"
---

# PDF

## Overview

Treat PDF as a fixed-layout delivery and evidence format. Unlike DOCX, PPTX, or
XLSX, a PDF is often lossy, hard to edit semantically, and easy to break
visually. Prefer changing the editable source when it exists; work directly on
PDF only when the PDF itself is the source, evidence, or final artifact.

## Runtime Dependencies

Treat the execution environment as unknown. Do not assume Python, Poppler, qpdf,
OCR tools, PDF libraries, browser engines, or converters are installed, and do
not run a full dependency preflight by default.

Start with the task-specific command or library path. If a runtime, package,
binary, OCR engine, or renderer is missing, handle that execution-time failure by
installing/enabling the minimum local dependency when appropriate, switching to
an equivalent available tool that preserves the PDF contract, or reporting the
exact missing dependency and install command.

## Route

1. Identify the job: inspect, read/extract, render/QA, create PDF, merge/split,
   rotate/crop, compress/optimize, repair, fill forms, redact, watermark,
   encrypt/decrypt, OCR scanned pages, extract images, or package for handoff.
2. Classify the PDF surface:
   - final render: PDF is the fixed-layout output from another source
   - native PDF: existing PDF must be edited, rearranged, repaired, filled, or
     analyzed directly
   - scanned/image PDF: OCR, deskew, rotation, and image quality dominate
   - form PDF: AcroForm/XFA fields or visual non-fillable fields matter
   - evidence/extraction: text, tables, images, citations, or page coordinates
     must be extracted with traceability
3. Preserve source of truth:
   - If the user has DOCX/PPTX/XLSX/Markdown/HTML source and asks for content
     changes, edit the source and regenerate PDF.
   - If the user asks for PDF-only operations or supplies only PDF, operate on
     the PDF and report any semantic limitations.
4. Inspect before editing:
   `python3 {baseDir}/scripts/pdf_tool.py inspect input.pdf --out report.json`
5. Choose the output route:
   - Use PDF for final print/share/signoff, archival, forms, scans, and fixed
     page layout.
   - Use Markdown/CSV/JSON only as extracted evidence or intermediate data.
   - Use PNG page renders for visual verification, not as a substitute for the
     deliverable unless the user asks for images.
6. Choose tools by task:
   - Poppler tools (`pdfinfo`, `pdftoppm`, `pdftotext`) for portable inspection,
     rendering, and text extraction.
   - pypdf for page-level merge/split/rotate, metadata, simple attachments, and
     encryption when installed.
   - pikepdf/qpdf for repair, linearization, encryption, low-level structural
     transforms, and damaged PDFs when available.
   - pdfplumber for text/table/layout extraction on machine-generated PDFs.
   - OCRmyPDF/Tesseract for scanned PDFs when available.
   - PyMuPDF/PDFium/pdf.js for high-quality rendering or coordinate work when
     available and licensing/environment constraints fit the task.
   - reportlab/WeasyPrint/Chrome print for new PDFs, selected by source format
     and layout complexity.
7. Verify before delivering:
   - Re-inspect the output PDF.
   - Render representative pages, or every page for short/high-stakes files.
   - Compare page count, page sizes, rotations, text extractability, forms,
     annotations, links, images, encryption, and file size against intent.
   - For redaction, verify removed content is not recoverable as text or hidden
     objects; visual black boxes alone are insufficient.
   - For OCR, verify searchable text exists on expected pages and that language,
     orientation, and page order are correct.

## References

Load only the reference needed for the current route:

- `references/workflow.md` for PDF task routing, source-of-truth decisions, and
  delivery flow.
- `references/tool-selection.md` for library and command-line tool choices,
  capability boundaries, and license/environment notes.
- `references/extraction.md` for text, table, image, citation, and coordinate
  extraction from PDFs.
- `references/forms-redaction-ocr.md` for fillable forms, visual form overlays,
  redaction, OCR, scans, orientation, and searchable PDF checks.
- `references/verification.md` for visual, structural, OCR, extraction, and
  delivery QA reports.

## Scripts

- `python3 {baseDir}/scripts/pdf_tool.py inspect file.pdf --out report.json`
  reports page count, metadata, page sizes, encryption, form fields, outlines,
  annotations, attachments, text/image signals, Poppler info, and warnings.
- `python3 {baseDir}/scripts/pdf_tool.py render file.pdf --dir renders --dpi 150`
  renders pages to PNG with Poppler when available.
- `python3 {baseDir}/scripts/pdf_tool.py extract-text file.pdf --out text.txt`
  extracts text with Poppler if available, otherwise pypdf.
- `python3 {baseDir}/scripts/pdf_tool.py merge out.pdf in1.pdf in2.pdf ...`,
  `split`, and `rotate` perform baseline page operations with pypdf.

The scripts are portable baseline tools. They do not replace a real PDF viewer,
OCR engine, browser renderer, office exporter, or domain-specific parser. Use
richer host tools when available, then keep the same verification discipline.

## Quality Bar

- Do not edit a generated PDF when the editable source is available and content
  changes are required; regenerate from source instead.
- Do not trust PDF text extraction as layout verification. Render pages and
  inspect visual output when layout matters.
- Do not claim OCR success merely because a command ran; verify searchable text
  and page alignment.
- Do not redact by covering text with a rectangle unless the underlying content
  is removed or the limitation is explicitly accepted.
- Preserve page order, page boxes, rotations, bookmarks, links, forms,
  annotations, attachments, metadata, accessibility tags, and encryption unless
  intentionally changing them.
- Keep extracted claims traceable to page numbers and, when useful, bounding
  boxes.
- State limitations plainly when rendering, OCR, form field detection, or
  structural repair is unavailable.
