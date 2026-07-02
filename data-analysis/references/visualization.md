# Visualization

Choose charts that reveal the actual data structure and decision.

## How to produce charts

Do **not** hand-write chart code. Use the templated asset library: pick a
template, map your real columns onto its role fields, and render.

```
python3 {baseDir}/scripts/render_chart.py \
  --template time-trend \
  --data analysis_runs/<run_id>/series.csv \
  --map x=order_date,y=revenue,series=channel \
  --title "Revenue by channel" --subtitle "USD · 2024-01..06 · n=18,204" \
  --out analysis_runs/<run_id>/charts/revenue_trend.svg
```

Default output is static SVG (self-contained, prints clean, no JS); `--format
png` for raster, `--format html` for a self-contained interactive version from
the same spec. Templates and their role fields are documented in
`{baseDir}/references/visualization-assets/charts.md`. The eight templates map
1:1 to the Defaults below. Restyle every chart at once by editing
`{baseDir}/assets/charts/theme.json`.

## Defaults

Each default has a ready template (→ name) in the asset library.

- Time trend: line chart with annotated change points. → `time-trend`
- Distribution: histogram, density, box/violin, or ECDF. → `distribution`
- Group comparison: dot/interval chart with CI; bar only when categories are few and baseline matters. → `group-comparison`
- Correlation: scatter with trend and sample size; heatmaps only for many variables. → `correlation`
- Funnel: ordered step chart with counts and rates. → `funnel`
- Cohort: matrix heatmap with clear cohort and age axes. → `cohort`
- Root cause: contribution waterfall or ranked contribution bars. → `contribution`
- A/B test: effect size with CI plus guardrail table. → `ab-effect` (chart) + table

## Rules

- Plot the result, not only raw inputs.
- Label units, filters, date range, and sample size.
- Avoid dual axes unless unavoidable.
- Use log scale only when explained.
- Do not hide outliers without showing sensitivity.
- Save charts under `analysis_runs/<run_id>/charts/`.
