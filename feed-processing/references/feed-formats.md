# Feed Formats

Support RSS 2.0, Atom, JSON Feed, OPML-derived source lists, and RDF when the
parser can recover items.

Classify payloads using both response headers and bounded body sniffing. Prefer a
recognized feed root over a misconfigured content type. Treat HTML as a discovery
surface and reject arbitrary JSON that does not satisfy the JSON Feed shape.

## RSS

Preserve `channel` metadata, `item`, `guid`, `isPermaLink`, `link`, `pubDate`,
`category`, `enclosure`, `description`, and `content:encoded` when available.

## Atom

Preserve `feed`, `entry`, `id`, `updated`, `published`, `link`, `summary`,
`content`, and author names.

## JSON Feed

Preserve `id`, `url`, `external_url`, `content_html`, `content_text`,
`summary`, `date_published`, `date_modified`, authors, tags, and attachments.

## Parser Warnings

Emit warnings for missing title, missing link, duplicate item identity, invalid
dates, missing dates, likely summary-only content, unsupported content types,
and malformed XML that was partially recovered.
