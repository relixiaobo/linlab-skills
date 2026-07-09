# Presentation Workflow

## Decision Flow

1. Define the audience and outcome.
2. Decide live-talk vs reading/share vs agent-maintained source vs human-editable
   PowerPoint behavior.
3. Extract the core thesis, supporting proof, constraints, data, examples, citations, and must-include assets.
4. Build an asset inventory when real brands, products, screenshots, charts, people, or places appear.
5. Choose the artifact route: source-first HTML/project, PPTX export,
   template-fill PPTX, preserve-edit PPTX, regenerated PPTX, human-editable
   PPTX, PDF handout, speaker outline, presenter deck, or cover image.
6. Choose the visual system: design direction, theme tokens, motif, and layout recipe set.
7. Create a deck plan before building slides, including recipe, density, layout
   intent, and asset role/fit/slot/layer for each slide.
   For important images, include intrinsic width, height, aspect ratio, aspect
   class, crop permission, focal point, and minimum effective PPI.
8. For PPTX output, choose the build mode:
   - `single-pass` for new decks compiled from a complete plan
   - `source-first-edit` for edits to an agent-generated deck with source specs
   - `preserve-edit` for partial edits to a user-owned or source-unknown deck
   - `regenerate` for user-requested restructure or redesign of an existing deck
   - `template-edit` for native template shells
   - `repair` for already-broken files
9. Compile layout from the plan before writing PPTX objects. Use
   `references/layout-compiler.md` for geometry, layering, wrapping, and
   overflow rules.
10. Build from the compiled plan.
11. Verify visually and structurally. For PPTX output, run the delivery gate.
12. Fix concrete issues and recheck. Do not deliver a PPTX with a failed gate
    unless the unresolved blocker is explicitly accepted by the user.

## Deck Plan Schema

When emitting JSON, follow `assets/schemas/deck-plan.schema.json`.

Capture:

- `title`: deck title
- `audience`: intended audience
- `goal`: communication outcome
- `outputRoute`: PPTX, HTML deck, PDF handout, speaker outline, or cover image
- `buildMode`: single-pass, source-first-edit, preserve-edit, regenerate,
  template-edit, html-deck, pdf-handout, speaker-outline, cover-image, or repair
- `deliveryMode`: live-talk, reading-share, agent-maintained-source, handout, or another explicit mode
- `revisionSurface`: source-first, native-pptx, visual-only, or mixed
- `visualTemperament`: editorial narrative, grid analytical, or another deliberate direction
- `visualSystem`: design direction, style pack, theme, motif, and typography posture
- `layoutMode`: compiler, template-preserve, or manual-repair
- `storySpine`: short sequence of messages the deck must carry
- `globalElements`: page numbers, totals, table of contents, section counters,
  and closing slide policy
- `slides`: slide objects with stable `id`, final `slide`, `purpose`,
  `headline`, `evidence`, `layout`, `density`, `layoutIntent`,
  `visualSpec`, `layers`, and `notes`
- `sourceMaterials`: paths or URLs actually used
- `verificationPlan`: checks to run before delivery

## Creation Pattern

- Start with the story spine: opening promise, problem, insight, proof, implications, action.
- Convert content into slides by purpose, not by paragraph count.
- Keep one primary message per slide.
- Prefer fewer stronger slides over many weak slides.
- Use section dividers when the audience needs a mental reset.
- Assign a registered layout recipe to every slide before writing slide code.
- Use the chosen motif on most slides so the deck reads as one system.
- For modern keynote-style decks, start from a stage/product/media recipe and
  keep the page sparse; avoid report cards and decorative business templates.
- For reading decks, increase self-contained context with grids, captions, and
  annotations, but keep a visible hierarchy and split crowded pages.
- For live talks, write slide headlines as spoken claims and put elaboration in
  notes instead of visible paragraphs.
- For data slides, include source notes and avoid unsupported precision.
- For vague style requests, show three concrete direction previews or describe
  three concrete first-slide directions using the user's actual content; avoid
  asking the user to choose from abstract style words alone.

## Layout Compiler Pattern

- Use `references/layout-compiler.md` for generated PPTX geometry.
- The model chooses slide intent, recipe, density, asset role, and proof.
- Deterministic code chooses rectangles, wrapping, z-order, pagination, and
  safe-area conformance.
- Deterministic code reads or receives image dimensions and keeps picture boxes
  aspect-aware; it must not stretch assets to force a fit.
- Sparse slides must not default to upper-left body text. Convert them to a
  statement, metric, quote, section, split, or hero-media composition.
- Images are layout objects. Adding an image after a slide is already built
  requires relayout, not blind insertion.
- Classic recipes should vary the rhythm: split, metric, timeline, comparison,
  chart, map-callout, feature-grid, evidence-wall, quote, section, and close.

## PPTX Build Discipline

- Treat a new PPTX as a compiled artifact, not as the shared working state.
- Keep the complete deck plan or slide spec as the source of truth.
- Use a Python-first default toolchain for PPTX creation: deterministic layout
  code writes native PowerPoint objects with `python-pptx`, then
  `pptx_tool.py` gates the output.
