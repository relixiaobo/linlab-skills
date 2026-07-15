# Skill Evaluation System

This directory measures whether a Skill changes agent behavior for a user job.
It does not contain deterministic tests for Skill scripts; those live under
`tests/`.

## Evaluation Model

A Skill is an intervention variable. Cases are therefore organized by user job,
not by Skill name:

```text
User task case x execution condition x repetition -> result
```

The control condition exposes no repository Skill. A `skill-enabled` condition
exposes one or more exact Skill packages. An `ablation` condition starts from the
same package and deterministically removes or replaces selected resources. Every
result records hashes for both the source and materialized Skill. A condition may
pin `skills[].revision`; the runner resolves it to a full commit and materializes
the Skill with `git archive`, so later working-tree changes cannot alter the
intervention.

This separation answers four different questions:

1. Did the agent route the user job correctly?
2. Did the Skill improve the outcome or process?
3. Which part of the Skill caused the change?
4. Was the gain worth its token and time cost?

## Directory Boundary

```text
evals/
|-- schemas/       # versioned case, condition, suite, and result contracts
|-- cases/         # user jobs; never grouped by the Skill under test
|-- suites/        # paired experiment matrices and repetitions
|-- conditions/    # baseline, Skill-enabled, and ablation interventions
|-- runners/       # validation, materialization, execution, and aggregation
|-- judges/        # Judge Adapter registry and domain evidence/scoring adapters
+-- regressions/   # promoted failures, when added

tests/
|-- unit/          # runner and pure-function tests
|-- integration/   # deterministic Skill tool/workflow tests
+-- fixtures/      # machine-test fixtures

results/           # generated raw runs; ignored by git
reports/           # reviewed, decision-bearing evaluation reports
portfolio/         # portfolio status and keep/change/retire decisions
```

Legacy definitions remain under `evals/artifact-skills/` and several
Skill-named directories during migration. They are not the canonical format for
new agent evaluations.

## Case Isolation

Each case has a hard Agent-visible/private split:

```text
case-id/
|-- prompt.md      # Agent-visible, natural user request
|-- input/         # Agent-visible source files
+-- oracle.yaml    # judge-only routes, outcomes, weights, and failure taxonomy
```

`prompt.md` must not contain `$skill-name` or otherwise force a Skill. The
runner copies only `prompt.md`, `input/`, and condition-selected Skill packages
into the payload directory. It does not copy `oracle.yaml`, put its path in the
Agent environment, or include the condition id/kind in the adapter manifest.

Checked-in `oracle.yaml` files use JSON-compatible YAML so PyYAML is optional.
All structural contracts are enforced from the checked-in JSON Schemas through
the dependencies declared in `evals/requirements.txt`; Python code adds only
cross-field and filesystem safety rules.

Filesystem separation is necessary but not sufficient. The executor adapter
must start a fresh independent agent session, register exactly the Skills listed
in `agent-manifest.json`, restrict the session to the payload/output roots, and
avoid persistent memory from earlier runs. Do not pass expected answers,
assertions, suspected bugs, intended fixes, or prior conclusions to the Agent.

## Commands

Install the evaluation and repository-validation dependencies once:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r evals/requirements.txt
```

Validate the representative paired suite and all common schemas:

```sh
.venv/bin/python evals/runners/evalctl.py validate \
  --suite evals/suites/representative-ab.json
```

Materialize all payloads without invoking an Agent:

```sh
.venv/bin/python evals/runners/evalctl.py materialize \
  --suite evals/suites/representative-ab.json \
  --run-id local-inspection
```

Execute with an Agent adapter. Each configured case resolves its Judge Adapter
from the hidden oracle and `evals/judges/registry.json`:

```sh
.venv/bin/python evals/runners/evalctl.py run \
  --suite evals/suites/representative-ab.json \
  --run-id model-build-001 \
  --agent-command 'agent-adapter --manifest {manifest}'
```

`--judge-command 'judge-adapter --result {result} --oracle {oracle}'` is an
explicit whole-suite override for development or compatibility. The result
records it as `command-override` rather than a registry adapter.

The repository adapters can run isolated Codex sessions and blind presentation
review directly:

```sh
.venv/bin/python evals/runners/evalctl.py run \
  --suite evals/suites/presentation-image-smoke.json \
  --results-dir /tmp/linlab-skill-eval-results \
  --run-id presentation-image-smoke-001 \
  --agent-command 'python3 {repo}/evals/runners/codex_exec_adapter.py'
```

Rejudge intact artifacts without invoking the Agent again:

```sh
.venv/bin/python evals/runners/evalctl.py rejudge \
  --suite evals/suites/presentation-image-smoke.json \
  --run-root /tmp/linlab-skill-eval-results/presentation-image-smoke-001
```

To preserve a failed run, clone it under a new run id, reuse intact executor
outputs, and rerun only conditions whose executor artifacts are missing or no
longer match their recorded hashes:

```sh
.venv/bin/python evals/runners/evalctl.py resume \
  --suite evals/suites/presentation-image-smoke.json \
  --source-run /tmp/linlab-skill-eval-results/presentation-image-smoke-001 \
  --results-dir /tmp/linlab-skill-eval-results \
  --run-id presentation-image-smoke-001-recovery \
  --agent-command 'python3 {repo}/evals/runners/codex_exec_adapter.py'
