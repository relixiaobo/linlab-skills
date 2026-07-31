# Root Cause Analysis

Use for metric spikes/drops, anomalies, and "why did this change?" questions.

## Workflow

1. **Validate the change**: compare against historical variance, rolling average, or expected seasonality.
2. **Locate timing**: identify whether it is a step change, drift, spike, or data gap.
3. **Decompose the metric**: break into components, e.g. revenue = volume * price * mix.
4. **Rank contributors**: compare before/after by dimension using absolute contribution, not just percent change.
5. **Test hypotheses**: data issue, instrumentation change, mix shift, seasonality, campaign, outage, product change.
6. **Write report**: primary driver, share of impact, evidence, rejected hypotheses, recommendations.

## Guardrails

- Do not start with dimension drilldowns until the metric change is verified.
- Do not over-index on high percent change from tiny baselines.
- Align time windows and compare like-for-like weekdays/seasonality when relevant.
- Check instrumentation or pipeline changes before business explanations.
- Separate data quality root causes from business root causes.

## Output

Include:

- What changed.
- When it changed.
- How large the change was.
- Main driver and contribution.
- Supporting evidence.
- Rejected hypotheses.
- Caveats and next checks.

