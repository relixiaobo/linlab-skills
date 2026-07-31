# Review Workflow

Use this for comments, tracked changes, redlines, precise edits to existing
DOCX files, and reader testing.

## Review Mode Selection

- `comments`: ask questions, flag risks, or leave reviewer notes without changing
  wording.
- `tracked-changes`: propose concrete wording changes while preserving review
  history.
- `redline`: compare an original and revised document and generate a native
  change-marked file.
- `clean-copy`: accept or reject changes only when the user explicitly requests
  it.
- `reader-test`: test whether the document works for a reader without access to
  the conversation.

Do not silently accept/reject tracked changes, delete comments, or overwrite a
review copy without preserving the original.

## Precise DOCX Editing

For nontrivial edits to existing DOCX:

1. Inspect the package with `docx_tool.py`.
2. List or extract paragraph/table context before editing.
3. Prefer stable anchors: paragraph references, nearby headings, table index,
   row/column coordinates, or unique text plus surrounding context.
4. Apply targeted edits.
5. Save to a new file unless the user explicitly asks to overwrite.
6. Re-inspect and report comments/revisions left open.

When available, prefer a DOCX editing library that supports hash-anchored
paragraph references, comments, tracked changes, and batch edits. This is safer
than blind global find/replace in WordprocessingML.

## Comments

Good comments are concrete and actionable:

- anchor to specific text
- explain the issue or question
- suggest what evidence, decision, or wording would resolve it
- avoid generic praise or style commentary unless requested

Summarize unresolved comments by severity or topic in the delivery report.

## Tracked Changes

- Use the user's requested reviewer/author name. If absent, use the system user
  or `Reviewer`; do not use an AI model name.
- Keep tracked edits focused and minimal.
- Avoid rewriting whole paragraphs when a targeted wording change is enough.
- For paragraph rewrites, preserve the original meaning and make the diff easy
  for a human reviewer to scan.

## Redline Generation

Use redline comparison when the user provides original and modified copies, or
asks for "show changes between these docs". Prefer a library/tool that creates
native Word revisions rather than a plain textual diff.

Check:

- original and revised inputs are clearly identified
- author name is set appropriately
- output opens without repair warnings
- tables, moved content, and formatting changes are either represented or listed
  as limitations

## Reader Testing

For substantial docs, run a reader test before final delivery:

1. Predict 5-10 questions a realistic reader would ask.
2. Answer each question using only the document text.
3. Mark questions as answered, partially answered, or missing.
4. Fix missing definitions, unsupported claims, contradictions, and unclear
   decisions in the source document.

Reader testing is especially useful for decision memos, specs, proposals,
policies, board briefs, and onboarding/playbook documents.
