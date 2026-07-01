# Specification checks (verifying the question, not just the math)

The skill verifies every number by a second path (DuckDB ⇄ pandas agree to the
penny). That catches **implementation** errors — a bug in how the metric was
computed. It cannot catch **specification** errors: a wrong metric definition,
wrong grain, wrong filter, or wrong date window, computed *perfectly* by two
paths, still agrees with itself. That is "the right answer to the wrong question"
(a Type III error), and it is more common and more dangerous than an arithmetic
bug — the non-expert reader is the least able to catch it.

Recomputation is self-referential. To catch a specification error you need an
**independent reference frame**. Two gates provide it.

## Gate 1 — Definition Contract (during PLAN, blocks EXECUTE)

Before computing, fill `templates/definition_contract.yaml`: metric, grain,
filters, window, population, assumptions. The form is not the point — the
discipline is:

- **Enumerate before choosing.** For each field with more than one defensible
  reading, list the alternatives and why you rejected them. "Revenue" might be
  gross, net-of-refunds, or recognized; "active user" might be logged-in, took an
  action, or DAU-over-window. Reason in *solution space* (the options), not just
  restate your pick.
- **Gate questions by impact.** Where a different reading would *materially change
  the answer*, mark `answer_moving: true` and either confirm with the user or
  state the assumption loudly and proceed. Do **not** interrogate the user about
  ambiguities that don't move the number — that is the opposite failure.
- This is the "never guess metric definitions / grain / filters / windows"
  Operating Rule turned into a fillable, auditable object.

Scale to tier: **Quick** skips the file and states the one load-bearing
assumption inline; **Standard** fills the contract lightly; **Rigorous** fills it
fully and ships it next to the result.

## Gate 2 — Triangulation & reasonableness (during VALIDATE, ≠ recomputation)

Run `scripts/triangulate.py`. Each check compares the answer to something
**outside the computation** — a known total, the universe size, the claimed
grain, the stated window, an independent estimate, a conservation law:

| Check | Catches | Example |
| --- | --- | --- |
| `reconcile` | wrong filter / population / definition | top-line ties to a finance total or a raw `COUNT(*)` |
| `coverage` | a silently dropped population | distinct customers ≈ the known universe size |
| `grain` | fan-out / double counting | the grain key is actually unique (one row = one unit) |
| `window` | wrong / partial date range | data falls inside the stated window, no partial period |
| `magnitude` | catastrophic grain / unit error | result within ~1 order of magnitude of a Fermi estimate |
| `parts` | a missing or double-counted slice | a breakdown sums to the whole |

Each prints `[PASS]` / `[WARN]` / `[FLAG]` and exits non-zero on FLAG so it can
gate. A FLAG is not an arithmetic disagreement — it is a sign the *specification*
is off.

Two rules that make these honest:

- **Estimate the magnitude *first*.** Derive the expected size from an independent
  basis (rate × population, parts × unit value) *before* looking at the computed
  value, or you will rationalize a band that contains it.
- **Triangulate against a trusted reference.** Reconciling to another wrong number
  gives false comfort. Prefer an authoritative/governed source, a prior certified
  figure, or a raw row count. If none exists, fall back to `magnitude` + internal
  conservation checks (`parts`, `grain`) and say so — never invent a reference.

## Report

Never report the number naked. Ship the contract plus the triangulation results
as the analysis's header: *"Net revenue, per-order grain, FY2025 UTC, US customers
only; reconciles to finance topline within 0.3%; magnitude check passed; sensitive
to refund treatment — gross would be +12%."* That sentence is what lets a reader
trust a number whose definition they could not otherwise see.
