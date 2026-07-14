# Feed-Content Pack Schema

Use a feed-content pack as the sink-neutral handoff artifact after portable
processing and optional selection/full-text steps.

Required top-level fields:

- `schemaVersion`
- `generatedAt`
- `scope`
- `sources`
- `selectedItems`
- `skipped`
- `errors`
- `warnings`
- `coverage`

Preserve every requested source when the input comes from the portable
processor. Each source must retain `sourceId`, `inputUrl`, terminal `status`,
`attempts`, warnings, and errors. Successful sources should retain
`resolvedFeedUrl`.

Each selected item must include `sourceId`, `feedUrl`, `title`, and at least
one identity field: `itemId`, `rawId`, or `url`. Full-text results must
include `status`, `selectedStrategy`, `quality`, and an attempts ledger.

Coverage must reconcile:

```text
requestedSources = parsedSources + emptySources + notModifiedSources
                 + failedSources + skippedSources
```

Require `selectedItems` to match the selected item array and require
`parsedItems` to be greater than or equal to `selectedItems`.

A downstream consumer must be able to decide whether a write is acceptable
without re-fetching sources. Always run `validate_feed_pack.mjs` before handoff.
