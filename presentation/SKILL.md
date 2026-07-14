---
name: presentation
description: Create, redesign, edit, analyze, or verify slide decks, PowerPoint/PPTX files, HTML decks, talks, speaker notes, presenter mode, PDF handouts, and deck covers. Use for new or rebuilt decks where beauty and communication impact are primary, and for precision PPTX edits where unintended changes are unacceptable. Do not use when the primary artifact is a long-form document, workbook, or PDF-native report.
---

# Presentation

Use one of two routes. Creation and rebuilding optimize for beauty through one
HTML-canonical Studio. Precision editing optimizes for accuracy by patching the
original PPTX package. They share verification standards, not a production
pipeline.

## Route 1: Studio

Use Studio for:

- a new deck;
- a rewritten story, compression, expansion, or full restructure;
- an existing PPTX used as factual or visual source material;
- a constrained redesign where declared wording, values, count, order, slide
  assignment, charts, notes, links, theme, or other invariants must survive;
- HTML talks, presenter mode, PPTX/PDF/image exports, and speaker notes.

`deck.html` is the production source of truth. A source PPTX used for rebuilding
is evidence and asset provenance, not a file being incrementally transformed.
When invariants matter, inspect first and make the preservation matrix
authoritative.

Read `references/studio.md` and `references/asset-intake.md` for every Studio
deck. Also read `references/evidence.md` for factual or research-heavy work,
`references/narrative-archetypes.md` before shaping the argument,
`references/theme-library.md` before setting the visual direction,
`references/layout-library.md` before assigning slide compositions, and
`references/export.md` before production.

### Studio Workflow

1. Establish audience, objective, use setting, density, outputs, notes, factual
   cutoff, and actual downstream editability needs.
2. Extract source claims, definitions, caveats, citations, quotes, and assets.
   Build `evidence-ledger.json` for source-heavy work. For constrained redesign,
   build the preservation matrix and one-to-one slide bindings when required.
3. Select and adapt one narrative archetype, then shape the argument and slide
   jobs. When the user explicitly requests outline review before production,
   stop at a decision-ready outline and discuss it.
4. Build the visual asset plan before choosing layouts. Classify the subject as
   visual, mixed, or analytical; for every planned media item record the exact
   subject, visual job, relevance to the claim, source or generation plan,
   `cover`/`contain` treatment, and crop policy. A visual or mixed deck must
   show the real subject where inspection matters instead of collapsing into
   text, cards, and diagrams.
5. Automatically select and adapt one theme from the content, audience, venue,
   evidence profile, and export constraints. Do not generate three full visual
   directions for user selection by default.
6. Choose a small core layout set from the real content shapes. Render
   real-content prototypes covering the opening, normal rhythm, hardest
   dense/data/diagram/media case, and close. Revise weak frames before expanding.
7. Build the complete canonical HTML deck with stable slide ids, explicit
   layouts, local dependencies, fixed geometry, and hidden speaker notes.
8. Inspect HTML and evidence, render the full deck, compile requested outputs,
   report PPTX object coverage, run technical gates, render PPTX, compare it
   with HTML, and complete at least one fix-and-recheck pass.

### Studio Technology

HTML may use plain CSS, Tailwind CSS, CSS Grid/Flex, ECharts, Mermaid, D3, or
other local libraries. These are authoring choices, not separate routes.

Use auditable `<img>` elements for content-bearing raster media. Give each one
a stable asset id, semantic role, declared `cover` or `contain` fit, and an
intentional focal point when cropped. Never use independent width/height scaling
or `background-size: 100% 100%` for subject imagery.

Compile each element to the strongest faithful representation available:

1. native PowerPoint text, shapes, links, notes, tables, and charts;
2. SVG vector objects;
3. raster fallback regions;
4. full-slide raster only with explicit acceptance.

Do not promise that arbitrary CSS becomes native PowerPoint geometry. When PPTX
editability matters, report actual native, SVG, raster, semantic table/chart,
link, notes, and full-slide raster coverage.

### Studio Tool

Start a project from the executable template, selected theme, and narrative
archetype:

```bash
node {baseDir}/scripts/studio_tool.mjs init work/deck \
  --theme analytical-ledger --archetype research-report
cd work/deck && npm install
node studio.mjs doctor .
```

Inspect the catalogs with `themes`, `archetypes`, and `layouts` before
initialization when the choice is not obvious.

Production commands:

```bash
node studio.mjs check .
node studio.mjs render-html .
node studio.mjs compile .
node studio.mjs compare .
```

