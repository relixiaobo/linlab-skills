# Presentation Image Smoke Pilot - 2026-07-15

Status: infrastructure pilot only. It provides no evidence that one
Presentation Skill version is better than another.

## Scope

- Suite: `presentation-image-smoke`
- Run id: `presentation-image-smoke-20260715`
- Case: `create-investor-update`
- Repetitions: 1 per condition
- Model: `gpt-5.6-sol`, medium reasoning, network enabled
- Provider: isolated forwarding of the active custom provider
- Repository commit: `7ddfada3e31e0c776f9dbb922b1b2869f22e0a9f`
- Repository state: dirty because the revision adapter and judge were under test
- Raw local run: `/tmp/linlab-skill-eval-results/presentation-image-smoke-20260715`

Pinned interventions:

| Condition | Skill revision / materialization |
| --- | --- |
| `baseline` | No repository Skill |
| `presentation-main` | `92ac3e14332a31a4905946add5e40a276ff22afc`, source `1efea4c03751faa168720ee5a1b2e8a97354ce58f2ac12980d5fd89b7fabab75` |
| `presentation-image-improved` | `0fdd27c2d8f182d1785832c75da5362554b321f5`, source `c9747f89ca8db04aab6fc4d826523fff331ab2552f3a1bb5ffb2b4f1aba3711c` |
| visual-instruction ablation | Same improved revision, materialized `3db1641172c8017dfd591b40a52bc361382d6e5787fbcb43f7fa40a327520de7` |

## Observed Failures

| Condition | Agent outcome | Judge outcome | Infrastructure finding |
| --- | --- | --- | --- |
| `baseline` | The trace shows a completed 10-slide PPTX and final checks, but no artifact survived | Not run | Three malformed JSONL transport lines caused the strict adapter to reject the successful session; recoverable usage is 2,145,618 tokens |
| `presentation-main` | PPTX, contact sheet, and verification report survived | Failed before scoring | The active provider returned repeated 502 responses; route detection also missed the relative `skills/presentation/SKILL.md` read |
| `presentation-image-improved` | The trace shows a completed 10-slide PPTX, contact sheet, and clean gate, but no artifact survived | Not run | Three malformed JSONL transport lines caused the same adapter failure; recoverable usage is 5,660,649 tokens |
| visual-instruction ablation | PPTX, HTML, contact sheet, and verification report survived | Failed before scoring | The active provider returned repeated 502 responses; route detection had the same relative-path false negative |

All four stored result statuses are `failed` and all quality scores are null.
The two judge failures are identical upstream availability failures, not deck
review outcomes. The two executor failures occurred after the Agent finished its
work and are adapter data-loss defects, not Agent failures.

## Infrastructure Decisions

1. Preserve raw traces and copy deliverables before JSONL interpretation.
2. Recover valid events around malformed lines and record exact parse diagnostics.
3. Treat relative reads of a materialized `SKILL.md` as natural-routing evidence.
4. Persist deterministic judge evidence before blind model review.
5. Retry only transient model-provider failures and retain every attempt.
6. Support immutable-source `resume`: rejudge intact outputs and rerun only lost
   executor artifacts under a new run id with explicit lineage.

## Decision

No keep/change/retire decision is permitted from this pilot. The next admissible
step is a recovery run to validate the harness, followed by a fresh repeated
benchmark before drawing a Presentation Skill quality conclusion.

## Recovery Run

Run id: `presentation-image-smoke-20260715-recovery-01`

The immutable-source resume path reran only the two lost executors and reused the
two intact outputs. All four conditions then completed blind rejudging.

| Condition | Recovery action | Agent tokens | Score | Critical pass |
| --- | --- | ---: | ---: | --- |
| `baseline` | Reran executor | 2,619,229 | 0.8789 | No: expected control-route failure |
| `presentation-main` | Reused executor output | 6,451,940 | 0.9358 | No: rendered verification |
| `presentation-image-improved` | Reran executor | 4,331,848 | 0.8659 | No: rendered verification |
| visual-instruction ablation | Reused executor output | 9,268,764 | 0.9737 | Yes |

The initial recovery judges still failed because the active custom provider
returned 502 for `--output-schema`. A minimal controlled probe showed that the
same provider and model succeeded without that argument. Rejudging therefore
used a JSON-only prompt with unchanged local protocol validation; all four
conditions then scored on the first model attempt. LibreOffice rendering also
recovered after an earlier macOS code-signature policy failure.

Direct review of the independent PPTX renders confirmed the judge's critical
findings:

- `presentation-main` slide 8 partially hides the `$92k` label behind the Q2
  bar, and slide 9 places explanatory text at or beyond its panel boundary.
- `presentation-image-improved` has unintended line breaks in the opening
  metrics, month labels, and the central `AGENT WORKSPACE` label.
- the visual-instruction ablation has the cleanest exported sequence in this
  single run.

## Sensitivity Limit

All four PPTX files have `picture_count=0`. The source case supplies no photos,
screenshots, logos, or candidate assets, and the task permits constructed
visuals when appropriate. The judge therefore correctly treated the decks as
analytical and did not penalize the absence of images.

This means the smoke is useful for routing, factual fidelity, editability, and
export verification, but it is not a valid test of image selection, semantic
relevance, `cover`/`contain`, focal-point cropping, or raster stretching. The
score ordering cannot answer the original image-handling question, and the
mixed reused/rerun recovery plus one repetition is not decision-grade evidence.

The next benchmark must add a controlled image-sensitive case with supplied
official screenshots or photos, plausible distractors, varied aspect ratios,
and hidden deterministic asset/crop expectations. Only after that case passes a
fresh repeated A/B/ablation run should the image instructions be kept, changed,
or removed.

That next case is now prepared as `create-incident-response-launch`, with its
four-condition smoke suite in `evals/suites/presentation-image-assets-smoke.json`.
It supplies approved 16:10 desktop UI, 9:16 mobile UI, and 5:1 wordmark assets,
plus a third-party dashboard and generic architecture-photo distractor. The
hidden oracle joins source hashes to PPTX media and tests required use,
forbidden use, crop, aspect integrity, UI legibility, and final rendered review.
