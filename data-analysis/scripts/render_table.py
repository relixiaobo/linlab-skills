#!/usr/bin/env python3
"""Render a house-styled HTML table from a data file + a JSON spec.

Like charts, tables are never hand-written. A spec describes per-column
treatment — number/currency/percent formatting, sign coloring (green +, red −),
heatmap shading, in-cell sparklines (nanoplots), spanners — and this script
emits an HTML fragment that `build_report.py` inlines into a finding's
`table_html` slot. Solves what markdown tables cannot: conditional color,
heatmaps, and sparklines.

Example:
  python3 render_table.py \\
    --data analysis_runs/<id>/guardrails.csv \\
    --spec analysis_runs/<id>/guardrails.spec.json \\
    --out analysis_runs/<id>/tables/guardrails.html

Spec (all keys optional):
  { "rowname": "metric",
    "columns": ["metric","control","treatment","lift","p","trend"],
    "labels":  {"control":"Control","p":"p-value"},
    "spanners":[{"label":"Arm","columns":["control","treatment"]}],
    "format":  {"control":{"type":"percent","decimals":1},
                "lift":{"type":"percent","decimals":1,"sign":true},
                "rev":{"type":"currency","currency":"USD","decimals":0},
                "n":{"type":"integer"}},
    "sign_color": ["lift"],
    "heatmap": [{"columns":["p"],"palette":["#059669","#FFFFFF"],"domain":[0,0.1]}],
    "nanoplot": [{"column":"trend","type":"line"}],   # cell values: "8 9 11 12"
    "source_note": "..." }
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import pandas as pd
except ImportError as exc:  # pragma: no cover
    raise SystemExit("pandas is required: pip install pandas") from exc

try:
    from great_tables import GT, loc, style
except ImportError as exc:  # pragma: no cover
    raise SystemExit("great-tables is required: pip install great-tables polars") from exc

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _tableio import read_table  # noqa: E402
from _tablestyle import BAD, GOOD, MUTED, nanoplot_house, style_house  # noqa: E402


def apply_format(gt, col: str, fmt: dict):
    kind = fmt.get("type", "number")
    decimals = fmt.get("decimals", 2)
    sign = fmt.get("sign", False)
    if kind == "percent":
        return gt.fmt_percent(columns=[col], decimals=decimals, force_sign=sign)
    if kind == "currency":
        return gt.fmt_currency(columns=[col], currency=fmt.get("currency", "USD"), decimals=decimals)
    if kind == "integer":
        return gt.fmt_integer(columns=[col])
    return gt.fmt_number(columns=[col], decimals=decimals, force_sign=sign)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--spec", type=Path, help="JSON spec (see module docstring)")
    parser.add_argument("--title", default="")
    parser.add_argument("--subtitle", default="")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    spec = json.loads(args.spec.read_text(encoding="utf-8")) if args.spec else {}
    df = read_table(args.data)

    rowname = spec.get("rowname")
    columns = spec.get("columns")
    if columns:
        if rowname and rowname not in columns:
            columns = [rowname, *columns]
        missing = [c for c in columns if c not in df.columns]
        if missing:
            raise SystemExit(f"Columns not in data: {', '.join(missing)}")
        df = df[columns]

    gt = GT(df, rowname_col=rowname) if rowname else GT(df)

    title = args.title or spec.get("title", "")
    subtitle = args.subtitle or spec.get("subtitle", "")
    if title:
        gt = gt.tab_header(title=title, subtitle=subtitle or None)

    for col, fmt in spec.get("format", {}).items():
        if col in df.columns:
            gt = apply_format(gt, col, fmt)

    for np_spec in spec.get("nanoplot", []):
        col = np_spec["column"]
        if col in df.columns:
            gt = gt.fmt_nanoplot(columns=col, plot_type=np_spec.get("type", "line"), options=nanoplot_house())

    for sp in spec.get("spanners", []):
        gt = gt.tab_spanner(label=sp["label"], columns=sp["columns"])

    labels = spec.get("labels")
    if labels:
        try:
            gt = gt.cols_label(cases=labels)
        except TypeError:  # older great_tables
            gt = gt.cols_label(**labels)

    for hm in spec.get("heatmap", []):
        gt = gt.data_color(
            columns=hm["columns"],
            palette=hm.get("palette", ["#FFFFFF", "#4F46E5"]),
            domain=hm.get("domain"),
            reverse=hm.get("reverse", False),
            na_color="#FFFFFF",
            autocolor_text=True,
        )

    for col in spec.get("sign_color", []):
        if col not in df.columns:
            continue
        nums = pd.to_numeric(df[col], errors="coerce")  # robust to numpy/string types
        pos = [i for i, v in enumerate(nums) if pd.notna(v) and v > 0]
        neg = [i for i, v in enumerate(nums) if pd.notna(v) and v < 0]
        if pos:
            gt = gt.tab_style(style=style.text(color=GOOD, weight="bold"), locations=loc.body(columns=[col], rows=pos))
        if neg:
            gt = gt.tab_style(style=style.text(color=BAD, weight="bold"), locations=loc.body(columns=[col], rows=neg))

    if spec.get("source_note"):
        gt = gt.tab_source_note(source_note=spec["source_note"])

    gt = style_house(gt)
    if subtitle:
        gt = gt.tab_style(style=style.text(color=MUTED), locations=loc.subtitle())

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(gt.as_raw_html(), encoding="utf-8")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
