# GitHub Commenting

Apply the skill's evidence and reporting rules to comments. A no-findings comment
must reflect the actual reviewed scope and failed or unavailable checks.

Before posting, confirm the authorized destination and compare the current PR head
with the reviewed snapshot. If it moved, assess the intervening changes and reuse
unaffected evidence before commenting on the current head. Existing authorization
remains sufficient unless the destination or scope changes.

Post one comment per distinct issue. Use an inline comment only at a valid location
in the PR diff. Put related inherited issues outside the diff in a summary with a
commit-pinned link; do not attach them to an unrelated changed line. Distinguish
required fixes from nonblocking suggestions.

Link to the reviewed repository using its full commit SHA and the smallest useful
line range:

```text
https://github.com/owner/repo/blob/<full-sha>/path/to/file.ts#L10-L15
```

Use a committable suggestion only for a small, self-contained replacement that
fully resolves the issue. Describe structural or multi-file fixes in prose.

Use the available tool's actual schema. With `gh`, pass prepared multiline content
through `--body-file`. Do not invent confirmation parameters or add a redundant
approval step.
