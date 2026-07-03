# Flows And States

Use this reference for user journeys, business rules, validation, acceptance
criteria, and state-heavy product behavior.

## Flow Record

Document each meaningful flow with this shape:

```markdown
### FLOW-1: [Name]

- **Actor:** [role/persona]
- **Entry path:** [surface, trigger, source object]
- **Entry state:** [permissions, object state, data known]
- **Goal:** [user-visible outcome]
- **Mainline:**
  1. [step]
  2. [step]
  3. [step]
- **Decision points:** [choices user/system makes]
- **Validation:** [rules checked before proceeding]
- **Result state:** [what changes after success]
- **Failure/recovery:** [what happens when it fails]
- **Requirements/stories:** FR-1, STORY-1
```

If a flow has no reachable entry path, it is not ready to specify.

## State Coverage

For each important screen, object, or workflow state, check:

- default / ready state
- empty state
- loading or pending state
- disabled or ineligible state
- validation error
- system failure
- permission denied
- success / confirmation
- undo, cancel, retry, or recovery

Mention omitted states only when their omission could be misread.

## EARS-Style Acceptance Criteria

Write acceptance criteria as observable behavior. Use these patterns:

- `When [event], the [system/surface] shall [response].`
- `If [precondition/failure], the [system/surface] shall [response].`
- `While [state], the [system/surface] shall [response].`
- `Where [optional capability exists], the [system/surface] shall [response].`
- `The [system/surface] shall [always-true behavior].`

Examples:

- `AC-1: When a finance admin confirms payout approval, the payout shall move to Approved and show the approver name and timestamp.`
- `AC-2: If the payout amount exceeds the workspace limit, the approval form shall stay disabled and explain which limit blocks approval.`
- `AC-3: While approval is pending, the payout list shall show the Pending state and keep the Approve action unavailable to non-approvers.`

Avoid:

- "The flow should be intuitive."
- "The backend stores the status in payout_status."
- "Use Redis to prevent duplicate approvals."

## Business Rules

Business rules should be separate from UI steps:

```markdown
- **BR-1:** Only workspace owners and finance admins can approve payouts.
- **BR-2:** A payout above the workspace limit requires two distinct approvers.
- **BR-3:** A user cannot approve a payout they created.
```

Then reference rules from flows, stories, or acceptance criteria.

## Validation Rules

For validations, specify:

- trigger: when the rule is checked
- field or object being checked
- blocking or warning behavior
- user-facing message or copy
- recovery path

Example:

```markdown
- **FR-3:** The approval form validates payout eligibility before submission.
  - **AC-7:** When a payout is already settled, the form shall block approval and show "This payout has already been settled."
```

## Permissions

Define:

- roles
- allowed actions
- denied actions
- visibility differences
- audit trail if needed

Do not rely on role names alone. State what each role can observe and do.

## Edge Cases

Include edge cases that can affect user trust, data correctness, or support
load:

- duplicate submission
- concurrent edits or approvals
- expired sessions
- missing source data
- stale UI after state changes elsewhere
- interrupted network or external dependency failure
- reversal, cancellation, or refund-like states

Edge cases should still map to acceptance criteria when they are in scope.
