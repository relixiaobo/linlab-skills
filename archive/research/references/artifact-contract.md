# Artifact Contract

## Table Of Contents

- When To Create Artifacts
- Directory Layout
- JSONL Schemas
- Report Shape
- Validation

## When To Create Artifacts

Create artifacts for standard/deep research, batch work, repeated research, or whenever the user wants a durable report.

For quick lookups, artifacts are optional unless the user asks.

## Directory Layout

Default root:

```text
.research/
  INDEX.md
  runs/
    <run-id>.json
  <topic-slug>/
    route.txt
    plan.md
    sources.jsonl
    claims.jsonl
    audit.md
    report.md
    raw/
```

Use `scripts/init_run.py --topic "..." --domain general --depth standard` to create this structure.

## JSONL Schemas

`sources.jsonl`:

```json
{"id":"S1","url":"https://example.com","title":"Title","publisher":"Publisher","published_at":"2026-06-25","accessed_at":"2026-06-25","tier":"S","source_type":"official","supports":["C1"],"notes":"Why this source matters"}
```

`claims.jsonl`:

```json
{"id":"C1","claim":"Specific factual claim","status":"supported","confidence":"high","source_ids":["S1"],"notes":"Scope or caveat"}
```

Allowed claim statuses:

- supported
- partially-supported
- contradicted
- unresolved
- background

Allowed confidence values:

- high
- medium
- low
- unresolved

## Report Shape

For a standard/deep report:

```text
# <Topic>

## Scope
## Executive Summary
## Key Findings
## Evidence
## Conflicts And Uncertainty
## Open Questions
## Sources
## Audit
```

Domain paths may add sections, but must preserve source and audit sections.

## Validation

Before final delivery of artifact-based research:

```bash
python scripts/validate_artifacts.py .research/<topic-slug>
```

Fix JSONL errors, missing files, or unsupported cited source ids before presenting the report as complete.
