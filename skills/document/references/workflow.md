# Document Workflow

## Decision Flow

1. Define the audience, outcome, reader action, and review path.
2. Decide revision surface: source-first Markdown/project, native DOCX edit,
   generated DOCX/PDF deliverable, reader test, or summary/intake.
3. Extract source claims, evidence, required details, constraints, metadata, and unknowns.
4. Choose archetype, design preset, and form factors before drafting.
5. Choose the artifact route: Markdown source, DOCX export, native DOCX edit,
   PDF handout, comments, tracked changes, redline, reader test, or summary.
6. Create a document plan before drafting or editing.
7. Build from the plan.
8. Verify structure, source fidelity, layout semantics, review state, and format-specific risks.
9. Fix concrete issues and recheck.

## Document Plan Schema

When emitting JSON, follow `assets/schemas/document-plan.schema.json`.

Capture:

- `title`: document title
- `audience`: intended readers
- `goal`: communication outcome
- `outputRoute`: Markdown, DOCX, PDF, comments, redline, or summary
- `revisionSurface`: source-first, native-docx, generated-docx, visual-only, or mixed
- `reviewMode`: none, comments, tracked-changes, redline, clean-copy, reader-test, or mixed
- `metadata`: author, date, version, status, classification, template, or other document-control fields
- `archetype`: memo, brief, proposal, report, policy, review, playbook, form, or another deliberate shape
- `designPreset`: plain_editorial, business_brief, operator_reference, formal_record, existing_template, or user-provided
- `tone`: concise, formal, legal, executive, technical, persuasive, or another deliberate style
- `sourceMaterials`: inputs used
- `sourceMap`: how source materials support sections or claims
- `sections`: section objects with `heading`, `purpose`, `formFactor`, `source`, and `notes`
- `verificationPlan`: checks to run before delivery

## Creation Pattern

- Start from the reader's decision or action.
- Put the conclusion before supporting detail unless the genre requires suspense.
- Use section hierarchy to reveal the argument, not just to group paragraphs.
- Choose form factors by reading task: prose for argument, lists for scan, tables for repeated comparable fields, callouts for decisions and caveats.
- Prefer concrete claims backed by source material over broad advice.
- Keep document length proportional to the decision at stake.

## Revision Pattern

- Treat Markdown, structured source, or a native DOCX edit workspace as the
  source of truth; treat DOCX/PDF as derived deliverables unless the user says
  the Word file itself is authoritative.
- Keep source files near generated output so a later agent can revise without
  reverse-engineering binary files.
- Keep section headings, local asset paths, source notes, metadata, and review
  state explicit.
- When revising generated deliverables, edit source first, regenerate output,
  then rerun verification.

## Existing Document Pattern

- Inspect structure, visible text, headings, tables, images, comments, and tracked changes before editing.
- Preserve template style unless the user asks for redesign.
- Separate content edits from formatting fixes.
- Do not silently accept or reject tracked changes.
- Keep comments/redlines intentional and report their final state.
- Do not flatten real Word semantics into plain text: preserve heading styles, numbering, table geometry, fields, comments, notes, and relationships unless the edit requires changing them.

## Reader Test Pattern

- For substantial decision docs, specs, policies, proposals, and reports,
  predict 5-10 questions a realistic reader would ask.
- Check whether the document answers them without relying on conversation
  context.
- Flag gaps, contradictions, ambiguous terms, missing definitions, and claims
  without evidence.
- Fix the source document, not only the final export.

## Delivery Report

When finished, report:

- artifact path
- output route
- source materials used
- verification performed
- known limitations
