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
| `data-analysis` | `quick_validate.py` | `py_compile` | `.venv/bin/python tests/integration/data-analysis/run_checks.py` runs deterministic verification, report, chart, and table checks | Requires `data-analysis/requirements.txt` for full `18 passed, 0 failed, 0 skipped`; paired Agent evaluation uses `analyze-order-revenue`. |
| `document` | `quick_validate.py` | `py_compile` + `node --check` | `evals/run_artifact_skill_checks.py` inspects Markdown and DOCX-style tool surfaces | Does not render DOCX visually; use host document tools for visual QA on real documents. |
| `pdf` | `quick_validate.py` | `py_compile` | `evals/run_artifact_skill_checks.py` generates/inspects sample PDFs and runs PDF smoke checks | Merge/split/rotate need `pypdf`; OCR/redaction need external engines and task-specific tests. |
| `presentation` | `quick_validate.py` | `py_compile` + `node --check` | `tests/integration/presentation/run_checks.py` covers schemas, catalogs, Studio tooling, PPTX/HTML/render regressions, and complex PPTX fixtures | Paired `create-investor-update` evaluation adds natural routing, image relevance, aspect-ratio/crop, visual quality, artifact, and cost scoring; rendered human or model review still needs an external judge adapter. |
| `feed-processing` | `quick_validate.py` | `node --check` | `evals/feed-processing/run_checks.py` runs offline source-list, discovery, parse, window, diff, full-text, and pack-validation checks | Does not verify live publisher behavior or third-party article extraction engines; use forward-testing for real feeds. |
| `shape-product-spec` | `quick_validate.py` | `py_compile` | `tests/integration/shape-product-spec/run_checks.py` validates `spec_check.py` on good/bad artifacts, including constraint/option/tradeoff coverage | Paired `shape-merchant-addon-controls` evaluation covers natural routing and product judgment; use fresh sessions and an external judge adapter for forward tests. |
| `spreadsheet` | `quick_validate.py` | `py_compile` | `evals/run_artifact_skill_checks.py` inspects CSV/XLSX-style tool surfaces | Formula recalculation needs LibreOffice/Excel/Sheets for full calculation verification. |
| `video-studio` | `quick_validate.py` | `py_compile` + `node --check` | `evals/video-studio/run_checks.py` runs probe, manifest validation, ffmpeg render, QA, cover, and package on a fixture video | Manim/LaTeX math overlay and browser capture are optional paths not covered by the core smoke gate. |
| `archive/research` | `quick_validate.py` | n/a | archived only | Archived because trigger experiments showed low unique value; no active workflow gate. |

## Notes

- `python3 evals/runners/evalctl.py validate --suite
  evals/suites/representative-ab.json` validates the shared Agent-evaluation
  contracts. The suite contains 3 user-job cases and 21 planned runs across
  baseline, Skill-enabled, visual-guidance ablation, and 3 repetitions.
- `python3 -m unittest discover -s tests/unit -p 'test_*.py' -v` checks oracle
  isolation, condition materialization, protocol capture, and paired deltas.
- Generated workspaces are ignored by git: `artifact-skills-workspace/`,
  `feed-processing-workspace/`, `video-studio-workspace/`, and other
  `*-workspace/`
  directories.
- `evals/run_all_skill_checks.py` uses `.venv/bin/python` for data-analysis when
  present, otherwise the current Python interpreter.
- Legacy `evals/<skill>/run_checks.py` paths remain compatibility wrappers for
  the three migrated deterministic gates.
