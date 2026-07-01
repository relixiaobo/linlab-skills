# Batch Mode

## Table Of Contents

- When To Use
- Workflow
- Field Design
- Evidence Rules
- Outputs

## When To Use

Use batch mode when the user wants to compare many entities, tools, papers, products, companies, standards, vendors, or options.

Batch is not a domain. Combine it with the appropriate domain path when needed:

- papers + batch -> literature
- companies + batch -> entity dossier or general market research
- libraries + batch -> codebase-docs
- regulations + batch -> standards-regulatory

## Workflow

1. Define items. If the list is missing, generate candidates and mark them as candidate items.
2. Define fields before research. Fields must be answerable from sources.
3. Research each item into structured JSON.
4. Validate field coverage and source ids.
5. Generate a comparison table plus synthesis.

## Field Design

Good fields are specific and sourceable:

- official_url
- current_status
- latest_release_or_update
- evidence_summary
- strengths
- weaknesses
- risk_or_caveat
- source_ids
- confidence

Avoid vague fields like "quality" unless you define a scoring rubric.

## Evidence Rules

Each item should have at least one primary or official source when possible. If not, mark `insufficient-primary-source`.

Do not let one item have much deeper source coverage than the others unless the asymmetry is disclosed.

## Outputs

Recommended files inside `.research/<slug>/`:

```text
items.json
fields.json
results.jsonl
comparison.md
```

The final answer should include a concise table, key patterns, outliers, and uncertainty.
