# Executable Theme Library

Themes control visual grammar: color behavior, type character, shape language,
spacing, elevation, and media posture. They do not determine the argument
sequence or force a fixed page roster. Select the narrative archetype first,
then choose the theme and per-slide layouts independently.

Each package under `assets/themes/<id>/` contains:

- `tokens.css`: executable color, type, spacing, geometry, and selective
  component overrides;
- `design.md`: character, signature moves, and adaptation guidance;
- `preview.webp`: a four-frame rendered contact sheet covering opening, normal
  structure, real media, and close;
- metadata in `assets/themes/index.json`, including fit, avoid cases, energy,
  density, asset bias, CJK fallbacks, and export risks.

Run `node scripts/studio_tool.mjs themes` to inspect metadata and
`node scripts/studio_tool.mjs init <dir> --theme <id> --archetype <id>` to
create a project. Maintainers regenerate all previews with
`node scripts/render_theme_previews.mjs`.

## Selection

Select a theme internally from audience, topic, evidence density, venue,
delivery mode, asset availability, brand constraints, and export risk. Record
the choice and at least one content-specific adaptation in the Studio brief.

Do not ask the user to choose among multiple rendered directions unless a real
preference changes the result and cannot be inferred, such as conservative
board authority versus expressive conference storytelling. In that case, show
the smallest decision artifact needed to resolve the tradeoff.

## Professional Core

- `analytical-ledger`: research, strategy, investment, board, and dense
  evidence. Default for professional analytical work.
- `institutional-editorial`: policy, history, institutional narrative, and
  executive thought leadership.
- `modern-swiss`: product, transformation, operating models, conferences, and
  short live talks.
- `technical-blueprint`: engineering, energy, architecture, operations, and
  technical diligence.

## Complementary Themes

- `stage-keynote`: product reveals, major announcements, town halls, and
  high-impact live presentations.
- `photo-editorial`: architecture, places, culture, portfolios, brand stories,
  and real-image-led case studies.
- `soft-humanist`: teaching, training, healthcare, people and culture,
  public-interest, and approachable consumer work.
- `expressive-neo-grid`: creative pitches, founder talks, brand reviews,
  conferences, and design-led research.
- `dark-technology`: AI, developer tools, data products, cybersecurity,
  technical launches, and interface-heavy demos.

## Theme Versus Other Layers

- A research report may use `analytical-ledger`, `photo-editorial`, or
  `dark-technology` depending on its evidence and audience.
- A product launch may use `stage-keynote`, `modern-swiss`, or
  `soft-humanist` depending on the product and venue.
- `data-journalism` is usually a layout and evidence posture inside an
  analytical theme, not automatically another palette.
- `pitch-deck`, `course-module`, and `weekly-report` are narrative archetypes,
  not themes.

## Adaptation Test

Before full production, answer:

- What visual idea could only have come from this content?
- What recurring device improves explanation or memory?
- Which theme token or default composition was changed to serve that idea?
- Does the system work on the hardest real-content slide?
- Could the deck be rethemed for an unrelated topic without redesign?

If the last answer is yes, the theme is still a skin. Revise the concept.
