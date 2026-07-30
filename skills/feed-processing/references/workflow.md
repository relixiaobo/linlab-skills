# RSS Workflow

Use the lightest workflow that preserves provenance and validation.

## On-Demand Feed Pack

1. Normalize inputs with `source_list.mjs`.
2. Discover feed URLs for page URLs with `feed_discover.mjs`.
3. Fetch feed payloads with `feed_fetch.mjs` when live network access is needed.
4. Parse feed payloads with `feed_parse.mjs`.
5. Apply the requested scope with `feed_window.mjs`.
6. Optionally apply rules and full-text extraction.
7. Build and validate a feed-content pack.

## Health Audit

Use `source_list.mjs`, `feed_discover.mjs`, `feed_fetch.mjs`, `feed_parse.mjs`,
and `feed_profile.mjs`. Report dead feeds, parse warnings, stale feeds, duplicate
identity risks, missing dates, and likely summary-only feeds.

## Research Packet

Run the on-demand pack workflow, then apply `feed_rules.mjs` and
`full_text_extract.mjs` only to selected candidates. Keep attempt ledgers so the
user can see whether text came from feed content, static extraction, or failed
routes.

## Host Collections

Host adapters such as Tenon `#subscribe` are read-only source collectors. Convert
host records to a source list, then use the same portable scripts. Do not let RSS
scripts create, edit, or delete host objects.
