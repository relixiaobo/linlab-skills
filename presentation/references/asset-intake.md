# Asset Intake

Use this reference for photographs, screenshots, logos, maps, diagrams, charts,
documents, videos, and assets extracted from an existing PPTX.

## Visual Asset Plan

Build this plan after slide jobs are known and before layouts are assigned.
Classify the deck as:

- **Visual**: the audience must inspect real people, places, objects, products,
  interfaces, documents, or environments.
- **Mixed**: real or conceptual media and constructed visuals both carry the
  argument.
- **Analytical**: charts, diagrams, tables, and typography carry most claims;
  media appears only when it adds evidence or necessary context.

For each planned item record: slide reference, visual job, exact subject/action/
context, asset class, why it belongs on that slide, source or generation plan,
candidate files, status, `cover`/`contain`, focal point, and crop policy.
Mark text-only slides explicitly as thesis, transition, decision, or reset.

Asset classes:

- **Real evidence**: supplied or sourced photography, screenshots, documents,
  maps, logos, facilities, equipment, products, or interfaces.
- **Conceptual image**: generated or abstract imagery that explains or evokes
  an idea without pretending to document reality.
- **Constructed visual**: chart, diagram, timeline, table, or map built from
  verified information.
- **Intentional reset**: a deliberately sparse text-led frame.

Visual and mixed decks must include media-bearing slides wherever the audience
needs to see the subject itself. Do not use a quota for analytical decks, and
do not add stock photography merely to make the deck look visual.

## Relevance Gate

Do not accept the first plausible image. Inspect candidates at full resolution
and reject any candidate that fails one of these checks:

- The visible subject, action, and setting match the slide, not just its broad
  topic or mood.
- The image adds evidence, inspectable context, or a deliberate metaphor that
  can be stated in one sentence.
- A named product, person, place, event, document, or interface is represented
  by the real thing, not a generic substitute.
- The crop can preserve the important subject at the target slot ratio.
- Text, logos, UI, faces, and identifying details remain legible and intact.

When no candidate passes, change the query, capture the real state, generate a
clearly conceptual image, build a diagram, or report the asset as blocked. Do
not fill the slot with an irrelevant image.

## Identity And Provenance

Prefer official or user-provided assets when identity matters. Record source,
owner, retrieval date, rights, local file, factual role, and every crop,
recolor, cleanup, or annotation. Generated visuals may explain an idea; they
must not impersonate a real product screenshot, person, place, logo, document,
or event.

An image is not evidence merely because it looks plausible. Link every factual
asset to the claim it supports and to a source authoritative enough for that
claim.

## Quality

- Inspect pixel dimensions, format, transparency, profile, aspect ratio, and
  effective resolution at final size.
- Run `python3 scripts/pptx_tool.py image-info <images...>` when available
  before inserting raster assets.
- Use vector originals for logos, maps, and diagrams when reliable.
- Use `contain` for screenshots, documents, maps, charts, and logos that must be
  inspected; use `cover` only for photography with an intentional crop.
- Never use `fill`, independent width/height scaling, or
  `background-size: 100% 100%` for content-bearing imagery.
- For `cover`, choose and record the focal point after viewing the actual
  candidate at the target ratio. Cropping a face, product, label, or key action
  is a failed treatment, even if the frame looks balanced.
- Use an auditable `<img>` element with `data-asset-id`, `data-asset-role`,
  `data-fit`, and `data-focal-point` for cover crops. Reserve CSS background
  images for non-content decoration.
- Keep labels and UI text legible at presentation size.
- Reject unexplained watermarks, compression artifacts, soft images, and
  decorative stock imagery that does not carry the subject.

Example:

```html
<figure class="media-frame">
  <img src="assets/factory-line.webp"
    alt="Operators inspecting the assembly line"
    data-asset-id="asset-factory-line"
    data-asset-role="subject"
    data-fit="cover"
    data-focal-point="62% 48%"
    style="object-position: 62% 48%;">
</figure>
```

## Screenshots

Capture the real required state. Record product version, viewport, device, and
capture date when material. Remove private data without changing the behavior
being claimed. Do not composite controls or states in a way that looks like an
authentic screenshot.

## Existing PPTX

When a PPTX is a Studio evidence source, extract original media without
resampling and retain the source slide/object relationship in the asset record.
When Surgeon replaces media, record target object identity, relationship, media
part, crop, alt text, hyperlink, and allowed side effects in the edit manifest.
