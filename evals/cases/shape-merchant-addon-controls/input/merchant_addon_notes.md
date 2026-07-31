# Messy Notes: Merchant Add-On Controls

Sales says enterprise merchants keep asking to limit which paid add-ons can be
enabled by regional managers. Today any workspace owner can enable an add-on,
then finance discovers it on the invoice later.

Important notes:

- Target user: finance admin at multi-region merchant.
- Existing roles: workspace owner, finance admin, regional manager.
- Regional managers should be able to request an add-on, not buy it directly.
- Finance admins approve or reject requests.
- Workspace owners can still enable immediately, but the action should be
  visible to finance.
- Add-on request should start from the Add-ons page and from a locked feature
  upsell.
- We need an audit trail for who requested, approved, rejected, or enabled.
- MVP is web only. Do not include mobile app support.
- Do not build budget forecasting in v1.
- Success: fewer surprise invoice escalations and approvals happen before the
  next invoice is generated.
- Open issue: should finance approval be required for owners too?
