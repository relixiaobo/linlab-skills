# Skill Status

This file tracks the intended role, status, and next action for each skill in
this repository. Use it as the portfolio-level map before adding, merging, or
retiring skills.

## Status Labels

- `active`: keep maintaining; clear source of truth, editing primitives, risks,
  and verification standards.
- `watch`: useful, but boundary or trigger behavior needs more evidence.
- `candidate-retire`: likely overlaps with base model capability or another
  skill; do not expand without a new concrete reason.
- `archived`: kept for reference, but removed from default installation and
  active maintenance.
- `planned`: worth building only after the boundary and handoff contract are
  clear.

## Current Skills

| Skill | Status | Source of truth | Primary object | Verification / quality bar | Notes |
| --- | --- | --- | --- | --- | --- |
| `code-review` | active | Git diff, PR, branch, review comments | Review findings | Bug/regression/security findings with line-grounded evidence and confidence | Clear domain-specific workflow; keep separate. |
| `data-analysis` | active | Raw data, metric definitions, SQL/Python, findings ledger | Trustworthy findings | Profile data, define metric/grain/window, verify key numbers, triangulate specification | Evidence layer for later reports, decks, and workbooks. |
| `document` | active | Markdown/structured source or native DOCX when required | Reading/review artifact | Source fidelity, section structure, DOCX semantics, comments/redlines, reader questions | Optimized for agent-maintained documents and Word review workflows. |
| `pdf` | active | Native PDF, page renders, extracted evidence, or editable source that exports PDF | Fixed-layout PDF artifact | Page count/boxes, render checks, text/OCR extraction, forms, annotations, links, redaction, encryption, and output re-inspection | Optimized for PDF-native operations and final-layout QA, not drafting source documents/slides/sheets. |
| `presentation` | active | Canonical `deck.html` plus narrative/theme/layout decisions and evidence/preservation records for Studio work; original PPTX package plus edit manifest for Surgeon work | Slide/talk artifact | Source accuracy, rendered HTML/export aesthetic gates, concrete PPTX editability coverage, package/object diff for precise edits, and route-aware technical checks | Two routes: Presentation Studio for all creation/rebuilding, PPTX Surgeon for minimum-change edits. Studio separates narrative archetypes, themes, and per-slide layouts. |
| `feed-processing` | active | Feed URLs, page URLs, source tables, OPML files, prior feed-content packs, and fetched article pages | Feed-content pack | Source-list profiling, fetch-window coverage, feed parse warnings, full-text attempt ledger, pack validation, and fixture/eval checks | Portable subscription-content processor; host adapters such as Tenon `#subscribe` are optional. |
| `shape-product-spec` | active | Product idea, feature request, business rule, source notes, screenshots, existing docs, interviews, user flows, evidence, assumptions, constraints, options, and approved decisions | Decision-ready and execution-ready product spec | Stable IDs, explicit decisions/evidence/non-goals, clean-slate vs constrained target framing, constraint classification, flow/state coverage, story slices, testable acceptance criteria, assumptions/open questions, contradiction review, and `spec_check.py` smoke validation | Solves the pre-build spec gap: the user wants an agent or team to build/change/evaluate a product capability, but intent is not executable yet. |
| `spreadsheet` | active | Workbook spec/source script, native XLSX, or flat data file | Calculable workbook/data-entry artifact | Sheet roles, formulas, named ranges, validation, links, protection, source data coverage, and open/render limits | Optimized for durable spreadsheet models, not ordinary tables inside documents or slides. |
| `video-studio` | active | Media files, scripts, manifests, platform packaging settings | Finished video/package | ffprobe/ffmpeg QA, platform dimensions, audio/subtitle/frame checks | Clear production toolchain and verification surface. |

## Archived Skills

