---
name: presentation
description: Create, edit, analyze, or improve slide decks, presentations, PPT/PowerPoint or .pptx files, agent-maintainable deck source, HTML decks, pitch decks, talks with speaker notes or presenter mode, lecture decks, PDF handouts, speaker outlines, and deck cover images. Use when the primary artifact is a slide/talk/deck experience, not when the user wants a long-form memo, report, policy, workbook, or PDF-native file operation.
---

# Presentation

## Overview

Build presentation artifacts as communication products, not as file-format chores.
Treat PPTX, HTML, PDF, and images as output formats selected by the user's goal.
Choose for the audience, revision workflow, and delivery setting before choosing
tools. For a user-supplied PPTX that needs editing, default to preservation:
keep the original package, masters, layouts, theme, fonts, media, animations,
and all untouched slides unchanged. Use source-first regeneration for new decks
or explicit redesign/restructure work, not as the default route for partial
edits to an existing deck.

Default to a Python-first PPTX toolchain. Use `python-pptx` for new decks,
controlled regeneration, and native template generation. Do not use
`python-pptx` as the default mechanism for partial edits to a user-owned PPTX,
because saving a complex third-party deck can rewrite unrelated package parts.
Use scoped OOXML/OPC edits plus `package-diff` for preservation work.

## Runtime Dependencies

Treat the execution environment as unknown. Do not assume Python, Node, PPTX
libraries, office automation, browser engines, converters, or rendering tools
are installed, and do not run a full dependency preflight by default.

Start with the task-specific command or host tool. If a runtime, package,
binary, browser, or office capability is missing, handle that execution-time
failure by installing/enabling the minimum local dependency when appropriate,
switching to an equivalent available tool that preserves the deck contract, or
reporting the exact missing dependency and install command.

## Route

1. Identify the job: new deck, existing deck analysis, existing deck edit,
   HTML deck, PPTX export, template fill, PDF handout, speaker outline,
   presenter-mode talk, reading/share deck, agent-maintained source, or cover
   image.
2. Classify delivery mode:
   - live talk: low-density slides, strong pacing, speaker notes, presenter
     affordances when using HTML
   - reading/share deck: self-contained slides, denser but still structured
   - agent-maintained source: stable slide IDs, reusable layout recipes,
     explicit assets, and deterministic verification matter more than manual
     PowerPoint object editability
   - human-editable PowerPoint: native shapes/text/charts matter more than
     web-only visual effects; use only when downstream humans will edit manually
   - visual showcase: HTML/PDF can use richer motion and browser rendering
3. If the user supplied source material, read it first and extract thesis,
   audience, proof, data, constraints, claims, citations, and must-include
   details before planning slides. If the user supplied only a topic and factual
   accuracy matters, gather or verify source facts before authoring.
   If source materials include findings, metrics, caveats, charts, tables, or
   verification notes, use them as evidence for slide claims and chart captions.
4. If named brands, products, people, places, or screenshots appear in the deck,
   build an asset inventory before designing. Prefer official logos, product
   images, UI screenshots, and source-provided charts over generic decoration.
   See `references/asset-intake.md`.
5. If the user supplied an existing deck or template, inspect content and visual
   structure before editing. For PPTX files, use
   `python3 {baseDir}/scripts/pptx_tool.py inspect path/to/deck.pptx --out report.json`
   before editing. Use `references/pptx-operations.md` to decide whether the
   deck needs preserve-edit, source-first edit, native template-fill, explicit
   repair, or source-material regeneration. For partial edits to a user-owned
   or source-unknown PPTX, assume preserve-edit unless the user explicitly asks
   for redesign, restructuring, or full regeneration.
6. Choose one visual system before building: design direction, theme, motif,
   typography posture, layout recipe set, and layout compiler contract. Use
   `references/visual-deck-system.md`, `references/layout-recipes.md`, and
   `references/layout-compiler.md` for visual decks. If the user asks for
   modern, premium, launch, keynote, or less old-fashioned templates, choose the
   `Keynote Stage` direction unless the content clearly needs another system.
7. If the user gives a vague style request and there is time to show work,
   create or describe three concrete visual directions using real deck content.
   Avoid asking the user to choose from abstract style labels alone.
8. Create a deck plan before building. Include stable slide ids, final order,
   build mode, global elements, purpose, headline, evidence/source, layout
   recipe, content density, layout intent, visual asset roles, fit/slot/layer
   treatment, and output notes. If emitting JSON, keep it compatible with
   `{baseDir}/assets/schemas/deck-plan.schema.json`. See
   `references/workflow.md`.
