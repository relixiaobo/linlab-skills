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
- Treat imagery as part of the argument, not late decoration. For visual
  subjects, plan a mix of real media, screenshots, maps, document excerpts,
  charts, and diagrams before assigning layouts. Conceptual generated visuals
  are acceptable when real evidence is unavailable, but they must be labelled
  illustrative and never imply a real person, place, product, or event.
- Text-only slides should have a deliberate job: thesis, transition, decision,
  or reset. Do not let every slide collapse into text, cards, and diagrams when
  the audience needs to inspect the subject itself.
- Avoid ornamental gradients, floating decoration, nested cards, and generic
  illustration that could be reused for an unrelated subject.

## HTML Source Contract

Use local HTML, CSS, SVG, and media assets. Add a project-local library only
when the content requires it. Bundle dependencies and assets locally, expose a deterministic
ready promise for asynchronous visuals, and preserve fixed 1920x1080 geometry
unless another aspect ratio is required.

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
