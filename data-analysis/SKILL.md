---
name: data-analysis
description: >-
  Use when the user already has data — a file (CSV, Excel, Parquet, JSON) or a read-only database — and wants to understand or analyze it, not build software around it. Trigger whenever they want to make sense of a dataset: profiling a messy table to see what's in it, how clean it is, and which columns are actually usable; investigating why a metric moved (revenue, churn, conversion, signups); reconciling numbers that disagree across sources; comparing channels, segments, or cohorts to find what's driving a result; checking or debugging an A/B test, including segment reversals like Simpson's paradox; running SQL or statistical analysis; producing charts, reports, or written findings. Do NOT use for training or deploying ML models, building ETL or data pipelines, web scraping, creating dashboard UI components, database administration (users, grants), or teaching statistics concepts.
metadata: { "openclaw": { "requires": { "bins": ["python3"] }, "envVars": [{ "name": "DATABASE_URL", "required": false, "description": "Optional read-only database URL for analysis tasks." }] } }
---

# Data Analysis

Use this skill when the user asks to analyze files, tables, metrics, experiments, trends, anomalies, cohorts, funnels, reports, or statistical relationships. The default operating model is: **general workflow in this file, domain expertise in references, deterministic checks in scripts**.

This skill's value is not doing analysis the model cannot do — it is making analysis **trustworthy and auditable**: profiling before trusting data, verifying every number by a second path (implementation) and triangulating it against an independent reference (specification), and leaving behind artifacts — queries, scripts, checks, a ledger — someone else can re-run and check. Those deterministic artifacts are reproducible; the model's judgment is logged, not bit-identical, so do not overclaim "reproducible" for the analysis as a whole. Spend that rigor where the decision warrants it (see **Start Here**); do not run the full machinery on a one-line question — but never drop below the floor.

## Setup

Scripts need Python packages beyond the standard library. Install once:

`python3 -m pip install -r {baseDir}/requirements.txt`

Dependencies are tiered (see `requirements.txt`). **Core** analysis + verification — `profile_dataset.py`, `query_duckdb.py`, `check_join_fanout.py`, `triangulate.py`, `validate_findings.py` — needs only **pandas + duckdb** and runs everywhere. The output layers are **optional**: `build_report.py` needs jinja2, `render_chart.py` needs vl-convert-python, `render_table.py` needs great-tables + polars; Parquet/xlsx need pyarrow/openpyxl, and `query_database.py` needs sqlalchemy plus a driver. A script that needs an absent package exits with a clear "X is required" message — install just that one; the trust machinery never depends on the presentation layer.

## Start Here

Three things vary per task. They are **not three modes to puzzle over, and they do not gate each other** — make **two decisions**, hold **one floor**, set **one display flag**. The three sections after this one are the detail behind each; this is the whole decision in one place.

**Decision 1 — how much rigor?** (scales with *stakes*) — *What decision does the result feed?*
- Nothing yet / open exploration → **Quick**.
- A number someone will act on → **Standard**. A ship / finance / causal call, or anything leaving the room → **Rigorous**.
- Detail: *Effort Tiers* below.

**Decision 2 — what deliverable?** (scales with *consumption*, not stakes) — *Who consumes it, and will it outlive this chat?*
- No → **answer in chat**.
- A visual makes it land → **chat + one chart/table**.
- Shared, revisited, a decision of record, or it spans several findings → **HTML report**.
- Default to the lightest and **offer** the upgrade. Detail: *Deliverable* below.

**The floor** — holds on *every* task, independent of both decisions. The moment you present a specific number as a finding (even one line in chat) you must:
1. **State the load-bearing definition inline** — "share = emails containing the word at least once," not a bare "42%."
2. **Carry any data-quality caveat the profile surfaced** — duplicate rows, zero-as-missing, NULL keys, partial periods.
3. **Not show a ratio or figure you have not sanity-checked** — a 30-second magnitude/parts check, not necessarily a full recompute.

Tiers scale the *ledger, the report, and full second-path recomputation* — never this floor. **Quick drops the machinery, not the honesty.**

**Display flag** — set at *output time*, changes nothing about the work done. `audience`: `consumer` (default — machinery collapsed) or `analyst` (expanded for audit). Detail: *Disclosure* below.

> The two decisions are independent. A Quick task can still warrant a report; a one-line answer can still need the one load-bearing number verified. **Letting one decision silently collapse the others is the most common misread — don't.**

## Effort Tiers

Detail behind **Decision 1**. Match rigor to stakes; decide during Discover.

- **Quick** — one file or one number ("profile this CSV", "is this column usable", "what's the average X"). Profile, answer directly, add the caveat. No ledger, no report, no separate plan, no full recompute — but **the floor still holds**: state the definition, carry profile caveats, don't publish an unchecked figure.
- **Standard** — a metric explanation, single comparison, or small investigation. Profile, a light (often mental) plan, compute, one independent verification of each key number, a short written findings summary.
- **Rigorous** — revenue/finance reconciliation, A/B ship decisions, causal claims, anything leaving the room as a report. Full workflow below: plan, findings ledger, independent cross-checks, rendered report, review checklist.

