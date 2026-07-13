# Theme Selection

Themes control visual grammar: color behavior, type character, shape language,
spacing, and media posture. They do not determine the argument sequence or
force a fixed page roster.

Treat `assets/themes/index.json` as the catalog authority. Inspect it with:

```bash
node scripts/studio_tool.mjs themes
```

Each theme package contains executable `tokens.css` and content-specific
guidance in `design.md`. Select from audience, topic, evidence density, venue,
asset availability, brand constraints, and export risk. Record at least one
adaptation in the Studio brief.

Do not ask the user to choose among several rendered directions unless a real
preference cannot be inferred. Resolve that preference with the smallest useful
decision artifact.

Before full production, answer:

- What visual idea could only have come from this content?
- What recurring device improves explanation or memory?
- Which default was changed to serve the evidence?
- Does the system work on the hardest real-content slide?
- Could the deck be rethemed for an unrelated topic without redesign?

If the last answer is yes, the theme is still a skin. Revise the concept.