9. Choose the output route:
   - Use PPTX when the user explicitly asks for PowerPoint, provides a PPTX template, or needs a file for PowerPoint/Keynote workflows. For new PPTX decks, treat the file as a compiled artifact from the complete deck plan; do not make chained append scripts the default build strategy.
   - Use source-first HTML or another inspectable project format when future
     revisions are likely to be handled by an agent.
   - Use a self-contained HTML deck when the user wants a polished, inspectable, browser-presentable artifact and did not require PPTX.
   - Use PDF or cover images only when the user asks for a handout, preview, share card, or static export.
10. Build the artifact with the route's intended tools:
   - For new PPTX creation, prefer the Python-first route:
     `deck plan -> slide specs -> deterministic layout compiler -> python-pptx
     writer -> gate`. If `python-pptx` is missing, install the minimum local
     dependency when appropriate or report the exact blocker.
   - For edits to an agent-generated deck with its source spec available, edit
     the source spec and regenerate from a clean output path instead of patching
     the compiled PPTX.
   - For an existing PPTX partial edit, preserve by patching only the targeted
     slide parts, relationship parts, media parts, notes parts, or metadata
     required by the requested edit. Do not rebuild unrelated slides, masters,
     layouts, themes, fonts, media, charts, animations, or notes.
   - For a user-requested full restructure, treat the original deck as source
     material, rebuild the deck plan, and generate a new PPTX. Do not promise
     package-level preservation for a redesign.
   - Keep source of truth explicit: source HTML/PPTX project, deck plan, asset
     manifest, and verification report should be easier for an agent to modify
     than a binary-only final export.
   - For multi-section PPTX work, helper modules may produce slide specs,
     charts, images, screenshots, or assets, but a single final writer should
     render slide order, closing slides, page numbers, section counters, and
     total counts.
   - For generated PPTX decks, let the model choose recipes, density, asset
     roles, and intent; let deterministic layout code own geometry, wrapping,
     z-order, bounds, and pagination. Do not make hand-placed coordinates the
     primary strategy for a substantial deck.
   - If the user explicitly needs humans to manually edit the deck in
     PowerPoint, design for native PPTX editability from the first slide. Read
     `references/editable-pptx.md`.
   - Do not silently downgrade an explicit PPTX request to HTML/PDF, and do not hand-author OOXML ZIP packages as a substitute for a missing PPTX library unless the user approves that lower-level route or no install path is available and you state the limitation.
   - Prefer bundled scripts for deterministic checks, and use equivalent host tools only when they preserve the same verification contract.
11. Verify before delivering. For any PPTX produced or edited by the agent, run
    `python3 {baseDir}/scripts/pptx_tool.py gate path/to/deck.pptx --out report.json`.
    `inspect` is diagnostic; `gate` is the delivery-blocking check. If `gate`
    fails, repair the deck and rerun it before delivery, or explicitly report
    the unresolved blocker. At minimum also search for placeholders, check source
    fidelity, inspect visual layout, open or render the artifact when tools
    allow it, run one fix-and-recheck pass, and report what was verified. If
    emitting JSON, keep it compatible with
    `{baseDir}/assets/schemas/verification-report.schema.json`.

## References

Load only the reference needed for the current route:

- `references/workflow.md` for deck planning, content mapping, build discipline, and delivery flow.
- `references/asset-intake.md` for factual source checks, brand/product assets,
  screenshots, and image selection.
- `references/pptx-operations.md` for PPTX/template inspection, single-writer generation, OOXML package risks, and PowerPoint QA.
- `references/editable-pptx.md` only when human manual PowerPoint editability is
  explicitly required.
- `references/visual-deck-system.md` for design directions, themes, motifs, typography, and composition rules.
- `references/layout-recipes.md` for registered slide recipes and when to use each one.
- `references/layout-compiler.md` for generated deck geometry, density,
  layering, asset roles, overflow prevention, and PPTX QA gates.
- `references/html-deck.md` for self-contained HTML deck structure, template usage, and interaction rules.
- `references/speaker-notes.md` when the deck is for a talk, training,
  roadshow, or any live presentation with speaker notes.
- `references/verification.md` for placeholder, rendering, overflow, asset, and source-fidelity checks.

## Scripts