`python3 {baseDir}/scripts/pptx_tool.py image-info <images...>` reports source
dimensions and a safe default treatment before insertion.

`compile` uses the pinned `dom-to-pptx` browser bundle with the correct
`width`/`height` options, waits for declared browser readiness, injects HTML
speaker notes into PPTX OOXML, runs the PPTX gate, and writes editability
evidence.

## Route 2: Surgeon

Use Surgeon for a localized change to a user-owned or source-unknown PPTX when
the original package is the artifact of record.

- Keep the input unchanged and patch a copy.
- Create an edit manifest with stable targets, `expectedBefore`,
  `intendedAfter`, exact match count, allowed package parts, and a
  preserve-everything-except-listed-operations policy.
- Patch the minimum OOXML/OPC parts. Do not route through HTML or a deck-wide
  load/save cycle.
- Assert the requested target and prove that no unexpected package, object,
  content, relationship, geometry, animation, notes, theme, or metadata change
  occurred.

Read only `references/precision-edit.md` and `references/verification.md` unless
media provenance requires `references/asset-intake.md`.

Portable commands:

```bash
python3 {baseDir}/scripts/pptx_tool.py inspect source.pptx --out before.json
python3 {baseDir}/scripts/pptx_tool.py gate source.pptx --out baseline-gate.json
python3 {baseDir}/scripts/pptx_tool.py compare before.json after.json --out diff.json
python3 {baseDir}/scripts/pptx_tool.py package-diff source.pptx edited.pptx \
  --allow 'ppt/slides/slide7.xml' --out package-diff.json
python3 {baseDir}/scripts/pptx_tool.py gate edited.pptx --baseline before.json --out final-gate.json
```

## Quality Gates

- Beauty never licenses invented facts, altered numbers, fake citations, fake
  screenshots, or fabricated brand/product evidence.
- Studio prototypes and the full deck require rendered visual review with veto
  power. A cover cannot certify a weak dense slide.
- Theme packages are priors. Adapt them into a content-specific visual idea;
  do not apply them unchanged as skins.
- Narrative archetypes are reasoning priors, not fixed page-count templates.
- Match registered layouts to real content shapes. Do not invent data or force
  content into a layout that does not fit.
- Treat imagery as part of the argument. A candidate image must match the
  slide's subject, action, and context; generic mood imagery is not a substitute.
- A visual or mixed subject may not ship with zero media-bearing slides unless
  the missing assets are reported as a blocker.
- Never stretch raster or identity-bearing media. HTML runtime checks, rendered
  review, and the PPTX gate must show no aspect distortion or accidental crop.
- Use real DOM elements for swatches, markers, and arrowheads. Avoid CSS
  pseudo-elements and border triangles in export-critical visuals.
- Reserve width for CJK text and verify line breaks in rendered PPTX.
- Controlled Studio work must prove every preservation rule.
- Surgeon work must prove target, package, content, and object scope.
- Any delivered PPTX must pass `pptx_tool.py gate`, or the unresolved blocker
  must be stated plainly.
- Pixel comparison detects export drift; it does not replace human aesthetic
  review.

Read `references/verification.md` for final evidence. A required failed gate
blocks delivery until repaired or explicitly reported as unresolved.

## Canonical Artifacts

Keep one authority for each concern:

- Studio brief (`assets/schemas/studio-brief.schema.json`): audience, objective,
  narrative direction, visual asset plan, selected theme adaptation, core
  layout strategy, prototype decision, outputs, and editability requirement.
- `deck.html`: narrative, visible content, notes, and visual system.
- Evidence ledger: sources, claims, definitions, cutoff, and assets.
- Preservation matrix: constrained-rebuild invariants.
- Edit manifest: Surgeon target and package scope.
- Verification report: final evidence and limitations.

Use schemas in `assets/schemas/`. An outline is a working artifact, not a second
production source.

## Reference Map

- `references/studio.md`: Studio source roles, workflow, beauty bar, and constrained rebuilds.
- `references/evidence.md`: evidence ledger, cutoff, claims, definitions, and bindings.
- `references/asset-intake.md`: visual asset planning, relevance, provenance, fit, crop, and quality.
- `references/narrative-archetypes.md`: argument sequences for research, launch, sales, learning, operating review, and talks.
- `references/theme-library.md`: automatic theme selection and executable packages.
- `references/layout-library.md`: content-to-layout mapping, limits, and custom-composition rules.
- `references/export.md`: runtime, browser readiness, CSS safety, compilation, notes, and comparison.
- `references/precision-edit.md`: minimum-change OOXML editing.
- `references/verification.md`: route-specific delivery gates.
