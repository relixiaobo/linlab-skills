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
| `feature-grid` | 3-6 capabilities, pillars, benefits, modules | compact grid with consistent icon/label/spec rhythm |
| `gallery` | examples, screenshots, evidence wall | image grid with consistent ratios and captions |
| `quote` | memorable voice or turning point | large quote, source, minimal support text |
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

### diagram

- text labels stay in HTML/text boxes, not inside SVG paths when avoidable
- geometry should explain relationships, not decorate
- use one connector style

### feature-grid

- each cell needs the same content structure
- keep labels short and action-oriented
- use icons, numbers, or spec labels only when they clarify the feature set
- avoid equal-weight paragraphs in every cell

### gallery

- use consistent image ratios
- captions explain why each example matters
- screenshots use contain-fit when text readability matters
- for named brands/products, each visible logo or UI should come from the asset
  inventory or be explicitly marked as placeholder

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
