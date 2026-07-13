# Verification

Verification follows the route. Studio proves communication quality, factual
fidelity, export fidelity, and declared preservation. Surgeon proves the listed
change and the absence of unintended changes.

## Studio Gates

### Accuracy

- Every factual or quantitative claim resolves to accepted evidence.
- Dates, definitions, units, caveats, citations, quotes, and branded assets are
  preserved.
- Post-cutoff sources are limited to declared retrospective use.
- A constrained redesign verifies every preservation-matrix rule and slide
  binding.

### Aesthetic

Review prototypes and the full deck at contact-sheet and full-size views. Score
1-5, but let any blocking 1 or 2 veto the average:

- content-specific concept;
- message hierarchy;
- composition and focal point;
- typography and asset quality;
- information design;
- rhythm and coherence;
- craft and export polish.

A strong Studio deck should reach at least 4 in each category. Revise when the
hardest slide is materially weaker than the cover, the visual device is generic,
or the sequence accumulates pages without building and resolving an argument.

### Runtime And Export

- HTML inspection has no errors, placeholders, broken local assets, visible
  notes, nested slides, or missing fixed-stage geometry.
- Browser render has no console or request failures.
- Every expected slide is rendered.
- PPTX passes the technical gate.
- HTML/PPTX comparison has no blocking fidelity mismatch.
- Notes and links survive when requested.
- Editability evidence reports native, SVG, raster, semantic table/chart, and
  full-slide raster counts with limitations.

Pixel comparison is evidence for large visual drift, not proof of beauty.
Inspect text wrapping, crop, hierarchy, alignment, density, and coherence with
human visual judgment.

## Surgeon Gates

- The target was unique before editing and matches the intended result after.
- The old value is absent at the target.
- Package changes are restricted to manifest-authorized parts.
- Object/content diffs contain only expected changes.
- No new technical regression appears against the baseline.
- A rendered sanity check shows no local visual damage.

Any unexplained package, relationship, object, text, geometry, animation, notes,
or metadata change fails the edit.

## Delivery Evidence

Keep a final verification report compatible with
`assets/schemas/verification-report.schema.json`. Reference the Studio brief or
edit manifest, preservation matrix when applicable, evidence report, render
manifest, contact sheet, visual comparison, PPTX gate, editability report, and
remaining limitations. Do not mark final status passed while a required gate
is failed or an error remains open.
