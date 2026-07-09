# Presentation Verification

Approach verification as a bug hunt. First renders often have concrete issues.

## Universal Checks

- source claims are represented faithfully
- recent or unstable facts have sources or are marked as assumptions
- slide order supports the story
- actual slide order matches the deck plan when a plan exists
- each designed slide uses a registered recipe and respects that recipe's
  geometry rules
- no lorem, TODO, placeholder, sample, dummy, or xxxx text remains
- no broken local asset references
- text does not overflow or overlap
- objects stay within the slide/safe area unless intentionally full-bleed
- repeated layouts are intentional
- contrast is projector-readable
- images are cropped intentionally
- image display boxes preserve the intended aspect ratio unless a planned crop
  is documented
- image effective resolution remains high enough for the intended slot
- images do not cover text, tables, cards, charts, or other primary content
- named brands/products have real logos or explicitly accepted placeholders
- screenshots and charts remain readable at final slide size
- final artifact opens or renders when local tools allow it
- every designed slide has a registered layout recipe
- the deck uses one visual system instead of slide-by-slide styling
- the source of truth is clear, inspectable, and available for future agent
  revisions
- live-talk decks keep presenter-only material out of visible slide content

## PPTX Checks

- inspect package structure with `scripts/pptx_tool.py`
- run `scripts/pptx_tool.py gate deck.pptx --out report.json` before delivery;
  a failed gate means the PPTX is not ready to deliver unless the user accepts
  the blocker explicitly
- for new or regenerated PPTX, verify the deck was built from a complete plan
  or source spec with one final writer, not by chained append scripts
- for edits to agent-generated decks with source specs, verify the source spec
  was updated and the PPTX was regenerated from a clean output path
- for preserve-edit work on an uploaded PPTX, run `scripts/pptx_tool.py
  package-diff before.pptx after.pptx --allow ... --out package-diff.json` and
  fail the edit if package parts outside the requested edit scope changed
- for preserve-edit work, do not treat a high-level library save as sufficient
  evidence. The package diff must prove the scope.
- verify the closing slide is last unless the deck plan explicitly says otherwise
- verify static page numbers, total counts, and section counters after any structural edit
- verify one final writer or an explicit repair workflow was used for new multi-section decks
- check for out-of-bounds shapes, pictures, and native PPTX tables
- check for text/picture overlap, blank shapes covering pictures, and
  full-slide pictures placed above text
- check for picture aspect distortion, severe low effective PPI, large crop
  risk, and missing package image dimensions
- check for section-picture collisions when media is added to existing decks
- check that picture counts include native PPTX `p:pic` elements, not only
  DrawingML picture namespace elements
- check grids, process rows, value chains, card sets, timelines, and tables
  against recipe limits
- check for sparse title/stub slides that should have been merged with the
  following content slide or made into an intentional section/statement slide
- check for dense tables, tiny text, and single-row timelines with too many
  milestones
- render thumbnails or slides when possible
- check slide relationships and content types
- check notes/media/chart references
- open or convert the file when possible
- if human PowerPoint editability was explicitly required, verify text is not
  flattened into slide images
- when adding pictures to an existing PPTX, compare before/after inspect
  reports; no new picture layering warning is acceptable without explicit
  repair or documented acceptance

## PPTX Delivery Gate

Use this command for every PPTX created or edited by the agent:

```bash
python3 scripts/pptx_tool.py gate output.pptx --out pptx-gate-report.json
```

The gate fails on package errors, placeholder text, page-number drift, object
overflow, table overflow, crowded tables, tiny text, over-compressed timelines,
sparse stub slides, early closing slides, text-picture overlaps,
section-picture collisions, blank shapes above pictures, full-slide pictures
above text, picture aspect distortion, and severe image resolution problems.

For existing-deck edits, keep a before report and compare after the edit:

```bash
python3 scripts/pptx_tool.py inspect before.pptx --out before-report.json
python3 scripts/pptx_tool.py inspect after.pptx --out after-report.json
python3 scripts/pptx_tool.py compare before-report.json after-report.json --out edit-diff.json
python3 scripts/pptx_tool.py package-diff before.pptx after.pptx --allow 'ppt/slides/slide5.xml' --out package-diff.json
python3 scripts/pptx_tool.py gate after.pptx --out pptx-gate-report.json
```

If the gate, compare, or package-diff command returns nonzero, repair and rerun
the command. Do not treat a successful file open in PowerPoint as a substitute
for the gate or the preservation diff.

## HTML Checks

- inspect static structure with `scripts/html_tool.mjs`
- open in a browser when possible
- check desktop and narrow viewport framing
- verify keyboard navigation
- verify notes are hidden in audience view and available where expected
- search generated files for placeholders
- review visual warnings: layout variety, missing `data-layout`, text-only
  slides, bullet density, tiny text, remote dependencies, and broken local assets

## Delivery Report

When emitting JSON, follow `assets/schemas/verification-report.schema.json`.

Include:

- `artifact`: final artifact path
- `outputRoute`: artifact route such as HTML deck or PPTX
- `filesProduced`: produced deliverables
- `sourceMaterials`: source inputs used
- `editProvenance`: edit mode and evidence for source-first regeneration or
  scoped preservation
- `packageDiffCheck`: package-diff status and allowlist for preserve-edit work
- `checks`: check objects with name, status, tool, and evidence or result
- `issues`: issues found, including fixed issues
- `limitations`: checks not possible in the current environment
- `finalStatus`: passed, warning, or failed
