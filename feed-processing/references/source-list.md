# Source Lists

Accept:

- plain URL lists;
- CSV, TSV, and Markdown tables;
- OPML files;
- portable request objects;
- prior feed-content packs;
- source records collected by a host adapter.

Normalize each source to:

- `sourceId`: stable caller ID or deterministic fallback;
- `inputUrl`: the original source identity;
- `urlKind`: `feed`, `page`, or `unknown`;
- optional `feedUrl` and `siteUrl`;
- optional metadata such as title, author, folders, tags, status, notes, and row
  references;
- optional `etag` and `lastModified`;
- optional supplied `payload`, `contentType`, and `finalUrl`.

Prefer explicit feed columns in this order: `xmlUrl`, `feedUrl`, `rssUrl`,
`atomUrl`, then `feed`. Treat `siteUrl`, `htmlUrl`, and `homepage` as
explicit page URLs. Treat a generic `url` as `unknown` unless its path
strongly suggests a feed.

URL shape is only a hint. A path ending in `/rss` may return HTML and must still
enter the normal classification and discovery workflow.

Deduplicate exact input URLs during normalization. After fetching and discovery,
deduplicate sources that resolve to the same canonical feed while preserving
both source records and provenance.
