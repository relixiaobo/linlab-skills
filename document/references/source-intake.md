# Source Intake

Use this before drafting when source material is not already clean Markdown or
plain text.

## Goal

Convert source material into LLM-friendly Markdown for understanding, planning,
and source mapping. Treat intake Markdown as a content contract, not as a
high-fidelity visual conversion.

## Route Selection

- DOCX: inspect with `docx_tool.py`; extract text with an available document
  converter such as pandoc, python-docx, markitdown, or host document tooling.
- PDF: use a PDF/text extraction tool first; use OCR only when pages are scans
  or image-heavy.
- XLSX/CSV: preserve tables with sheet names, column headers, units, and notes.
- PPTX: extract slide text, speaker notes, tables, and image references when the
  document task depends on presentation content.
- HTML/web: fetch readable content and preserve links, headings, tables, and
  citations.
- images/scans: OCR or vision extraction; mark low-confidence text and preserve
  image provenance.
- ZIP or folder: inventory files first, then convert only relevant inputs.

## Intake Contract

For each source, record:

- original path or URL
- converter/tool used
- conversion limits such as OCR, missing tables, or unsupported comments
- extracted assets or companion files
- source reliability and date when relevant

Prefer a small source index:

```markdown
# Source Index

| ID | Source | Tool | Output | Notes |
| --- | --- | --- | --- | --- |
| S1 | input/report.pdf | pdf text extraction | sources/report.md | tables checked manually |
| S2 | input/policy.docx | pandoc --track-changes=all | sources/policy.md | tracked changes preserved in text |
```

Use source IDs in the document plan and section `source` fields.

## Safety

- Do not treat extraction output as complete when the source has scanned pages,
  complex tables, handwritten marks, comments, or tracked changes.
- Do not silently ignore comments, footnotes, endnotes, captions, or appendix
  tables when they are relevant to the user's request.
- If source facts are recent or high-stakes, verify against primary sources or
  ask the user for authoritative material.

## When To Re-Inspect

Re-inspect source artifacts when:

- the user asks for exact wording or legal/policy fidelity
- edits target comments, tracked changes, headers, footers, tables, fields, or
  footnotes
- the output will be a formal record, policy, proposal, contract-adjacent
  document, or board/executive brief
