---
name: document
description: Create, edit, analyze, review, or polish professional documents including source-first Markdown drafts, Word/DOCX files, reports, memos, briefs, proposals, policies, contracts, PDF handouts, comments, redlines, reader tests, and summaries.
---

# Document

## Overview

Build documents as durable written communication. Treat DOCX, Markdown, PDF, and
plain text as delivery routes selected by audience, review workflow, fidelity,
and layout risk.
Default to source-first artifacts that another agent can inspect, revise, and
regenerate. Use DOCX/PDF as delivery exports unless the user explicitly needs
the Word file itself to be the source of truth.

## Route

1. Identify the job: create, rewrite, edit, review, redline, comment, inspect,
   summarize, convert, or package for handoff.
2. Classify the revision surface and review mode:
   - source-first: Markdown or structured source stays primary; DOCX/PDF are
     regenerated deliverables
   - native DOCX: edit the existing Word file directly because comments,
     tracked changes, template preservation, or binary handoff is the job
   - reader test: evaluate whether the document works for a fresh reader
   - summary/intake: convert source material into usable Markdown first
3. Extract audience, decision or reader action, source materials, required
   claims, approval constraints, template/style constraints, metadata, and
   review path.
   If source materials include findings, metrics, caveats, charts, tables, or
   verification notes, treat them as source evidence, not as prose to copy
   blindly.
4. For multi-format or non-text source files, choose an intake route before
   drafting. Use `references/source-intake.md`.
5. Choose an archetype and form-factor plan before drafting. For new documents
   or major rewrites, read `references/document-system.md`.
6. If the user supplied a DOCX, inspect it before editing with
   `python3 {baseDir}/scripts/docx_tool.py inspect path/to/file.docx --out report.json`
   when useful. Preserve existing template conventions unless the user requests
   a redesign. For precise edits, comments, or tracked changes, read
   `references/review-workflow.md`.
7. Create a document plan before writing. If emitting JSON, keep it compatible
   with `{baseDir}/assets/schemas/document-plan.schema.json`.
8. Choose the output route:
   - Use Markdown for fast drafts, reviewable structure, and agent-friendly iteration.
   - Use DOCX when the user needs Word compatibility, comments, tracked-change workflows, exact table/list behavior, or template preservation.
   - Use PDF only for fixed-layout delivery or handouts after the source document is stable.
9. Build or edit with the route's intended tools:
   - For DOCX creation, editing, comments, redlines, or template preservation, first prefer a real DOCX library, office automation, or host document tool available in the task environment. If the required package or command is missing, verify that absence and try to install or enable it in the local task environment when permissions allow.
   - If Markdown is the source and DOCX is a deliverable, prefer a file-first
     Markdown-to-DOCX route and keep the `.md` alongside generated output. See
     `references/markdown-to-docx.md`.
   - Do not silently downgrade an explicit DOCX/Word request to Markdown, plain text, or PDF, and do not hand-author WordprocessingML ZIP packages as a substitute for a missing DOCX library unless the user approves that lower-level route or no install path is available and you state the limitation.
   - Prefer bundled scripts for deterministic structure checks; use richer host rendering/conversion tools only when they preserve the same verification discipline.
10. Verify before delivering. At minimum check source fidelity, heading
    structure, placeholders, local assets, tables, comments/redlines, source
    coverage, and render/open limits. For substantial docs, include a reader
    test or at least a predicted-reader-questions pass.

## References

Load only the reference needed for the current route:

- `references/workflow.md` for planning, source mapping, and delivery flow.
- `references/source-intake.md` for converting PDFs, DOCX, spreadsheets, web
  pages, images/OCR, and other source materials into LLM-friendly Markdown.
- `references/document-system.md` for archetypes, design presets, form factors, tone, hierarchy, and table gates.
- `references/docx-operations.md` for DOCX package inspection, comments, tracked changes, OOXML risks, and template preservation.
- `references/review-workflow.md` for comments, tracked changes, redlines,
  precise DOCX edit anchoring, and reader testing.
- `references/markdown-to-docx.md` for Markdown-first Word export, front matter,
  templates, and generated deliverables.
- `references/verification.md` for source-fidelity, structural, and format QA.

## Scripts

- `python3 {baseDir}/scripts/docx_tool.py inspect file.docx --out report.json` inspects DOCX package structure, headings, sections, tables, comments, tracked changes, relationships, media, headers/footers, notes, manual bullets, and placeholder-like text.
- `node {baseDir}/scripts/markdown_tool.mjs inspect draft.md --out report.json` inspects Markdown/HTML-like drafts for headings, hierarchy jumps, long paragraphs, tables, local asset references, remote dependencies, and placeholder-like text.

The scripts are portable baseline tools. Do not assume product-specific tools
exist. If a host offers richer DOCX rendering, PDF export, visual QA, comments,
or redline tooling, use it and keep the same final verification discipline. If
the requested DOCX route requires a missing library or office command, follow the
skill-dependency rule before changing formats.

## Quality Bar

- Do not deliver generic prose when the user provided concrete source material.
- Make the document's purpose obvious from the title, opening, and section order.
- Pick document archetype and form factors deliberately; do not use tables as decorative layout boxes.
- Preserve factual source fidelity; label inferences and assumptions.
- Keep the revision surface explicit. Future agent edits should target source
  Markdown or stable DOCX anchors, not an opaque final export.
- Keep headings parallel and useful for skimming.
- Keep Word semantics real: headings are heading styles, lists are numbering definitions, tables have deliberate geometry, comments/redlines are intentional.
- Do not leave placeholders, TODOs, unresolved comments, or accidental tracked changes unless the user asked for them.
- For high-stakes documents, test whether a fresh reader can answer the key
  questions from the document alone.
- State limitations plainly when rendering, DOCX editing, or visual verification is unavailable.
