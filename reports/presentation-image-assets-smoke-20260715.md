# Presentation Controlled Image Asset Smoke - 2026-07-15

Status: controlled smoke complete. The result is directional evidence, not a
keep/change/retire decision, because every condition has only one fresh run.

## Scope

- Suite: `presentation-image-assets-smoke`
- Run id: `presentation-image-assets-smoke-20260715-01`
- Case: `create-incident-response-launch`
- Repetitions: 1 per condition
- Model: `gpt-5.6-sol`, medium reasoning, network enabled
- Provider: isolated forwarding of the active custom provider
- Repository commit: `5202c96c3d11e6cbe40f8f01dfb5fa000f6be3d8`
- Repository state: clean
- Raw local run:
  `/tmp/linlab-skill-eval-results/presentation-image-assets-smoke-20260715-01`

The Agent-visible task required an editable 8-10 slide partner launch deck with
speaker notes. It supplied an official 16:10 desktop UI, 9:16 mobile UI, and
5:1 wordmark, plus a third-party dashboard and generic architecture-photo
decoy. The hidden oracle required all three official assets, prohibited both
decoys, required `contain` treatment with zero crop, and judged final renders.

Pinned interventions:

| Condition | Revision | Source / materialized SHA-256 |
| --- | --- | --- |
| `baseline` | No repository Skill | n/a |
| `presentation-main` | `92ac3e14332a31a4905946add5e40a276ff22afc` | `1efea4c03751faa168720ee5a1b2e8a97354ce58f2ac12980d5fd89b7fabab75` / same |
| `presentation-image-improved` | `0fdd27c2d8f182d1785832c75da5362554b321f5` | `c9747f89ca8db04aab6fc4d826523fff331ab2552f3a1bb5ffb2b4f1aba3711c` / same |
| visual-instruction ablation | Same improved revision | `c9747f89ca8db04aab6fc4d826523fff331ab2552f3a1bb5ffb2b4f1aba3711c` / `3db1641172c8017dfd591b40a52bc361382d6e5787fbcb43f7fa40a327520de7` |

The ablation retained the improved tooling but restored the pre-change top-level
workflow, routing description, asset-intake, export, Studio, and verification
instructions.

## Results

`Task score` removes the expected 0.08 route criterion and renormalizes the
remaining outcome criteria. This prevents the control's intentional route
failure from being mistaken for artifact quality.

| Condition | Score | Task score | Image relevance / fit / verification | Critical failures | Exact required assets | Tokens | Agent duration |
| --- | ---: | ---: | --- | --- | ---: | ---: | ---: |
| `baseline` | 0.9068 | 0.9857 | 1.00 / 0.96 / 0.99 | `correct-route` (expected) | 3/3 | 3,807,748 | 11.5 min |
| `presentation-main` | 0.8920 | 0.8826 | 1.00 / 0.70 / 0.70 | `image-fit`, `rendered-verification` | 3/3 | 6,085,719 | 22.0 min |
| `presentation-image-improved` | 0.9272 | 0.9209 | 1.00 / 0.88 / 0.70 | `rendered-verification` | 3/3 | 7,582,668 | 20.5 min |
| visual-instruction ablation | 0.8360 | 0.8217 | 0.25 / 0.96 / 0.99 | `image-relevance` | 0/3 exact; 3/3 visible derivatives | 10,365,826 | 26.9 min |

All four conditions excluded both forbidden assets. Every exact required-asset
use in the first three conditions had zero crop and effectively zero aspect
delta. No condition passed every critical criterion.

Key deltas:

- Improved versus main: +0.0352 overall and +0.0383 task score. It removed the
  critical image-fit failure, used 24.6% more tokens, and finished 6.7% faster.
- Improved versus the visual-instruction ablation: +0.0912 overall and +0.0991
  task score, while using 26.8% fewer tokens and finishing 23.7% faster.
- Improved versus baseline: +0.0204 overall only because it passed routing. Its
  task score was 0.0648 lower, with 99.1% more tokens and 77.8% more Agent time.

## Render Review

Independent review of every contact sheet and each judge-identified failure
slide confirmed the following:

- `baseline` produced the strongest artifact in this repetition. It used the
  official desktop UI on slides 1-2, mobile UI on slide 4, and wordmark on
  slides 1 and 9. All were complete, proportional, clean, and legible.
- `presentation-main` used the correct exact assets without crop or stretch,
  but red eyebrow text crossed the official wordmark on slides 1 and 9. The
  tagline was also too small. Its claimed final review did not catch either
  repeated brand defect.
- `presentation-image-improved` retained every official source file exactly,
  excluded both decoys, and preserved complete viewports. Smaller UI labels
  approached the practical legibility limit. More importantly, the real Office
  render joined the third slide-5 workflow label as `Reviewactivity`; the
  Agent's fallback geometry renderer did not reproduce or catch that defect.
- The visual-instruction ablation was visually strong and clearly showed the
  official desktop, mobile, and wordmark content. Its compiler nevertheless
  embedded browser-rendered derivatives rather than the original media: the
  desktop ratio became 1.6028 instead of 1.6000 and mobile became 0.5605 instead
  of 0.5625. The exact-source matcher therefore found 0/3 required files and
  applied the documented relevance cap.

The ablation result is not evidence that it selected unrelated images. It is
evidence that, without the new visual instructions, the workflow lost auditable
source identity and slightly resampled identity-bearing media. Exact SHA
matching currently conflates that provenance failure with semantic relevance;
future reports should expose both dimensions even if the critical provenance
veto remains.

## What This Establishes

1. The controlled case is image-sensitive. Unlike the earlier investor-update
   smoke, it exercises real raster media, required and forbidden selection,
   extreme aspect ratios, crop, legibility, and rendered verification.
2. The new visual instructions have directional causal value beyond the tool
   changes. They kept exact official media auditable and outperformed the
   ablation on quality, tokens, and time in this repetition.
3. The improved instructions are not sufficient for delivery. A deck can pass
   source matching, crop, aspect, and package gates while still failing final
   text fit under a real presentation renderer.
4. The Skill has not demonstrated net value over the explicit no-Skill control.
   The baseline produced a better task artifact at roughly half the tokens.
5. This case tests selection among supplied assets and `contain` treatment. It
   does not test autonomous image sourcing, implicit visual need, photography,
   `cover` focal-point crops, or generated conceptual media.

## Decision And Next Gate

Decision: defer keep/change/retire. Do not remove the new visual instructions;
they have a plausible positive effect. Do not promote them as proven either.

Before the decision-grade run, separate semantic asset match from exact-source
provenance in the reported evidence. A normalized pixel or perceptual matcher
should recognize faithful resized derivatives, while exact SHA remains the
stronger direct provenance signal. Forbidden assets should be checked through
both exact and normalized visual matching.

Then run the same four conditions for three fresh repetitions and add a second
case covering implicit visual need plus a focal-point `cover` crop. Pre-register
the decision rule:

- at least 2/3 improved runs pass every critical image and verification gate;
- median task score improves by at least 0.03 over `presentation-main`;
- median image relevance and fit do not regress against either control;
- median token overhead versus `presentation-main` stays at or below 25%, or a
  unique capability gain justifies it;
- against the no-Skill control, the Skill either stays within 0.03 task score or
  proves a unique gain on the implicit-visual case.

If quality does not repeat or the cost remains material without a unique gain,
simplify the instructions or retire the added workflow surface.
