# Skill Validation Matrix

This file records the repeatable checks for each skill. The authoritative
command is:

```sh
python3 evals/run_all_skill_checks.py
```

## Coverage

| Skill | Structural | Script syntax | Smoke / workflow gate | Current limit |
| --- | --- | --- | --- | --- |
| `code-review` | `quick_validate.py` | n/a | `evals/code-review/run_checks.py` validates a realistic local-diff fixture and expected finding anchors | Does not grade model review prose; use forward-testing for reviewer judgment quality. |
| `data-analysis` | `quick_validate.py` | `py_compile` | `.venv/bin/python evals/data-analysis/run_checks.py` runs deterministic verification, report, chart, and table checks | Requires `data-analysis/requirements.txt` for full `18 passed, 0 failed, 0 skipped`. |
| `document` | `quick_validate.py` | `py_compile` + `node --check` | `evals/run_artifact_skill_checks.py` inspects Markdown and DOCX-style tool surfaces | Does not render DOCX visually; use host document tools for visual QA on real documents. |
| `pdf` | `quick_validate.py` | `py_compile` | `evals/run_artifact_skill_checks.py` generates/inspects sample PDFs and runs PDF smoke checks | Merge/split/rotate need `pypdf`; OCR/redaction need external engines and task-specific tests. |
| `presentation` | `quick_validate.py` | `py_compile` + `node --check` | `evals/run_artifact_skill_checks.py` inspects HTML/PPTX-style tool surfaces | Does not visually render full decks; use browser/PowerPoint/LibreOffice for real deck QA. |
| `feed-processing` | `quick_validate.py` | `node --check` | `evals/feed-processing/run_checks.py` runs offline source-list, discovery, parse, window, diff, full-text, and pack-validation checks | Does not verify live publisher behavior or third-party article extraction engines; use forward-testing for real feeds. |
| `shape-product-spec` | `quick_validate.py` | `py_compile` | `evals/shape-product-spec/run_checks.py` validates realistic definition prompts and `spec_check.py` on good/bad artifacts, including constraint/option/tradeoff coverage | Does not grade strategic product judgment or evidence quality; use forward-testing on messy real product inputs for trigger and review quality. |
| `spreadsheet` | `quick_validate.py` | `py_compile` | `evals/run_artifact_skill_checks.py` inspects CSV/XLSX-style tool surfaces | Formula recalculation needs LibreOffice/Excel/Sheets for full calculation verification. |
| `video-studio` | `quick_validate.py` | `py_compile` + `node --check` | `evals/video-studio/run_checks.py` runs probe, manifest validation, ffmpeg render, QA, cover, and package on a fixture video | Manim/LaTeX math overlay and browser capture are optional paths not covered by the core smoke gate. |
| `archive/research` | `quick_validate.py` | n/a | archived only | Archived because trigger experiments showed low unique value; no active workflow gate. |

## Notes

- Generated workspaces are ignored by git: `artifact-skills-workspace/`,
  `feed-processing-workspace/`, `video-studio-workspace/`, and other
  `*-workspace/`
  directories.
- `evals/run_all_skill_checks.py` uses `.venv/bin/python` for data-analysis when
  present, otherwise the current Python interpreter.