| Skill | Status | Archive path | Reason | Restore only if |
| --- | --- | --- | --- | --- |
| `research` | archived | `archive/research` | Prior trigger experiments showed low trigger rate, and much of the workflow resembles base model plus browsing behavior. | Deep, auditable research artifacts prove unique value beyond normal browsing/search, such as source logs, claim audits, domain routing, patent/grant/regulatory workflows, or literature-review machinery. |

## Cross-Skill Guidance

Do not make repository-level handoff contracts mandatory. Codex chooses skills
from their names and descriptions, then loads only the selected `SKILL.md`.
Users may install only one skill or a subset of this repository, so each skill
must remain useful on its own and must not assume any other skill exists.

The artifact skills (`presentation`, `document`, `spreadsheet`, and `pdf`) still
have legacy shared trigger and smoke definitions in
`tests/fixtures/artifact-skills/suite.json` and
`tests/integration/artifact-skills/run_checks.py`.
The former `presentation-surgeon-single-target`, `document-board-memo`, and
`document-redline-review` behavior cases have moved to the Skill-independent
`evals/cases/edit-board-deck-subtitle`,
`evals/cases/create-enterprise-pilot-board-memo`, and
`evals/cases/review-remote-access-policy` experiments; their deterministic
fixture checks remain under `tests/`. Migrate the remaining Agent behavior
coverage into user-job cases under `evals/cases/`; keep deterministic file and
tool checks under `tests/`.

Treat a Skill as an intervention variable. Compare the same natural prompt and
inputs under baseline, Skill-enabled, and relevant ablation conditions. Record
quality, route, artifact, token, latency, and failure-taxonomy results before a
portfolio keep/change/retire decision.

Repository-level validation is tracked in `evals/VALIDATION_MATRIX.md` and can
be run with `.venv/bin/python tests/run_all.py`.

Use this file only as portfolio guidance. If artifacts should be reusable, make
them ordinary files with clear names and contents. Do not encode dependencies on
other skills.

Reusable artifacts can include:

- `data-analysis`: verified findings, metric definitions, caveats, source
  paths, chart/table artifacts, and verification status.
- `document`: thesis, section outline, source map, comments/redlines, and
  reader-test results.
- `pdf`: page renders, extracted text/tables/images, form-field inventory,
  redaction/OCR limitations, and PDF verification reports.
- `presentation`: Studio brief, selected narrative archetype, adapted theme,
  core layout strategy, evidence ledger, representative risk prototypes,
  preservation matrix or edit manifest, canonical HTML deck source, speaker
  notes, export editability evidence, and
  accuracy/aesthetic/technical gates.
- `feed-processing`: source list, fetch scope, source profiles, parse warnings, selected
  items, skipped/error coverage, full-text attempt ledgers, pack validation, and
  feed-content pack paths.
- `shape-product-spec`: product model, evidence ledger, objective/constraint
  framing, clean-slate and constrained options, source decisions, flow/state
  maps, story and requirement IDs, business rules, acceptance criteria,
  assumptions, open questions, and story-slice suggestions.
- `spreadsheet`: data dictionary, workbook formulas, named ranges, sheet
  dependencies, and validation issues.

## Split / Merge Rule

Do not split skills by file extension alone. Split only when a domain has all of
the following:

1. A distinct source of truth.
2. Distinct editing primitives.
3. Distinct high-risk failure modes.
4. Distinct verification tools or acceptance criteria.

If a candidate skill lacks these, prefer a reference file inside an existing
skill or rely on the base model.

## Research Skill Decision Record

Decision: archive `research` under `archive/research` and remove it from the
default install list.

Reasons:

- The trigger surface is broad and overlaps with normal browsing/search tasks.
- Good research behavior is increasingly a baseline expectation rather than a
  specialized skill.
- The skill may still be useful as reference material for future deep,
  auditable workflows where source logs, claim audits, and reusable artifacts
  create value beyond baseline browsing.

Next decision options:

- Restore as explicit-only if a narrower research workflow earns its own skill.
- Split useful pieces into another skill only when they satisfy the split rule.
- Delete the archive later if no future workflow reuses it.
