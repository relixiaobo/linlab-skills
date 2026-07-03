---
name: shape-product-spec
description: Shape product ideas, feature requests, business rules, or product changes into decision-ready and execution-ready product specs before agents execute them. Use when a user wants an agent or team to build, change, evaluate, or review a product capability but the goal, users, constraints, tradeoffs, flows, business rules, scope, or acceptance criteria are too ambiguous to execute safely; covers PRDs, product briefs, discovery synthesis, story maps, user flows, acceptance criteria, prototype behavior specs, clean-slate vs brownfield option framing, contradiction audits, and implementation handoff specs. Do not use for generic writing, pure market research with no product decision, pure visual design, pure implementation architecture, or file-format work where the format operation is the primary task.
---

# Shape Product Spec

## Problem Solved

This skill solves one concrete problem: the user has a product idea, feature
request, business rule, or product change that should become a decision-ready
and execution-ready product spec, but the current intent is not executable yet.

Without this step, the agent tends to guess the user, scope, edge cases,
business rules, acceptance criteria, or evidence behind the request. The skill
turns that underdefined intent into a compact execution context before build
work starts. When constraints shape the answer, it distinguishes the best
clean-slate answer, the best answer under current constraints, and the minimum
acceptable answer.

## Overview

Convert rough product intent into a compact product spec that PMs, founders,
CEOs, stakeholders, designers, developers, reviewers, agents, or future
sessions can discuss and act on without guessing. The core deliverable is not
"a PRD"; it is a decision and execution artifact that preserves why the work
matters, what is in and out, what evidence exists, what assumptions remain, how
users move through the product, and how completion will be verified.

PRD, feature spec, story map, prototype behavior spec, decision memo, and
implementation handoff are output shapes. Choose the smallest shape that makes
the work executable without pretending uncertainty is resolved.

Do not add product methods as ceremony. Use them only to answer the operational
question: what should change, for whom, under which constraints, and why is this
the right version to execute now?

## Route

1. Identify the real job:
   - define a fuzzy idea
   - synthesize research or interview notes into opportunities
   - create or rewrite a PRD / feature spec
   - map a user journey or release slice
   - specify prototype behavior from screenshots or rough flows
   - review an existing product artifact for contradictions and gaps
   - prepare a decision-ready and execution-ready product spec
2. Classify the risk and surface:
   - exploratory idea: emphasize assumptions, evidence, non-goals, and next
     validation step
   - feature definition: emphasize users, flows, rules, states, acceptance
     criteria, and scope boundaries
   - brownfield change: preserve current behavior and state exactly what
     changes
   - prototype/UI behavior: cover entry paths, screens, states, copy, rules,
     and failure recovery
   - high-stakes domain: emphasize privacy, compliance, auditability, approvals,
     reversibility, traceability, and residual risk
   - narrow build slice: keep the artifact lean and optimize for agent execution
3. Frame objectives and constraints before committing to a solution:
   - identify the actual objective, non-goals, and minimum acceptable outcome
   - separate hard constraints, soft constraints, legacy constraints,
     resolvable constraints, and unknown constraints
   - compare clean-slate, constrained/brownfield, minimum acceptable, deferred,
     and no-build options when the choice materially affects the product
   - choose the current target and state the accepted tradeoffs
4. Extract source material before structuring: user problem, target actors,
   current alternatives, job to be done, trigger, source notes, screenshots,
   decisions already made, rejected alternatives, constraints, dependencies,
   metrics, contradictions, unknowns, and evidence strength.
5. Separate definition from implementation:
   - Definition describes observable behavior, product rules, decisions,
     constraints, acceptance, and verification.
   - Implementation suggestions describe possible technical approaches and must
     be labeled as suggestions.
   - Do not pin frameworks, tables, APIs, field names, internal state machines,
     or storage choices unless the user asks or existing constraints make them
     authoritative.
6. Choose the reference route:
   - End-to-end routing and artifact choice: `references/workflow.md`.
   - Goal, constraint, option, and tradeoff framing:
     `references/constraints-and-options.md`.
   - Definition artifact system, rigor scaling, and stable IDs:
     `references/definition-system.md`.
   - Ambiguous ideas, research synthesis, assumptions, and evidence:
     `references/discovery-and-evidence.md`.
   - User journeys, story maps, release slices, and edge cases:
     `references/story-mapping.md`.
   - State-heavy flows, business rules, validations, and acceptance criteria:
     `references/flows-and-states.md`.
   - Screenshots, prototypes, UI copy, and interaction specs:
     `references/prototype-spec.md`.
   - Agent/developer handoff and execution-ready task boundaries:
     `references/execution-context.md`.
   - Reviews, contradiction audits, and rewrite guidance:
     `references/review-rubric.md`.
