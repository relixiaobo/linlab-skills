# Judge Adapter Contract

Judge Adapters let every user-job case use the same evaluation lifecycle while
keeping domain evidence and scoring logic outside the runner.

The boundary is job-oriented, not Skill-oriented. A presentation-producing job
may use the `presentation` adapter regardless of which Skill condition produced
the artifact. A data-analysis job can use a different adapter without changing
materialization, isolation, result capture, repetition, comparison, resume, or
rejudge behavior.

## Selection

The hidden case oracle selects an adapter by stable id:

```json
{
  "evaluation": {
    "adapter": "presentation",
    "config": {}
  }
}
```

`registry.json` maps that id to a repository-owned command, supported job ids,
adapter kind, and protocol version. Registry config is merged with case config;
case values win. `--judge-command` remains an explicit whole-suite override for
development and compatibility, and is recorded as adapter `command-override`.
The adapter owns the complete evaluation strategy for the job, including any
deterministic gates and model review. There is no second per-case judge dispatcher.

## Environment

The runner invokes an adapter with a clean copy of the process environment plus:

- `EVAL_ORACLE_FILE`: hidden case oracle;
- `EVAL_RESULT_FILE`: executor observation being judged;
- `EVAL_PAYLOAD_DIR`: Agent-visible prompt and inputs;
- `EVAL_OUTPUT_DIR`: declared Agent deliverables and traces;
- `EVAL_JUDGE_RESULT_FILE`: required raw result destination;
- `EVAL_JUDGE_ADAPTER_ID`: resolved registry id;
- `EVAL_JUDGE_PROTOCOL_VERSION`: currently `1.0`;
- `EVAL_JUDGE_CONFIG`: merged registry and case configuration as JSON;
- `EVAL_JUDGE_EVIDENCE_DIR`: persistent evidence directory;
- `EVAL_JUDGE_TRACE_DIR`: persistent model or tool trace directory.

The adapter must not mutate Agent output. It may write only its result, evidence,
and trace locations. The runner hashes the complete output tree before and after
the adapter and reports `artifact-mutation` when this boundary is violated.

## Result Protocol

The adapter writes JSON compatible with
`evals/schemas/eval-judge-result.schema.json`:

```json
{
  "scores": [
    {
      "criterion_id": "source-fidelity",
      "value": 0.9,
      "passed": true,
      "rationale": "Every source claim is preserved.",
      "evidence": ["artifact/report.md"]
    }
  ],
  "failure_tags": [],
  "summary": "The artifact passed the declared rubric."
}
```

Criterion ids and failure tags must come from the hidden oracle. Failure tags are
domain-defined slugs rather than a core-runner enumeration. The JSON Schema is
the authoritative structural contract and requires explicit pass state,
rationale, evidence, failure tags, and summary. The runner adds oracle weights,
computes both the raw weighted score and a route-neutral Task score, identifies
critical failures, and normalizes the result. Partial criterion coverage remains
a partial judgment and cannot complete a required suite.

After every attempt, the runner hashes every regular file under
`judge-evidence/` into `evidence-manifest.json`. The result records adapter id,
kind, protocol, registry hash, exact command, merged config, logs, exit code,
Judge duration, repository state, Adapter entrypoint hash, and evidence-manifest
hash. Model-assisted adapters also retain per-attempt duration and usage. This
preserves which evaluator actually produced the observation and its cost.

## Adapter Rules

- Prefer deterministic evidence before model judgment.
- Apply deterministic score caps only to high-precision checks such as numeric
  truth, artifact integrity, source identity, or explicit structural contracts.
  Treat free-form phrase matches and misses as semantic review evidence.
- Keep provider, renderer, parser, and tool failures separate from artifact
  quality failures.
- Blind model judges to condition names and prior scores.
- Ground every score in persisted evidence; do not reward response claims alone.
- Judge every `intervention_activations[].observable_outcomes` id through the
  normal outcome protocol and retain evidence that can reveal the declared
  behavior change.
- Put exact metric, filter, grain, and join expectations in structured case
  config so deterministic evidence can be recomputed independently.
- Put presentation slide-count bounds in `evaluation.config.slide_count` with
  integer `minimum` and `maximum` values. The adapter accepts rubric-text ranges
  only as a compatibility fallback and never applies a global slide-count cap.
- Put product-spec facts, state coverage, scope boundaries, and structural
  minimums in criterion-oriented case config instead of hard-coding one answer.
- Put document create/review mode, Markdown artifact format, source facts,
  decision or review expectations, and non-binding structure hints in
  criterion-oriented case config. Do not turn free-form term or layout hints
  into deterministic vetoes.
- Treat a missing required artifact as missing evidence, not a model-review
  opportunity.
- Keep domain-specific logic inside the adapter. Do not add presentation, code
  review, data, document, or spreadsheet branches to `evalctl`.
- Add a fixture registry and a mixed-case runner test for new protocol behavior.

## Current Coverage

`presentation`, `data-analysis`, `product-spec`, `document`, and `spreadsheet`
are production hybrid adapters. Presentation persists PPTX inspection, render,
and asset evidence; data-analysis recomputes metric truth and join fan-out;
product-spec runs the portable readiness inspector and audits Case-defined
facts, options, flows, scope, stable IDs, and acceptance criteria; document
selects Case-defined create or review guidance, runs the portable Markdown
inspector, and audits Case-defined concept and structure hints; spreadsheet
inspects XLSX structure, source fidelity, formulas, names, checks, links, and
recalculation evidence. All apply high-precision deterministic vetoes after
blind review while leaving free-form semantics to the blind evaluator. The
representative suite resolves the first three adapters; the board-memo,
policy-review, and pricing-model suites resolve their domain adapters
independently. Code-review and PDF adapters remain explicit migration work.
Suites must explicitly choose whether judging is required; only optional suites
may contain cases without `evaluation.adapter`.
