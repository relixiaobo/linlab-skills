# Linlab Skills

Personal Codex skills maintained by Linlab.

## Skills

- `code-review` - high-signal PR, branch, and local-diff review with confidence scoring and git-history context.
- `data-analysis` - trustworthy analysis of files, tables, metrics, experiments, and trends.
- `document` - source-first professional documents, DOCX/Word workflows, comments, redlines, and reader tests.
- `pdf` - PDF-native inspection, extraction, page operations, rendering, OCR/form/redaction guidance, and QA.
- `presentation` - source-first slide decks, PPTX/HTML decks, speaker notes, handouts, and deck QA.
- `shape-product-spec` - shapes product ideas, features, and business rules into decision-ready and execution-ready specs with goals, constraints, options, flows, acceptance criteria, and review audits.
- `spreadsheet` - source-first spreadsheet workbooks, XLSX/CSV inspection, formulas, validation, and workbook QA.
- `video-studio` - manifest-driven local video editing, rendering, packaging, and QA.

See `SKILL_STATUS.md` for each skill's status, boundary, source of truth, and next action.

Archived skills are kept under `archive/` for reference and are not installed by
the default command.

## Install

For Codex CLI, copy or symlink a skill folder into the user skills directory:

```sh
mkdir -p ~/.agents/skills
ln -s "$PWD/code-review" ~/.agents/skills/code-review
```

To install all skills:

```sh
mkdir -p ~/.agents/skills
for skill in code-review data-analysis document pdf presentation shape-product-spec spreadsheet video-studio; do
  ln -s "$PWD/$skill" "$HOME/.agents/skills/$skill"
done
```

Codex detects skill changes automatically in new sessions. If a skill does not
appear in `/skills` or `$` completion, restart Codex CLI.

## Validate

Validate a skill with Codex's skill validator:

```sh
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py code-review
```

Run repository-level eval checks:

```sh
python3 evals/run_all_skill_checks.py
python3 evals/run_artifact_skill_checks.py
python3 evals/shape-product-spec/run_checks.py
python3 evals/data-analysis/run_checks.py
```

For a full `data-analysis` gate, install its dependencies first. A local venv is
recommended because Homebrew Python may reject global pip installs:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r data-analysis/requirements.txt
.venv/bin/python evals/data-analysis/run_checks.py
```

Eval definitions and fixtures are grouped by skill family under `evals/`, for
example `evals/artifact-skills/`, `evals/data-analysis/`, and
`evals/video-studio/`.
See `evals/VALIDATION_MATRIX.md` for the current validation level and limits for
each skill.

## Repository Structure

Each skill folder is intentionally self-contained and should contain only runtime
skill resources: `SKILL.md`, optional `agents/`, `references/`, `scripts/`, and
`assets/`.

Repository-level eval definitions and fixtures live under `evals/`. Generated
`*-workspace/` folders are local evaluation outputs and are not part of the
published source.
