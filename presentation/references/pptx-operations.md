# PPTX Operations

PPTX files are ZIP packages of XML parts, relationships, media, charts, notes,
layouts, masters, and content types. Treat them as structured packages, not as
single files.

Use a Python-first default toolchain. `python-pptx` is the default writer for
new decks and controlled regeneration. It is not the default preserve-edit
writer for a user-owned PPTX because opening and saving a complex third-party
deck can rewrite unrelated parts. For preserve-edit work, use mature package
and XML primitives such as `zipfile` and `lxml`, or an available mature
OOXML/OPC library, but keep the edit scoped and prove the scope with
`package-diff`.

## Inspect First

Use:

```bash
python3 scripts/pptx_tool.py inspect input.pptx --out report.json
```

Before delivery, use:

```bash
python3 scripts/pptx_tool.py gate output.pptx --out pptx-gate-report.json
```

Read the report for:

- slide count and slide order
- missing relationship targets
- media/chart/notes references
- slide layouts and masters
- image-only slide candidates when humans need to manually edit the PPTX or when
  no separate source project exists
- placeholder-like text
- page-number mismatches and static total-count drift
- out-of-bounds shapes, pictures, and tables
- dense tables, tiny text, single-row timeline crowding, sparse stub slides, and
  closing slides that appear before later content
- text/picture overlap, blank shapes covering pictures, and full-slide pictures
  above text
- section-picture collisions when pictures are inserted above section title text
- package media dimensions, picture display aspect, effective image resolution,
  aspect distortion, and large crop risks
- hidden or unusual package parts

## Preservation Edit Contract

When the user uploads a PPTX and asks for a partial edit, default to
preserve-edit. The objective is to keep the original deck intact and change only
the requested target objects.

Use preserve-edit for:

- text replacement on specific slides
- replacing an image in the same intended slot
- adding or updating speaker notes, comments, timing, or metadata
- fixing page numbers, counters, broken relationships, or known package defects
- small edits where slide count, order, theme, master, layouts, fonts, and
  visual style should remain unchanged

Do not use preserve-edit for broad redesign, overall beautification, new story
structure, new visual language, deck compression, or multi-slide content
rewrites. Route those requests to regeneration from the existing deck as source
material.

Preserve-edit rules:

- Copy the original PPTX to a new output path before editing.
- Patch only the minimum required package parts: target slide XML, target slide
  relationships, the directly referenced media/chart/data part, notes part, or
  required metadata.
- Use scoped OOXML/OPC edits for user-owned decks. Do not use `python-pptx` to
  open and save a complex user-owned PPTX for a partial edit unless the user
  accepts possible package-wide normalization.
- Do not rebuild the whole deck through a generation library.
- Do not recreate untouched slides, masters, slide layouts, theme, media,
  charts, animations, notes, comments, or document properties unless explicitly
  required by the edit.
- Do not normalize formatting, fonts, colors, coordinates, object order, or XML
  namespaces in untouched parts.
- If an edit requires changing layout, treat only that target slide as relayout;
  keep unrelated slides package-identical.
- If the user asks for broad redesign, new outline, global visual cleanup, or
  content restructuring, confirm or clearly route to regeneration instead of
  silently converting a preserve-edit request into a rebuild.

Verification for preserve-edit:

```bash
python3 scripts/pptx_tool.py inspect before.pptx --out before-report.json
python3 scripts/pptx_tool.py inspect after.pptx --out after-report.json
python3 scripts/pptx_tool.py compare before-report.json after-report.json --out edit-diff.json
python3 scripts/pptx_tool.py package-diff before.pptx after.pptx \
  --allow 'ppt/slides/slide5.xml' \
  --allow 'ppt/slides/_rels/slide5.xml.rels' \
  --allow 'ppt/media/image12.png' \
  --out package-diff.json
python3 scripts/pptx_tool.py gate after.pptx --out pptx-gate-report.json
```

The `package-diff` allowlist must match the actual edit scope. A preserve-edit
fails when unrelated package parts change, even if the deck opens successfully.
If local rendering tools are available, also render the edited slide and nearby
slides for visual review.

Evidence from local experiments:

- `python-pptx` can edit a simple deck it generated while changing only the
  target slide part, so it is acceptable for agent-owned generated decks when
  source specs are available.
- On a complex user-owned PPTX, a one-text change through `python-pptx` rewrote
  many unrelated package parts. The same text change through scoped OOXML
  patching changed only `ppt/slides/slide1.xml`.

Treat these results as a routing rule: agent-owned decks are source-first;
source-unknown user decks are preserve-edit.

## Existing Deck Restructure

When the user asks to restructure, redesign, summarize, modernize, or otherwise
rebuild an existing PPTX, do not use preserve-edit. Treat the existing file as
source material:

1. Inspect and extract slide order, visible text, tables, charts, images, and
   section structure.
2. Build a new deck plan and visual system.
3. Map retained claims and evidence into registered layout recipes.
4. Generate a new PPTX from the complete plan with the single-writer contract.
5. Run the delivery gate.

Package-level preservation is not part of a regeneration contract. Source
fidelity, visual quality, editability, and gate results are the contract.

## Template Editing

When using an existing deck as a template:

1. Render or inspect thumbnails if possible.
2. Classify the route:
   - existing deck with partial edits only: preserve-edit
   - raw PPTX template plus new material: fill native slide shells
   - existing deck, same slide count/order/wording but visual cleanup requested:
     1:1 beautify, with user-approved scope
   - existing deck, new outline/page count: treat as source material
   - finished deck plus notes/audio/timings: native enhancement only
