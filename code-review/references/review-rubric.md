# Code Review Rubric

Use this rubric for every substantial review. The goal is high signal: fewer findings, each defensible.

## Evidence Standard

Report an issue only when all are true:

- The issue is introduced or exposed by the reviewed change.
- The failure mode is concrete and reproducible by reasoning from code, types, API contracts, tests, docs, or project instructions.
- A senior reviewer would expect the author to act on it.
- The recommendation is specific enough to guide a fix.

Do not report:

- Pre-existing problems not made worse by the change.
- Style, taste, naming, or broad maintainability suggestions unless an applicable project instruction requires them.
- Issues a linter, formatter, or typechecker will trivially catch, unless the review environment cannot run those tools and the failure blocks correctness.
- General test coverage requests without a concrete untested failure mode.
- Hypothetical problems that require unknown inputs, unknown state, or unlikely environment assumptions.
- Project-instruction violations that are scoped to a different directory or are explicitly silenced in code.

## Confidence Scores

Assign a numeric score to each candidate before deciding whether to report it:

- 100: Certain. The code cannot compile, parse, or work as intended; or the rule violation is explicit and scoped.
- 90: Very high confidence. Clear failure path with strong local evidence and no plausible benign interpretation.
- 80: High confidence. Actionable issue with enough context to justify a PR comment.
- 70: Plausible but needs more evidence. Do not report by default.
- 50: Weak signal or minor concern. Do not report.
- 25: Speculative. Do not report.
- 0: False positive.

Default reporting threshold is 80. If a user asks for an ultra/deep review, keep the threshold but spend more effort validating candidates; do not lower the bar silently.

## Severity

Use severity for user-facing ordering:

- Critical: Data loss, auth bypass, secret exposure, remote code execution, destructive production behavior, or guaranteed severe outage.
- High: Definite correctness, security, persistence, or compatibility failure in normal use.
- Medium: Real bug or rule violation with narrower trigger conditions or bounded impact.
- Low: Defense-in-depth issue or minor but clear project-rule violation. Report low severity only when confidence is very high and the issue is still actionable.

## Required Review Passes

### Project-Rule Compliance

Find applicable instruction files before evaluating rule compliance:

- Root and ancestor `AGENTS.md`, `CLAUDE.md`, or `AGENT.md`.
- Directory-local instruction files that are ancestors of changed files.
- Repo docs that are explicitly referenced by those instructions.

Only enforce a rule when it clearly applies to the changed file or behavior. Quote or paraphrase the exact rule in the finding.

### Diff-Only Bug Scan

Review the patch itself before reading broad context. Look for:

- Syntax, import, export, type, or symbol mismatches.
- Incorrect conditionals, off-by-one logic, wrong branch/flag handling, missing awaits, broken promise/error handling.
- API contract violations, wrong serialization, lost state, stale cache behavior, concurrency races, resource leaks.
- UI state regressions, accessibility regressions, or event ordering bugs when the changed code is user-facing.

### Introduced-Code Context Scan

Read nearby code only where it validates or rejects a candidate issue. Prefer targeted reads over broad browsing.

Use git history and blame by default for substantial PR reviews:

- `git log --oneline -- <file>` for changed files when history may explain intent.
- `git blame -L <start>,<end> -- <file>` around changed lines or related unchanged code when ownership or invariants matter.
- `gh pr view`, `gh pr diff`, and PR comments when reviewing a GitHub PR.

Do not turn history analysis into a style critique. Use it to validate behavior, invariants, prior fixes, or project-specific constraints.

### Security and Regression Scan

Focus on newly introduced risk:

- Authorization, authentication, permission, sandbox, or trust-boundary changes.
- Path traversal, command injection, unsafe deserialization, XSS, SSRF, credential exposure, or insecure external navigation.
- Persistence, migration, data deletion, data corruption, or concurrency behavior.
- User-visible workflow regressions and compatibility breaks.

## Validation

For each candidate finding:

1. Identify the exact changed line or behavior that introduces it.
2. Check whether existing code, tests, framework behavior, or project rules already address it.
3. Look for a plausible benign interpretation; if one exists and cannot be ruled out, lower the confidence.
4. Prefer running targeted read-only commands or tests only when they materially increase confidence.
5. Discard duplicates and merge related symptoms into one finding.

## Output Shape

Use this structure:

```markdown
Findings

[P1/High] Title
File: path/to/file.ts:123
Confidence: 90
Why introduced: ...
Problem: ...
Recommendation: ...

Open Questions

- ...

Summary

No reportable findings.
Residual risk: ...
```

When the host environment has a preferred review format, adapt to that format while preserving findings-first ordering, severity, confidence, evidence, and fix recommendation.
