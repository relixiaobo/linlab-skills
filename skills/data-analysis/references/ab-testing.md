# A/B Testing

Use for randomized experiments, feature rollouts, and treatment/control comparisons.

## Required Inputs

- Experiment unit.
- Assignment mechanism.
- Treatment/control labels.
- Exposure rules.
- Start and end dates.
- Primary metric.
- Guardrail metrics.
- Exclusion rules.

## Checks Before Results

- Sample ratio mismatch (SRM).
- Duplicate or conflicting assignments.
- Exposure after assignment.
- Metric window relative to exposure.
- Balance on important pre-treatment covariates when available.
- Missing or delayed events.

## Analysis

Report:

- Group sizes.
- Numerator and denominator for rates.
- Absolute effect.
- Relative effect.
- Confidence interval.
- p-value when appropriate.
- Practical significance.
- Guardrail changes.

## Common Pitfalls

- User-level randomization but event-level analysis without clustering.
- Multiple exposures per user counted as independent.
- Post-treatment filters that bias results.
- Stopping early without correction.
- Reporting "no effect" when underpowered.
- Ignoring guardrails.

## Decision Language

Use "ship", "do not ship", or "continue" only when the evidence and decision threshold are clear. Otherwise present tradeoffs and missing evidence.