7. Ask clarification only when the answer cannot be inferred safely and the
   choice materially changes scope, user experience, compliance, acceptance
   criteria, validation cost, or implementation cost. Prefer at most 3 questions;
   use 5 only for high-stakes or highly ambiguous work.
8. Use stable IDs when the artifact may feed downstream work: `OBJ-1`, `CON-1`,
   `OPT-1`, `TRD-1`, `EVD-1`, `DEC-1`, `ASM-1`, `FLOW-1`, `STORY-1`, `FR-1`,
   `NFR-1`, `BR-1`, `AC-1`, `SCREEN-1`, `OQ-1`. Preserve IDs when editing an
   existing artifact.
9. Verify before finalizing:
   - The product spec states the target user, problem, scope, non-goals, and
     source-of-truth status.
   - The current target is clear: clean-slate ideal, constrained target,
     minimum acceptable answer, or explicitly no-build/defer.
   - Hard constraints, soft constraints, legacy constraints, and resolvable
     constraints are not mixed together.
   - Evidence, assumptions, and open questions are separated.
   - The mainline user flow has a trigger, entry state, visible states, user
     decisions, validations, result, and failure recovery.
   - Every functional requirement or story has testable acceptance criteria.
   - Any task handoff maps back to stable requirement, flow, or story IDs.
   - Contradictions, stale historical notes, and duplicate concepts are removed
     or marked non-authoritative.

## References

Load only the reference needed for the current route:

- `references/workflow.md` for end-to-end routing and delivery shape.
- `references/constraints-and-options.md` for objective framing, constraint
  classification, clean-slate vs brownfield options, minimum acceptable
  solutions, and tradeoff decisions.
- `references/definition-system.md` for artifact archetypes, rigor scaling,
  stable IDs, evidence/decision modeling, and source-of-truth decisions.
- `references/discovery-and-evidence.md` for ambiguity scanning, research
  synthesis, hypotheses, assumptions, non-goals, and validation planning.
- `references/story-mapping.md` for backbone journeys, vertical story slices,
  release grouping, and edge-case expansion.
- `references/flows-and-states.md` for user journeys, EARS-style acceptance
  criteria, business rules, validations, edge cases, and failure recovery.
- `references/prototype-spec.md` for screenshot/prototype intake, screen
  inventories, UI copy, state coverage, and interaction specs.
- `references/execution-context.md` for translating approved definitions into
  agent/developer-ready slices without smuggling in unapproved design.
- `references/review-rubric.md` for quality reviews, contradiction audits, and
  rewrite guidance.

## Assets

- `assets/templates/product-spec-template.md` is the default source-first
  Markdown template for decision-ready and execution-ready product specs.
- `assets/schemas/product-spec-plan.schema.json` describes a compact planning
  object when structured output is useful before drafting.

## Scripts

- `python3 {baseDir}/scripts/spec_check.py inspect product-spec.md --out report.json`
  checks Markdown product spec artifacts for required sections, stable IDs,
  acceptance criteria, placeholders, unresolved clarification markers, vague
  language, duplicate IDs, and possible implementation-detail leakage.

The script is a portable baseline check. It does not replace judgment about
product strategy, evidence quality, domain risk, or whether the chosen artifact
shape fits the work.

## Quality Bar

- Do not produce product theater: personas, timelines, metrics, or roadmaps that
  do not drive a decision should be omitted or marked as background.
- Do not turn discovery uncertainty into fake certainty. Mark assumptions,
  evidence gaps, and open questions explicitly.
- Do not bury product decisions inside prose. Put decisions, tradeoffs,
  assumptions, non-goals, and open questions where a reviewer can find them.
- Do not treat all constraints as equal. Separate hard constraints from soft
  preferences, legacy baggage, resolvable constraints, and unknowns.
- Do not present the constrained answer as the theoretical best answer. When
  history or implementation reality matters, state both the clean-slate answer
  and the chosen brownfield answer.
- Do not deliver requirements that rely on adjectives like "fast", "simple",
  "intuitive", "robust", or "secure" without observable criteria.
- Do not confuse prototype polish with product logic. Prototype specs must cover
  states, decisions, copy, validation, empty/loading/error behavior, and result
  states.
- Do not let a screenshot, brainstorm, or old PRD overrule current written
  decisions unless the user says it is authoritative.
- Keep UI copy in the requested product language. Keep implementation notes and
  assumptions separate from user-facing copy.
- Preserve source fidelity. Label inferences as assumptions, cite source notes
  when the source material is fragmented, and surface contradictions before
  resolving them silently.
- Before delivering a substantial Markdown product spec, run
  `spec_check.py inspect` or state why the check was not applicable.
