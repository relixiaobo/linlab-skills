# Human-Editable PPTX

Use this only when downstream humans need to manually edit text, shapes, charts,
and images in PowerPoint. This is not the default optimization target. Most
users will ask an agent to modify the deck later, so the normal priority is
source-first maintainability: a clear deck plan, inspectable source files,
stable slide IDs, local assets, and deterministic regeneration.

Human PowerPoint editability must be designed from the start; it cannot be
reliably recovered from a visually rich HTML deck or screenshot deck.

## Route Choice

- Native PPTX generation/editing library available: use it first.
- Existing PPTX template plus new content: preserve native slide shells when
  possible, clone/fill slides, and verify relationships.
- Existing PPTX beautify with same slide count/order/wording: preserve the text
  contract and improve layout.
- Finished PPTX needs notes, narration, timings, or transitions only: patch the
  existing file instead of regenerating the visual design.
- Visual freedom matters more than editability: HTML/PDF may be the better
  deliverable. Keep the source project available so an agent can revise it.

If an explicit human-editable PPTX request cannot be satisfied with reliable
tooling, state the gap and ask before switching to HTML/PDF or a screenshot-based
PPTX.

## Editable Design Rules

When generating a human-editable native PPTX:

- set slide size explicitly, usually 16:9 widescreen
- use real text boxes and list paragraphs, not pasted bullet characters
- use native shapes for rectangles, rules, callouts, and simple diagrams
- use native chart/table APIs for data when practical
- place images in stable boxes with explicit crop/contain behavior
- keep colors in a small theme token set; do not rely on default Office theme
- keep speaker notes in notes fields, not visible slide text
- avoid flattening a full slide into one image unless the user accepts that the
  PPTX is a visual delivery file and future edits should happen in the source
  project

## HTML-To-PPTX Constraint Path

If the chosen local tooling converts HTML to editable PPTX element by element,
author HTML under PowerPoint-like constraints from the first slide:

- use a fixed 16:9 canvas that maps to PowerPoint widescreen, commonly
  `960pt x 540pt` or the converter's documented equivalent
- wrap all visible text in `p`, `h1`-`h6`, or `li`; do not put bare text inside
  layout `div`s
- put fills, borders, rounded corners, and shadows on wrapper shapes, not text
  elements
- use `img` tags for images; do not rely on CSS `background-image`
- avoid CSS gradients, filters, complex blend modes, web components, and
  runtime animation if editability is the goal
- use solid fills or simple segmented shapes instead of browser-only effects

When converting an already-designed visual HTML deck to editable PPTX, first
tell the user what will be simplified: gradients, shadows, complex SVGs,
animation, web components, unsupported fonts, or background images.

## Verification

Run `pptx_tool.py inspect` on the result. When possible, also open or render the
deck and check:

- slide count and order are correct
- text can be selected and edited
- images/charts are present and not distorted
- no stale placeholders, hidden notes, or orphaned relationships remain
- slide masters/layouts are not accidentally duplicated into a broken package
- fonts and colors are acceptable on a different machine or PowerPoint install

Report honestly when only package inspection was possible and visual rendering
was not available.
