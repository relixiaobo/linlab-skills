# Presentation Studio

Use Studio for a new deck, a complete rewrite, a full restructure, or a redesign
that may rebuild the file while preserving declared content. Studio has one
production source: `deck.html`.

## Source Role

Decide what the source controls before designing:

- **Evidence source**: facts, claims, citations, caveats, quotes, and assets must
  survive; narrative, page count, order, and composition may change.
- **Constrained source**: a preservation matrix additionally fixes items such as
  wording, values, slide assignment, count, order, notes, links, charts, theme,
  or aspect ratio.
- **Reference source**: the source informs tone or subject but is not factual
  authority.

A source PPTX used in Studio is never incrementally transformed. Extract its
content and assets, record its authority, then rebuild in canonical HTML. Use
Surgeon instead when the original package itself must remain unchanged outside
listed edits.

## Workflow

1. **Frame the decision.** Record audience, use setting, objective, reading
   density, requested outputs, notes, and actual downstream editability needs.
2. **Establish truth.** Build the evidence ledger and asset register. For a
   constrained redesign, inspect the source PPTX and complete the preservation
   matrix before authoring.
3. **Shape the argument.** Select and adapt one narrative archetype, then create
   the outline, section logic, and slide jobs. For large research decks, review
   the outline with the user when requested before investing in full production.
4. **Set one direction.** Choose and adapt one theme internally from the
   content, audience, evidence profile, venue, and export constraints. Do not
   ask the user to choose among three fully rendered directions by default.
5. **Set the layout strategy and prototype risk.** Choose a small core set from
   the registered layout library based on the real content shapes. Render
   real-content frames that cover the opening, normal rhythm, hardest
   dense/data/diagram/media case, and close. A short or single-slide deck may
   combine roles in one prototype.
6. **Build the deck.** Implement the accepted system in `deck.html`. Keep
   stable slide ids, explicit layouts, hidden speaker notes, local assets, and
   deterministic geometry.
7. **Compile and prove.** Inspect HTML, validate evidence bindings, render HTML,
   compile requested exports, report PPTX object coverage, render the PPTX, and
   compare it with HTML before delivery.

## Beauty Standard

Beauty is not a theme name. The visual idea should arise from the content and
help the audience understand or remember it.

- Give every slide one dominant claim and one clear visual job.
- Use a recurring explanatory device, not a repeated card template.
- Let opening, explanation, proof, reset, and close create rhythm.
- Prototype the slides with long labels, dense evidence, maps, tables, charts,
  screenshots, or diagrams. Sparse covers do not certify the system.
- Keep the hardest analytical slide at the same craft level as the opening.
- Use real product, place, person, document, interface, and brand evidence when
  identity matters.
- Avoid ornamental gradients, floating decoration, nested cards, and generic
  illustration that could be reused for an unrelated subject.

## HTML Source Contract

HTML may use plain CSS, Tailwind CSS, CSS Grid/Flex, ECharts, Mermaid, D3, or
other local libraries. These are element authoring choices, not production
routes. Bundle dependencies and assets locally, expose a deterministic ready
promise for asynchronous charts, and preserve fixed 1920x1080 geometry unless
another aspect ratio is required.

The project config records `themeId`, `archetypeId`, the copied narrative
record, and the copied layout catalog. These choices guide authoring but do not
replace `deck.html` as the production source of truth.

Each slide must be a top-level element matching the configured selector:

```html
<section class="slide" id="slide-market-map" data-slide="market-map" data-layout="map-callout">
  <div class="slide-content" data-claim-id="claim-market-size">
    <!-- audience-facing composition -->
  </div>
  <aside class="speaker-notes" hidden>Talk track and transition.</aside>
</section>
```

Use stable ids rather than positional selectors for evidence, preservation, and
review references.

## Constrained Redesign

The preservation matrix is authoritative. Classify each rule as:

- `exact`: byte/text/value/order identity is required;
- `semantic`: the meaning and all material details must survive, but
  representation may change;
- `allowed-change`: the named field may be redesigned.

Create a one-to-one source/output slide binding when slide assignment is fixed.
Compare source and rebuilt content, objects, notes, links, and every declared
invariant. Better appearance cannot override a failed preservation rule.
