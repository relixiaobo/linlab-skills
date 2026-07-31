# Document Verification

Approach verification as a source-fidelity and format-integrity pass.

## Universal Checks

- source claims are represented faithfully
- archetype, design preset, and form factors fit the reader's job
- title and section order match the requested outcome
- no lorem, TODO, placeholder, sample, dummy, or xxxx text remains
- headings are hierarchical and skimmable
- links and local asset references are not broken
- tables are readable and not needlessly wide
- lists use real list semantics when delivered as DOCX
- comments/redlines are intentional and reported
- source of truth is clear and available for future agent revisions
- source coverage is obvious for substantive claims
- final artifact opens or renders when local tools allow it

## DOCX Checks

- inspect package structure with `scripts/docx_tool.py`
- check relationship targets and content types
- check heading sequence, manual bullet risks, table geometry risks, headers/footers, and notes
- check placeholder locations, including headers, footers, comments, and text boxes
- check comments and tracked changes
- render or convert when possible
- verify headers, footers, footnotes, and endnotes when relevant

## Markdown Checks

- inspect static structure with `scripts/markdown_tool.mjs`
- check heading hierarchy
- check long paragraphs, excessive table width, and remote image dependencies
- check front matter and document-control metadata when Markdown is the source
- check bare URLs, duplicate headings, empty headings, and source coverage warnings
- check local asset references
- search generated files for placeholders

## Reader Test Checks

- predict 5-10 realistic reader questions for substantial documents
- verify the document answers them without conversation context
- flag missing definitions, unsupported claims, contradictions, and unclear decisions
- fix the source document before regenerating exports

## Delivery Report

When emitting JSON, follow `assets/schemas/verification-report.schema.json`.

Include:

- `artifact`: final artifact path
- `outputRoute`: artifact route such as Markdown, DOCX, PDF, comments, redline, or summary
- `filesProduced`: produced deliverables
- `sourceMaterials`: source inputs used
- `checks`: check objects with name, status, tool, and evidence or result
- `issues`: issues found, including fixed issues
- `limitations`: checks not possible in the current environment
- `readerQuestions`: reader-test questions and whether each was answered
- `finalStatus`: passed, warning, or failed
