# Shape Product Spec Workflow

Use this workflow when the user asks for product definition, feature definition,
PRDs, product briefs, story maps, product-flow reviews, prototype behavior
specs, contradiction audits, or implementation-facing product specs.

## 1. Intake The Source

Collect only context that materially changes the definition:

- product or feature name
- target users, roles, non-users, and affected operators
- problem, job to be done, or decision the product enables
- current alternatives and why they fail
- source notes, interviews, screenshots, existing docs, decisions, and
  contradictions
- known evidence, missing evidence, and confidence level
- business objects and lifecycle states
- existing product surface, entry paths, permissions, and dependencies
- constraints: privacy, compliance, billing, rollout, platform, localization,
  accessibility, operations, support
- success signal, counter-metric, and risks

When source material conflicts, preserve the conflict until it is resolved.
Silent conflict resolution is usually worse than an explicit open question.

## 2. Frame Objectives, Constraints, And Options

Before choosing the artifact shape, decide what kind of answer the user needs:

- actual objective: the user or business reality that should change
- minimum acceptable outcome: the smallest result that still solves the problem
- clean-slate best answer: best direction without inherited constraints
- constrained target: best current answer under real constraints
- revisit trigger: condition that would make the decision worth reopening

Classify constraints as hard, soft, legacy, resolvable, or unknown. If a
constraint is claimed but not evidenced, keep it as an assumption or open
question.

When constraints materially affect the product, compare at least two options:
clean-slate, brownfield/constrained, minimum acceptable, deferred ideal, or
no-build/operational. Select one target only when the user needs an
execution-facing definition.

## 3. Choose The Artifact Shape

Pick the smallest artifact that can carry the decision safely:

- **Discovery brief**: unclear problem, weak evidence, or early idea validation.
- **One-page feature definition**: narrow change, 1-2 flows, low risk.
- **Definition pack**: multiple flows, product rules, business logic, or agent
  execution handoff.
- **Story map**: the team needs release slices across a user journey.
- **Prototype behavior spec**: screenshots, mockups, or UI flows are central.
- **Brownfield change definition**: existing behavior must be preserved while a
  change is introduced.
- **Decision memo / PRFAQ-style brief**: stakeholders need why/why now/why this
  before the build shape is stable.
- **Review report**: the user needs risks, contradictions, and fixes rather than
  a new artifact.
- **Execution pack**: the definition is approved and needs implementation
  slices, verification, and agent handoff.

Do not force every request into a long PRD. Shape fit is part of product
quality.

## 4. Reconstruct The Product Mainline

Before writing sections, answer:

- Who is acting?
- What object, decision, or workflow are they working with?
- What state do they start in?
- What action triggers the feature?
- What confirms success?
- What can block, invalidate, reverse, or degrade the result?
- What must remain unchanged?

If the answers are unavailable, infer only when a reasonable default exists and
record the assumption. Ask when the answer changes scope, UX, compliance,
business rules, validation, or acceptance tests.

## 5. Preserve Why, What, And How Separately

Definition layer:

- objectives, constraints, options, and tradeoffs
- user goals and observable behavior
- product rules, validations, permissions, eligibility, billing, quotas
- states, transitions, copy, result states, failure recovery
- decisions, tradeoffs, assumptions, evidence, and non-goals
- acceptance criteria and success signals

Implementation/design layer:

- frameworks, APIs, services, storage, schemas, jobs, component names, internal
  state models

Keep implementation details out of the definition unless they are already
decided constraints. If useful, add a clearly labeled "Implementation
Suggestions" or "Known Technical Constraints" section.

## 6. Design Flows Before Screens

For every important flow, define:

1. Trigger
2. Entry condition
3. Visible state
4. User decision or system decision
5. Validation and business rules
6. Settlement/result state
7. Failure, empty, loading, disabled, and recovery states

Only then specify screens, panels, buttons, copy, and field behavior.

## 7. Draft With Stable Traceability

Use stable IDs when the artifact will feed implementation or review:

- `OBJ-1`: objective
- `CON-1`: constraint
- `OPT-1`: option
- `TRD-1`: tradeoff
- `EVD-1`: evidence item
- `DEC-1`: product decision
- `ASM-1`: assumption
- `FLOW-1`: user journey or workflow
- `STORY-1`: user story or vertical slice
- `SCREEN-1`: prototype/surface state
- `FR-1`: functional requirement
- `BR-1`: business rule
- `NFR-1`: non-functional requirement
- `AC-1`: acceptance criterion
- `OQ-1`: open question

Keep IDs stable during rewrites. Downstream references should not break just
because sections moved.

## 8. Finalize With A Quality Pass

Before final output:

- Remove or isolate historical notes that are no longer authoritative.
- Merge duplicate requirements and normalize glossary terms.
- Check that clean-slate, constrained, and minimum acceptable answers are
  distinguished when constraints matter.
- Check that hard constraints, soft constraints, legacy constraints, and
  resolvable constraints are not mixed together.
- Check that every flow has an entry path and result state.
- Check that every requirement or story has at least one testable acceptance
  criterion.
- Check that evidence, assumptions, and open questions are separated.
- Check that non-goals block likely overbuild.
- Check that UI copy matches product rules and uses user-facing terms.
- Check that task handoff items map to stable IDs.
- For Markdown artifacts, run `spec_check.py inspect` when a file exists.

## 9. Review Output Shape

For a review, lead with actionable risks:

1. Blocking contradictions or missing decisions.
2. Unclear objective, mixed constraints, or missing tradeoff decision.
3. Unsupported assumptions presented as facts.
4. Untestable requirements or hidden scope.
5. Broken or unreachable user flows.
6. Prototype state/copy mismatches.
7. Implementation-detail leakage into product definition.
8. Suggested restructure or rewrite plan.
