# Product Spec: Merchant Add-On Approval

## 1. Purpose And Reader

This definition is for agents, developers, and product reviewers implementing
approval controls for paid add-ons in the merchant workspace. The Markdown
product spec is the source of truth for product behavior.

## 2. Decision Summary

- **DEC-1:** Regional managers can request paid add-ons, while finance admins
  approve or reject the requests before the add-on is enabled.
- **DEC-2:** Workspace owner immediate enablement remains preserved in v1, but
  finance receives audit visibility.
- **Primary risk:** Owner approval requirements are unresolved.
- **Not building:** Mobile support and budget forecasting are excluded from v1.

## 3. Objective, Constraints, And Options

- **OBJ-1:** Prevent surprise enterprise add-on spend while keeping legitimate
  regional requests moving.
- **Minimum acceptable outcome:** Regional managers can request approval, finance
  admins can approve or reject, and each decision leaves an audit trail.
- **Clean-slate best answer:** All paid add-on enablement would use a unified
  approval policy with configurable thresholds and finance-owned defaults.
- **Selected target:** OPT-2 because it controls regional manager purchases
  without changing owner enablement in v1.
- **Revisit trigger:** If finance confirms owners must also be gated, reopen
  owner enablement before implementation.

### Constraints

- **CON-1 legacy:** Workspace owners can currently enable add-ons immediately;
  changing that path in v1 could block existing customers.
- **CON-2 hard:** Regional managers must not directly purchase paid add-ons in
  v1.
- **CON-3 resolvable:** Owner approval can move behind the same finance queue
  after the owner policy is decided.

### Options Considered

- **OPT-1 clean-slate:** Route every paid add-on purchase through a finance
  approval policy.
- **OPT-2 brownfield target:** Gate regional manager purchases now while keeping
  owner immediate enablement visible to finance.
  - **TRD-1:** Accept temporary inconsistency between owner and regional manager
    purchase paths to avoid blocking existing owner workflows.
- **OPT-3 minimum acceptable:** Add a request/approval queue for regional
  managers only and defer owner audit visibility.

## 4. Problem, Users, And Evidence

Enterprise finance admins need add-on purchases reviewed before the next invoice
so they are not surprised by regional spend.

- **EVD-1:** Sales notes say enterprise merchants ask to limit which paid
  add-ons regional managers can enable.
- **EVD-2:** Current behavior lets workspace owners enable an add-on, then
  finance discovers the spend on the invoice later.
- **ASM-1:** Finance admins already have access to the web workspace.

## 5. Scope

### In Scope

- Regional managers can request a paid add-on.
- Finance admins can approve or reject requests.
- Workspace owners can enable an add-on immediately and finance can see the
  audit event.

### Out Of Scope

- Mobile app support is deferred from v1.
- Budget forecasting is not part of this release.

## 6. Product Model / Glossary

- **Add-on Request** - A pending request from a regional manager to enable a
  paid add-on.
- **Pending Review** - The state after a regional manager requests finance
  approval.
- **Approved** - The state after a finance admin approves the add-on request.
- **Rejected** - The state after a finance admin rejects the request.

## 7. User Flows

### FLOW-1: Regional manager requests an add-on

- **Actor:** Regional manager
- **Entry path:** Add-ons page or locked feature upsell
- **Entry state:** User can view add-ons but cannot purchase paid add-ons
- **Goal:** Request finance approval for a paid add-on
- **Mainline:**
  1. User opens a paid add-on.
  2. User selects Request approval.
  3. User confirms the request.
- **Decision points:** User can cancel before confirmation.
- **Validation:** User must belong to the merchant workspace.
- **Result state:** Add-on Request moves to Pending Review.
- **Failure/recovery:** If request creation fails, the page keeps the add-on
  locked and offers Retry.
- **Requirements/stories:** STORY-1, FR-1

### FLOW-2: Finance admin approves or rejects a request

- **Actor:** Finance admin
- **Entry path:** Add-on approvals queue
- **Entry state:** Add-on Request is Pending Review
- **Goal:** Decide whether the paid add-on should be enabled
- **Mainline:**
  1. Finance admin opens the request.
  2. Finance admin reviews requester, add-on, region, and price.
  3. Finance admin approves or rejects.
- **Decision points:** Approve or reject.
- **Validation:** Request must still be Pending Review.
- **Result state:** Approved requests enable the add-on; rejected requests keep
  the add-on locked.
- **Failure/recovery:** If the request is no longer pending, the queue refreshes
  and explains that the request has already changed.
- **Requirements/stories:** STORY-2, FR-2, BR-1

## 8. Stories And Requirements

### Stories

- **STORY-1:** As a regional manager, I want to request a paid add-on so that I
  can start approval without bypassing finance.
  - **Release:** MVP
  - **Acceptance:** AC-1, AC-2
- **STORY-2:** As a finance admin, I want to approve or reject pending requests
  so that paid add-ons are controlled before invoicing.
  - **Release:** MVP
  - **Acceptance:** AC-3, AC-4

### Functional Requirements

- **FR-1:** Regional managers can request approval for a paid add-on from the
  Add-ons page or a locked feature upsell.
  - **AC-1:** When a regional manager confirms an add-on request, the workspace
    shall create an Add-on Request in Pending Review state.
  - **AC-2:** If request creation fails, the surface shall keep the add-on
    locked and show Retry.
- **FR-2:** Finance admins can approve or reject pending Add-on Requests.
  - **AC-3:** When a finance admin approves a Pending Review request, the
    workspace shall enable the add-on and record the approver.
  - **AC-4:** When a finance admin rejects a Pending Review request, the
    workspace shall keep the add-on locked and record the rejection.

### Business Rules

- **BR-1:** Regional managers cannot directly purchase paid add-ons in v1.
- **BR-2:** Workspace owner immediate enablement remains allowed and creates an
  audit event visible to finance.

## 9. Prototype / UI Behavior

### SCREEN-1: Add-on detail locked state

- **Purpose:** Explain why the add-on is locked and let regional managers
  request approval.
- **Entry:** FLOW-1
- **Visible data:** Add-on name, price, region, approval status.
- **Actions:** Request approval, Cancel.
- **States:** default, loading, disabled, error, success.
- **Copy:** "Request finance approval" and "Your request was sent to finance."
- **Rules referenced:** BR-1

## 10. Edge Cases And Failure States

- **EC-1:** If a request changes while a finance admin is reviewing it, the
  approval queue shall refresh before accepting a decision.

## 11. Success Metrics / Completion Signals

- **SM-1:** Finance-visible audit events exist for every requested, approved,
  rejected, or owner-enabled paid add-on.

## 12. Execution Context

- **Suggested story slice:** STORY-1 and STORY-2 can ship together as the
  request/approval value loop.
- **Verification plan:** Create request, approve request, reject request, and
  stale-review manual checks all pass.

## 13. Open Questions

- **OQ-1:** Should finance approval also be required for workspace owners?
