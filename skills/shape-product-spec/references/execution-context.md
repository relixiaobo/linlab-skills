# Execution Context

Use this reference when approved or mostly approved product definition needs to
become execution-ready stories, tasks, or an agent/developer briefing.

## Handoff Boundary

Only generate implementation tasks after the definition is stable enough to
avoid rework. If major product decisions remain open, produce a decision list or
discovery brief instead of a task plan.

Execution context may include implementation suggestions, but suggestions must
not override product behavior.

## Developer / Agent Brief

A concise execution brief should include:

- source of truth and status
- goal and non-goals
- affected users and permissions
- evidence, assumptions, and unresolved questions
- flows in scope
- product model/glossary
- requirements or stories and acceptance criteria
- business rules and validations
- edge cases and failure states
- dependencies and constraints
- verification plan
- suggested implementation boundaries, if requested

## Story Slicing

Prefer vertical feature slices when possible:

- slice delivers one user-visible flow or outcome
- slice has its own acceptance criteria
- slice can be tested independently
- slice references requirement, story, or flow IDs
- slice is small enough for one agent pass when possible

Use foundation-first slicing only when a shared data model, integration, or
platform change must exist before any user-visible behavior can work.

## Task Pattern

```markdown
- [ ] 1. Add regional manager add-on request flow
  - Covers FLOW-1, STORY-1, FR-1, BR-1
  - Acceptance: AC-1, AC-2
  - Verification: run request-flow test and manually check locked add-on state
  - Notes: preserve workspace owner immediate enablement behavior
```

Avoid tasks like "Implement backend" without a definition reference.

## Traceability

Every task should map to one or more of:

- flow ID
- story ID
- functional requirement ID
- business rule ID
- acceptance criterion ID
- screen ID for prototype-specific behavior
- open question ID when the task is blocked

If a task has no mapping, either the definition is missing or the task is out of
scope.

## Agent Context Discipline

Keep the execution pack small enough for an agent to load and act:

- lead with current objective and non-goals
- include only authoritative decisions and necessary evidence
- move historical research to an appendix or link
- put exact files/code areas only when known from codebase exploration
- state verification commands and manual checks explicitly
- include a progress/status field only if the artifact will be reused

## Task Readiness Checks

Before handing tasks to developers or agents:

- each requirement has acceptance criteria
- each task has a testable outcome
- dependencies and order are clear
- non-goals are not accidentally included
- open questions are not hidden inside tasks
- risks are explicit
- verification evidence is defined

## Implementation Suggestions

When the user asks for implementation planning, keep suggestions in a separate
section:

- recommended component boundaries
- data or API shape candidates
- migration considerations
- analytics events
- testing strategy
- rollout / feature flag suggestion

Mark them as suggestions unless they are confirmed constraints.