- Allow section modules to produce slide specs, data, images, screenshots, or
  charts, but do not let them append directly to the same PPTX.
- Use one final writer to render slides in final order.
- Add closing slides only after all content sections are assembled.
- Render page numbers, total counts, tables of contents, section counters, and
  other global elements in the final pass.
- Rebuild from a clean output path when regenerating; do not rely on prior deck
  state.
- Do not hand-place long rows of cards, stages, or value-chain nodes. Use recipe
  limits and wrap, paginate, or change layout before rendering.
- Do not hand-place long single-row timelines. Group, wrap, or paginate before
  labels become tiny or run past the slide edge.
- Do not emit a title/subtitle-only slide immediately followed by the table or
  evidence it introduces; merge the content, make a deliberate section divider,
  or create a real statement slide.
- Do not force wide or long tables into one page. Split, summarize, or paginate
  when the table crosses the body area or drops below readable type.
- Do not append pictures after text generation. Resolve picture roles and slots
  before final writing so text, images, and containers cannot collide.

If forced to repair an already-mutated PPTX, explicitly label the work as
repair, then perform a full order and page-number verification pass after every
structural change.

## Existing Deck Image Insertion

- Run `pptx_tool.py inspect` before editing and keep the report for comparison.
- Run `pptx_tool.py image-info` on local image files before insertion when
  available.
- Inspect the target slide family before inserting media: cover, section,
  image-led, split, map-callout, chart, table, process, or closing.
- Assign every inserted image a role, fit, slot, and layer before writing it.
- Use contain-fit for detail-bearing images. Use cover-fit only for photography
  or planned backgrounds where crop is acceptable. Do not use stretch for real
  images unless distortion is explicitly accepted.
- If the target slide is a section divider, use the image only as a bottom
  background layer with text above a contrast overlay, or create a separate
  map-callout/image-led slide. Do not place a foreground image above section
  title text.
- If the image is evidence, map, chart, or screenshot, prefer a content recipe
  such as split, map-callout, chart, or evidence-wall instead of decorating a
  section divider.
- After editing, rerun `pptx_tool.py inspect`, run `pptx_tool.py compare` on
  the before/after reports, and run `pptx_tool.py gate` on the edited deck.
  Treat any new `text_picture_overlaps`, `section_picture_collisions`,
  `blank_shape_over_pictures`, `full_slide_picture_over_text`, or
  `picture_overflows` as a failed insertion that needs relayout.

## Revision Pattern

- Treat final PPTX/PDF/images as derived deliverables unless the user supplies
  an existing PPTX for partial editing. In that case, treat the uploaded PPTX
  package as the source of truth and preserve untouched parts.
- Distinguish the two editing surfaces:
  - agent-generated deck with source specs: edit the spec and regenerate
  - user-owned or source-unknown deck: preserve-edit only the requested scope
- Keep source files easy for a later agent to modify: stable `data-slide`
  numbers or slide identifiers, `data-layout` recipes, tokenized colors,
  local asset paths, and clear notes.
- Keep the deck plan and asset manifest near the produced artifact for future
  revision context.
- When revising source-first artifacts, edit the source artifact first,
  regenerate derived exports, then rerun verification.
- When revising an existing PPTX with preserve-edit, patch only the target parts,
  run before/after inspect, run compare, run package-diff with an edit-scope
  allowlist, then run gate.
- Do not use `python-pptx` to open and save a complex user-owned PPTX for a
  partial edit. Experiments showed this can rewrite many unrelated package
  parts. Use scoped OOXML/OPC edits for preservation work.

## Existing Deck Pattern

- Inspect slide order, titles, visible text, media, and visual patterns.
- Determine route before editing:
  - partial edit to uploaded PPTX: preserve-edit by default
  - edit to an agent-generated PPTX with available source specs:
    source-first-edit and regenerate
  - preserve slide count/order/wording but improve visuals: 1:1 beautify with
    user-approved scope
  - allow restructuring or redesign: treat deck as source material and
    regenerate a new PPTX
  - use as a native template shell: template-fill PPTX
  - add notes/timings only: native enhancement
- Identify template layouts before editing.
- Map new content to existing layout families.
- Preserve the deck's visual language unless the user asks for redesign.
- Preserve untouched package parts; do not rebuild unrelated slides, masters,
  layouts, themes, fonts, media, charts, animations, notes, or comments.
- Remove unused groups and placeholders.
- After moving, duplicating, or deleting slides, rerender or update all static
  page numbers and global counters.
- For preserve-edit, prove the unchanged scope with `pptx_tool.py package-diff`
  and explicit `--allow` globs for only the parts that should change.
- Do not flatten a deck into slide images when future agent revisions are
  expected unless the source project remains available and documented.

## Delivery Report

When finished, report:

- artifact path
- output route
- source materials used
- edit mode and preservation or regeneration evidence when editing PPTX
- verification performed
- package-diff result when using preserve-edit
- known limitations
