# Fetch Windows

Use explicit scope semantics.

- `all`: include every item present in the current feed payload. Warn that this
  is not necessarily the publisher's complete archive.
- `last_n_days`: include items whose best parsed timestamp is within the
  requested day window. Put missing or invalid dates into `date_ambiguous`.
- `since_cursor`: include stable-ID new or changed items relative to a prior
  cursor or pack.
- `newest_n`: include the newest N items per source or across the batch,
  depending on the user's request.
- `date_range`: include items between explicit start and end timestamps.

Prefer `publishedAt`, then `updatedAt`, then source order only as a weak fallback
with warning. Never hide ambiguous-date items; count and report them separately.
