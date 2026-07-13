---
name: presentation
description: Create, rebuild, edit, analyze, or verify slide decks, PowerPoint/PPTX files, and HTML presentations. Use Studio for new or rebuilt decks where beauty and communication impact are primary. Use Surgeon for precise edits to an existing PPTX when unintended changes are unacceptable. Do not use when the primary artifact is a long-form document, workbook, or PDF-native report.
---

# Presentation

Choose one route. Studio creates and rebuilds from canonical HTML. Surgeon
patches the original PPTX package. Share verification standards, not a
production pipeline.

## Studio

Use Studio for a new deck, rewritten story, full restructure, or redesign. An
existing PPTX may supply facts and assets, but it is not incrementally
transformed. Keep `deck.html` as the production source of truth.

Read `references/studio.md`. Read `references/evidence.md` for research-heavy
work, `references/asset-intake.md` when real assets matter, and
`references/export.md` before production. Inspect narrative, theme, and layout
catalogs through the Studio tool; read their references only when the choice is
not obvious.

### Workflow

1. Record audience, objective, use setting, density, outputs, factual cutoff,
   and actual editability needs. For constrained redesigns, inspect the source
   and make the preservation matrix authoritative.
2. Select one narrative archetype, adapt one theme, and choose a small core
   layout set from the real content shapes. Review the outline first only when
   the user requests it.
3. Prototype real content covering the opening, normal rhythm, hardest
   data/diagram/media case, and close. Fix weak frames before expanding.
4. Build the complete HTML deck with stable slide ids, explicit layouts, local
   assets, deterministic geometry, and hidden speaker notes.
5. Inspect and render HTML, compile the requested PPTX, run the technical gate,
   and complete at least one fix-and-recheck pass. Run Office-rendered PPTX
   comparison only for high-risk slides or when the user requests strict export
   fidelity.

Use local HTML, CSS, and SVG. Add a project-local visualization library only
when the content requires it. Compile each element to the strongest faithful
representation available: native PowerPoint objects, SVG, then bounded raster
fallback. Report actual editability coverage rather than calling the whole deck
editable.

### Commands

```bash
node {baseDir}/scripts/studio_tool.mjs init work/deck \
  --theme analytical-ledger --archetype research-report
cd work/deck && npm ci
node studio.mjs doctor .
node studio.mjs check .
node studio.mjs render-html .
node studio.mjs compile .
```

For strict export fidelity, or when charts, dense CJK text, media, or unusual
CSS are central to the deck, run `node studio.mjs compare .` when an Office
renderer is available. Its absence is a verification limitation, not a reason
to make LibreOffice or Poppler a core Studio dependency.

Use `themes`, `archetypes`, and `layouts` to inspect the executable catalogs.

## Surgeon

Use Surgeon for a localized edit when the original PPTX is the artifact of
record.

- Keep the input unchanged and patch a copy.
- Define stable targets, `expectedBefore`, `intendedAfter`, exact match count,
  allowed package parts, and permitted side effects in an edit manifest.
- Patch the minimum OOXML/OPC parts. Do not use HTML or a deck-wide load/save
  cycle.
- Prove the requested result and the absence of unrelated package, content,
  object, relationship, geometry, notes, animation, theme, or metadata changes.

Read `references/precision-edit.md` and `references/verification.md`. Read
`references/asset-intake.md` only when media provenance matters.

```bash
python3 {baseDir}/scripts/pptx_tool.py inspect source.pptx --out before.json
python3 {baseDir}/scripts/pptx_tool.py gate source.pptx --out baseline-gate.json
python3 {baseDir}/scripts/pptx_tool.py compare before.json after.json --out diff.json
python3 {baseDir}/scripts/pptx_tool.py package-diff source.pptx edited.pptx \
  --allow 'ppt/slides/slide7.xml' --out package-diff.json
python3 {baseDir}/scripts/pptx_tool.py gate edited.pptx \
  --baseline before.json --out final-gate.json
```

## Non-Negotiables

- Never invent facts, numbers, citations, screenshots, or branded evidence.
- Treat archetypes, themes, and layouts as priors, not fill-in templates.
- Let rendered review veto a weak prototype or full deck.
- Prove every declared preservation rule in a constrained Studio rebuild.
- Prove target and package scope in Surgeon.
- Reserve width for CJK text and inspect final PPTX wrapping.
- Deliver a PPTX only after `pptx_tool.py gate` passes or report the blocker.
- Treat HTML visual review as the default beauty gate. Treat pixel comparison
  as optional export evidence, not aesthetic judgment.

Keep one authority per concern: Studio brief for decisions, `deck.html` for
visible content and notes, evidence ledger for claims, preservation matrix for
constrained rebuilds, edit manifest for Surgeon scope, and verification report
for delivery evidence. Use schemas in `assets/schemas/`.

## References

- `references/studio.md`: Studio source roles, workflow, and beauty standard.
- `references/evidence.md`: claims, definitions, cutoff, and bindings.
- `references/asset-intake.md`: provenance and asset quality.
- `references/narrative-archetypes.md`: archetype selection rules.
- `references/theme-library.md`: theme selection and adaptation.
- `references/layout-library.md`: content-to-layout rules.
- `references/export.md`: browser readiness, compilation, and comparison.
- `references/precision-edit.md`: minimum-change OOXML editing.
- `references/verification.md`: route-specific delivery gates.
