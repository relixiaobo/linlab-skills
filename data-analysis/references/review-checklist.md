# Review Checklist

Run this before final delivery. The **Floor** applies to *every* task — including Quick ones that skip the rest of this list; the remaining sections scale up with the tier (see SKILL.md → Start Here).

## Floor (every task, even Quick)

If you present a specific number as a finding:

- [ ] The load-bearing definition is stated inline (what the number means), not a bare figure.
- [ ] Data-quality caveats the profile surfaced (duplicate rows, zero-as-missing, NULL keys, partial periods) are carried into the finding.
- [ ] No ratio or figure is shown that you did not at least sanity-check (magnitude/parts).

## Data Scope

- [ ] Source files/tables named.
- [ ] Date range stated.
- [ ] Filters and exclusions stated.
- [ ] Unit of analysis/grain stated.

## Computation (is the number computed correctly?)

- [ ] All important numbers were computed, not guessed.
- [ ] Each key number recomputed by an independent path (e.g. DuckDB and pandas agree).
- [ ] Scripts/SQL paths saved.
- [ ] Row counts and sample sizes recorded.
- [ ] Joins checked for fan-out when relevant.
- [ ] Null handling explicit.

## Specification (is it the right number for the question?)

Recomputation agrees with itself even on a wrong definition — check the question, not only the math.

- [ ] Definition Contract settled: metric, grain, filters, window, population (Standard/Rigorous).
- [ ] Rejected readings enumerated, not just the chosen one.
- [ ] Answer-moving ambiguities confirmed with the user or stated loudly and proceeded.
- [ ] Result triangulated against an independent reference with `scripts/triangulate.py` (`reconcile` / `coverage` / `grain` / `window` / `magnitude` / `parts`, as applicable).
- [ ] No `[FLAG]` left unresolved — or the FLAG is explained in a caveat.

## Findings

- [ ] Each finding has evidence.
- [ ] Each important finding has a verification check.
- [ ] Effect sizes or impact sizes included where relevant.
- [ ] Refuted or inconclusive hypotheses are not hidden when they matter.
- [ ] Caveats state what the data cannot prove.

## Privacy

- [ ] Raw PII suppressed or masked.
- [ ] Small groups suppressed when relevant.
- [ ] Secrets not printed.

## Communication

- [ ] Direct answer appears first.
- [ ] Method and scope are concise.
- [ ] Tables are compact or saved as artifacts.
- [ ] Next steps are concrete.

