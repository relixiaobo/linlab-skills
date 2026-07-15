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
and trace locations.

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

Criterion ids and failure tags must come from the hidden oracle. The runner adds
oracle weights, computes the weighted score, identifies critical failures, and
normalizes the result. Partial criterion coverage remains a partial judgment.

After every attempt, the runner hashes every regular file under
`judge-evidence/` into `evidence-manifest.json`. The result records adapter id,
kind, protocol, registry hash, exact command, merged config, logs, exit code, and
evidence-manifest hash. This preserves which evaluator actually produced the
observation.

## Adapter Rules

- Prefer deterministic evidence before model judgment.
- Keep provider, renderer, parser, and tool failures separate from artifact
  quality failures.
- Blind model judges to condition names and prior scores.
- Ground every score in persisted evidence; do not reward response claims alone.
- Treat a missing required artifact as missing evidence, not a model-review
  opportunity.
- Keep domain-specific logic inside the adapter. Do not add presentation, code
  review, data, document, or spreadsheet branches to `evalctl`.
- Add a fixture registry and a mixed-case runner test for new protocol behavior.

## Current Coverage

`presentation` is the first production adapter. The mixed fixture suite proves
that one suite can resolve two different adapters. Canonical data-analysis,
product-spec, code-review, and other artifact adapters remain explicit migration
work; cases without `evaluation.adapter` stay unjudged unless a command override
is supplied.
