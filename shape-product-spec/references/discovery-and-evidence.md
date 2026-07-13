# Discovery And Evidence

Use this reference when source material is ambiguous, research-heavy,
contradictory, or too solution-first.

## First-Principles Frame

Product definition starts from uncertainty management:

- What problem do we believe exists?
- Who experiences it and in what moment?
- What evidence supports it?
- What assumption would invalidate the product if false?
- What decision must be made now?
- What should not be built yet?

Do not let a polished artifact hide weak evidence. If evidence is missing, say
so and propose the smallest validation step.

## Ambiguity Scan

Scan the input for gaps in these categories:

- **Problem and goal**: what user pain or business need is being solved?
- **Actors**: who can do this, who cannot, and who is affected?
- **Current alternative**: what do users do today and why is it insufficient?
- **Evidence**: quotes, observations, usage data, sales notes, support tickets,
  research files, or explicit stakeholder decisions.
- **Scope**: what is included, excluded, deferred, or explicitly preserved?
- **Objects**: what product objects exist and what states can they enter?
- **Entry paths**: where does the user naturally start?
- **Flow behavior**: mainline, alternate paths, and failure paths.
- **Rules**: eligibility, permissions, billing, quotas, validation,
  localization, accessibility, compliance, privacy.
- **Success**: what proves the feature is working or worth shipping?
- **Dependencies**: external services, existing systems, approvals, data
  availability, rollout gates.
- **Terminology**: duplicate names for the same object or one term used for
  multiple concepts.

## Evidence Ledger

Use evidence IDs when the artifact may be reviewed later:

```markdown
- **EVD-1:** Sales notes from 2026-07-01 say enterprise merchants want regional
  managers to request add-ons instead of purchasing directly.
- **EVD-2:** Support ticket cluster: finance teams discover add-on spend only
  after invoice generation.
```

Evidence can be strong, weak, or absent:

- **Strong**: direct user quote, observed behavior, reliable usage data,
  repeated support/sales signal, approved stakeholder decision.
- **Weak**: single anecdote, secondhand summary, competitor imitation, internal
  opinion, old document with unknown status.
- **Absent**: plausible but unverified. Mark as assumption and do not present as
  fact.

## Hypotheses And Assumptions

Use hypotheses for uncertain product bets:

```markdown
- **HYP-1:** We believe finance admins will approve add-on requests before
  invoice generation if requests appear in their existing approvals queue.
  - Evidence: EVD-1, EVD-2
  - Riskiest assumption: finance admins already review that queue weekly.
  - Validation: interview 3 finance admins or inspect queue usage logs.
```

Use assumptions for inferred defaults:

```markdown
- **ASM-1:** Finance admins already have access to the web workspace.
```

Do not create many assumptions to avoid asking hard questions. If assumptions
pile up, produce a discovery brief instead of a build-ready definition.

## Clarification Rules

Ask a question only when all are true:

- the answer cannot be safely inferred from source material
- multiple reasonable answers exist
- choosing the wrong answer changes scope, UX, acceptance tests, compliance,
  cost, or product correctness

Prefer no more than 3 questions. Use up to 5 for high-stakes definitions.

Good clarification questions are constrained:

```markdown
1. Which users can approve an add-on request?
   A. Only workspace owners
   B. Owners and finance admins
   C. Finance admins only
   Recommended: C, because the notes say regional managers request and finance
   approves, while owner behavior is explicitly unresolved.
```

Avoid asking for preferences that do not change the definition.

## Non-Goals

Non-goals prevent overbuild. Include exclusions that a future agent could
reasonably add by mistake:

- adjacent features users may assume are included
- platform surfaces deferred from v1
- roles or user segments excluded from the release
- automation intentionally left manual
- integrations not part of current scope

Each non-goal should usually include a reason.

## Contradiction Handling

When two source statements conflict:

1. Quote or summarize both sides.
2. Identify the product consequence.
3. Recommend a resolution when one is clearly safer.
4. Keep it as an open question if the decision belongs to the user.

Do not average contradictory requirements into vague prose.
