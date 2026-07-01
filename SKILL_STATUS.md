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
| `presentation` | active | Agent-maintainable deck source or native PPTX when required | Slide/talk artifact | Slide narrative, visual hierarchy, asset fidelity, presenter/read deck fit, render/export checks | Optimized for communication on slides, not generic PPTX file handling. |
| `video-studio` | active | Media files, scripts, manifests, platform packaging settings | Finished video/package | ffprobe/ffmpeg QA, platform dimensions, audio/subtitle/frame checks | Clear production toolchain and verification surface. |

## Archived Skills

| Skill | Status | Archive path | Reason | Restore only if |
| --- | --- | --- | --- | --- |
| `research` | archived | `archive/research` | Prior trigger experiments showed low trigger rate, and much of the workflow resembles base model plus browsing behavior. | Deep, auditable research artifacts prove unique value beyond normal browsing/search, such as source logs, claim audits, domain routing, patent/grant/regulatory workflows, or literature-review machinery. |

## Planned / Possible Skills

| Skill | Status | Build only if | Boundary |
| --- | --- | --- | --- |
| `spreadsheet` | planned | Users need to create, edit, or verify workbooks as durable artifacts | Excel/CSV/Sheets as calculable models: sheets, ranges, formulas, pivots, charts, validation, workbook QA. Not ordinary tables inside documents or slides. |

## Cross-Skill Guidance

Do not make repository-level handoff contracts mandatory. Codex chooses skills
from their names and descriptions, then loads only the selected `SKILL.md`.
Users may install only one skill or a subset of this repository, so each skill
must remain useful on its own and must not assume any other skill exists.

Use this file only as portfolio guidance. If artifacts should be reusable, make
them ordinary files with clear names and contents. Do not encode dependencies on
other skills.

Reusable artifacts can include:

- `data-analysis`: verified findings, metric definitions, caveats, source
  paths, chart/table artifacts, and verification status.
- `document`: thesis, section outline, source map, comments/redlines, and
  reader-test results.
- `presentation`: slide narrative, speaker notes, asset inventory, deck source,
  and render/export checks.
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
