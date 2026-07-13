# Source Lists

Accept these source inputs:

- plain URL lists;
- CSV, TSV, Markdown tables, or spreadsheet-export rows;
- OPML files;
- prior feed-content packs;
- host source records from read-only adapters.

Prefer explicit feed columns in this order: `xmlUrl`, `feedUrl`, `rssUrl`,
`atomUrl`, then site columns `url`, `siteUrl`, `htmlUrl`, and `homepage`.

Preserve metadata when present: title, author, folder, category, tags, status,
notes, priority, source group, and row reference. Treat `disabled`, `paused`,
`archived`, or `stale` as metadata until the user or rule file says to exclude
them.

Dedupe by canonical feed URL first, then site URL. Keep duplicate row references
as warnings; do not silently discard their provenance.
