# Workflow

Use this lifecycle for most data analysis work. It combines broad analyst SOPs, MAGIC-style phase gates, and verification-loop discipline.

Scale the lifecycle to the effort tier (see SKILL.md → Effort Tiers). A **Quick** task collapses to Profile → Answer; a **Standard** task runs a light plan plus one verification per key number; only a **Rigorous** task runs every phase with a ledger and rendered report. Always profile (Phase 2), and the **floor** (SKILL.md → Start Here) holds at every tier — definition stated, profile caveats carried, no unchecked figure; everything else flexes with the stakes.

## Phase 1: Discover

- Identify data sources, file formats, database connections, prior reports, and business context.
- Determine the decision the analysis should support.
- Clarify only genuinely ambiguous fields: metric definition, date range, grain, population, treatment/control, or output format.
- Check for an optional `analysis_context/` directory — durable, cross-run notes a
  prior analysis may have left (distinct from per-run `analysis_runs/<run_id>/`
  artifacts). If present, read it before planning; never assume it exists:
  - `LEARNINGS.md` — findings worth carrying forward.
  - `METRICS.md` — confirmed metric definitions (see `templates/metric_definition.yaml`).
  - `SCHEMA_NOTES.md` — table/column meanings discovered earlier.
  - `GOTCHAS.md` — data-quality traps to avoid repeating.

## Phase 2: Profile

Always profile before cleaning or modeling.

Minimum profile:

- Row count and column count.
- Data types.
- Sample rows.
- Missingness.
- Numeric ranges and outliers.
- Categorical cardinality.
- Date range and timezone clues.
- Duplicate rows and likely key duplicates.
- PII-like columns.

Use `scripts/profile_dataset.py` for files when possible.

## Phase 3: Plan

Write or mentally fill `templates/analysis_plan.md`.

The plan must define:

- Question.
- Unit of analysis / grain.
- Metrics and definitions.
- Filters and date windows.
- Method.
- Validation checks.
- Privacy constraints.
- Output artifacts.

Keep simple tasks light, but do not skip planning for multi-step work.

For Standard/Rigorous work, settle the metric, grain, filters, window, and population in a **Definition Contract** (`templates/definition_contract.yaml`) before executing: enumerate the readings you rejected, and confirm only the ambiguities that would move the answer. See `references/specification-checks.md`.

## Phase 4: Execute

- Prefer SQL for filtering, joining, and aggregation.
- Prefer Python for profiling, statistical analysis, charts, and custom checks.
- Save queries and scripts under `analysis_runs/<run_id>/queries/` and `analysis_runs/<run_id>/scripts/`.
- Save expensive or irreversible intermediate states as checkpoints.
- Test custom code on a sample before applying to a large dataset.

## Phase 5: Validate

Validation has two independent jobs. Do both for an important finding:

**Computation** — did I compute the number correctly? (catches implementation bugs)

- Independent recomputation (e.g. DuckDB and pandas agree).
- Alternate aggregation path.
- Row-count/key-count sanity check.

**Specification** — is it the right number for the question? (catches "right answer to the wrong question"; recomputation can't, because it agrees with itself on a wrong definition/grain/filter). Run `scripts/triangulate.py` against an independent reference:

- `reconcile` to a known/trusted total; `coverage` vs the expected universe.
- `grain` (one row = one unit), `window` (date range), `magnitude` (Fermi order-of-magnitude), `parts` (a breakdown sums to the whole).
- Sensitivity check against filters, outliers, or missingness.

Record validation in the findings ledger.

## Phase 6: Deliver

Deliver a concise answer plus artifact paths.

A report should include:

- Question.
- Data scope.
- Method.
- Findings.
- Verification.
- Caveats.
- Reproducibility paths.

## Finding Ledger Contract

Each durable finding should have:

| Field | Meaning |
| --- | --- |
| `id` | Stable finding id, e.g. `F001` |
| `claim` | One-sentence finding |
| `computation` | SQL/script path or command |
| `evidence` | Key numbers, row counts, filters, dates |
| `verification` | Independent check or sanity check |
| `caveat` | Limitation or what the finding cannot prove |
| `status` | `verified`, `refuted`, or `needs_followup` |

