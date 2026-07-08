# Presentation Verification

Approach verification as a bug hunt. First renders often have concrete issues.

## Universal Checks

- source claims are represented faithfully
- recent or unstable facts have sources or are marked as assumptions
- slide order supports the story
- actual slide order matches the deck plan when a plan exists
- no lorem, TODO, placeholder, sample, dummy, or xxxx text remains
- no broken local asset references
- text does not overflow or overlap
- repeated layouts are intentional
- contrast is projector-readable
- images are cropped intentionally
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
- verify the closing slide is last unless the deck plan explicitly says otherwise
- verify static page numbers, total counts, and section counters after any structural edit
- verify one final writer or an explicit repair workflow was used for new multi-section decks
- render thumbnails or slides when possible
- check slide relationships and content types
- check notes/media/chart references
- open or convert the file when possible
- if human PowerPoint editability was explicitly required, verify text is not
  flattened into slide images

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
- `checks`: check objects with name, status, tool, and evidence or result
- `issues`: issues found, including fixed issues
- `limitations`: checks not possible in the current environment
- `finalStatus`: passed, warning, or failed
