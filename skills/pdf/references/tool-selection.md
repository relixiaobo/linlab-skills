# PDF Tool Selection

Pick the smallest tool that preserves the PDF features that matter.

## Baseline Tools

- Poppler `pdfinfo`: page count, metadata, encryption, page boxes, syntax clues.
- Poppler `pdftoppm`: page rendering to PNG for visual verification.
- Poppler `pdftotext`: fast text extraction with optional layout mode.
- pypdf: pure-Python page operations, metadata, outlines, form field reads,
  simple merge/split/rotate, encryption and decryption support.

## When Available

- qpdf: content-preserving structural transforms, checking, repair, splitting,
  merging, encryption, decryption, and linearization. It does not render or
  extract text.
- pikepdf: Python interface to qpdf for repair, object-level work, metadata,
  encryption, image extraction, page manipulation, and linearization.
- pdfplumber: machine-generated PDF text/table/layout extraction with character,
  line, rectangle, image, annotation, and coordinate data. It is not an OCR
  engine and works poorly on pure scans.
- OCRmyPDF: add an OCR text layer to scanned PDFs, deskew/rotate pages, output
  searchable PDF/PDF-A, and validate outputs. Requires external OCR tooling.
- PyMuPDF/MuPDF: high-performance rendering, extraction, annotation, redaction,
  and conversion. Check license and environment suitability before building a
  reusable dependency around it.
- PDFium/pypdfium2: rendering and extraction with a permissive dependency model
  when available.
- pdf-lib: JavaScript creation/modification, forms, flattening, page copying,
  fonts, images, and browser/Node workflows.
- pdf.js: browser-grade rendering and viewer workflows, useful for web
  previews, browser tests, and pixel-based visual QA.
- reportlab: programmatic PDF generation when layout is controlled by code.
- WeasyPrint/Chrome print: HTML/CSS-to-PDF generation when source is naturally
  HTML and browser rendering is the intended layout engine.

## Risk Rules

- Do not use a page-level library for semantic edits when it will drop forms,
  annotations, outlines, tags, attachments, or signatures without detection.
- Do not flatten forms, annotations, or layers unless the user asked for a
  flattened deliverable.
- Treat digital signatures as fragile: most edits invalidate them.
- Treat encrypted PDFs as access-controlled artifacts. Use passwords only when
  provided or clearly authorized.
- Treat accessibility tags and PDF/A conformance as deliverable requirements
  when present or requested.
- Check license before adding a new dependency to a reusable script or package.
