# Layout Selection

Layouts solve the shape of one slide. Themes control visual grammar;
archetypes control sequence; layouts control composition. Treat
`assets/layouts/index.json` as the catalog authority. Inspect it with:

```bash
node scripts/studio_tool.mjs layouts
```

Every slide must declare `data-layout`.

- Match the layout to the content's real structure. Do not invent numbers,
  options, chronology, or relationships to fit a composition.
- Respect catalog limits. Split or redesign overloaded grids, timelines,
  tables, and screenshot walls instead of shrinking them.
- Give each slide one dominant visual job.
- Use `custom-composition` only when registered layouts cannot express the
  content faithfully, and record why.
- Reuse alignment, typography, and explanatory devices across layouts.

Choose four to eight core layout ids for most decks. Add another only when the
content introduces a genuinely new shape.
