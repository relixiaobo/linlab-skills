# Representative Skill Evaluation Pilot - 2026-07-15

Status: calibration pilot complete. All seven Agent runs and all seven
production Judge Adapter runs completed, but the experiment has one repetition
and exposed scoring-calibration defects. It is not decision-grade evidence for
changing or retiring a Skill.

## Scope

- Suite: `representative-ab`
- Run id: `representative-pilot-20260715-001`
- Repetitions: 1 per condition, overriding the suite default of 3
- Planned and completed runs: 7 Agent runs and 7 required judgments
- Model: `gpt-5.6-sol`, medium reasoning, network enabled
- Provider: isolated forwarding of the active custom provider
- Repository commit: `abd50df912d753abe25a8804c849852c43ba8d26`
- Repository state at launch: clean
- Judge registry SHA-256:
  `27dc1a148d2e66c304e08f50ccb387b751bcfbdde5b2a52f820285e07680a1c2`
- Raw local run: `results/representative-pilot-20260715-001`
- Estimated USD cost: unavailable from the custom provider; token counts are the
  cost proxy

Pinned interventions:

| Condition | Skill | Source SHA-256 | Materialized SHA-256 |
| --- | --- | --- | --- |
| `baseline` | none | n/a | n/a |
| `presentation-enabled` | `presentation` | `1efea4c03751faa168720ee5a1b2e8a97354ce58f2ac12980d5fd89b7fabab75` | same |
| `presentation-no-visual-guidance` | `presentation` | `1efea4c03751faa168720ee5a1b2e8a97354ce58f2ac12980d5fd89b7fabab75` | `b5f092e690e5b406d85d7f48dd18214ced70a807e57430d5463a3525e5986676` |
| `data-analysis-enabled` | `data-analysis` | `6cb33e74d220f0f84f1bb256f4634e352b46e453bb6337a9442d1fe4de6be4a4` | same |
| `shape-product-spec-enabled` | `shape-product-spec` | `a8b4331f348a1cdf6596f30b32ba73a2d3e92f060f5433159162fdda658c0a4e` | same |

The Presentation ablation changed only
`presentation/references/asset-intake.md`; all other Skill files were identical
to `presentation-enabled`.

## Score Interpretation

Every case assigns 0.10 to `correct-route`. A no-Skill control must score zero
on that criterion by construction, so raw deltas mix routing with task quality.
The table therefore also reports a route-neutral Task score:

```text
Task score = (raw score - 0.10 * route score) / 0.90
```

Judge tokens are evaluation overhead. Agent tokens and Agent duration measure
the treatment's execution cost. Judge wall time is not currently persisted as a
first-class result field.

| Case / condition | Raw score | Task score | Critical pass | Agent tokens | Judge tokens | Agent duration |
| --- | ---: | ---: | --- | ---: | ---: | ---: |
| Presentation / `baseline` | 0.8586 | 0.9540 | No: route, verification | 2,129,426 | 223,796 | 15.9 min |
| Presentation / `presentation-enabled` | 0.9769 | 0.9743 | Yes | 4,565,171 | 166,325 | 20.0 min |
| Presentation / `presentation-no-visual-guidance` | 0.9187 | 0.9097 | No: verification | 4,792,814 | 279,926 | 14.9 min |
| Data / `baseline` | 0.6850 | 0.7611 | No: route, fan-out | 77,665 | 47,446 | 1.56 min |
| Data / `data-analysis-enabled` | 1.0000 | 1.0000 | Yes | 368,914 | 51,117 | 4.02 min |
| Product spec / `baseline` | 0.6048 | 0.6720 | No: route, flows, scope | 142,140 | 140,824 | 4.70 min |
| Product spec / `shape-product-spec-enabled` | 0.8908 | 0.8787 | Yes | 206,168 | 112,006 | 5.26 min |

## Paired Results

### Presentation

`presentation-enabled` versus baseline improved raw score by 0.1183, but only
0.0203 after removing route. Agent tokens increased 114.4% and Agent duration
increased 25.6%. Both decks were highly faithful, editable ten-slide decks with
native constructed visuals and no placed images.

The complete visual guidance scored 0.0647 higher on Task score than the
ablation while using 4.7% fewer Agent tokens, but taking 34.0% longer. Most of
that score gap came from compiled-PPTX verification and one run's slide-9 label
wrapping, not from image selection or image fit.

This case cannot evaluate the intervention named by the ablation. The input
contains only Markdown and supplies no photos, screenshots, logos, or candidate
assets. All three decks have `picture_count=0`; the visual story is carried by
editable shapes and charts. The controlled image case in
`presentation-image-assets-smoke` remains the relevant test for source identity,
selection, crop, aspect ratio, and raster legibility.

### Data Analysis

`data-analysis-enabled` improved raw score by 0.3150 and Task score by 0.2389.
It used 375.0% more Agent tokens and 158.0% more Agent time. Both conditions
computed the three requested values correctly and independently reconciled
order-level and line-level revenue. The enabled condition additionally produced
the required auditable ledger contract, a definition contract, a reproducible
calculation, and an independent awk verification, earning 1.0000.

