# HTML Decks

Use HTML decks when the user wants a polished, inspectable, browser-presentable
artifact and did not require PowerPoint.

## Requirements

- Produce a self-contained `index.html` unless the user asks for a project folder.
- Use local or inline assets; do not depend on remote CDNs.
- Use a fixed 16:9 slide stage. Prefer authoring at 1920×1080 and scaling the
  whole stage uniformly to fit the browser. A responsive `aspect-ratio: 16 / 9`
  wrapper is acceptable for simple decks, but slide content must not reflow into
  a different composition on phones.
- Support keyboard navigation.
- Keep presenter controls outside the visual safe area.
- Respect reduced-motion preferences if animations are present.
- Make print/PDF fallback acceptable.
- Start from `assets/templates/html-deck/index.html` when creating a new HTML
  deck unless the user provided a stronger template.
- Put a registered layout recipe on every slide with `data-layout`.
- Include hidden `<aside class="notes">` per slide when the deck is for a live
  talk or training.

## Suggested Structure

```html
<main class="deck" data-deck>
  <section class="slide layout-cover" data-slide="1" data-layout="cover">...</section>
  <section class="slide layout-split" data-slide="2" data-layout="split">...</section>
</main>
```

## CSS Rules

- Define a small design token set at `:root`.
- Use stable slide dimensions with `aspect-ratio: 16 / 9`.
- Avoid layout shifts on hover or navigation.
- Do not use decorative gradient blobs or generic bokeh backgrounds.
- Keep text sizes fixed by role, not by viewport width.
- Avoid system/default fonts for display type unless matching a supplied brand
  system. Choose typography deliberately and load or bundle it reliably.
- Use the template component classes before inventing new one-off CSS:
  `.chrome`, `.kicker`, `.display`, `.lead`, `.panel`, `.metric`,
  `.stage-visual`, `.device-frame`, `.feature-grid`, `.visual-frame`,
  `.map-frame`, `.callout`, `.statement`, `.takeaway-table`, `.timeline`,
  `.quote`, `.gallery`, and `.tag`.
- Keep raw color values inside token declarations; slide CSS should consume tokens.
- Make screenshots and images part of the recipe, not decorative background filler.

## Layout Contract

- Use only recipes from `layout-recipes.md` unless the source material requires a
  custom page.
- For custom pages, name the recipe clearly in `data-layout` and keep the same
  token, spacing, and motif system.
- Avoid more than two consecutive slides with the same `data-layout`.
- Avoid text-only slides except `section`, `statement`, `quote`, and deliberate
  close pages.
- Prefer `product-stage`, `hero-media`, `metric`, and `feature-grid` when the
  user asks for a modern/keynote feel.

## Verification

Run:

```bash
node scripts/html_tool.mjs inspect path/to/index.html --out verification.json
```

Then inspect or screenshot the deck in a browser when available.
Treat `low_layout_variety`, `text_only_slide_found`, and `bullet_dump_risk`
warnings as design issues to fix unless the user asked for a plain outline.
Treat `keyboard_navigation_not_obvious`, `missing_16_9_stage_hint`, and
`display_none_slide_switching_risk` as structural issues for browser-presented
decks.
Also check keyboard navigation, notes visibility, fixed 16:9 framing, and
desktop plus narrow viewport screenshots when browser tools are available.
