# Domain: Business Analytics

Use for revenue, sales, operations, subscriptions, support, procurement, and executive reporting.

## Common Metrics

- Revenue: define gross/net, refunds, taxes, currency, and recognition date.
- ARR/MRR: define active subscription, expansion, contraction, churn, reactivation.
- Conversion: define denominator and eligibility.
- Retention: define logo vs revenue retention and cohort start.
- Churn: define voluntary/involuntary, gross/net, logo/revenue.
- Support: define created/resolved dates, SLA, business hours, reopen rules.

## Pitfalls

- Mixing booking date, invoice date, payment date, and revenue recognition date.
- Double-counting revenue after joining invoice headers to line items.
- Reporting percent change from tiny baselines.
- Comparing partial periods to full periods.
- Ignoring currency conversion and cents/dollars units.
- Mixing customer, account, workspace, and user grains.

## Recommended Analysis Pattern

1. Confirm metric definition and grain.
2. Build base table at metric grain.
3. Validate totals against known dashboard or finance source.
4. Segment only after total is reconciled.
5. Rank drivers by absolute contribution.