This is the strongest directional capability gain in the pilot. The exact size
is overstated by a deterministic false negative on the baseline fan-out
explanation, but the ledger and reproducibility gain is real and directly
observable.

### Product Specification

`shape-product-spec-enabled` improved raw score by 0.2860 and Task score by
0.2067. Agent tokens increased 45.0% and Agent duration increased 12.0%. The
enabled spec adds an explicit empty state, clearer screen and lifecycle states,
and more consistently observable acceptance criteria.

The measured delta is materially inflated by literal term matching. The blind
review found the baseline's clean-slate model, constrained release, non-goals,
and owner-policy question semantically clear, while deterministic term misses
capped three criteria at 0.50. The enabled result was also capped at 0.50 for
`target-options` even though its `TRD-1` section explicitly described the
trade-off. The direction is promising; the numeric effect is not calibrated.

## Failure Distribution

All executor and Judge Adapter invocations completed. There were no provider,
protocol, missing-artifact, or adapter-routing failures.

| Critical criterion | Count | Interpretation |
| --- | ---: | --- |
| `correct-route` | 3 | Expected for all three no-Skill controls |
| `rendered-verification` | 2 | Presentation baseline and visual-guidance ablation |
| `fanout-control` | 1 | Deterministic false negative on a substantively correct baseline explanation |
| `flows-and-states` | 1 | Baseline omitted an explicit empty state |
| `scope-and-open-policy` | 1 | Literal matcher missed clearly labeled non-goals |

Three of seven results passed every critical criterion: the three fully enabled
Skill conditions. That count must not be interpreted as a 100% Skill win rate
because control routing is intentionally scored as a critical failure.

## Judge Calibration Findings

1. Raw score is confounded by route. `run-summary.json` currently presents raw
   paired deltas, so a treatment receives an automatic 0.10 advantage over its
   control. Task score should be a first-class summary metric.
2. Deterministic vetoes exceed their reliable measurement boundary. Exact
   structure, numeric truth, artifact integrity, and source-asset identity are
   appropriate for deterministic caps. Open-ended semantic coverage based on a
   small phrase list is not.
3. The Data Judge marked `fanout=false` because the baseline did not use the
   literal fan-out vocabulary, despite explaining unique order grain, 3-to-5
   row expansion, and the incorrect 720.00 joined sum. The model rationale then
   contradicted the deterministic 0.50 cap.
4. The Product-spec Judge missed concepts expressed with valid synonyms or
   section semantics: items under `Non-goals` did not match "out of scope"; the
   baseline's selected MVP did not match "selected target"; and the enabled
   spec's explicit `TRD-1` trade-off did not match the phrase list.
5. The Presentation gate treated the legitimate phrase "low sample size" as a
   placeholder and treated three small numbered badges as blocking. The blind
   review found the rendered slide readable, yet the critical verification
   score was capped at 0.72.
6. Judge token usage is recorded, but Judge duration and per-attempt latency are
   absent from the result contract. End-to-end evaluation cost is therefore not
   fully observable.
7. Mutation sensitivity is not guaranteed by suite construction. The
   asset-guidance ablation ran against a case with no assets, so the intended
   behavior was never activated.

## Decision

Evaluation-system decision: keep the case x condition x repetition architecture
and the three production Adapter boundaries, but change score reporting and
deterministic-cap policy before using the system as a release gate.

Skill decisions:

- `presentation`: no decision from this suite. Its route-neutral gain is small,
  expensive, and unrelated to the image behavior targeted by the ablation.
- `data-analysis`: retain for repeated evaluation. It shows a strong, concrete
  auditability gain that plausibly justifies its cost, pending calibrated repeats.
- `shape-product-spec`: retain for repeated evaluation. It improves state and
  acceptance coverage at moderate cost, but the measured delta is inflated by
  Judge term matching.
- Presentation visual guidance: do not remove or promote based on this case;
  use image-sensitive cases instead.

No Skill prose change should be promoted from this single run.

## Next Gate

1. Add route-neutral Task score and its paired delta to the generated run
   summary while preserving raw score for routing evaluation.
2. Restrict deterministic score caps to high-precision evidence. Treat missing
   free-form semantic phrase matches as Judge evidence or warnings unless the
   case supplies a robust structured contract.
3. Fix the known placeholder false positive and record Judge duration and
   attempt latency.
4. Add suite validation for intervention activation: an ablation must name the
   behavior it changes, and at least one paired case must contain a trigger and
   a hidden observable for that behavior.
5. Rejudge the preserved outputs under the corrected adapters to measure the
   calibration delta, without presenting that as a fresh Agent run.
6. Run three fresh repetitions after calibration and report paired medians,
   dispersion, critical-pass rate, Agent cost, and Judge cost. Only then make a
   keep/change/retire decision.
