# SQL Guardrails

SQL analysis errors usually come from grain, joins, filters, nulls, and metric definitions.

## Before Writing SQL

Confirm:

- What one row represents in each table.
- Primary key or natural key.
- Time column and timezone.
- Metric definition.
- Inclusion/exclusion filters.
- Expected date range.

## Join Safety

Before trusting joined aggregates:

- Count rows before and after the join.
- Count distinct keys before and after.
- Check duplicate keys on both sides.
- Identify one-to-one, one-to-many, many-to-one, or many-to-many.
- For many-to-many joins, aggregate to the intended grain before joining.

Use `scripts/check_join_fanout.py` for local file joins.

## Metric Safety

- Always state numerator, denominator, and filters.
- Use inclusive start and exclusive end date filters where possible.
- Avoid `count(*)` for entities when joined rows may duplicate entities.
- Prefer `count(distinct id)` when entity grain is not guaranteed.
- Make null handling explicit.
- For rates, report numerator and denominator, not just percent.

## Query Review

Check:

- Do referenced tables/columns exist?
- Are date filters applied to large/partitioned tables?
- Is the aggregation at the target grain?
- Are joins causing fan-out?
- Are filters applied before or after aggregation intentionally?
- Are timezones and currency units handled?
- Could nulls be silently dropped by `where` or `inner join`?

