# Forms, Redaction, And OCR

## Forms

1. Inspect for fillable fields before overlaying text.
2. If AcroForm fields exist, prefer setting field values through a form-aware
   library or host tool.
3. Preserve field names, export values, checkboxes, radio groups, choice lists,
   and appearance streams.
4. If a form is not fillable, render pages and place text/checkmarks by
   coordinates. Verify with page images.
5. Flatten only when the user wants a non-editable final PDF.

XFA forms are a separate risk surface. Many Python libraries cannot preserve or
fill dynamic XFA reliably; use a dedicated viewer/tool or state the limitation.

## Redaction

Real redaction removes content from the PDF object structure. A black rectangle
or white overlay is not enough.

Minimum redaction checks:

- search extracted text for redacted terms
- inspect rendered pages for visual coverage
- remove or regenerate metadata, attachments, annotations, and hidden layers
  when they may contain sensitive text
- prefer a redaction-capable engine or regenerate from a sanitized source

## OCR And Scans

Scanned PDFs need image processing before text extraction can be trusted.

Route:

1. Inspect text density and image coverage.
2. Detect rotated or skewed pages when possible.
3. Run OCRmyPDF/Tesseract or another OCR engine when available.
4. Verify searchable text exists on pages that should contain text.
5. Render before and after OCR to check page order, orientation, and visual
   fidelity.

For multilingual documents, specify OCR languages instead of relying on English
defaults.
