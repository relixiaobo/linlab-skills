# Definition System

This reference defines artifact shapes and rigor levels for product definition
work. Use it before drafting a new feature definition, PRD, decision memo,
story map, or major rewrite.

## Design Principles

- The definition layer exists to reduce ambiguity for future agents and humans.
- Good artifacts preserve decisions, evidence, constraints, assumptions, and
  rejected scope.
- Good constrained solutions distinguish the clean-slate best answer, the
  selected brownfield/current answer, and the minimum acceptable answer.
- Requirements are source of truth for user-observable behavior, not disguised
  architecture plans.
- Short artifacts are acceptable when product risk is small. Vague artifacts are
  not.

## Artifact Archetypes

### Discovery Brief

Use when the idea is early or evidence is weak.

Required:

- problem hypothesis
- target user and current alternative
- evidence, assumptions, and confidence level
- riskiest assumption
- validation plan or next learning step
- non-goals and scope guardrails

### One-Page Feature Definition

Use for low-risk changes with one main flow.

Required:

- purpose and reader
- problem / user goal
- decision summary
- objective, key constraints, and selected target when the solution is
  constraint-shaped
- in scope / out of scope
- main flow
- requirements or stories with acceptance criteria
- assumptions or open questions

### Definition Pack

Use when developers or agents need product behavior without a PM in the room.

Required:

- source-of-truth status
- decision summary and non-goals
- objective, constraint classification, options considered, selected target,
  tradeoffs, and revisit triggers when constraints matter
- target users and non-users
- evidence and assumptions
- product model / glossary
- user flows with entry paths
- functional requirements or vertical stories
- business rules and validations
- edge cases and failure states
- acceptance criteria
- success metrics or completion signals
- execution notes and verification plan

Optional only when needed:

- launch/rollout plan
- stakeholder approvals
- compliance constraints
- analytics events
- risk register
- dependency map

### Story Map

Use when the main issue is slicing scope across a user journey.

Required:

- primary persona
- backbone journey, 3-7 activities when possible
- vertical stories under each activity
- MVP / R2 / Future grouping
- edge cases, risks, and open questions
- acceptance criteria for MVP stories

### Prototype Behavior Spec

Use when screenshots, mockups, or UI flows are the primary source or
deliverable.

Required:

- screen inventory
- entry paths
- state coverage: default, empty, loading, disabled, error, success
- UI copy
- user decisions and validation
- business rules visible in the UI
- acceptance criteria for interaction behavior

### Brownfield Change Definition

Use when existing product behavior, prototype, or codebase must be changed.

Required:

- current behavior
- changed behavior
- preserved behavior
- clean-slate answer, brownfield target, and minimum acceptable change
- migration or transition behavior
- compatibility, permissions, and data assumptions
- regression risks and acceptance criteria

### Decision Memo

Use when stakeholders need alignment before the build spec is stable.

Required:

- decision to make
- customer or business problem
- alternatives considered
- recommended option and rationale
- constraints, tradeoffs, and revisit trigger
- evidence and assumptions
- risks and reversibility
- follow-up definition work needed

### Review Report

Use when the user asks whether an existing definition, PRD, or spec is good,
complete, or ready.

Required:

- verdict
- blocking issues first
- evidence from the artifact
- fix recommendations
- residual risk and unanswered decisions

## Rigor Scaling

Scale rigor by product risk:

- **Low risk**: single flow, reversible, internal, no money or privacy impact.
  Keep one-page and action-oriented.
- **Medium risk**: several flows, permissions, moderate data integrity or
  support burden. Use stable IDs and explicit acceptance criteria.
- **High risk**: billing, privacy, compliance, irreversible actions, enterprise
  contracts, safety, or broad rollout. Add traceability, approvals, constraints,
  non-functional requirements, and explicit risk mitigation.

Do not scale by team size alone. A solo feature touching payments still needs
high rigor.

## Stable ID Rules

- Number IDs sequentially within each type: `OBJ-1`, `CON-1`, `OPT-1`,
  `TRD-1`, `FR-1`, `AC-1`, `FLOW-1`.
- Keep IDs stable during rewrites; add new IDs instead of renumbering old ones
  when downstream work may already reference them.
- Each acceptance criterion should map to exactly one requirement or story when
  possible.
- If one criterion validates multiple rules, reference all related IDs in the
  criterion text rather than duplicating it.
- Keep open questions numbered so a later answer can be traced back.

## Constraint And Option Layer

Use this layer when a solution depends on real-world limitations:

- `OBJ-*`: the outcome the work should create
- `CON-*`: hard, soft, legacy, resolvable, or unknown constraints
- `OPT-*`: clean-slate, brownfield target, minimum acceptable, deferred ideal, or
  no-build option
- `TRD-*`: accepted compromise and rationale

For small low-risk work, this can be a short paragraph. For brownfield or
high-stakes work, make it explicit enough that a future agent does not treat a
temporary compromise as the ideal product direction.

## Source Of Truth

State which artifact is authoritative:

- Markdown product spec
- existing PRD or product brief
- screenshots/prototype plus written rules
- meeting notes plus approved decisions
- research artifacts plus explicit assumptions
- implementation plan derived from approved definition

If a source is only historical background, label it as non-authoritative.

## Product Model

Every non-trivial definition needs a small product model:

- domain nouns and definitions
- object lifecycle states
- roles and permissions
- eligibility and constraints
- relationships between objects

The model should not become a database schema unless implementation design is in
scope.

## Metrics And Completion Signals

Use metrics only when they guide decisions. Good metrics are specific and have a
measurement path:

- user success: completion rate, time to complete, error rate
- business outcome: conversion, retention, cost reduction, support reduction
- operational signal: failure rate, latency, manual review volume
- counter-metric: what not to optimize at the expense of quality

For small internal tools, completion signals may be enough:

- operators can complete the workflow without manual workaround
- known error states are handled
- acceptance tests pass
