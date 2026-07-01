---
name: presentation
description: Create, edit, analyze, or improve slide decks, presentations, PPT/PowerPoint or .pptx files, agent-maintainable deck source, HTML decks, pitch decks, talks with speaker notes or presenter mode, lecture decks, PDF handouts, speaker outlines, and deck cover images.
---

# Presentation

## Overview

Build presentation artifacts as communication products, not as file-format chores.
Treat PPTX, HTML, PDF, and images as output formats selected by the user's goal.
Choose for the audience, revision workflow, and delivery setting before choosing
tools. Default to source-first artifacts that another agent can inspect, modify,
verify, and regenerate; optimize for human manual editing in PowerPoint only
when the user explicitly needs that.

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
   when useful. Use `references/pptx-operations.md` to decide whether the deck is
   a source, a 1:1 beautify target, a native template-fill target, or a finished
   deck that should only receive notes/audio/timing.
6. Choose one visual system before building: design direction, theme, motif,
   typography posture, and layout recipe set. Use
   `references/visual-deck-system.md` and `references/layout-recipes.md` for
   visual decks. If the user asks for modern, premium, launch, keynote, or less
   old-fashioned templates, choose the `Keynote Stage` direction unless the
   content clearly needs another system.
7. If the user gives a vague style request and there is time to show work,
   create or describe three concrete visual directions using real deck content.
   Avoid asking the user to choose from abstract style labels alone.
8. Create a deck plan before building. Include slide number, purpose, headline,
   evidence/source, layout recipe, visual treatment, and output notes. If
   emitting JSON, keep it compatible with
   `{baseDir}/assets/schemas/deck-plan.schema.json`. See
   `references/workflow.md`.
9. Choose the output route:
   - Use PPTX when the user explicitly asks for PowerPoint, provides a PPTX template, or needs a file for PowerPoint/Keynote workflows.
   - Use source-first HTML or another inspectable project format when future
     revisions are likely to be handled by an agent.
   - Use a self-contained HTML deck when the user wants a polished, inspectable, browser-presentable artifact and did not require PPTX.
   - Use PDF or cover images only when the user asks for a handout, preview, share card, or static export.
10. Build the artifact with the route's intended tools:
   - For PPTX creation or editing, first prefer a real PPTX generation/editing library or existing office automation available in the task environment. If the required package or command is missing, verify that absence and try to install or enable it in the local task environment when permissions allow.
   - Keep source of truth explicit: source HTML/PPTX project, deck plan, asset
     manifest, and verification report should be easier for an agent to modify
     than a binary-only final export.
   - If the user explicitly needs humans to manually edit the deck in
     PowerPoint, design for native PPTX editability from the first slide. Read
     `references/editable-pptx.md`.
   - Do not silently downgrade an explicit PPTX request to HTML/PDF, and do not hand-author OOXML ZIP packages as a substitute for a missing PPTX library unless the user approves that lower-level route or no install path is available and you state the limitation.
   - Prefer bundled scripts for deterministic checks, and use equivalent host tools only when they preserve the same verification contract.
11. Verify before delivering. At minimum search for placeholders, check source
    fidelity, inspect visual layout, open or render the artifact when tools
    allow it, run one fix-and-recheck pass, and report what was verified. If
    emitting JSON, keep it compatible with
    `{baseDir}/assets/schemas/verification-report.schema.json`.

## References

Load only the reference needed for the current route:

- `references/workflow.md` for deck planning, content mapping, and delivery flow.
- `references/asset-intake.md` for factual source checks, brand/product assets,
  screenshots, and image selection.
- `references/pptx-operations.md` for PPTX/template inspection, OOXML package risks, and PowerPoint QA.
- `references/editable-pptx.md` only when human manual PowerPoint editability is
  explicitly required.
- `references/visual-deck-system.md` for design directions, themes, motifs, typography, and composition rules.
- `references/layout-recipes.md` for registered slide recipes and when to use each one.
- `references/html-deck.md` for self-contained HTML deck structure, template usage, and interaction rules.
- `references/speaker-notes.md` when the deck is for a talk, training,
  roadshow, or any live presentation with speaker notes.
- `references/verification.md` for placeholder, rendering, overflow, asset, and source-fidelity checks.

## Scripts

- `python3 {baseDir}/scripts/pptx_tool.py inspect deck.pptx --out report.json` inspects PPTX package structure, slide order, relationships, media, notes, and likely placeholders.
- `node {baseDir}/scripts/html_tool.mjs inspect deck.html --out report.json` inspects static HTML decks for slides, broken local asset references, placeholder text, and basic structure.

The scripts are portable baseline tools. Do not assume product-specific tools exist.
If a host offers equivalent conversion, rendering, or browser automation, it may be
used, but the final artifact still needs the same verification report.

## Quality Bar

- Do not deliver a title-plus-bullets dump unless the user asked for a plain outline.
- Every normal slide needs a clear job: orient, explain, prove, compare, transition, or close.
- Every visual slide needs an intentional visual element: image, chart, diagram, icon system, typographic composition, data block, or structured layout.
- Do not invent a new layout for every slide. Choose from the registered recipes, then adapt content inside the recipe.
- Preserve source truth: do not invent data, citations, product specs, logos, or
  user quotes to make a slide feel complete.
- Keep the deck density intentional. Live talks need fewer words and stronger
  pacing; reading decks can carry more detail but must remain scanable.
- Use real assets when a real entity is named. A generic silhouette, fake UI,
  or decorative gradient is not a substitute for an official logo, product
  image, UI screenshot, or source chart.
- Preserve templates by removing unused placeholder groups, not just clearing text.
- Run at least one fix-and-recheck pass after creating or editing a visual deck.
- State limitations plainly when rendering or conversion is unavailable.