- `python3 {baseDir}/scripts/pptx_tool.py image-info assets/photo.jpg --out image-report.json` inspects image pixel size, aspect ratio, aspect class, and recommended slots before PPTX insertion.
- `python3 {baseDir}/scripts/pptx_tool.py inspect deck.pptx --out report.json` inspects PPTX package structure, slide order, relationships, media, notes, image-only slide candidates, placeholders, page-number candidates, shape/picture/table bounds, dense tables, tiny text, single-row timeline crowding, sparse stub slides, closing-slide placement, section-picture collisions, picture layering risks, image aspect distortion, image crop risk, and effective image resolution.
- `python3 {baseDir}/scripts/pptx_tool.py gate deck.pptx --out report.json` runs the required PPTX delivery gate and returns nonzero when blocking layout, order, page-number, package, placeholder, table, timeline, picture-layering, image-aspect, or severe image-resolution issues remain.
- `python3 {baseDir}/scripts/pptx_tool.py compare before.json after.json --out diff.json` compares inspect reports after editing an existing PPTX and returns nonzero when the edit introduces new layout or picture-layering regressions.
- `python3 {baseDir}/scripts/pptx_tool.py package-diff before.pptx after.pptx --allow 'ppt/slides/slide5.xml' --out package-diff.json` compares PPTX package part hashes and fails when changes occur outside explicitly allowed part globs. Use it for preserve-edit work.
- `node {baseDir}/scripts/html_tool.mjs inspect deck.html --out report.json` inspects static HTML decks for slides, registered layouts, broken local asset references, placeholder text, presenter-text leaks, text-only slides, and basic structure.

The scripts are portable baseline tools. Do not assume product-specific tools exist.
If a host offers equivalent conversion, rendering, or browser automation, it may be
used, but the final artifact still needs the same verification report.

## Quality Bar

- Do not deliver a title-plus-bullets dump unless the user asked for a plain outline.
- Every normal slide needs a clear job: orient, explain, prove, compare, transition, or close.
- Every visual slide needs an intentional visual element: image, chart, diagram, icon system, typographic composition, data block, or structured layout.
- Do not invent a new layout for every slide. Choose from the registered recipes, then adapt content inside the recipe.
- For generated PPTX, use a recipe-driven layout compiler: the model selects
  intent and recipe; deterministic code places objects, wraps overflowing
  groups, and controls layer order.
- Preserve source truth: do not invent data, citations, product specs, logos, or
  user quotes to make a slide feel complete.
- Preserve existing PPTX truth: when the user asks to edit an uploaded PPTX,
  leave everything outside the requested edit unchanged unless the user approves
  a redesign or structural rebuild.
- Keep the deck density intentional. Live talks need fewer words and stronger
  pacing; reading decks can carry more detail but must remain scanable.
- Use real assets when a real entity is named. A generic silhouette, fake UI,
  or decorative gradient is not a substitute for an official logo, product
  image, UI screenshot, or source chart.
- New PPTX decks with multiple sections must use a complete deck plan plus one
  final writer, not chained append scripts that mutate the same PPTX.
- Page numbers, total counts, tables of contents, section counters, and closing
  slides are final-pass elements.
- A closing or thank-you slide must be generated only after all content and
  appendix slides unless the deck plan explicitly marks it as a mid-deck break.
- Do not split a title/subtitle stub and its table or evidence onto adjacent
  slides; merge, paginate, or use a statement/section recipe intentionally.
- Images must not be appended after slide rendering without relayout. Give each
  image a role, slot, fit, and layer before rendering.
- Image placement must be aspect-aware. Read or infer each image's intrinsic
  width, height, aspect ratio, aspect class, crop permission, focal point, and
  minimum readable size before choosing a recipe slot.
- Do not use `stretch` for photographs, screenshots, maps, charts, logos, or
  product images unless the distortion is explicitly accepted. Use `contain`
  for detail-bearing assets and `cover` only for photography or intentional
  editorial background crops.
- If an image does not fit the current recipe slot, change the recipe, paginate,
  choose another asset, or reject the insertion instead of scaling or cropping
  blindly.
- When adding images to an existing PPTX, inspect before and after the edit.
  The edit fails if it introduces new text-picture overlaps, section-picture
  collisions, blank shapes over pictures, full-slide pictures over text, or
  picture overflows, image aspect distortion, or severe image resolution
  warnings.
- Any PPTX delivered by the agent must pass `pptx_tool.py gate`, or the final
  response must state the unresolved gate blockers plainly.
- Grids, process rows, value chains, and cards must obey recipe limits; wrap,
  paginate, or change recipe instead of overflowing the slide.
- Tables and timelines must obey recipe limits: split wide or long tables,
  avoid tiny type, and wrap or paginate timelines with too many milestones.
- Rounded containers must fit their text with clear padding and restrained
  radius; avoid large empty round rectangles around small text.
- Preserve templates by removing unused placeholder groups, not just clearing text.
- Run at least one fix-and-recheck pass after creating or editing a visual deck.
- State limitations plainly when rendering or conversion is unavailable.
