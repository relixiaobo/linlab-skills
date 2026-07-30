# Markdown To DOCX

Use this when Markdown is the source and DOCX is the deliverable.

## Principle

Prefer file-first conversion: write or update a `.md` source file, then convert
from that file to DOCX. Do not embed long Markdown strings inside code when a
file can be used. The Markdown remains the revision surface for future agents;
the DOCX is a generated deliverable unless the user says otherwise.

## Recommended Source Shape

Use YAML front matter when the document needs metadata, template selection, or
batch conversion control:

```markdown
---
format: docx
title: "Executive Brief"
author: "Team"
date: "2026-07-01"
status: draft
version: "0.1"
classification: internal
template: business_brief
convert: true
---

# Executive Brief
```

Useful fields:

- `format`: docx, pdf, markdown, or multiple outputs
- `title`: document title and default output name
- `author`, `date`, `version`, `status`, `classification`
- `template`: business_brief, formal_record, operator_reference, or a
  user-provided template name/path
- `convert`: false for notes/reference files that should not be exported
- `document_type`: document, note, reference, email, system

## Conversion Route

1. Inspect Markdown with `markdown_tool.mjs`.
2. Choose a template or preserve a supplied DOCX template when available.
3. Use a real conversion tool when available: pandoc, formaldoc, md-converter,
   docx-js, python-docx, or a host document tool.
4. Generate DOCX next to the Markdown source.
5. Inspect the DOCX with `docx_tool.py`.
6. Render/open/export to PDF when local tools allow visual QA.

## Template Choice

- `business_brief`: executive memos, proposals, reports
- `plain_editorial`: specs, internal docs, technical writing
- `operator_reference`: playbooks, checklists, SOPs
- `formal_record`: policies, legal-adjacent docs, HR/compliance
- `existing_template`: user supplied a DOCX/template to preserve

If the user supplies a DOCX template, inspect it first and preserve heading
styles, list definitions, page size, margins, headers/footers, and table
conventions.

## Markdown Authoring Rules

- One `#` title unless using `titleLevel`/template mapping intentionally.
- Do not skip heading levels.
- Keep tables for repeated comparable fields; avoid paragraph-length cells.
- Use real Markdown lists, not manually aligned text.
- Keep image paths local and checked in or packaged with the output.
- Use footnotes/citations consistently when claims need provenance.

## Delivery

Report both source and generated artifacts:

- Markdown source path
- DOCX output path
- template/tool used
- verification checks run
- known conversion limits
