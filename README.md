# Linlab Skills

Personal Codex skills maintained by Linlab.

## Skills

- `code-review` - high-signal PR, branch, and local-diff review with confidence scoring and git-history context.
- `data-analysis` - trustworthy analysis of files, tables, metrics, experiments, and trends.
- `document` - source-first professional documents, DOCX/Word workflows, comments, redlines, and reader tests.
- `pdf` - PDF-native inspection, extraction, page operations, rendering, OCR/form/redaction guidance, and QA.
- `presentation` - one HTML-canonical Studio with narrative archetypes, executable themes, content-fit layouts, and verified exports, plus surgical OOXML editing for precise PPTX changes.
- `feed-processing` - portable RSS/Atom/JSON Feed/OPML subscription processing into validated feed-content packs.
- `shape-product-spec` - shapes product ideas, features, and business rules into decision-ready and execution-ready specs with goals, constraints, options, flows, acceptance criteria, and review audits.
- `spreadsheet` - source-first spreadsheet workbooks, XLSX/CSV inspection, formulas, validation, and workbook QA.
- `video-studio` - manifest-driven local video editing, rendering, packaging, and QA.

See `portfolio/SKILL_STATUS.md` for each skill's status, boundary, source of
truth, and next action.

Archived skills are kept under `archive/` for reference and are not installed by
the default command.

## Install

For Codex CLI, copy or symlink a skill folder into the user skills directory:

```sh
mkdir -p ~/.agents/skills
ln -s "$PWD/skills/code-review" ~/.agents/skills/code-review
```

To install all skills:

```sh
mkdir -p ~/.agents/skills
for skill in skills/*; do
  ln -s "$PWD/$skill" "$HOME/.agents/skills/${skill##*/}"
done
```

Codex detects skill changes automatically in new sessions. If a skill does not
appear in `/skills` or `$` completion, restart Codex CLI.

## Validate

Create the repository environment and install its declared dependencies:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install \
  -r evals/requirements.txt \
  -r skills/data-analysis/requirements.txt
```

Run the deterministic repository gate, or validate one Agent evaluation suite
in isolation:

```sh
.venv/bin/python tests/run_all.py
.venv/bin/python evals/runners/evalctl.py validate \
  --suite evals/suites/representative-ab.json
```

See `evals/README.md` for isolated baseline, Skill-enabled, and ablation runs.
Agent evaluation cases are grouped by user job under `evals/cases/`, never by
the Skill under test. Deterministic checks and their fixtures live under
`tests/`.
See `evals/VALIDATION_MATRIX.md` for the current validation level and limits for
each skill.

## Repository Structure

Each skill folder is intentionally self-contained and should contain only runtime
skill resources: `SKILL.md`, optional `agents/`, `references/`, `scripts/`, and
`assets/`.

Repository-level Agent experiments live under `evals/`; deterministic tests
live under `tests/`; portfolio decisions live under `portfolio/`. Generated raw
runs live under the ignored `results/` directory, while reviewed summaries may
be committed under `reports/`.
