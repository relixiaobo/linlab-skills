# Layout Library

Layouts solve the shape of one slide. Select them after the claim and evidence
are known. Themes control visual grammar; archetypes control sequence; layouts
control composition.

The executable catalog is `assets/layouts/index.json`. Run
`node scripts/studio_tool.mjs layouts` to inspect the metadata. Every slide must
declare `data-layout`; use `custom-composition` only when the registered library
cannot express the content faithfully.

## Content-To-Layout Map

| Content shape | Layout |
| --- | --- |
| Deck promise | `cover` |
| Dominant real image or document | `hero-media` |
| Real product or interface reveal | `product-stage` |
| Narrative reset | `section` |
| Claim/evidence or concept/example | `split` |
| One to four verified values | `metric` |
| Exactly two aligned alternatives | `compare` |
| Chronology or linear sequence | `timeline` |
| Mechanism, hierarchy, system, or loop | `diagram` |
| Quantitative proof | `chart` |
| Geography, route, basin, or region | `map-callout` |
| Three to six parallel ideas | `feature-grid` |
| Two to six related visual examples | `gallery` |
| One earned sentence or number | `statement` |
| One sourced voice | `quote` |
| Exact lookup plus conclusion | `table-takeaway` |
| Final judgment or action | `close` |
| Interface, code, or workflow walkthrough | `scripted-demo` |
| Multi-source proof or risk field | `evidence-wall` |
| Content shape outside the registered set | `custom-composition` |

## Hard Rules

- Match the layout to the content's real structure. Do not invent numbers to
  justify `metric` or `chart`, force three options into `compare`, or use a
  linear timeline for a feedback loop.
- Respect catalog limits. Split or redesign an eight-card grid, a twelve-node
  timeline, an unreadable table, or a screenshot wall instead of shrinking it.
- Use one dominant visual job per slide. A table, map, chart, and process should
  not compete on the same frame unless one is clearly subordinate.
- Let custom compositions earn their complexity through explanation or memory.
  Record why a registered layout was insufficient.
- Reuse alignment, typography, and recurring explanatory devices across
  different layouts. Variety should create rhythm, not visual discontinuity.

## Deck-Level Strategy

Choose a small core set, usually four to eight layout ids, that fits the
archetype and hardest evidence. Add a layout only when the content introduces a
new shape. A long deck may use many instances of the same layout id while still
varying composition through hierarchy, scale, media, and theme-specific moves.
