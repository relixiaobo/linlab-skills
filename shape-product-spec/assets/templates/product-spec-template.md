---
title: "[Product / Feature]"
status: "Draft"
source_of_truth: "Markdown product spec"
created: "YYYY-MM-DD"
updated: "YYYY-MM-DD"
---

# Product Spec: [Product / Feature]

## 1. Purpose And Reader

[Who this definition is for, what decision or build work it supports, and which
source material is authoritative.]

## 2. Decision Summary

- **DEC-1:** [What will be built, changed, validated, or intentionally deferred.]
- **Why now:** [Timing or reason, only if it matters.]
- **Primary risk:** [Main unresolved or high-impact risk.]
- **Not building:** [Most important non-goal.]

## 3. Objective, Constraints, And Options

- **OBJ-1:** [Actual user or business reality this work should change.]
- **Minimum acceptable outcome:** [Smallest outcome that makes the work useful.]
- **Clean-slate best answer:** [Best answer without inherited constraints.]
- **Selected target:** [OPT-* and why it is the current target.]
- **Revisit trigger:** [Condition that would make the decision worth reopening.]

### Constraints

- **CON-1 hard:** [Non-negotiable constraint, source, and impact.]
- **CON-2 legacy:** [Existing behavior/system/user expectation and impact.]
- **CON-3 resolvable:** [Constraint that could later be removed and how.]

### Options Considered

- **OPT-1 clean-slate:** [Summary and why it is ideal.]
- **OPT-2 brownfield target:** [Summary of current selected approach.]
  - **TRD-1:** [Accepted cost or compromise and rationale.]
- **OPT-3 minimum acceptable:** [Smallest useful version and when to choose it.]

## 4. Problem, Users, And Evidence

### Problem

[The user/business problem in plain language.]

### Target Users

- **[Role/persona]:** [Context, trigger, and job to be done.]

### Non-Users / Exclusions

- [Who or what is out of scope for this release.]

### Evidence

- **EVD-1:** [Quote, observation, data point, support/sales signal, or approved
  decision.]
- **ASM-1:** [Assumption and why it is reasonable.]

## 5. Scope

### In Scope

- [Specific capability or behavior.]

### Out Of Scope

- [Specific exclusion and reason.]

## 6. Product Model / Glossary

- **[Term]** - [Definition and relationship to other terms.]
- **[State]** - [Meaning and allowed transitions.]

## 7. User Flows

### FLOW-1: [Flow Name]

- **Actor:** [Role]
- **Entry path:** [Surface and trigger]
- **Entry state:** [Permissions, object state, data known]
- **Goal:** [User-visible outcome]
- **Mainline:**
  1. [Step]
  2. [Step]
  3. [Step]
- **Decision points:** [Choices]
- **Validation:** [Rules checked]
- **Result state:** [What changes after success]
- **Failure/recovery:** [What happens on failure]
- **Requirements/stories:** FR-1, STORY-1

## 8. Stories And Requirements

### Stories

- **STORY-1:** As a [user], I want [capability] so that [outcome].
  - **Release:** MVP
  - **Acceptance:** AC-1, AC-2

### Functional Requirements

- **FR-1:** [Actor/system] can [capability] [under conditions].
  - **AC-1:** When [event], the [system/surface] shall [observable response].
  - **AC-2:** If [precondition/failure], the [system/surface] shall [observable response].

### Business Rules

- **BR-1:** [Rule with actor/object/condition/result.]

### Non-Functional Requirements

- **NFR-1:** [Observable quality requirement and target.]

## 9. Prototype / UI Behavior

### SCREEN-1: [Screen / State]

- **Purpose:** [Decision, confirmation, or information this screen supports]
- **Entry:** FLOW-1
- **Visible data:** [User-facing data]
- **Actions:** [Primary, secondary, destructive]
- **States:** [default, empty, loading, disabled, error, success]
- **Copy:** [Labels, helper text, error copy]
- **Rules referenced:** BR-1

## 10. Edge Cases And Failure States

- **EC-1:** [Scenario] -> [required behavior and recovery path].

## 11. Success Metrics / Completion Signals

- **SM-1:** [Metric, definition, target, and related requirement.]
- **Counter-metric:** [What should not be optimized at the expense of quality.]

## 12. Execution Context

- **Suggested story slice:** [Requirement/story IDs and outcome.]
- **Known constraints:** [Confirmed technical/product constraints.]
- **Implementation suggestions:** [Clearly optional unless confirmed.]
- **Verification plan:** [Commands, manual checks, review evidence.]

## 13. Open Questions

- **OQ-1:** [Decision needed, owner if known, impact if unanswered.]

## 14. Appendix

[Historical notes, source excerpts, screenshots, or non-authoritative context.]
