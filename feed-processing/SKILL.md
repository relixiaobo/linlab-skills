---
name: feed-processing
description: >-
  Process RSS, Atom, JSON Feed, OPML, feed URLs, page URLs, source tables, supplied feed payloads, and prior feed-content packs through a host-neutral contract. Use when an agent must discover feeds, fetch or audit subscriptions, recover redirects and HTML landing pages, normalize mixed batches, apply time scopes, filter content, inspect feed health, extract selected article text with provenance, or produce a validated sink-neutral feed-content pack. Use the bundled reference CLI when process execution is available or a conforming adapter otherwise. Do not use for generic scraping, bypassing authentication or paywalls, scheduling refreshes, host-specific mutations, or building a feed reader UI.
---

# Feed Processing

Produce validated, sink-neutral feed data. Keep source collection, scheduling,
persistent storage, notifications, and writes to host applications outside this
skill.

## Portability Boundary

- Treat `references/portable-contract.md` and its JSON schemas as the normative
  interface.
- Use JSON stdin/stdout as the portable reference interface. Treat file paths as
  optional conveniences.
- Use the bundled Node.js reference CLI when the runtime can execute it.
- Use another implementation only when it preserves the same source states,
  recovery order, errors, coverage, and validation semantics.
- Report `capability_unavailable` instead of claiming live coverage when the
  runtime cannot execute a processor or access required content.
- Never depend on a particular agent tool name, browser session, scheduler,
  host object model, or output application.

## Resolve The Request

Determine:

1. Sources: URLs, source records, source tables, OPML, prior packs, or supplied
   payloads.
2. Scope: `all`, `last_n_days`, `since_cursor`, `newest_n`, or `date_range`.
3. Strictness: use `best_effort` unless the user explicitly requests
   all-or-nothing behavior.
4. Full text: keep off for source audits and imports; use only for selected
   items when article bodies are needed.
5. Capabilities: reference CLI, conforming adapter, or restricted local-payload
   processing.

## Default Workflow

1. Resolve the directory containing this `SKILL.md` as `<skill-root>`.
2. Build a request conforming to `references/feed-request.schema.json`.
3. Run the end-to-end processor:

   ```sh
   node <skill-root>/scripts/feed_process.mjs process --input -
   ```

4. Require `validation.ok: true`. In best-effort mode, preserve failed sources
   and continue; in strict mode, stop on source failure.
5. Apply `feed_rules.mjs` only when explicit filtering or routing rules are
   needed.
6. Run `full_text_extract.mjs` only for selected items and only with capabilities
   actually supplied by the runtime.
7. Build a downstream artifact with `feed_pack.mjs` and validate it with
   `validate_feed_pack.mjs` before any host writes.

For one-off URLs, use:

```sh
node <skill-root>/scripts/feed_process.mjs process --url https://example.com/feed.xml
```

Inspect the reference interface with:

```sh
node <skill-root>/scripts/feed_process.mjs capabilities
```

## Processing Rules

- Preserve caller-provided `sourceId` across redirects, discovery, and canonical
  URL changes.
- Follow bounded HTTP(S) redirects and record the redirect chain.
- Parse feed payloads directly. For HTML responses, discover candidates using
  the final response URL, then fetch and parse candidates before accepting them.
- Return `empty` for a valid feed with no items.
- Return `failed` only after bounded recovery is exhausted.
- Keep every source in exactly one terminal state: `parsed`, `empty`,
  `not_modified`, `failed`, or `skipped`.
- Deduplicate sources that resolve to the same canonical feed while retaining
  source coverage and provenance.
- Do not use a generic page-fetch failure as evidence that a feed is dead when
  the reference processor or a conforming adapter is available.
- Do not automatically invoke third-party bridge services.

## Host Integration

Allow a host adapter to:

- collect source records;
- provide process execution, HTTP, cache, or browser-rendering capabilities;
- persist cursors or conditional-request metadata;
- consume the validated result;
- write to a document, database, mailbox, outliner, or application.

Do not place host-specific collection or mutation instructions inside this
skill. Keep those behaviors in separate integration workflows.

## Supporting References

- Portable protocol and capability profiles: `references/portable-contract.md`
- Request schema: `references/feed-request.schema.json`
- Result schema: `references/feed-result.schema.json`
- Source normalization: `references/source-list.md`
- Feed formats: `references/feed-formats.md`
- Scope semantics: `references/fetch-windows.md`
- Pack schema: `references/feed-pack-schema.md`
- Recovery and errors: `references/bad-feed-handling.md`
- Full-text strategy: `references/full-text-extraction.md`
- Filtering and routing: `references/rules.md`
- Safety and publisher constraints: `references/safety-and-copyright.md`

## Diagnostic Helpers

Use `feed_fetch.mjs`, `feed_discover.mjs`, and `feed_parse.mjs` separately only
for debugging, adapter development, or local fixtures. Do not manually recreate
the recovery state machine for normal live processing.

## Completion Contract

Report:

- scope and capability profile;
- requested, parsed, empty, unchanged, failed, skipped, and recovered source
  counts;
- selected and skipped item counts;
- notable failures with `nextAction`;
- validation status;
- the inline result or an artifact reference supplied by the host.