When unsure, ask what decision the result feeds, then pick the lowest tier that protects it. Running Rigorous machinery on a Quick question wastes time and buries the answer.

## Deliverable

Detail behind **Decision 2**. Effort Tier sets how much rigor; this sets what to hand back. It tracks **consumption, not stakes** — a low-stakes result can still need a shareable report, and a high-stakes number can be a one-line answer mid-conversation. Ask: *who consumes this, and will it outlive the conversation?* Pick the lightest form that serves them, then offer to upgrade.

- **Answer in chat** — a single number or fact, a sanity check, or iterative exploration where each answer feeds the next question. No artifact.
- **Chat + one chart or table** — when a visual makes the answer land but it is still a glance. Produce one with `render_chart.py` / `render_table.py` and reference it; do not wrap it in a report.
- **HTML report** (`build_report.py`) — when the result will be shared or revisited, is a decision of record that needs an audit trail, spans several findings/charts/tables, or the user asks for one ("report", "one-pager", "something I can send").

Default to the lightest and offer the upgrade ("want this as a shareable report?"). Producing a report nobody asked for buries a one-line answer; making someone re-ask for one is friction — defaulting low plus the offer avoids both.

**Reports are HTML only — there is no markdown report.** The chat reply itself is plain text/markdown, but that is the answer, not a report artifact. The findings ledger stays TSV (machine-checkable audit record, not a report). The rule scopes the *shareable deliverable*: internal working artifacts the model reads — e.g. `profile.md` from `profile_dataset.py`, run notes — may be markdown.

## Disclosure — a display setting, not a decision

This is **not** a third decision; it is the **display flag** from Start Here, applied at output time. It changes *how much of the work you show*, never *whether the work is done*. Run the full rigor regardless — a non-expert is the reader least able to catch a wrong answer, so it protects them most — and vary only the surface.

