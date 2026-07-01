# PDF Extraction

PDF extraction is evidence work. Preserve page references and explain extraction
limits.

## Text

- Prefer Poppler `pdftotext` for fast extraction from text PDFs.
- Use pypdf for lightweight fallback extraction.
- Use pdfplumber or PyMuPDF when coordinates, reading order, columns, font
  metadata, or layout objects matter.
- If extracted text is empty or nonsense, inspect whether pages are image-only,
  encrypted, rotated, or encoded with unusual fonts.

## Tables

- Use pdfplumber/PyMuPDF table extraction when available.
- Validate extracted tables against the rendered page: headers, row counts,
  wrapped cells, spanning cells, footnotes, and page breaks are common failure
  points.
- For financial, legal, or scientific tables, include page number and table
  caption/source in the output.

## Images

- Use `pdfimages`, pikepdf, PyMuPDF, or available host tools for image
  extraction.
- Preserve original formats when possible. Avoid re-encoding unless the user
  requested optimization or conversion.

## Citations And Coordinates

For answer generation or evidence packs, cite:

- source filename
- page number
- section/table/figure label when present
- bounding box or nearby text when useful

Do not imply perfect reading order unless it was verified on rendered pages.
