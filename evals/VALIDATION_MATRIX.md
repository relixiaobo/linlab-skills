# Skill Validation Matrix

This file records the repeatable checks for each skill. The authoritative
command is:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r tests/requirements.txt
.venv/bin/python tests/run_all.py
```

The full gate also requires Node.js, FFmpeg/FFprobe, and Poppler tools on
`PATH`.

## Coverage

| Skill | Structural | Script syntax | Smoke / workflow gate | Current limit |
| --- | --- | --- | --- | --- |
| `code-review` | `skill-packages:code-review` | n/a | `tests/integration/code-review/run_checks.py` validates a realistic local-diff fixture and expected finding anchors | Does not grade model review prose; use forward-testing for reviewer judgment quality. |
| `data-analysis` | `skill-packages:data-analysis` | `py_compile` | `.venv/bin/python tests/integration/data-analysis/run_checks.py` runs deterministic verification, report, chart, and table checks | Requires `skills/data-analysis/requirements.txt` for full `18 passed, 0 failed, 0 skipped`; the production Judge Adapter recomputes metric truth, grain, and fan-out for `analyze-order-revenue` before blind review. |
| `document` | `skill-packages:document` | `py_compile` + `node --check` | `tests/integration/artifact-skills/run_checks.py` inspects Markdown and DOCX-style tool surfaces | The production Judge Adapter checks natural routing and Case-defined Markdown creation/review contracts for `create-enterprise-pilot-board-memo` and `review-remote-access-policy`; it does not render DOCX visually or claim native DOCX edits for Markdown sources. |
| `pdf` | `skill-packages:pdf` | `py_compile` | `tests/integration/artifact-skills/run_checks.py` generates/inspects sample PDFs and runs PDF smoke checks | Merge/split/rotate need `pypdf`; OCR/redaction need external engines and task-specific tests. |
| `presentation` | `skill-packages:presentation` | `py_compile` + `node --check` | `tests/integration/presentation/run_checks.py` covers schemas, catalogs, Studio tooling, PPTX/HTML/render regressions, and complex PPTX fixtures | Paired `create-investor-update` evaluation covers natural routing, factual fidelity, visual quality, artifacts, and cost; `create-incident-response-launch` adds controlled asset handling; `edit-board-deck-subtitle` adds a structured edit manifest, exact-target, package-scope, semantic-preservation, and baseline-gate evidence for precision edits. |
| `feed-processing` | `skill-packages:feed-processing` | `node --check` | `tests/integration/feed-processing/run_checks.py` runs offline source-list, discovery, parse, window, diff, full-text, and pack-validation checks | Does not verify live publisher behavior or third-party article extraction engines; use forward-testing for real feeds. |
| `shape-product-spec` | `skill-packages:shape-product-spec` | `py_compile` | `tests/integration/shape-product-spec/run_checks.py` validates `spec_check.py` on good/bad artifacts, including constraint/option/tradeoff coverage | The production Judge Adapter checks Case-defined source fidelity, options, flow/state coverage, scope, stable IDs, and acceptance criteria before blind product judgment. |
| `spreadsheet` | `skill-packages:spreadsheet` | `py_compile` | `tests/integration/artifact-skills/run_checks.py` inspects CSV/XLSX-style tool surfaces | Formula recalculation needs LibreOffice/Excel/Sheets for full calculation verification. |
| `video-studio` | `skill-packages:video-studio` | `py_compile` + `node --check` | `tests/integration/video-studio/run_checks.py` runs probe, manifest validation, ffmpeg render, QA, cover, and package on a fixture video | Manim/LaTeX math overlay and browser capture are optional paths not covered by the core smoke gate. |
| `archive/research` | `skill-packages:archive/research` | `py_compile` | archived only | Archived because trigger experiments showed low unique value; no active workflow gate. |

## Notes

- `.venv/bin/python evals/runners/evalctl.py validate --suite
  evals/suites/representative-ab.json` validates the shared Agent-evaluation
  contracts. The suite contains 3 user-job cases and 18 planned runs across
  baseline, Skill-enabled, and 3 repetitions. Behavior-specific ablations live
  in suites whose cases explicitly activate them.
- `.venv/bin/python -m unittest discover -s tests/unit -p 'test_*.py' -v` checks oracle
  isolation, revision-pinned materialization, JSONL recovery, natural route
  evidence, authoritative schema enforcement, required judging, per-case Judge
  Adapter routing, intervention activation, output immutability, domain failure
  tags, presentation, data-analysis, and product-spec deterministic vetoes,
  evidence manifests, rejudge/resume, and paired deltas.
- `.venv/bin/python evals/runners/evalctl.py validate --suite
  evals/suites/presentation-image-smoke.json` validates the three-condition
  historical image-handling pilot before any model sessions are started. Its
  text-only case intentionally excludes the visual-guidance ablation.
- `.venv/bin/python evals/runners/evalctl.py validate --suite
  evals/suites/presentation-image-assets-smoke.json` validates the controlled
  asset-selection case with required desktop/mobile/brand images, forbidden
  distractors, extreme aspect ratios, and the revision-pinned historical
  visual-guidance ablation.
- `.venv/bin/python evals/runners/evalctl.py validate --suite
  evals/suites/presentation-current-image-assets-ab.json` validates the current
  baseline/Skill/asset-guidance ablation experiment with 3 repetitions and
  required judging.
- `.venv/bin/python evals/runners/evalctl.py validate --suite
  evals/suites/presentation-precision-edit-ab.json` validates the natural-route
  baseline/Skill/precision-guidance ablation experiment. The Judge Adapter
  requires a schema-valid edit manifest, the unique target replacement, one
  allowed changed package part, exact normalized XML equivalence, semantic
  preservation, and a baseline-aware final gate.
- `.venv/bin/python evals/runners/evalctl.py validate --suite
  evals/suites/document-board-memo-ab.json` validates the single-repetition
  baseline/Document migration. The Judge Adapter persists Markdown inspection,
  source-concept, structure, artifact-declaration, and blind reader-quality
  evidence without treating semantic term misses as deterministic failures.
- `.venv/bin/python evals/runners/evalctl.py validate --suite
  evals/suites/document-redline-review-ab.json` validates the single-repetition
  baseline/Document editorial-review migration. Case-defined review mode drives
  source anchoring, issue coverage, comment actionability, source fidelity, and
  Markdown-versus-native-DOCX workflow review.
- Generated workspaces live under the ignored `work/` directory.
- `tests/run_all.py` uses the current Python interpreter for every Python gate,
  discovers every checked-in suite and Python/Node script, and treats Node as a
  required dependency.
- The repository-owned `skill-packages:<skill>` checks are mandatory. Optional
  `external-quick-validate:<skill>` checks are reported as `skipped` when the
  Codex system validator is unavailable.
- The evaluation runner and Skill validator dependencies are declared in
  `evals/requirements.txt`.
