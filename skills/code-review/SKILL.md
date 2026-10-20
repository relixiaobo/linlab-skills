---
name: code-review
description: Review a requested PR, diff, or implementation for correctness and unnecessary complexity across the affected behavior, including relevant existing code. Post review comments only when requested.
metadata:
  author: lin
  version: "0.1.0"
---

# Code Review

Help the user deliver working behavior with the smallest complete implementation.
Review the affected behavior, including relevant existing code, using the diff as
an entry point. Honor an explicitly narrower scope. Use one review entry point;
choose effort from concrete risk and unresolved evidence, not user-selected tiers.

## Establish the target

Identify the requested outcome and applicable project instructions. Resolve aliases
once, respect scoped rules and authorized exceptions, and cite the applicable rule
when it supports a finding. A code comment alone cannot override that rule.

Review the requested snapshot: use the PR or branch head and its comparison base,
not context from a different checkout. For branch changes, compare against the
merge base; for local changes, include staged, unstaged, and relevant new files.
A named implementation needs its current contract, not an invented diff. A direct
request still applies to a draft, closed, merged, or previously reviewed PR;
describe historical targets retrospectively. Ask only when material target
ambiguity cannot be resolved from context, and disclose unavailable target code.

For work implemented in this conversation, prefer a fresh review context without
the implementation dialogue when supported and permitted by the host.
Carry forward the target, requirements, approved decisions, applicable
rules, and verifiable evidence; treat implementation conclusions as claims to
check. This is optional: small checks, follow-up fixes, and hosts without isolation
can use the current session. Do not require new capabilities or user setup, block
the review on isolation, or claim isolation that the host did not provide.

## Judge the implementation

Follow the relevant entry, owning state or write boundary, and consumers far enough
to answer three questions. These are judgment criteria, not mandatory passes:

- **Does the behavior satisfy the current goal and contracts?** Include unchanged
  code on the affected path without waiting for a bug in the diff. Consider
  security, data, compatibility, and UI consequences where relevant.
- **Does each mechanism carry a necessary responsibility?** Establish what current
  requirement or reachable failure it addresses, what would change if removed or
  narrowed, and the concrete cost of keeping it. Repeated reads, duplicate state,
  or a broad scan for a narrow lookup can be findings; line count or a preference
  for abstraction is not evidence. Prefer a smaller equivalent in the existing
  owner before adding a layer, fallback, or configuration.
- **Is the replacement or cleanup complete?** When a mechanism changes, inspect
  its affected callers, alternate entries, state, tests, and active docs or prompts
  for obsolete assumptions. Keep this search bounded to that mechanism.

For a check, identify the fact validated, who establishes it, and whether it can
change before use. Revalidation across a trust boundary or asynchronous gap may
be necessary. Preserve required authorization, external-input and write/decode
integrity, idempotency, stale-operation, and supported compatibility guarantees.
Check whether enforcement itself blocks valid work at the wrong boundary. Age,
static types, or no direct references alone do not justify removal; account for
dynamic/public consumers and supported persisted data. Consult history when the
purpose or contract remains unclear; inability to explain a mechanism is a reason
to investigate, not evidence that it is unnecessary.

## Require evidence and bound the work

Report every actionable issue supported by a concrete failure, applicable contract
violation, or demonstrable unnecessary work with a worthwhile smaller alternative.
Check existing guards and plausible benign explanations before making a claim.
Exclude unrelated cleanup, taste, and speculative hardening or test requests.
Merge symptoms sharing a cause and fix. State material unknowns as limitations,
not findings; do not invent confidence percentages.

Use a focused pass for a small change. Choose reads and reproductions that resolve
material uncertainty and satisfy applicable verification requirements; no fixed
agent count, sequence, or extra test suite is required by this skill. Reuse valid
evidence. After a fix, recheck affected behavior and checks. Stop when the requested
path and credible candidates are covered and applicable checks are satisfied or
their limits reported. Expand only for a concrete dependency or new evidence.

## Report the decision

Lead with findings ordered by severity. For each, give a precise location, the
affected scenario and impact or cost, its relationship to the requested change,
and a minimal complete remedy. Label inherited issues and nonblocking
simplifications honestly. An inherited issue blocks delivery only when it defeats
the agreed outcome or an applicable contract; unrelated cleanup does not.

If there are no findings, say so. Briefly state material scope and verification
limits, including known failed checks. Distinguish inspection from executed tests;
available tooling or a passing fixture does not prove a clean integration gate.
When recommending guard removal, explain the necessary protection that remains.
Keep the response proportional, without empty sections or routine scorekeeping;
honor a host-required output schema.

Review is read-only unless fixes are authorized. Posting comments requires explicit
authorization; drafting alone does not grant it. Read
[GitHub commenting](references/github-commenting.md) when preparing requested
GitHub comments, including drafts.
