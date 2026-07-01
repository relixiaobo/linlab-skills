---
name: code-review
description: Review GitHub pull requests, branches, or local git diffs with high-signal, confidence-scored findings. Use when asked to run a code review, review a PR or diff, perform a PR gate, find bugs/regressions/security issues/project-rule violations, assess whether comments should be posted to GitHub, or create inline PR review comments.
---

# Code Review

## Overview

Perform a focused code review of the change under review, not the whole codebase. Default to terminal-only findings; post GitHub comments only when the user explicitly asks.

This skill adapts the Claude Code `code-review` plugin workflow for Codex: independent review passes, project-instruction compliance, bug/security checks, git history analysis, numeric confidence scoring, and aggressive false-positive filtering.

## Required References

Read `references/review-rubric.md` before reviewing any non-trivial PR, branch, or diff.

Read `references/github-commenting.md` only when the user asks to post PR comments or inline review comments.

## Review Target

Identify the target before reviewing:

- PR URL or `owner/repo/pull/N`: use GitHub CLI or available GitHub tools to fetch PR title, body, state, diff, comments, and changed files.
- PR number in the current repo: use `gh pr view <number>` and `gh pr diff <number>`.
- Current branch with a PR: use `gh pr view` and `gh pr diff`.
- Local diff without a PR: review `git diff` plus `git diff --cached` when staged changes exist. Compare against the fork point or upstream branch when the user asks for a branch review.

If the target is ambiguous and no safe inference is available, ask one concise clarification.

## Status Handling

Before doing expensive review work, check the target status. A direct user request
to review a specific PR, branch, or diff is an explicit request; do not stop just
because the PR is draft, small, automated, or already reviewed.

Hard stop by default only when:

- A GitHub PR target is closed and the user did not explicitly ask to inspect a closed PR.

Treat these as soft signals, not skip conditions, when the user requested review:

- PR is draft: continue the review, and mention draft status only in the summary or residual risk.
- PR is clearly trivial or automated: continue for a requested target; keep the review proportionate.
- A previous assistant review already exists: continue if the user asked for another pass or named this target in a new request.

Still review assistant-generated PRs unless the hard stop applies.

## Core Workflow

1. Create a short todo list for the review.
2. Collect only the context needed for the target: status, PR metadata, changed files, diff, relevant project instruction files, and relevant git history/blame for changed areas.
3. Summarize the author intent from PR title/body and changed files.
4. Run independent review passes where practical:
   - Project-rule compliance: check applicable `AGENTS.md`, `CLAUDE.md`, `AGENT.md`, or other repo instructions scoped to changed files.
   - Diff-only bug scan: inspect the changed lines for obvious compile, parse, logic, data, and API-contract failures.
   - Introduced-code/context scan: read nearby code and git history/blame where needed to validate behavior in context.
   - Security/regression scan: focus on new attack surface, permissions, data exposure, concurrency, persistence, and irreversible behavior.
5. Validate every candidate issue with a second look. Discard anything that depends on speculation, broad preference, or missing evidence.
6. Assign each remaining issue a numeric confidence score from 0 to 100.
7. Report only high-signal findings. Default threshold: report issues with confidence >= 80; include 70-79 only when the user asked for an exploratory review and clearly mark them as lower confidence.

## Output

Lead with findings ordered by severity, then open questions, then a brief summary. If there are no reportable findings, say so directly and mention any material residual risk, such as unavailable tests, missing PR metadata, or inaccessible GitHub context.

For each finding include:

- File and line reference when available.
- Severity.
- Confidence score.
- Why this is introduced by the change.
- Concrete failure mode or rule violation.
- Minimal fix recommendation.

Do not edit code during review unless the user explicitly asks for fixes.
