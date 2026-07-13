# Studio Runtime And Export

Studio uses `studio.config.json` and `scripts/studio_tool.mjs` as one thin
orchestration layer around HTML inspection, evidence checks, browser rendering,
PPTX compilation, notes patching, and PPTX inspection. Office-rendered visual
comparison is an optional export-fidelity adapter.

`compile` calls the pinned `dom-to-pptx` browser bundle directly and passes
`width` and `height`. Do not use the package's v2.0.3 CLI for custom dimensions;
that CLI forwards unsupported `slideWidth` and `slideHeight` option names.

## Browser Readiness

The compiler waits for fonts, images, network idle, and an optional promise:

```js
window.__PRESENTATION_READY__ = Promise.all([
  document.fonts.ready,
  renderCharts(),
]);
```

Use this for asynchronous charts, diagrams, media, or web components. Bundle
dependencies locally and remove remote runtime dependencies before delivery.

## CSS And DOM Safety

- Use fixed slide dimensions and stable Grid/Flex tracks.
- Use real DOM elements for legend swatches, markers, rules, and arrowheads.
  Pseudo-elements and CSS border triangles can compile as misplaced squares or
  disappear.
- Use SVG paths for connectors and arrows.
- Keep overflow hidden at the slide boundary, not on text containers that need
  to reveal wrapping defects.
- Avoid browser-only filters, blend modes, masks, and clipping unless their
  exported representation has been tested.
- CJK font metrics differ between browser and office renderers. Reserve width,
  avoid forced one-line headlines, and verify rendered PPTX line breaks.

## Element Strategy

Studio does not choose a deck-level backend. Each element compiles to the
strongest faithful representation available:

1. native PowerPoint text, shapes, links, notes, tables, or charts;
2. SVG vector containers for diagrams or charts;
3. raster regions where fidelity cannot be preserved otherwise;
4. full-slide raster only with explicit acceptance.

Prefer stable SVG for vector diagrams; canvas output is raster. SVG remains a
vector object, not automatically a semantic PowerPoint chart. HTML tables and
charts may compile as editable shape collections rather than native semantic
objects.

## Notes And Editability

Place notes in `<aside class="speaker-notes" hidden>`. The compiler extracts
their visible text and patches the generated OOXML notes slides with JSZip. The
PPTX editability report records native object, SVG, raster, full-slide raster,
hyperlink, and notes coverage. Report these facts instead of promising that an
entire PPTX is simply editable.

## Optional Office Comparison

`compare` renders HTML and PPTX, normalizes each pair to 480x270, computes pixel
delta metrics, and writes diff images. Use it for strict export fidelity or
risky slides involving charts, dense CJK text, media, or unusual CSS. It is a
triage signal, not an aesthetic judge; inspect contact sheets and risky slides
at full size.

If no Office renderer is available, complete the HTML review and PPTX technical
gate, then record that Office-rendered comparison was not run. Do not add a
browser PPTX renderer solely to turn this optional check into a mandatory one.