```

`resume` never mutates the source run. Each target result records whether it
reused executor output or reran the executor, plus the source result hash.

Agent commands may use `{repo}`, `{run}`, `{payload}`, `{prompt}`, `{input}`,
`{skills}`, `{output}`, `{manifest}`, and `{agent_result}`. Judge commands may
also use `{result}`, `{oracle}`, and `{judge_result}`. The runner rejects hidden
oracle placeholders in an Agent command.

## Executor Protocol

The adapter receives `EVAL_RUN_MANIFEST`, `EVAL_PROMPT_FILE`, `EVAL_INPUT_DIR`,
`EVAL_SKILLS_DIR`, `EVAL_OUTPUT_DIR`, and `EVAL_AGENT_RESULT_FILE`. It must write
`EVAL_AGENT_RESULT_FILE` as JSON:

```json
{
  "status": "completed",
  "response_path": "response.md",
  "artifacts": ["deck.pptx"],
  "traces": ["trace.json"],
  "route": {
    "primary_skill": "presentation",
    "selected_skills": ["presentation"]
  },
  "usage": {
    "input_tokens": 12000,
    "output_tokens": 3000,
    "total_tokens": 15000,
    "estimated_cost_usd": 0.42
  },
  "model": {
    "name": "model-build-id",
    "config": {"reasoning_effort": "high"}
  }
}
```

All response, artifact, and trace paths must be regular files relative to
`EVAL_OUTPUT_DIR`. The runner hashes them before judging.

The bundled Codex adapter copies deliverables before interpreting the event
stream. Malformed JSONL transport lines are skipped only during best-effort
extraction and are recorded in `trace/parse-diagnostics.json`; the untouched raw
trace remains authoritative. A malformed command-output event therefore cannot
discard an otherwise completed artifact, route record, or final usage event.

## Judge Adapter Protocol

The hidden oracle may declare `evaluation.adapter`. The runner resolves that id
from the versioned registry, verifies that it supports the case job, merges
registry and case configuration, and records the exact adapter identity and
registry hash in every result. The adapter owns the complete deterministic,
model, or hybrid judging strategy; cases do not declare a second judge-routing
model.

Every suite explicitly sets `judging.required`. A required suite fails validation
before execution when any case lacks an adapter, and a run succeeds only when all
judgments are complete. Migration or payload-inspection suites may set it to
`false`; their unjudged cases remain explicit in the summary instead of being
mistaken for completed quality evaluations. `--judge-command` supplies a
whole-suite adapter override.

The full registry, environment, evidence-manifest, and authoring contract is in
`evals/judges/README.md`.

An adapter runs only after the Agent process has finished. It receives the hidden
oracle through `EVAL_ORACLE_FILE`, plus result, payload, and output paths. It
writes `EVAL_JUDGE_RESULT_FILE`:

```json
{
  "scores": [
    {
      "criterion_id": "image-relevance",
      "value": 0.8,
      "passed": true,
      "rationale": "Images carry specific slide jobs.",
      "evidence": ["deck.pptx slide 4", "render/slide-004.png"]
    }
  ],
  "failure_tags": [],
  "summary": "No critical visual failure."
}
```

The runner takes weights from the oracle, never from the judge, and computes the
weighted score only when every criterion is present. Partial judging keeps its
total score and pass state null. Completed judging records explicit critical
failures. Raw results include route, artifacts, hashes, model/config, token use,
cost, latency, failures, and provenance. `run-summary.json` pairs each treatment
with the baseline at the same case and repetition and reports metric deltas.

The runner also records adapter id, kind, protocol version, registry path/hash,
exact command, merged config, logs, exit code, and a hash of the generated
evidence manifest. It hashes the Agent output tree before and after judging and
rejects an adapter that mutates it. Domain scoring logic and failure tags belong
to the adapter and case contract, never in `evalctl`.

The presentation judge first persists deterministic PPTX inspection, gate, and
render evidence under `judge-evidence/`. Blind model review runs afterward and
retries only transient provider failures such as 429, 502, timeouts, or stream
disconnects. Every attempt is retained under `judge-trace/attempt-NN/`. Judge
infrastructure failure leaves quality scores null; it is not a zero score.
Structured output defaults to schema mode for the OpenAI provider and to a
JSON-only prompt plus the same local protocol validation for custom providers.
This avoids treating a provider's unsupported response-format parameter as a
deck failure. Transient local renderer failures are also retried and remain
judge infrastructure errors if they do not recover.

The data-analysis judge independently recomputes configured metrics from the
source CSV, verifies the declared filter and grain, measures one-to-many join
inflation, validates the findings ledger, and persists all of that evidence before
blind review. Missing metric values, filter scope, grain/fan-out controls,
verification, or audit fields deterministically cap the corresponding score.

Image-sensitive cases may declare
`metadata.presentation_asset_expectations` in the hidden oracle. The
presentation judge hashes source assets and joins them to PPTX media records,
then deterministically caps image relevance or fit when required exact assets
are missing, forbidden exact assets are embedded, or a required `contain` asset
is cropped beyond its declared limit. The blind judge also receives both source
assets and final slide renders for semantic comparison.

## Promotion Rule

Do not promote a one-off failure directly into Skill prose. First classify it:

- a deterministic tool or file-contract failure becomes a test under `tests/`;
- a recurring agent behavior failure becomes a novel case or regression case;
- an unclear rubric becomes a judge-contract change;
- a real capability delta, repeated across fresh sessions, justifies changing
  the Skill;
- no quality gain with material token/time cost is evidence to simplify or
  retire the Skill.
