# Asset Intake

Use this reference for photographs, screenshots, logos, maps, diagrams, charts,
documents, videos, and assets extracted from an existing PPTX.

## Asset Program

Before assigning layouts, classify the deck's visual material:

- **Real evidence**: supplied or sourced photographs, screenshots, maps,
  documents, logos, facilities, equipment, or interfaces that the audience must
  inspect.
- **Conceptual visual**: generated or abstract imagery that creates context,
  emotion, or an explanatory metaphor without pretending to be evidence.
- **Constructed visual**: charts, diagrams, timelines, tables, and maps built
  from verified data.
- **Intentional reset**: a text-led slide whose sparseness is part of the
  narrative rhythm.

For a visual subject, do not let constructed visuals replace every real or
conceptual view. Include media-bearing slides when the audience needs to see
the place, object, person, interface, document, or operating environment itself.
For an analytical subject, use media only when it carries evidence or useful
context; never add generic stock photography to satisfy a quota.

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
- Use vector originals for logos, maps, and diagrams when reliable.
- Use `contain` for screenshots, documents, maps, charts, and logos that must be
  inspected; use `cover` only for photography with an intentional crop.
- Never stretch an identity-bearing asset.
- Keep labels and UI text legible at presentation size.
- Reject unexplained watermarks, compression artifacts, soft images, and
  decorative stock imagery that does not carry the subject.

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
