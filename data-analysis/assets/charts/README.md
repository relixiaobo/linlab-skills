# Chart asset library

House-styled, templated charts. **The skill never hand-writes chart code.** It
picks a template, maps the dataset's real columns onto the template's canonical
role fields, and renders with `scripts/render_chart.py`.

Why this design: the Vega-Lite spec is the durable asset. The default render is
static **SVG** — self-contained, offline, prints clean, no JS runtime, identical
on every device. The *same* spec renders interactive (`--format html`, via
vega-embed) with zero changes when a surface benefits. Restyle every chart at
once by editing `theme.json`; never restyle a single template by hand.

## How to render

```
python3 scripts/render_chart.py \
  --template <name> \
  --data <file.csv|tsv|parquet|json|xlsx> \
  --map <role=column,role=column> \
  --title "..." --subtitle "units · filters · date range · sample size" \
  --out analysis_runs/<run_id>/charts/<name>.svg
```

- `--format svg` (default) · `png` · `html` (interactive, self-contained).
- Roles you do not supply are pruned automatically (e.g. omit `ci_low/ci_high`
  and the interval bars disappear; omit `series` and it becomes single-series).
- Put units, filters, date range, and sample size in `--subtitle` — this is how
  the `visualization.md` labeling rule is satisfied.

## Templates and their roles

Required roles are **bold**; the rest are optional and prune cleanly if absent.

| Template | Use for | Roles |
| --- | --- | --- |
| `time-trend` | metric over time, with change-point annotations | **x** (date), **y** (number), series (group); annotations table: **at** (date), **label** |
| `distribution` | shape of one numeric variable | **value** (number), group (overlay by group) |
| `group-comparison` | compare groups with uncertainty (preferred over bars) | **group**, **estimate**, ci_low, ci_high |
| `correlation` | relationship between two numbers + fitted trend | **x**, **y**, group (color) |
| `funnel` | ordered conversion steps | **step**, **count**, order (sort), label (count/rate text) |
| `cohort` | retention / matrix heatmap | **cohort**, **period**, **value** (0–1 rate; text shows `%`) |
| `contribution` | ranked drivers of a change (signed, diverging) | **factor**, **contribution** (signed) |
| `ab-effect` | experiment effect sizes with CI vs a zero line | **metric**, **effect**, ci_low, ci_high, significant |

### Annotations (time-trend)

Pass a second table for change-point markers:

```
  --annotations changes.csv --annotations-map at=event_date,label=event_name
```

Omit it and the annotation rule/label layers prune away.

## Notes / known edges

- `cohort` expects `value` as a rate in `0–1` and formats cells as `%`. For raw
  counts, the `.0%` formatting will mislead — adjust the template or pass rates.
- `ab-effect` pairs with a **guardrail table** (sample sizes, SRM, secondary
  metrics). That belongs in the table layer (great_tables), not this chart.
- Default sizing fits 3–8 categories / a half-year of monthly points. For very
  wide data, pass `--width/--height`.
- The house font is Inter with a system-sans fallback; charts render fine
  without Inter installed, just with the fallback face.
