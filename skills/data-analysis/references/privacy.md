# Privacy

Use privacy-by-default for all data outputs.

## Before Data Reaches The Model

The most consequential privacy decision is what enters the model's context in the
first place. Pasting raw, PII-laden rows into chat *is itself a disclosure* — and
the output rules below cannot un-disclose it. Minimize at the input boundary:

- **Compute on the data, don't ingest it.** The bundled scripts (`profile_dataset.py`,
  `query_duckdb.py`, `triangulate.py`) run locally and return summaries, not rows.
  They send nothing anywhere. Prefer querying and aggregating over dumping raw
  rows into context.
- **Send the smallest sample needed**, with PII columns dropped or masked *before*
  the sample is shown — not after. A 5-row preview should already be redacted.
- **Never paste secrets, tokens, or credentialed URLs into context at all** — not
  even masked. Treat connection strings and keys as never-ingest.
- **Free-text fields are the high-risk case.** Before feeding a free-text corpus
  into reasoning, strip obvious PII columns and redact in-line identifiers by hand;
  an automated text PII gate (e.g. Presidio redaction) is the intended control and
  is not yet bundled, so until then this redaction is manual and load-bearing.

## Sensitive Data

Treat as sensitive:

- Email, phone, address, government ID, account IDs.
- Names when tied to behavior, health, finance, employment, or location.
- Free-text fields that may contain personal data.
- Small groups that can identify people.
- Secrets, tokens, passwords, URLs with credentials.

## Output Rules

- Do not print raw secrets.
- Do not show raw PII unless explicitly necessary and approved.
- Mask or hash identifiers in user-facing tables.
- Suppress small cells by default, e.g. `n < 5`.
- Use aggregate results for sensitive domains.
- Keep raw extracts in protected run artifacts, not chat.

## Analysis Rules

- Prefer minimal columns.
- Drop or mask PII before sending examples to the user.
- Document privacy filters and suppression rules in the report.
- For healthcare data, assume stricter rules and read `references/domains/healthcare.md`.

