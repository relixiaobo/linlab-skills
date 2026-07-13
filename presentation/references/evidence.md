# Evidence And Claims

Use `assets/schemas/evidence-ledger.schema.json` for source-heavy decks. The
ledger separates factual authority from slide prose so research can be audited
without scraping citations back out of the layout.

## Ledger Model

- `cutoffDate`: latest state the deck may claim.
- `sources`: authority, publisher, publication/access dates, local or remote
  location, rights, and status.
- `claims`: statement, kind, verification status, structured value, source
  references, definitions, caveats, conflicts, and optional slide use.
- `definitions`: metric scope, unit, and calculation meaning.
- `assets`: local file, source, factual role, rights, and transformations.

Bind visible HTML to ledger ids:

```html
<strong data-claim-id="claim-production-2025">...</strong>
<span data-source-id="source-regulator-annual-report">Source: ...</span>
<img data-asset-id="asset-basin-map" src="assets/basin-map.svg" alt="...">
```

Multiple ids may be separated by spaces or commas.

## Cutoff Discipline

- A claim's `relevantAt` date must not exceed `cutoffDate`.
- A source published after the cutoff is blocked unless it is explicitly marked
  `cutoffUse: retrospective`; that source may verify pre-cutoff state but must
  not introduce later events.
- Keep plans, estimates, interpretations, and observed facts distinct.
- Preserve source units and definitions. Do not add unlike liquids and gas
  measures without a declared conversion.
- Record material source conflicts instead of silently selecting the more
  convenient number.

## Source Quality

Prefer, in order, the authority closest to the claim: regulator or government,
operator/company filing, technical or academic primary work, established
industry research, then media or secondary summaries. A verified claim should
not depend only on candidate sources without a review warning.

For current, regulated, financial, safety, reserves, production, project, or
transaction claims, capture the exact source passage or table location. Record
definitions and caveats beside the claim, not only in a final bibliography.

## Validation

```bash
python3 scripts/evidence_tool.py check evidence-ledger.json \
  --html deck.html --out qa/evidence-report.json
```

The checker validates ids, references, cutoff dates, rejected sources/claims,
local assets, HTML bindings, `usedBy` declarations, and slides that contain
metric-like values without claim bindings. Warnings require review; errors
block factual delivery.
