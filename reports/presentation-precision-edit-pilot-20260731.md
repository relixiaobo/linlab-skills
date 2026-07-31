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
- Final Judge commit: `fd1b402608e90436e0a35b0209df9860e4d6a9c9`,
  clean for all three conditions
- Judge registry SHA-256:
  `5a5b6b3da5634ebeec7403d2fe9450dfcfec2b20fc717e8a73bc7182899df4f4`
- Presentation Judge Adapter SHA-256:
  `44f451f94f063794845b91889d82c4dd87bf8e2bb6f0f5376ed1e94cccbab2f7`

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
| `baseline` | 0.8000 | 0.8889 | No | `correct-route`, `verification-evidence` |
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
| `baseline` | 336,677 | 5.28 min | 237,499 | 1.91 min |
| `presentation-enabled` | 898,006 | 7.88 min | 228,359 | 1.55 min |
| `presentation-no-precision-edit-guidance` | 606,641 | 9.22 min | 233,817 | 1.84 min |

Against the ablation, the full Skill gained 0.1000 overall and 0.1111 Task
score, used 291,365 more Agent tokens, and finished the Agent phase 1.34 minutes
faster in this sample. The Judge used 5,458 fewer model tokens and finished
0.29 minutes faster. The provider reported no USD estimates.
These single-sample cost differences must not be generalized.

## Recovery And Integrity

The initial run used the registry command loaded before the interpreter fix.
All three Agent executions succeeded, but each Judge exited immediately because
system `python3` lacked `jsonschema`. Commit `fc45be8` added the `{python}`
placeholder, mapped it to the interpreter running `evalctl.py`, and changed all
production adapters to use it. Final `rejudge` then reused the intact Agent
artifacts and completed the first successful batch with `.venv/bin/python`.

An external review then found that the first successful blind-review batch was
not actually blind: nested path fields in `precision-edit.json` exposed the
condition directory. Those scores are superseded and are not reported above.
Commit `fd1b402` recursively redacts run, condition, repository, Agent-output,
and Judge-evidence paths in the temporary model workspace and rejects the
review whenever condition IDs, run IDs, or run-root paths remain. It also:

- recomputes `passed` after every deterministic cap and always appends the
  deterministic rationale and evidence;
- requires exactly one manifest operation and binds its action, change field,
  text target, source path and hash, output path, package parts, and operation
  references to the artifacts actually judged;
- compares schema-valid SHA-256 values case-insensitively.

The final reporting authority is the clean post-review rejudge at `fd1b402`.
Live inspection of all three temporary blind workspaces found no condition or
run-root marker. Generated tool-report file paths were relative under `source/`
or `judge-evidence/`; a recursive query for absolute strings in each
`precision-edit.json` returned an empty set.

The interpreter failure has no bearing on the quality scores. The final
rejudge integrity gate accepted every source result before judging, and a
separate hash audit verified:

- all 25 recorded Agent artifacts and traces;
- all 3 Judge evidence manifests against the hashes recorded in each result;
- all 48 Judge evidence records.

Every recorded SHA-256 matched its file. All final Judges used the same clean
commit, registry hash, and Adapter entrypoint hash.

## Validation

- 64 eval-platform unit tests passed.
- 45 Presentation integration tests passed.
- The full `tests/run_all.py` repository gate passed.
- The production suite validates with 9 planned runs and the expected
  `presentation-precision-editing` activation on the ablation.
- Strict Python compilation and `git diff --check` passed.
- Regression tests cover condition-path leakage, contradictory and additional
  manifest operations, uppercase SHA-256 values, and model `passed` flags that
  conflict with deterministic vetoes.

## Next Gate

The pilot is sufficient to merge the migration because it proves natural
routing, exact hidden-oracle enforcement, deterministic package preservation,
structured-manifest discrimination, rejudging, and provenance capture end to
end. It is not sufficient to claim a stable quality or efficiency advantage.

The next decision-bearing run should use the suite's checked-in three
repetitions. The keep/change/retire decision should compare paired full-Skill
and ablation results, report critical-pass consistency, and treat the manifest
criterion separately from edit correctness so the mechanism remains visible.
