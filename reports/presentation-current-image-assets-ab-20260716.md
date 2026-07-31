# Presentation Current Image Asset A/B - 2026-07-16

Status: 8 of 9 planned samples completed and were judged. One full-Skill sample
timed out on the initial run and both immutable recovery attempts. This is a
decision-bearing but incomplete evaluation: the observed incremental effect of
the asset-guidance reference is too small and unstable to justify changing
Presentation prose.

Decision: keep the current asset guidance unchanged. Prioritize a
sandbox-compatible render path and bounded fallback behavior, then add an
implicit-visual case before rerunning the ablation.

## Scope

- Suite: `presentation-current-image-assets-ab`
- Case: `create-incident-response-launch`
- Planned repetitions: 3 per condition, 9 total
- Model: `gpt-5.6-sol`, medium reasoning, network enabled
- Source run: `presentation-current-image-assets-ab-20260716-001`
- First recovery: `presentation-current-image-assets-ab-20260716-recovery-001`
- Final common Judge batch:
  `presentation-current-image-assets-ab-20260716-recovery-002`
- Raw local root: `/tmp/linlab-skill-eval-results`
- Agent execution commits: `b86db035bd1ab9db01585a400b14b77c36fc99e4`
  and `35b201149e07a9351ba7a2cf9cc3f48f1cb8eb05`, both clean
- Final Judge commit: `35b201149e07a9351ba7a2cf9cc3f48f1cb8eb05`,
  clean for every scored result
- Judge Adapter SHA-256:
  `780d8da71bfcdee2843fa06964e206973521625f2297f575ee9e0b3ec3569f36`

The Agent-visible prompt explicitly required the official desktop screenshot,
mobile screenshot, and wordmark; prohibited two supplied decoys; required full
viewports with preserved proportions; and required a rendered-deck review.
The hidden oracle measured the same behavior through exact asset matching,
crop/aspect inspection, final renders, and trace evidence.

The ablation was structurally valid. The case activated
`presentation-asset-handling`, and the ablation replaced only
`references/asset-intake.md` with a minimal provenance/aspect note.

| Condition | Skill source SHA-256 | Materialized SHA-256 |
| --- | --- | --- |
| `baseline` | No repository Skill | n/a |
| `presentation-enabled` | `c216379da17e23c16fbc0d6bb1b8fc8dce5afbc7f00754670d0b65e10d5dc916` | same |
| `presentation-no-visual-guidance` | `c216379da17e23c16fbc0d6bb1b8fc8dce5afbc7f00754670d0b65e10d5dc916` | `07827ac49a8b3748e1958d5b475bb8a3dad19ab38429062344ccbd95626e6f97` |

## Completion And Pass State

`Task score` removes the expected route criterion and renormalizes the artifact
criteria. `Task-critical pass` below also ignores the baseline's expected route
failure but retains source fidelity, image, editability, and rendered
verification failures.

| Condition | First-attempt executor success | Final executor success | Judged | Task-critical pass |
| --- | ---: | ---: | ---: | ---: |
| `baseline` | 3/3 | 3/3 | 3/3 | 2/3 |
| `presentation-enabled` | 2/3 | 2/3 | 2/3 | 2/2 |
| `presentation-no-visual-guidance` | 2/3 | 3/3 | 3/3 | 1/3 |

Do not read the full-Skill row as 3/3 and do not impute a zero quality score to
the missing sample. `presentation-enabled/rep-01` timed out after 1800, 2040,
and 2070 seconds. The traces show substantial deck construction, compilation,
inspection, HTML rendering, and fallback PPTX rendering work, but the Agent did
not finish the standard delivery protocol before any timeout.

The ablation's `rep-02` also timed out at 1800 seconds on its first attempt. It
completed on the first recovery at 2040 seconds.

## Final Scores

The final batch rejudged every intact output under one Judge commit. Medians and
ranges exclude the unscored timeout.

| Condition | n | Overall median (range) | Task median (range) | Critical passes |
| --- | ---: | ---: | ---: | ---: |
| `baseline` | 3 | 0.8992 (0.8332-0.9060) | 0.9774 (0.9057-0.9848) | 0/3 overall; 2/3 excluding route |
| `presentation-enabled` | 2 | 0.9632 (0.9516-0.9748) | 0.9600 (0.9474-0.9726) | 2/2 |
| `presentation-no-visual-guidance` | 3 | 0.9488 (0.9452-0.9724) | 0.9443 (0.9404-0.9700) | 1/3 |

Overall score is not a quality comparison against baseline because the
baseline intentionally has no registered Presentation route. Its high Task
scores show that this strongly specified task was solvable without repository
Skill instructions.

Key visual criteria:

| Condition | Visual-plan median | Image-relevance median | Image-fit median | Rendered-verification median |
| --- | ---: | ---: | ---: | ---: |
| `baseline` | 0.960 | 1.000 | 0.970 | 0.980 |
| `presentation-enabled` | 0.935 | 1.000 | 0.965 | 0.865 |
| `presentation-no-visual-guidance` | 0.960 | 1.000 | 0.970 | 0.700 |

Only two full-Skill/ablation pairs completed. Those paired comparisons are the
appropriate estimate of the ablated reference's incremental effect:

| Repetition | Overall delta | Task delta | Agent token delta | Agent duration delta |
| --- | ---: | ---: | ---: | ---: |
| 2 | +0.0064 | +0.0070 | +2,482,872 | +7.3 min |
| 3 | +0.0024 | +0.0026 | +260,626 | +3.0 min |
| Paired median | +0.0044 | +0.0048 | +1,371,749 | +5.1 min |

Both completed pairs favor the full Skill by a small amount, but the gain is
well below a material effect threshold and came with higher Agent cost in both
pairs. There is no completed pair for repetition 1.