- **Lead with a plain-language answer.** State the result and the one decision-relevant caveat first, in plain words. Gloss any technical term (SRM, Simpson's paradox, fan-out) on first use; never open with jargon.
- **Progressively disclose the machinery.** Method, full verification detail, the findings ledger, and reproducibility paths go in expandable/secondary layers — present but not in the way. The HTML report (`build_report.py`) collapses these into `<details>`; the chat reply offers them ("want the method/verification?") rather than dumping them.
- **Set the `audience` flag** in the report context: `consumer` (default — machinery collapsed) or `analyst` (everything expanded for audit). Visibility only. Add a `trust` line (e.g., "every number verified two ways") as the non-expert's reassurance.
- **Never let friendliness erode rigor.** The failure mode is a pretty report with an unverified number. Demote the audit trail in the presentation; never delete it.

## Operating Rules

These always hold; only the *depth* of planning, verification, and artifacts scales with the tier — the floor in **Start Here** never does.

- Never present a number you did not compute.
- Never guess table names, column names, metric definitions, grain, filters, or date windows. For Standard/Rigorous, settle them in a Definition Contract (`templates/definition_contract.yaml`) before computing; enumerate the readings you rejected and confirm only the ambiguities that move the answer.
- First touch of any dataset must include profiling.
- Treat raw input data and production databases as read-only.
- Write analysis artifacts under `analysis_runs/<run_id>/`, not next to raw data.
- Every important finding needs `claim`, `computation`, `evidence`, `verification`, and `caveat`.
- For SQL joins, check row-count and key fan-out before trusting aggregates.
- Verify the *specification*, not only the computation. Recomputing a number a second way agrees with itself on a wrong definition/grain/filter — triangulate the result against an independent reference (`scripts/triangulate.py`).
- Do not claim causality from observational data unless the design supports it.
- Suppress raw PII in user-facing output and avoid showing groups with very small `n`.
- Before delivering a Standard or Rigorous analysis, run the review checklist.

## Core Workflow

This is the Standard/Rigorous path. Quick tasks collapse it to **Profile (step 2) → answer in chat**, with the floor (Start Here) applied; they do not reach the ledger or report (steps 6–7).

1. **Discover** inputs, files, database config, prior context, and the user's decision need.
2. **Load and profile** every new dataset. Prefer `{baseDir}/scripts/profile_dataset.py` for files.
3. **Plan** the analysis with `templates/analysis_plan.md`, and settle the metric, grain, filters, window, and population in a Definition Contract (`templates/definition_contract.yaml`) — enumerate the readings you rejected; confirm only the ambiguities that move the answer. (Quick tier: skip the file, state the one load-bearing assumption inline.)
4. **Execute** with SQL/Python. Prefer read-only DuckDB for local files and sampled checks before full runs.
5. **Validate** two ways: recompute each key number by an independent path (implementation), AND triangulate the result against an external reference with `scripts/triangulate.py` — reconcile to a known total, and check coverage/grain/window/magnitude (specification). See `references/specification-checks.md`.
6. **Record findings** in `templates/findings_ledger.tsv` format.
7. **Report** (only when the Deliverable decision calls for one) — build a self-contained HTML report with `build_report.py`: charts and tables inlined into one shareable file, carrying data scope, method, evidence, verification, limitations, and artifact paths. Reports are HTML only.

## What To Read

Read only the relevant references:

- General workflow: `references/workflow.md`
- File/database access: `references/data-access.md`
- SQL joins, metrics, and aggregation guardrails: `references/sql-guardrails.md`
- Verifying the question, not just the math (Definition Contract + triangulation): `references/specification-checks.md`
- Statistical tests, models, effect sizes, and uncertainty: `references/statistical-methods.md`
- Root cause and anomaly investigations: `references/root-cause.md`
- A/B tests and experiments: `references/ab-testing.md`
- Visualization choices: `references/visualization.md`
- Privacy and sensitive data handling: `references/privacy.md`
- Final quality gate: `references/review-checklist.md`

For domain-specific analysis, read one domain reference before planning:

- Business/finance operations: `references/domains/business-analytics.md`
- Product growth and funnels: `references/domains/product-growth.md`
- Financial markets or company fundamentals: `references/domains/finance.md`
- Healthcare, clinical, or biomedical data: `references/domains/healthcare.md`
- Academic/statistical research: `references/domains/research-statistics.md`

## Bundled Scripts

- Profile a file:
  `python3 {baseDir}/scripts/profile_dataset.py path/to/data.csv --out analysis_runs/<run_id>/profile`
- Query local files with DuckDB (read-only; mutating SQL is rejected):
  `python3 {baseDir}/scripts/query_duckdb.py --file orders=orders.csv --sql "select count(*) from orders"`
- Query a read-only database (uses `DATABASE_URL` by default; rejects mutating SQL, never commits):
  `python3 {baseDir}/scripts/query_database.py --sql "select count(*) from orders"`
- Check join cardinality, NULL-key drops, unmatched keys, and fan-out:
  `python3 {baseDir}/scripts/check_join_fanout.py --left orders=orders.csv --right lines=order_lines.csv --left-key order_id --right-key order_id`
- Triangulate a result against an independent reference (specification check, not recomputation; exits 1 on FLAG):
  `python3 {baseDir}/scripts/triangulate.py reconcile --data orders.csv --column amount --agg sum --expected 104700 --tol 0.01`
  (Subcommands: `reconcile`, `coverage`, `grain`, `window`, `magnitude`, `parts`. See `references/specification-checks.md`.)
- Render a house-styled chart from a template (static SVG by default; `--format png|html`):
  `python3 {baseDir}/scripts/render_chart.py --template time-trend --data series.csv --map x=date,y=revenue,series=channel --title "..." --subtitle "units · range · n" --out analysis_runs/<run_id>/charts/trend.svg`
  (Templates and role fields: `{baseDir}/assets/charts/README.md`. Never hand-write chart code.)
- Render a house-styled HTML table (conditional color, heatmaps, in-cell sparklines) for a report's `table_html` slot:
  `python3 {baseDir}/scripts/render_table.py --data metrics.csv --spec spec.json --title "..." --out analysis_runs/<run_id>/tables/guardrails.html`
  (Spec keys and recipes: `{baseDir}/assets/tables/README.md`. Use for columns needing visual encoding; plain markdown tables are fine otherwise.)
- Validate a findings ledger:
  `python3 {baseDir}/scripts/validate_findings.py analysis_runs/<run_id>/findings.tsv`
- Build a self-contained HTML report (inlines SVG charts + HTML tables into one shareable file):
  `python3 {baseDir}/scripts/build_report.py --context analysis_runs/<run_id>/report_context.json --out analysis_runs/<run_id>/report.html`

## Domain Reference Pattern

`SKILL.md` stays general. Domain references hold expert knowledge: metric definitions, common pitfalls, causal assumptions, regulatory constraints, and reporting norms. If the current domain is not covered, use the general workflow and create a short `domain_notes.md` inside the run directory rather than inventing permanent domain knowledge.

## Final Response Contract

For completed analyses, tell the user:

- The direct answer.
- The data scope and method.
- The most important verified findings.
- The main caveats.
- Paths to report, scripts, queries, charts, and ledger.

Keep outputs easy to reuse outside the current answer: preserve metric
definitions, caveats, source paths, chart/table artifacts, and verification
status as ordinary files under the run directory. Do not require a hidden
protocol to understand the analysis.

Do not dump large tables into chat. Save them as artifacts and summarize the decision-relevant rows.
