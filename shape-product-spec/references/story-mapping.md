# Story Mapping

Use this reference when the user needs user-journey structure, MVP slicing,
release grouping, or an implementation plan that preserves user value.

## Core Model

Story mapping is useful because it keeps three dimensions visible:

- **Backbone**: the user's end-to-end happy path.
- **Vertical depth**: stories, rules, states, and edge cases under each step.
- **Horizontal release lines**: MVP, next release, future, or explicitly out of
  scope.

Start with the user's journey, not the system architecture.

## Coaching Mode

When the user wants collaboration or the idea is unclear:

1. Identify the primary persona and trigger.
2. Ask for the backbone in 3-7 high-level activities.
3. Confirm the backbone before adding detail.
4. Go vertical under each activity: stories, acceptance criteria, states,
   rules, risks.
5. Go horizontal: alternate flows, errors, edge cases, non-goals.
6. Draw release lines: MVP, R2, Future.
7. Summarize open questions and assumptions.

Ask one question at a time when the user is actively co-designing. For fast
generation, ask 3-5 questions up front and label assumptions.

## Generation Mode

When the user provides enough raw context, produce a complete first draft and
make assumptions explicit:

```markdown
## Story Map: [Feature]

### Persona
Primary: [role] - [context and goal]

### Backbone
1. [Activity 1]
2. [Activity 2]
3. [Activity 3]

### Release Lines
- **MVP:** STORY-1, STORY-2, STORY-4
- **R2:** STORY-3, STORY-5
- **Future:** STORY-6

### Stories
- **STORY-1:** As a [user], I want [capability] so that [outcome].
  - Activity: [Activity 1]
  - Release: MVP
  - Acceptance: AC-1, AC-2
  - Risks: [risk]
```

## Story Quality

Good stories:

- use the user's perspective, not system internals
- deliver visible user value
- are small enough to verify independently
- reference product rules and acceptance criteria
- include failure or edge states when relevant

Avoid stories like "build backend" or "make UI" unless the user explicitly asks
for technical task decomposition after the definition is stable.

## Release Slicing

MVP should include:

- the shortest path to user value
- the minimum rule set required to keep the product correct
- recovery states for trust-critical failures
- instrumentation or completion signals if success must be measured

Defer:

- alternate personas not needed for the first value loop
- bulk actions, advanced filters, or secondary integrations
- polish that does not affect comprehension or correctness
- automation that can safely stay manual for validation

## ASCII Map Shape

For compact outputs, an ASCII map is often enough:

```text
BACKBONE:  Request add-on  ->  Review request  ->  Decide request
MVP:       STORY-1             STORY-2             STORY-3
R2:        STORY-4                                 STORY-5
Future:    STORY-6
```

Follow the map with structured story details and acceptance criteria. Do not use
a diagram as the only source of truth.
