# Feed-Content Pack Schema

The pack is the feed-processing skill's native output. It is sink-neutral and
can be consumed by an outliner, document workflow, email workflow, export, or
future runtime monitor.

Required top-level fields:

- `generatedAt`: ISO timestamp.
- `scope`: fetch/window scope.
- `sources`: normalized feed sources.
- `selectedItems`: selected normalized items.
- `skipped`: skipped reason groups with counts and small visible samples.
- `errors`: per-source or per-item errors.
- `coverage`: source and item accounting.

Each selected item should include `sourceId`, `feedUrl`, `title`, and at least
one identity field: `itemId`, `rawId`, or `url`. Full-text results must include
`status`, `selectedStrategy`, `quality`, and an `attempts` ledger.

Coverage must reconcile with the arrays in the pack. A downstream consumer must
be able to decide whether a write is safe without re-fetching the feeds.
