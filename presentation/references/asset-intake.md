# Asset Intake

Use this when a deck references real entities, products, brands, screenshots,
charts, people, places, or current facts.

## Fact Gate

- Verify recent or unstable facts before putting them on slides: product
  availability, version numbers, specs, leadership, prices, regulations, dates,
  market data, and news.
- Prefer primary sources: official sites, docs, filings, press kits, source
  documents, or user-provided material.
- Record the source in the slide plan `evidence` field. Do not convert a fact
  into a decorative number without a source note.
- If facts cannot be verified and the deck depends on them, mark the item as an
  assumption or ask the user for source material.

## Brand And Product Assets

When a brand, product, company, app, venue, or named tool is visible in the
deck, build a small asset inventory before visual design:

- logo: SVG or transparent PNG; required for any visible brand
- product image: required for hardware, consumer goods, packaging, venues, and
  object-focused decks
- UI screenshot: required for apps, SaaS, dashboards, developer tools, and
  software workflows
- brand colors and fonts: useful after logo/product/UI assets are in place
- source charts and tables: use real charts/data when the content depends on
  quantitative evidence

Use official channels first: brand/press pages, product pages, app stores,
official docs, official social accounts, source decks, source PDFs, or the
user's own screenshots. Icon aggregators and favicons are fallbacks for logos,
not replacements for official artwork when official assets are available.

Do not silently replace missing real assets with generic silhouettes, fake UI,
stock atmosphere, decorative SVGs, or invented logos. Use a clearly labeled
placeholder only when the user accepts the asset gap or no source is available.

## Asset Quality

For non-logo media, collect enough candidates to choose well:

- prefer 1600px+ width for slide media; 2000px+ for hero images when possible
- reject low-resolution, watermarked, distorted, outdated, or off-brand images
- prefer two excellent images over many mediocre images
- make every image earn a communication role: evidence, product reveal,
  example, comparison, quote/source context, or emotional beat
- choose stable ratios before layout: 21:9, 16:9, 16:10, 4:3, 3:2, 1:1, 3:4
- reject generic images that conflict with the deck topic, geography, industry,
  audience, or evidence claim

## Asset Layout Roles

Every planned image should have a role before it is inserted:

- `background`: full-bleed or banded visual below text and overlays
- `hero`: dominant slide visual with minimal text
- `right-evidence` or `left-evidence`: split-layout proof beside text
- `map`: geography, route, territory, basin, field, or market context
- `chart`: quantitative evidence
- `thumbnail`: gallery or evidence-wall item
- `callout`: small support image or annotation
- `logo`: brand mark in cover, section, or footer
- `decorative-accepted`: decorative asset explicitly accepted by the user or
  clearly harmless to the message

Also specify fit, slot, and layer:

- fit: contain, cover, stretch, or original
- slot: visual-right, visual-left, hero, map-primary, gallery-tile, footer-logo,
  or another recipe slot
- layer: background, image, overlay, text, logo, or folio

Image insertion must trigger layout selection or relayout. Do not append a
picture onto a finished slide without resizing or moving existing text, cards,
and containers.

## Screenshots

For product screenshots, clarify or infer:

- purpose: faithful display, annotation, beautification, or conceptual redraw
- required fidelity: preserve all text/data, anonymize sensitive content, or
  crop to the relevant state
- target slot: 21:9, 16:10, 16:9, 4:3, 1:1, or full-bleed
- readability: text in the screenshot must remain legible after scaling

Use contain-fit for UI screenshots where text matters. Use cover-fit only for
photography or when the crop is intentionally editorial.

## Asset Manifest

For substantial decks, maintain a short manifest in the working folder:

```markdown
# Asset Manifest

| Asset | Role | Source | Local Path | Notes |
| --- | --- | --- | --- | --- |
| Brand logo | cover, footer | official press kit | assets/logo.svg | dark + light variants |
| Product screenshot | feature reveal | user supplied | assets/feature.png | contains customer data: anonymized |
| Market chart | proof slide | source PDF p.12 | assets/chart-q3.png | cite on slide |
```

Reference local paths from the deck. Do not rely on remote assets for final
delivery unless the user explicitly wants a network-dependent artifact.