## Image Evidence

All eight scored artifacts behaved identically on the deterministic image
contract:

- all three required official assets appeared in every deck;
- both forbidden decoys had zero matches in every deck;
- every required placement had zero crop;
- the maximum measured aspect delta was 0.0001;
- the minimum effective resolution was 135.6 PPI;
- image relevance was 1.00 for every scored sample;
- image fit stayed between 0.94 and 0.98.

The full Skill therefore did not demonstrate an incremental gain in exact asset
selection, decoy rejection, crop, or aspect integrity on this case. This is a
ceiling effect, not evidence that imagery or asset guidance is unimportant: the
prompt and manifest already stated the required files, forbidden files,
`contain` treatment, and zero-crop policy explicitly.

This case does not test implicit visual need, autonomous image sourcing,
candidate relevance under ambiguity, photography, generated conceptual media,
or focal-point `cover` crops.

## Render Review

Independent review of all eight contact sheets and the Judge-identified slides
confirmed that the meaningful failures were export typography and verification
evidence, not image selection or image distortion:

- `baseline/rep-03` has heavily duplicated footer text on slide 9. Its final
  gate also reports tiny text.
- `presentation-enabled/rep-02` preserves every image correctly but contains
  repeated horizontal overprint artifacts through large bold text on multiple
  slides.
- ablation `rep-01` breaks the slide-2 word `incident` across lines and joins
  overlapping text on slide 4.
- ablation `rep-02` renders cleanly, but the trace does not prove that the Agent
  opened or visually inspected the generated contact sheet before delivery.
- `presentation-enabled/rep-03` and ablation `rep-03` are both clean,
  coherent, image-faithful decks.

The final critical-pass difference suggests a possible process benefit from the
full guidance, but it is not decision-grade evidence. The full condition is
missing one sample, one full-Skill deck still has obvious rendered defects, and
the pass state changes under Judge resampling described below.

## Reliability And Cost

Final successful-sample medians:

| Condition | Agent tokens | Agent duration | Judge model tokens | Judge duration |
| --- | ---: | ---: | ---: | ---: |
| `baseline` | 3,889,806 | 14.4 min | 259,359 | 126.0 s |
| `presentation-enabled` | 8,159,931 | 26.1 min | 361,165 | 186.7 s |
| `presentation-no-visual-guidance` | 7,637,614 | 21.3 min | 263,912 | 172.9 s |

Across the source run and only the executor attempts actually rerun during
recovery, cumulative Agent wall time was:

- baseline: 48.1 minutes;
- full Skill: 150.8 minutes;
- ablation: 93.2 minutes;
- total: 292.1 minutes.

The final eight Judge calls consumed 2,350,910 model tokens and 20.6 minutes of
total Adapter time. The custom provider reported no USD estimate, so a monetary
Judge cost cannot be reconstructed. Failed Agent attempts also reported no
final token usage, which means Agent token totals understate actual cost.

Execution reliability is the strongest negative result. Repeated sandbox
failures affected browser launch and LibreOffice conversion. Agents then spent
large portions of their budgets installing browsers, probing application
fallbacks, or building one-off renderers. The full Skill's first-attempt success
rate was only 2/3, and one sample still failed after two recovery attempts.

## Judge Sampling Variance

The first and final recovery batches judged the same immutable executor outputs
with the same Judge commit and Adapter hash. Their Task-score changes ranged
from -0.0426 to +0.0126. In particular:

- full `rep-02` changed from critical fail to pass;
- ablation `rep-01` and `rep-02` changed from pass to critical fail;
- the largest absolute Task-score movement, 0.0426, was six times the larger
  completed paired full-versus-ablation effect of 0.0070.

The final common batch remains the reporting authority, but small score and
pass-rate differences cannot be treated as stable causal effects. Rendered
verification should move more trace-observable checks into deterministic
evidence before it is used as a decision threshold.

## Integrity Audit

- Both recovery `source-run-summary.json` files exactly match the SHA-256 of
  their source `run-summary.json`.
- All 18 recovery lineage records match the referenced source-result SHA-256.
- All 81 final Agent artifact hashes match their files.
- All 8 final Judge evidence-manifest hashes match their files.
- Every scored result records Judge commit `35b2011`, `repo_dirty=false`, the
  same registry hash, and the same Adapter entrypoint hash.
- Full and ablated Skill materializations are stable across repetitions.
- Source and recovery run directories remain unchanged.

## Validation

- 56 eval-platform unit tests passed.
- 45 Presentation integration tests passed.
- The production `presentation-current-image-assets-ab` suite validates with
  9 planned runs and the expected intervention-activation mapping.
- Strict Python compilation passed for all eval runners and Judge Adapters.
- `git diff --check` passed.

## Decision And Next Gate

Decision: retain the current Presentation asset guidance without adding,
removing, or rewriting prose from this result. The explicit task contract made
all conditions image-faithful, and the observed incremental gain is smaller
than Judge variance.

Before another Presentation prose experiment:

1. Provide one sandbox-compatible canonical browser and PPTX render path, and
   make fallback attempts bounded so a renderer failure cannot consume an
   entire 30-minute execution budget.
2. Make trace-observable verification facts deterministic, including whether
   final contact sheets or full-size slides were actually opened after the last
   render.
3. Add an implicit-visual case that supplies candidate assets without naming
   the winners in the prompt, plus a separate focal-point `cover` crop case.
4. Repeat full versus ablation with three completed pairs and a pre-registered
   material-effect threshold. Do not rerun this exact strong-contract case
   merely to fill the missing sample.

The next optimization target is the production and verification path, not more
asset-guidance text.
