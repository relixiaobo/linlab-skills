# PPTX Surgeon

Use Surgeon for a localized edit when the original PPTX package is the artifact
of record and everything outside the requested change must remain unchanged.
Do not route this work through HTML or a library that loads and saves the whole
deck.

## Manifest First

Create an edit manifest compatible with
`assets/schemas/edit-manifest.schema.json`. For every operation record:

- stable slide and object/text-run target;
- `expectedBefore` and `intendedAfter`;
- exact expected match count;
- field being changed;
- allowed package parts and why they may change;
- permitted side effects;
- verification scopes.

The preservation policy is
`preserve-everything-except-listed-operations`. An allowed part is not blanket
permission to alter unrelated XML inside that part.

## Procedure

1. Keep the source file unchanged and work on a copy.
2. Inspect and gate the source. Record pre-existing warnings as baseline state.
3. Resolve the target to exactly the expected object or run. Stop when it is
   missing or ambiguous.
4. Patch only the minimum OOXML/OPC parts. Preserve unknown XML, relationships,
   ordering, formatting, geometry, animation, notes, media, metadata, masters,
   and themes outside the manifest.
5. Assert the intended value and the removal or replacement of the old target.
6. Compare semantic/object snapshots and package hashes.
7. Gate against the baseline and render a visual sanity check.

## Portable Commands

```bash
python3 scripts/pptx_tool.py inspect source.pptx --out before.json
python3 scripts/pptx_tool.py gate source.pptx --out baseline-gate.json
python3 scripts/pptx_tool.py inspect edited.pptx --out after.json
python3 scripts/pptx_tool.py compare before.json after.json --out semantic-diff.json
python3 scripts/pptx_tool.py package-diff source.pptx edited.pptx \
  --allow 'ppt/slides/slide7.xml' --out package-diff.json
python3 scripts/pptx_tool.py gate edited.pptx --baseline before.json --out final-gate.json
```

`compare` proves technical and semantic snapshot differences; package scope is
not verified until the manifest-aware package and target assertions pass.

## Route Boundary

Switch to Studio only when the user authorizes a rebuild, restructure, or
visual redesign where package identity is no longer the contract. A faithful
recreation is still not a precision edit.