3. Identify layout families: cover, section, image-led, comparison, process, stat, quote, chart, closing.
4. Map new content to existing layouts.
5. Duplicate or remove whole slide/group structures deliberately.
6. Replace content after structural edits.
7. Clean unused placeholders and orphaned assets.
8. Repack and verify.

## Existing Deck Image Insertion

When adding pictures to an existing PPTX, treat the operation as relayout, not
as object append:

1. Run `pptx_tool.py inspect` and save the before report.
2. Identify the target slide family and its protected text zones.
3. Run `pptx_tool.py image-info` for local images when available. Record image
   width, height, aspect ratio, aspect class, crop permission, focal point, and
   minimum effective PPI.
4. Choose the image role, fit, slot, and layer before insertion.
5. If the image aspect conflicts with the chosen slot, change the recipe,
   paginate, choose another asset, or reject the insertion. Do not stretch or
   crop blindly.
6. For section slides, either place the image as a bottom background with
   contrast treatment and text above it, or create a separate content slide.
7. Never place a foreground image above existing section title/subtitle text.
8. Run `pptx_tool.py inspect` again and compare warning counts.
9. Run `pptx_tool.py compare before-report.json after-report.json --out edit-diff.json`.
10. Run `pptx_tool.py gate edited.pptx --out pptx-gate-report.json`.
11. Repair the deck when the edit introduces new `text_picture_overlaps`,
   `section_picture_collisions`, `blank_shape_over_pictures`,
   `full_slide_picture_over_text`, `picture_overflows`,
   `image_aspect_distortions`, or `severe_image_resolution_warnings`, or when
   the delivery gate fails.

## New PPTX Build Contract

For new PPTX decks, use a single-writer build unless the user explicitly asks
for manual repair of an existing file.

Preferred architecture:

```text
source material
-> deck plan / slide spec
-> assets
-> one PPTX builder
-> final global pass
-> delivery gate and verification
-> output.pptx
```

Rules:

- Use the deck plan or slide spec as the source of truth.
- Prefer `python-pptx` as the default native PPTX writer in this skill. Use
  optional non-Python backends only when the task environment or user request
  clearly calls for them.
- Give every planned slide a stable id and final position.
- Let helper scripts create JSON specs, charts, maps, screenshots, or images.
- Do not let helper scripts append directly to the same `.pptx` in sequence.
- Insert closing slides, acknowledgements, and appendix boundaries only in the
  final builder after all content slides are known.
- Render static page numbers and total counts only in the final global pass.
- Regenerate from a clean output path for each build.

Use append-based PPTX mutation only for small, deliberate edits to an existing
deck or for explicit repair work. For partial edits, prefer package-preserving
patches and prove the scope with `package-diff`. When using append or XML
reorder operations, run full order and page-number checks afterward.

## Package Risks

Common failure modes:

- slide exists but is not in `ppt/presentation.xml`
- slide relationship missing from `ppt/_rels/presentation.xml.rels`
- media/chart target referenced but absent
- `[Content_Types].xml` missing an override
- notes or comments copied with stale relationships
- placeholder text left in hidden groups
- section script adds a closing slide before later scripts append more content
- static page numbers drift after slide insertions, moves, or deletes
- text overflow visible only after rendering
- native tables live in `p:graphicFrame`; tools that inspect only text boxes and
  pictures can miss table overflow
- title-only stubs are generated before actual evidence because the builder
  treats source headings as slides instead of layout sections
- long tables and timelines are compressed into tiny type instead of being
  split, wrapped, or summarized
- an image is inserted onto a section divider as a foreground object and covers
  the section title or subtitle
- a partial edit is routed through full-deck regeneration, causing untouched
  masters, layouts, themes, fonts, media, object ids, animations, or XML parts to
  change unexpectedly

## Generation Notes

If generating PPTX with a library:

- set slide size explicitly
- build slides from the complete ordered spec in one final writer
- use real list paragraphs, not pasted bullet characters
- keep images in stable aspect-ratio boxes
- keep picture display boxes consistent with the asset aspect ratio unless a
  planned crop is encoded intentionally
- do not rely on default theme colors
- use native chart/table APIs when humans need to manually edit the data in
  PowerPoint
- add speaker notes as notes, not visible microcopy
- add or update static page numbers only after slide order is final
- verify by opening, converting, or rendering when possible

If the user explicitly requested PPTX and reliable PPTX generation is not
available, do not silently switch formats. First verify the missing dependency
or command, then install or enable an appropriate PPTX library/tool in the local
task environment when permissions allow. If that is blocked, ask before
delivering HTML, PDF, a slide plan, or a hand-authored OOXML package instead.
State the compatibility and verification gap clearly.

Hand-authored OOXML is a last-resort repair or packaging route, not the default
creation route. Use it only when an existing PPTX/template must be patched at the
package level, or when the user accepts the lower-level route after the normal
PPTX tool path is blocked.

## Editability Boundary

Human-editable PPTX means the recipient can select and change text, shapes,
charts, and images in PowerPoint. This is only a priority when downstream humans
will edit manually. If future revisions will be handled by an agent, prefer a
source-first project plus generated PPTX/PDF exports.

A PPTX that contains one full-slide PNG per slide is a visual delivery format,
not a human-editable deck. It can still be acceptable when the source project is
kept for future agent revisions.

If converting from HTML to human-editable PPTX, read `editable-pptx.md` before
authoring. Browser-only features such as complex gradients, filters, web
components, CSS background images, and animation usually need to be simplified.
