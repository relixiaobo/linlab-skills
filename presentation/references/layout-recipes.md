# Layout Recipes

Use registered recipes to keep decks coherent. Each slide plan should name one
recipe in `layout`.

## Recipe Set

| Recipe | Use When | Required Visual Move |
| --- | --- | --- |
| `cover` | opening, title, launch title | large claim, motif, subtitle, context label |
| `hero-media` | cinematic context, customer proof, place/person/product reveal | dominant media with readable text safe area |
| `product-stage` | product launch, feature reveal, screenshot, demo framing | one large product/media object on a clean stage |
| `section` | reset between acts | oversized act title or one statement |
| `split` | explain one idea with proof | one side text, one side image, diagram, or evidence frame |
| `metric` | prove with numbers | 1-3 large numbers with labels and source note |
| `compare` | before/after, options, tradeoffs | two or three aligned columns with shared scale |
| `timeline` | sequence, roadmap, process | horizontal or vertical steps with dates or stages |
| `diagram` | system, workflow, relationship | nodes, arrows, or spatial model with labels outside geometry |
| `chart` | quantitative evidence | one chart, one headline, clear annotation |
| `map-callout` | geography, basin, route, field, market, territory | map as primary visual with callouts tied to the claim |
| `feature-grid` | 3-6 capabilities, pillars, benefits, modules | compact grid with consistent icon/label/spec rhythm |
| `gallery` | examples, screenshots, evidence wall | image grid with consistent ratios and captions |
| `statement` | sparse idea that needs emphasis | centered or staged claim with optional proof label |
| `quote` | memorable voice or turning point | large quote, source, minimal support text |
| `table-takeaway` | table is necessary evidence | table plus one highlighted takeaway, not a raw dump |
| `close` | final takeaway or action | one final claim plus 1-3 next actions |
| `scripted-demo` | live product walkthrough, code demo, feature tour | current state, next action, and short presenter cue in notes |
| `evidence-wall` | many examples, logos, screenshots, or source snippets | consistent crop grid with a single takeaway and source labels |

## Deck Rhythm

- 6-8 slides: use at least 4 different recipes
- 9-14 slides: use at least 5 different recipes
- 15+ slides: use at least 6 different recipes and section resets
- no more than 2 consecutive slides should use the same recipe
- no more than 3 slides in a row should be mostly text
- every 3-5 slides should change energy with a section, quote, hero-media, or
  metric reset
- live talks should alternate explanation pages with proof, demo, quote, or
  visual reset pages so the presenter has rhythm

## Recipe Notes

### cover

- no bullet list
- use a large claim, subtitle, date/context, and one motif
- make the first viewport feel designed even without images

### hero-media

- let the media carry the slide; support copy stays short
- keep text in a safe area with strong contrast
- crop intentionally and avoid dark blurred atmospheric filler

### product-stage

- one object is the hero: product screenshot, device mock, UI panel, artifact, or diagram
- do not surround the object with many small cards
- pair it with a single claim and 2-4 spec labels or proof points

### split

- choose a 45/55 or 55/45 balance
- give the visual side a real role: screenshot, diagram, image, or evidence
- do not put a card inside another card
- keep text and visual rectangles non-overlapping
- if the visual is right-side evidence, constrain the text column before the
  visual slot starts

### metric

- make the number the first thing the audience sees
- include unit and source/note
- use one accent metric only when several metrics appear

### compare

- align columns to the same baseline
- use the same row structure on both sides
- avoid pros/cons walls; make the contrast visible

### timeline

- keep labels short
- show sequence with spacing, not paragraphs
- split into multiple slides when steps become dense
- for more than 5 process-like horizontal steps, wrap, paginate, or switch to
  vertical rhythm
- for more than 7 date/milestone labels in a horizontal timeline, group by era,
  wrap, paginate, or use a vertical/stacked timeline
- do not shrink milestone detail below 8 pt to keep a timeline on one row

### diagram

- text labels stay in HTML/text boxes, not inside SVG paths when avoidable
- geometry should explain relationships, not decorate
- use one connector style
- value-chain and process diagrams have a maximum of 5 nodes per horizontal row
- connectors must adapt to wrapped rows; they must not extend off-canvas

### feature-grid

- each cell needs the same content structure
- keep labels short and action-oriented
- use icons, numbers, or spec labels only when they clarify the feature set
- avoid equal-weight paragraphs in every cell
- use at most 4 columns in a single row
- wrap 5-6 items into two rows; split, group, or change recipe beyond 6 items
- keep card dimensions fixed so text and hover/edit states cannot shift layout

### map-callout

- use a real map or source geography when the slide claim is geographic
- reserve the map as the primary visual and attach 2-5 callouts
- use contain-fit when labels or boundaries matter
- avoid generic decorative maps for specific countries, basins, fields, or routes

### gallery

- use consistent image ratios
- captions explain why each example matters
- screenshots use contain-fit when text readability matters
- for named brands/products, each visible logo or UI should come from the asset
  inventory or be explicitly marked as placeholder

### statement

- use for sparse slides that would otherwise leave a small text block in a
  corner
- center, stage, or intentionally offset the claim
- pair with one proof label, icon, or small visual only when it clarifies the
  message

### quote

- quote text is the visual object
- keep source legible but secondary
- use sparingly for rhythm, not as filler

### chart

- one chart is the visual object
- title the chart with the takeaway, not the measure name
- label axes and highlight the key comparison
- include source, date, and denominator when relevant
- use editable/native chart objects in PPTX when humans need to modify data
  manually in PowerPoint; use rendered charts when source-first agent revisions
  or visual fidelity matter more

### table-takeaway

- use when a table is necessary evidence, not because the source has a table
- place a concise takeaway above or beside the table
- keep headers readable and rows within the body area
- split tables that require tiny type or horizontal scrolling
- split or summarize tables with 9+ rows and 6+ columns, 12+ rows, or 8+
  columns
- do not create a title-only slide immediately before the table slide

### scripted-demo

- keep visible slide content audience-facing only
- use a product-stage or split composition with one current state
- put presenter prompts, next-click reminders, and timing cues in notes
- avoid tiny UI details; zoom or crop to the interaction that matters

### evidence-wall

- use when many examples prove a pattern better than one large example
- keep tiles aligned to a fixed ratio and label sources consistently
- add one headline that interprets the wall; do not make the audience infer it
- split into multiple walls when captions or screenshots become unreadable
