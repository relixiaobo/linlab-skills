# Evals — methodology notes

`cases.yaml` lists the behaviors this skill must get right. How those cases are
turned into a benchmark matters more than the case list, because of one finding
from earlier benchmark runs:

> On **public, recognizable** datasets (Pima diabetes, Berkeley admissions,
> Online Retail), a frontier model scores 100% **with and without** the skill.
> It recognizes the dataset by structure — even after columns are renamed —
> and recalls the known traps unaided. With/without is indistinguishable on
> answer correctness, while the skill costs ~2.7x time and ~6x tokens.

So a benchmark that grades only final-answer correctness on famous data will
always report a +0.00 delta. That does not mean the skill is worthless; it
means the benchmark is measuring the wrong thing.

## Build evals that can actually isolate the skill's value

1. **Use novel, non-public data the model cannot recognize.** Synthesize tables
   with realistic but invented schemas and inject the traps yourself (zero-coded
   missingness, fan-out keys, SRM, segment reversals, mixed currency/units,
   NULL-dropping joins). If the model can name the dataset, the eval is leaking.

2. **Grade process and artifacts, not just the answer.** The skill's real
   deliverable is auditability. Assert on things a bare baseline skips:
   - a profile was produced *before* any number was reported;
   - each key number was verified by a second, independent path (e.g. DuckDB and
     pandas agree to the penny);
   - a findings ledger exists and passes `scripts/validate_findings.py`;
   - joins were fan-out-checked before aggregates were trusted;
   - PII/small-cell suppression actually happened in user-facing output.

3. **Add cases where naive analysis genuinely fails** (ambiguous grain, dirty
   encodings/CJK, NULL-heavy joins, partial-vs-full period comparisons). These
   separate the skill from a one-shot script.

4. **Track cost as a first-class metric.** Tier the cases (Quick/Standard/
   Rigorous) and confirm Quick cases do *not* trigger the full ledger+report
   machinery — that is the regression the Effort Tiers exist to prevent.

The benchmark harness output lives under `data-analysis-workspace/` (not part of
the shipped skill).

## The implemented gate: `run_checks.py`

`cases.yaml` is the aspiration; `run_checks.py` is what actually runs today and
ships with the skill:

```
python3 evals/data-analysis/run_checks.py
```

It is the machine-checked counterpart to the Operating Rules (which are only
instructions to the model). It synthesizes novel trap data in a tempdir — never
famous datasets, per the finding above — and asserts the verification and output
scripts behave under attack:

- `triangulate.py` **flags** fan-out grain, sign flips, orders-of-magnitude gaps,
  out-of-window dates, broken reconciliation, and broken part/whole conservation
  (exit 1), and **passes** the clean cases;
- it survives **tz-aware** dates without crashing and surfaces **NULL keys**;
- the report **trust badge cannot appear** unless a finding is genuinely
  `status: verified` with non-empty verification text — asserted against the
  produced HTML file, not stdout;
- `validate_findings.py` rejects a ledger with empty fields;
- the renderers still produce output (these checks **SKIP** when an optional
  dependency is absent, rather than failing).

Exit code is non-zero if any check fails. Run it after touching any script: it
exists because three real bugs once shipped in the verification tool undetected,
and a wrong verifier is worse than none. New regressions should land here as a new
`check(...)` before the fix.
