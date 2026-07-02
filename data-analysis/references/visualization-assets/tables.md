# Table asset library

House-styled HTML tables via [great_tables](https://posit-dev.github.io/great-tables/).
**Tables are never hand-written** — a JSON spec describes per-column treatment and
`scripts/render_table.py` emits an HTML fragment that `build_report.py` inlines
into a finding's `table_html` slot.

Unlike charts there is no fixed taxonomy of table types, so the asset is one
spec-driven builder plus the house style in `scripts/_tablestyle.py` (edit that
one file to restyle every table; keep its palette in sync with
`assets/charts/theme.json`).

These solve what markdown tables cannot: **conditional color, heatmaps, and
in-cell sparklines.** For plain tabular output, a markdown table is still fine —
reach for this only when a column needs visual encoding.

## How to render

```
python3 scripts/render_table.py \
  --data analysis_runs/<id>/guardrails.csv \
  --spec analysis_runs/<id>/guardrails.spec.json \
  --title "Experiment guardrails" --subtitle "treatment vs control · n/arm" \
  --out analysis_runs/<id>/tables/guardrails.html
```

Then reference it from the report context: a finding's `"table":
"tables/guardrails.html"`.

## Spec keys (all optional)

| Key | Effect |
| --- | --- |
| `rowname` | column to use as the row label (left stub) |
| `columns` | subset / reorder columns |
| `labels` | `{col: "Pretty Label"}` for headers |
| `spanners` | `[{label, columns}]` grouping headers |
| `format` | per-column `{type: number\|percent\|currency\|integer, decimals, sign, currency}` |
| `sign_color` | columns where positive → green, negative → red (text) |
| `heatmap` | `[{columns, palette, domain, reverse}]` — shade cells by value |
| `nanoplot` | `[{column, type: line\|bar}]` — in-cell sparkline |
| `source_note` | small footnote under the table |

## Recipes

**Guardrail / experiment table** — formats, sign-colored lift, significance
heatmap, trend sparkline:
```json
{ "rowname": "metric",
  "spanners": [{"label":"Arm","columns":["control","treatment"]}],
  "format": {"control":{"type":"percent","decimals":1},
             "lift":{"type":"percent","decimals":1,"sign":true},
             "p":{"type":"number","decimals":3}},
  "sign_color": ["lift"],
  "heatmap": [{"columns":["p"],"palette":["#059669","#FFFFFF"],"domain":[0,0.1]}],
  "nanoplot": [{"column":"trend","type":"line"}] }
```

**Ranked drivers** — magnitude heatmap instead of a chart:
```json
{ "rowname": "factor",
  "format": {"contribution":{"type":"currency","currency":"USD","decimals":0}},
  "heatmap": [{"columns":["contribution"],"palette":["#FEF2F2","#FFFFFF","#ECFDF5"],"domain":[-10000,10000]}] }
```

**Metric × segment** — a heatmap grid (one numeric column per period/segment):
```json
{ "rowname": "segment",
  "format": {"jan":{"type":"percent"},"feb":{"type":"percent"},"mar":{"type":"percent"}},
  "heatmap": [{"columns":["jan","feb","mar"],"palette":["#FFFFFF","#4F46E5"]}] }
```

## Notes / known edges

- **nanoplot** cell values are numbers separated by spaces (`"8 9 11 12"`); needs
  `polars` installed (in requirements). Sparklines are themed to house indigo.
- **`sign_color` is numeric**: positive = green, negative = red. For metrics where
  up is *bad* (churn, refunds, cost), don't use it — use a `heatmap` with a
  reversed palette, or pre-sign the column so the color matches the meaning.
- `data_color` auto-contrasts text on dark cells; pass a 2- or 3-stop `palette`.
- Output is `as_raw_html()` — a self-contained fragment with a scoped `<style>`
  (its own table id), so multiple tables in one report never clash.
