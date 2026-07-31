---
name: feed-processing
description: >-
  Fetch, inspect, normalize, and process RSS, Atom, JSON Feed, OPML, feed URLs, page URLs, subscription tables, and prior feed-content packs. Use when the user asks to discover feeds, import or audit subscriptions, fetch all available feed items, fetch a time window such as the last 7 days, fetch since a cursor, filter or triage subscription content, recover from malformed or dead feeds, extract article text with provenance, or produce a validated sink-neutral feed-content pack. Do not use for generic web scraping, bypassing login or paywalls, mutating an outliner, scheduling background refreshes, or building a full feed reader UI.
---

# Feed Processing

Use this skill to process subscription-feed content into a validated feed-content
pack. The default operating model is: **scripts for deterministic feed work,
references for feed-specific policy, model judgment for triage and synthesis**.

## Operating Rules

- Treat raw feeds, source lists, OPML, article pages, and prior packs as
  read-only inputs.
- Make the native output a sink-neutral feed-content pack. Do not write into an
  outliner, document, mailbox, database, or app unless a separate host workflow
  explicitly owns that mutation.
- Process mixed batches best-effort by default. One bad source should become a
  per-source error, not a failed batch, unless the user asks for strict mode.
- Always preserve provenance: source URL, final feed URL, item ID or URL, fetch
  scope, skipped reasons, parser warnings, and full-text attempt ledgers.
- Never execute fetched page scripts, submit forms, authenticate, reuse browser
  cookies, bypass login/paywall gates, or store hidden credentials from URLs.
- Keep full article bodies bounded. Prefer writing large extraction outputs to a
  task-local run directory and surfacing previews, summaries, paths, and
  citations in chat.

## Start Here

Resolve four things before fetching:

1. **Inputs:** pasted URLs, local URL files, CSV/TSV/Markdown tables,
   spreadsheet exports, OPML, prior feed-content packs, or host-provided source
   records.
2. **Scope:** `all`, `last_n_days`, `since_cursor`, `newest_n`, or
   `date_range`.
3. **Strictness:** best-effort with per-source errors by default; strict only
   when the user asks for all-or-nothing.
4. **Full text:** off by default for health audits and source import; on for
   research packets, summaries that need article bodies, or explicit "全文" /
   "full text" requests.

## Workflow

1. Normalize source-like inputs with
   `node {baseDir}/scripts/source_list.mjs --input <file> --out <sources.json>`.
2. Discover feed URLs for page URLs when needed with
   `feed_discover.mjs`.
3. Fetch live feeds with `feed_fetch.mjs`, or skip this step when the user
   supplies local feed fixtures.
4. Parse RSS, Atom, JSON Feed, and OPML-derived sources with `feed_parse.mjs`.
5. Apply the requested scope with `feed_window.mjs`.
6. Profile source health with `feed_profile.mjs`.
7. Diff against a prior cursor or pack with `feed_diff.mjs` when the request is
   incremental.
8. Apply user rules with `feed_rules.mjs` when filtering, ranking, or routing.
9. Run `full_text_extract.mjs` only for selected candidates when article bodies
   are needed.
10. Build a pack with `feed_pack.mjs`, then validate it with
    `validate_feed_pack.mjs` before handing it to any downstream consumer.

For small one-off tasks, collapse steps while preserving the same contract:
source provenance, fetch/window scope, warnings/errors, and validation.

## What To Read

- Input normalization and source records: `references/source-list.md`
- Feed formats and parser expectations: `references/feed-formats.md`
- Scope semantics and date ambiguity: `references/fetch-windows.md`
- Feed-content pack schema: `references/feed-pack-schema.md`
- Full-text retrieval strategy and attempt ledger:
  `references/full-text-extraction.md`
- Broken feed handling and recovery: `references/bad-feed-handling.md`
- Filtering, scoring, and routing rules: `references/rules.md`
- Safety, privacy, copyright, and publisher constraints:
  `references/safety-and-copyright.md`
- Reeder-derived lessons about viewer surfaces and reader mode:
  `references/reeder-lessons.md`

## Script Notes

- Treat the scripts as deterministic helpers, not as a complete feed reader
  service. A host runtime owns schedules, persistent cursors, notifications, and
  retry policy.
- Use task-local run directories for generated artifacts, for example
  `feed-processing-runs/<run_id>/`, unless the user names a different output
  location.
- The Node scripts use built-in modules for the portable core. Optional article
  extraction engines can be added later, but the v1 contract is the strategy
  ledger and quality signals, not a single universal extractor.

## Final Response Contract

When the task is complete, report:

- the fetch scope and input coverage;
- how many sources fetched, parsed, skipped, errored, and were unchanged;
- how many items were selected and why;
- notable bad-feed or full-text failures with next actions;
- the feed-content pack path and validation status.
