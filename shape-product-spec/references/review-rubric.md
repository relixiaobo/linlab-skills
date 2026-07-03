# Product Spec Review Rubric

Use this when reviewing, rewriting, or finalizing a product definition, PRD,
requirements spec, prototype behavior spec, story map, or implementation-facing
product spec.

## Review Stance

Lead with risks to usefulness, not template compliance. A short artifact can be
strong if it makes decisions clear and testable. A long artifact can be broken
if it hides scope, lacks flows, or presents assumptions as facts.

Severity:

- **Critical**: blocks implementation or can cause materially wrong behavior.
- **High**: likely causes rework, ambiguous tests, compliance/privacy/billing
  risk, or stakeholder misalignment.
- **Medium**: weakens handoff quality or leaves common edge cases unclear.
- **Low**: style, wording, or maintainability improvements.

## 1. Decision Readiness

Can a reviewer or builder act on the artifact?

Look for:

- actual objective and selected target
- clear decision summary
- explicit tradeoffs and non-goals
- unresolved decisions listed as open questions
- assumptions marked rather than hidden
- source-of-truth status stated

Red flags:

- every option sounds equally good
- major choices are buried in paragraphs
- open questions are phrased but not owned
- constrained compromise is presented as the clean-slate best answer

## 2. Objective And Constraint Fit

Is the recommended product shape the best answer under the stated conditions?

Look for:

- minimum acceptable outcome
- clean-slate option and constrained/brownfield target when history matters
- hard constraints separated from soft preferences
- legacy constraints separated from future direction
- resolvable constraints and revisit triggers
- tradeoffs that explain why the selected option wins now

Red flags:

- no objective beyond "build the feature"
- all constraints treated as equally binding
- historical baggage silently dictates the future product direction
- minimum viable scope is either undefined or includes every adjacent feature
- no condition under which the decision would be reconsidered

## 3. Evidence And Assumption Quality

Does the artifact distinguish known facts from bets?

Look for:

- evidence ledger or source notes
- customer quotes, usage data, support/sales signals, or approved decisions
- assumptions labeled with confidence or validation step
- riskiest assumption surfaced

Red flags:

- internal opinion presented as customer need
- competitor behavior treated as proof
- unsupported metrics or personas
- no validation path for early-stage ideas

## 4. Product Coherence

Does the artifact have a product thesis and mainline?

Look for:

- named user problem or job to be done
- target users and non-users
- coherent product object model
- features that serve the same outcome
- success signals that validate the thesis

Red flags:

- backlog list disguised as product definition
- multiple names for the same concept
- solution-first document with no user problem

## 5. Flow And State Completeness

Can the user journey be implemented without guessing?

Look for:

- real entry paths and triggers
- entry state and permissions
- visible states and user decisions
- validation timing
- result states after success
- empty/loading/disabled/error/recovery states where relevant

Red flags:

- screens with no trigger
- success state but no failure state
- "handle gracefully" without behavior

## 6. Requirement Testability

Would QA, a developer, or an agent know what done means?

Look for:

- stable IDs such as `FR-*`, `STORY-*`, `AC-*`
- acceptance criteria with trigger and expected result
- measurable non-functional requirements when quality matters
- business rules referenced from flows
- edge cases represented in tests or criteria

Red flags:

- "fast", "secure", "intuitive", "scalable", "robust" without observable
  criteria
- implementation details are precise while product behavior is vague
- acceptance criteria repeat the requirement without adding testability

## 7. Scope Honesty

Does the artifact prevent overbuild?

Look for:

- clear in-scope and out-of-scope items
- non-goals that block likely assumptions
- deferred items labeled with reason
- preserved behavior in brownfield changes
- dependencies and rollout constraints

Red flags:

- "MVP" includes every adjacent feature
- a deferred feature still appears in acceptance criteria
- old behavior is not described for a brownfield change

## 8. Prototype And Copy Quality

If UI/prototype behavior is involved, does it guide user decisions?

Look for:

- screen inventory tied to flows
- user-facing copy in the requested language
- action labels that name the action
- errors explaining cause and recovery
- UI text consistent with product rules

Red flags:

- UI exposes internal formulas, IDs, queue names, table fields, or backend terms
- copy contradicts eligibility, billing, permissions, or state rules
- screenshots are treated as final truth despite conflicting written rules

## 9. Downstream Usability

Can another agent, designer, or developer continue from the artifact?

Look for:

- stable IDs and cross-references
- glossary / canonical terms
- traceability from objective to constraints to selected option
- traceability from evidence to decisions to flows to acceptance criteria
- implementation suggestions separated from product definition
- appendices clearly marked as non-authoritative when historical

Red flags:

- tasks or implementation ideas with no definition mapping
- broken or duplicate IDs
- source material copied verbatim without synthesis

## Review Output

Use this shape:

```markdown
# Product Work Review: [name]

## Verdict
[2-3 sentences on readiness and core risk.]

## Findings
- **[critical|high|medium|low] Title** (section or quote) - Why it matters.
  Fix: concrete recommendation.

## Open Questions
- OQ-1: [decision needed and why]

## Suggested Restructure
[Only if structure is a real problem.]
```
