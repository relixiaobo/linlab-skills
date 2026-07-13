# Constraints And Options

Use this reference when a product spec is shaped by constraints, legacy behavior,
unclear goals, competing options, or a question like "what should we actually
build now?"

The goal is not to name-drop frameworks. The goal is to define the best current
answer under explicit conditions.

## Core Frame

Before selecting a product shape, answer:

- **OBJ-1 Actual objective:** What user or business reality should change?
- **Non-goal:** What tempting adjacent outcome is intentionally excluded?
- **Minimum acceptable outcome:** What must be true for this work to count?
- **Clean-slate best answer:** What would be best without inherited constraints?
- **Constrained target:** What should be done under current constraints?
- **Revisit trigger:** Which changed condition would make the decision wrong?

If the request is exploratory, show options without forcing a decision. If the
request is execution-facing, recommend one target and explain the tradeoff.

## Constraint Types

Classify constraints before treating them as binding:

- **Hard constraint:** Cannot be violated in this work. Examples: law,
  compliance, security, contract terms, data loss risk, platform limitation.
- **Soft constraint:** Real but negotiable. Examples: timeline, staffing,
  design debt, migration effort, stakeholder preference.
- **Legacy constraint:** Existing behavior, user habit, data shape, API, workflow,
  organizational decision, or customer expectation inherited from the past.
- **Resolvable constraint:** Can be removed through migration, refactor,
  process change, rollout, policy update, or user education.
- **Unknown constraint:** Claimed or likely, but not evidenced. Mark as an open
  question or assumption.

Do not let an unevidenced preference become a hard constraint. Do not ignore a
hard constraint because it makes the clean-slate answer prettier.

## Option Set

Use only the options needed for the decision:

- **OPT-1 Clean-slate option:** Best product answer if there were no legacy
  baggage. Useful for direction and future state.
- **OPT-2 Brownfield target:** Best answer under current constraints. Usually
  the recommended execution target.
- **OPT-3 Minimum acceptable option:** Smallest solution that still changes the
  user or business reality. Useful when time, risk, or validation cost matters.
- **OPT-4 Deferred ideal:** Future version after constraints are removed.
- **OPT-5 No-build / operational option:** Process, policy, support, or manual
  workaround when software should not be built yet.

For each option, capture:

- user impact
- scope and excluded scope
- constraints satisfied or violated
- cost, risk, and reversibility
- evidence strength and assumptions
- why it wins or loses for the current objective

## Decision Pattern

Use this compact structure inside a product brief or decision memo:

```markdown
## Objective, Constraints, And Options

- **OBJ-1:** [Actual objective.]
- **Minimum acceptable outcome:** [Smallest outcome that counts.]
- **Clean-slate best answer:** [Best direction without inherited constraints.]
- **Selected target:** OPT-2 because [reason].

### Constraints

- **CON-1 hard:** [Constraint, source, impact.]
- **CON-2 legacy:** [Inherited behavior or system reality, source, impact.]
- **CON-3 resolvable:** [Constraint and how it could later be removed.]

### Options

- **OPT-1 clean-slate:** [Summary.]
  - **Rejected for now:** [Reason.]
- **OPT-2 brownfield target:** [Summary.]
  - **Tradeoff TRD-1:** [Accepted cost and rationale.]
- **OPT-3 minimum acceptable:** [Summary.]
  - **Use if:** [Condition.]

### Revisit Triggers

- If [constraint changes], reconsider [option or scope].
```

## Method Borrowing

Use product methods as lightweight probes:

- **First principles:** reduce the request to objective, actors, constraints,
  and observable reality changed.
- **5 Whys / root cause:** use when the stated feature may be a symptom.
- **Jobs To Be Done:** use when the user, trigger, or desired progress is fuzzy.
- **Opportunity Solution Tree:** use when multiple opportunities or solutions
  compete and evidence is uneven.
- **Assumption mapping:** use when confidence is low or one bet could invalidate
  the feature.
- **Impact mapping:** use when business outcome, actors, and behavior change are
  disconnected.
- **Story mapping / vertical slice:** use when the main risk is overbroad scope.
- **PRFAQ / working backwards:** use when stakeholder alignment or launch
  narrative is more important than implementation detail.

Do not include the method names in final output unless useful for the reader.
Translate them into decisions, constraints, options, assumptions, and acceptance
criteria.
