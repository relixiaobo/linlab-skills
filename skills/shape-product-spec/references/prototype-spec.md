# Prototype Behavior Spec

Use this reference when the user provides screenshots, asks for a prototype
rewrite, or wants UI behavior aligned with product rules.

## Prototype Is Product Logic

A prototype spec is not a visual-polish brief. It answers:

- where the user enters the flow
- what each screen helps the user decide or confirm
- what states and rules the UI must represent
- what copy users see
- how the UI responds to validation, permissions, and failures
- what success looks like

Visual style belongs in the prototype only when the user explicitly asks or the
style affects product comprehension.

## Screenshot Intake

Treat screenshots as evidence. Record:

- current surface and likely entry path
- visible objects and terms
- actions available
- disabled, empty, error, or selected states visible
- copy that looks product-authoritative
- inconsistencies with written notes

Do not assume screenshots are final visual direction unless the user says so.

## Screen Inventory

Use this structure:

```markdown
### SCREEN-1: [Screen name]

- **Purpose:** [decision, confirmation, or information this screen supports]
- **Entry:** FLOW-1 step 2
- **Primary user decision:** [what the user chooses]
- **Visible data:** [fields, values, derived text]
- **Actions:** [primary, secondary, destructive]
- **States:** default, empty, loading, disabled, error, success
- **Copy:** [user-facing labels/messages]
- **Rules referenced:** BR-1, BR-2
```

For simple definitions, a compact table is fine.

## UI Copy Rules

Prototype copy should:

- use the user's language, not internal team jargon
- tell the user what happened and what they can do next
- expose only user-meaningful numbers and rules
- avoid formulas, field names, internal IDs, queues, retries, database terms,
  or implementation mechanisms
- use one canonical term for each product object
- be short enough for the UI space implied by the prototype

Keep developer notes outside UI copy.

## State And Interaction Checklist

For each interactive screen, specify:

- default state
- empty state
- loading state
- disabled state and reason
- validation error state
- system failure state
- permission denied state
- destructive confirmation
- success confirmation
- retry, cancel, close, or undo behavior

If the state is intentionally out of scope, mark it.

## Data Examples

Use realistic example values only to clarify behavior:

- good: "Payout amount: USD 12,450.00; workspace limit: USD 10,000."
- bad: "amount_cents=1245000 in payouts table."

Example data should not introduce new product rules that the definition does
not state.

## Prototype Acceptance Criteria

Prototype behavior should have acceptance criteria too:

- `AC-12: When the approver lacks permission, SCREEN-2 shall show the approval action disabled with the reason "Only owners and finance admins can approve payouts."`
- `AC-13: If submission fails after confirmation, SCREEN-3 shall keep the payout in Pending state and offer Retry and Cancel.`
