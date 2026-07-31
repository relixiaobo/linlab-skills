# Presentation Precision Edit Migration Pilot - 2026-07-31

Status: migration and calibration pilot passed. The migrated Case, three-way
ablation, private oracle, and Presentation Judge distinguish correct package
editing from the structured verification behavior supplied by the full Skill.
This one-repetition pilot is not a decision-grade estimate of effect size.

Decision: merge the migrated evaluation and keep the current precision-edit
guidance unchanged. Run the checked-in three repetitions before making a
broader keep/change/retire decision about the guidance.

## Scope

- Suite: `presentation-precision-edit-ab`
- Case: `edit-board-deck-subtitle`
- Run id: `presentation-precision-edit-pilot-20260731-05`
- Repetition override: 1 per condition, 3 total
- Model: `gpt-5.6-sol`, medium reasoning; Agent network enabled
- Raw local root:
  `/tmp/linlab-skill-eval-results/presentation-precision-edit-pilot-20260731-05`
- Agent execution commit: `c78da95f848530ba245b261c40e676501853e0fe`,
  clean for all three conditions
- Final Judge commit: `fc45be8e305c0d70848b8813901f8517df8af358`,
  clean for all three conditions
- Judge registry SHA-256:
  `5a5b6b3da5634ebeec7403d2fe9450dfcfec2b20fc717e8a73bc7182899df4f4`
- Presentation Judge Adapter SHA-256:
  `2c3f2aca7de8186db0e1dac81c3814ba0777207f22f53e765fee39ad1a8b50ec`

The task changes the unique slide 7 subtitle from `Q3 pipeline` to
`Q4 pipeline`. Every other text value, object property, note, relationship,
slide state, theme, package part, and presentation property must be preserved.
The hidden oracle also requires a schema-valid edit manifest whose source,
target, operation, and allowed package scope match the request.

| Condition | Skill source SHA-256 | Materialized SHA-256 |
| --- | --- | --- |
| `baseline` | No repository Skill | n/a |
| `presentation-enabled` | `2d12d4ab65be0e588b0e92ec298e0ca0a6891d0f6f6b5dde9c4a22347038b46a` | same |
| `presentation-no-precision-edit-guidance` | `2d12d4ab65be0e588b0e92ec298e0ca0a6891d0f6f6b5dde9c4a22347038b46a` | `b5328ec4341b5dcdc0110e4fe4ce583b3354345d7bc48a4e95c6cd4a5a02fd05` |

The ablation replaces only `SKILL.md` with the minimal same-name Presentation
overlay. It preserves natural routing while removing the exact targeting,
minimum OOXML patch, baseline-aware gate, and package-scope workflow under
test.

## Results

| Condition | Overall | Task | Critical pass | Critical failures |
| --- | ---: | ---: | --- | --- |
| `baseline` | 0.7950 | 0.8833 | No | `correct-route`, `verification-evidence` |
| `presentation-enabled` | 1.0000 | 1.0000 | Yes | None |
| `presentation-no-precision-edit-guidance` | 0.9000 | 0.8889 | No | `verification-evidence` |

All three conditions completed the requested PPTX edit correctly. Deterministic
evidence was identical on the core artifact contract:

- the source contained one old target and no new target;
- each edited deck contained no old target and exactly one new target;
- exactly one of 56 OPC members changed:
  `ppt/slides/slide7.xml`;
- the only object-level semantic change was the text on `shape:id:7`;
- slide count and order, all ten speaker notes, relationships, presentation
  state, and every non-target semantic field were preserved;
- the baseline-aware final technical gate reported no new regression.

The full Skill alone delivered one schema-valid edit manifest matching the
source hash, exact target, requested replacement, and allowed package part.
Baseline and ablation each delivered no manifest, so the deterministic cap set
`verification-evidence` to zero. This is the intended intervention boundary:
the ablation still routed to Presentation and produced the correct deck, but it
did not produce the auditable edit contract required by the full workflow.

The baseline's additional route failure is expected for a no-Skill control.
Its Task score excludes that route criterion and therefore remains comparable
to the artifact criteria.

## Cost And Runtime

| Condition | Agent tokens | Agent duration | Judge model tokens | Judge duration |
| --- | ---: | ---: | ---: | ---: |
| `baseline` | 336,677 | 5.28 min | 171,381 | 1.83 min |
| `presentation-enabled` | 898,006 | 7.88 min | 293,007 | 3.36 min |
| `presentation-no-precision-edit-guidance` | 606,641 | 9.22 min | 269,827 | 1.83 min |

Against the ablation, the full Skill gained 0.1000 overall and 0.1111 Task
score, used 291,365 more Agent tokens, and finished the Agent phase 1.34 minutes
faster in this sample. The Judge used 23,180 more model tokens and 1.53 more
minutes for the fuller evidence set. The provider reported no USD estimates.
These single-sample cost differences must not be generalized.

## Recovery And Integrity

The initial run used the registry command loaded before the interpreter fix.
All three Agent executions succeeded, but each Judge exited immediately because
system `python3` lacked `jsonschema`. Commit `fc45be8` added the `{python}`
placeholder, mapped it to the interpreter running `evalctl.py`, and changed all
production adapters to use it. Final `rejudge` then reused the intact Agent
artifacts and completed all three conditions with `.venv/bin/python`.

The interpreter failure has no bearing on the quality scores. The final
rejudge integrity gate accepted every source result before judging, and a
separate hash audit verified:

- all 25 recorded Agent artifacts and traces;
- all 3 Judge evidence manifests against the hashes recorded in each result;
- all 48 Judge evidence records.

Every recorded SHA-256 matched its file. All final Judges used the same clean
commit, registry hash, and Adapter entrypoint hash.

## Validation

- 60 eval-platform unit tests passed.
- 45 Presentation integration tests passed.
- The full `tests/run_all.py` repository gate passed.
- The production suite validates with 9 planned runs and the expected
  `presentation-precision-editing` activation on the ablation.
- Strict Python compilation and `git diff --check` passed.

## Next Gate

The pilot is sufficient to merge the migration because it proves natural
routing, exact hidden-oracle enforcement, deterministic package preservation,
structured-manifest discrimination, rejudging, and provenance capture end to
end. It is not sufficient to claim a stable quality or efficiency advantage.

The next decision-bearing run should use the suite's checked-in three
repetitions. The keep/change/retire decision should compare paired full-Skill
and ablation results, report critical-pass consistency, and treat the manifest
criterion separately from edit correctness so the mechanism remains visible.
