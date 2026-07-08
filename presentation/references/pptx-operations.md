# PPTX Operations

PPTX files are ZIP packages of XML parts, relationships, media, charts, notes,
layouts, masters, and content types. Treat them as structured packages, not as
single files.

## Inspect First

Use:

```bash
python3 scripts/pptx_tool.py inspect input.pptx --out report.json
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
- hidden or unusual package parts

## Template Editing

When using an existing deck as a template:

1. Render or inspect thumbnails if possible.
2. Classify the route:
   - raw PPTX template plus new material: fill native slide shells
   - existing deck, same slide count/order/wording: 1:1 beautify
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
3. Choose the image role, fit, slot, and layer before insertion.
4. For section slides, either place the image as a bottom background with
   contrast treatment and text above it, or create a separate content slide.
5. Never place a foreground image above existing section title/subtitle text.
6. Run `pptx_tool.py inspect` again and compare warning counts.
7. Repair the deck when the edit introduces new `text_picture_overlaps`,
   `section_picture_collisions`, `blank_shape_over_pictures`,
   `full_slide_picture_over_text`, or `picture_overflows`.

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
-> verification
-> output.pptx
```

Rules:

- Use the deck plan or slide spec as the source of truth.
- Give every planned slide a stable id and final position.
- Let helper scripts create JSON specs, charts, maps, screenshots, or images.
- Do not let helper scripts append directly to the same `.pptx` in sequence.
- Insert closing slides, acknowledgements, and appendix boundaries only in the
  final builder after all content slides are known.
- Render static page numbers and total counts only in the final global pass.
- Regenerate from a clean output path for each build.

Use append-based PPTX mutation only for small, deliberate edits to an existing
deck or for explicit repair work. When using append or XML reorder operations,
run full order and page-number checks afterward.

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

## Generation Notes

If generating PPTX with a library:

- set slide size explicitly
- build slides from the complete ordered spec in one final writer
- use real list paragraphs, not pasted bullet characters
- keep images in stable aspect-ratio boxes
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
