# GitHub Commenting

Load this reference only when the user explicitly asks to post review comments to GitHub.

## Commenting Policy

Default to terminal-only output. Do not post PR comments, submit reviews, or create inline comments unless the user explicitly requested that action in the current task.

Before posting, verify:

- Target PR owner, repo, and number.
- Current review findings are final and deduplicated.
- The comment tool or `gh` command is available and authenticated.
- The target line exists in the PR diff when posting inline.

## No-Issue Summary Comment

If the user requested a GitHub comment and there are no reportable issues, post:

```markdown
## Code review

No issues found. Checked for bugs, project-rule compliance, git history context, and high-confidence regressions.
```

## Inline Comments

Post one inline comment per unique issue. Do not post multiple comments for symptoms of the same root cause.

Each inline comment should include:

- A concise issue description.
- The concrete failure mode or scoped project-rule violation.
- The fix recommendation.
- A confidence score.
- Any required citation to project instructions or related code.

Use committable suggestion blocks only when all are true:

- The fix is small and self-contained.
- Applying the suggestion fully resolves the issue.
- No follow-up edits, migrations, generated files, formatting passes, or tests are required for the suggestion itself to make sense.

Do not use a suggestion block for structural fixes, multi-file changes, generated code, or fixes that need surrounding context the suggestion does not include.

## Code Links

When linking to code in GitHub comments, use a full commit SHA and line range:

```text
https://github.com/owner/repo/blob/<full-sha>/path/to/file.ts#L10-L15
```

Rules:

- Use a full SHA, not a branch name and not an abbreviated SHA.
- Match the owner/repo being reviewed.
- Use `#L[start]-L[end]`.
- Include at least one line of context before and after the exact issue when practical.

## Tool Choices

Prefer a dedicated GitHub inline comment tool when available. If using `gh`, use read commands first and avoid mutation until the final posting step.

Typical read-only commands:

```bash
gh pr view <number> --json title,body,state,isDraft,comments,headRefOid,files
gh pr diff <number>
gh pr view <number> --comments
```

Typical summary comment:

```bash
gh pr comment <number> --body-file <file>
```

If the environment offers an inline review MCP tool, pass a final, already-validated comment with confirmation enabled only after the user requested posting.
