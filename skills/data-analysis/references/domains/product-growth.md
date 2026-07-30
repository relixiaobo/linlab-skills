# Domain: Product Growth

Use for product analytics, funnels, activation, retention, feature adoption, cohorts, experiments, and user behavior.

## Core Concepts

- Identity: anonymous id, user id, account id, device id, merged identity.
- Event grain: one row per event, session, user-day, or exposure.
- Activation: define the first meaningful value event.
- Retention: define return event, cohort date, and window.
- Funnel: define eligibility, step order, allowed time window, and dedupe rule.
- Feature adoption: define exposure vs active use.

## Pitfalls

- Counting events instead of users.
- Duplicated events from retries or instrumentation bugs.
- Identity merges changing historical counts.
- Post-treatment filters in experiments.
- Timezone shifts around day/week boundaries.
- Survivorship bias in retention cohorts.

## Recommended Analysis Pattern

1. Validate event volume over time.
2. Check tracking changes and release dates.
3. Build a user-level or account-level base table.
4. Use explicit windows for funnel and retention.
5. Report counts and rates at each step.
6. For experiments, read `references/ab-testing.md`.

