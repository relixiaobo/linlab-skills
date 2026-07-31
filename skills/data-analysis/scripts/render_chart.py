#!/usr/bin/env python3
"""Render a house-styled chart from a Vega-Lite template + a data file.

The skill never hand-writes chart code. It picks one of the templates in
`assets/charts/templates/`, maps the dataset's real columns onto the template's
canonical role fields (x, y, series, value, group, ...), and this script:

  1. merges the house theme (`assets/charts/theme.json`) under the spec,
  2. injects the data,
  3. prunes encodings/layers whose role columns were not supplied,
  4. renders to static SVG (default), PNG, or a self-contained interactive HTML.

SVG is the default on purpose: self-contained, offline, prints clean, no JS
runtime, identical on every device. The same spec can later be rendered
interactive (--format html) with zero changes — the spec is the durable asset.

Example:
  python3 render_chart.py \\
    --template time-trend \\
    --data analysis_runs/<id>/revenue.csv \\
    --map x=order_date,y=revenue,series=channel \\
    --title "Revenue by channel" \\
    --subtitle "USD · 2024-01..2024-06 · n=18,204" \\
    --out analysis_runs/<id>/charts/revenue_trend.svg
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import numpy as np
    import pandas as pd
except ImportError as exc:  # pragma: no cover
    raise SystemExit("pandas is required: pip install pandas") from exc

try:
    import vl_convert as vlc
except ImportError as exc:  # pragma: no cover
    raise SystemExit("vl-convert-python is required: pip install vl-convert-python") from exc

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _tableio import read_table  # noqa: E402

ASSETS = Path(__file__).resolve().parent.parent / "assets" / "charts"


def parse_map(spec: str) -> dict:
    """Parse 'role=col,role=col' into {role: col}."""
    mapping = {}
    for pair in spec.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if "=" not in pair:
            raise SystemExit(f"Bad --map entry '{pair}', expected role=column")
        role, col = pair.split("=", 1)
        mapping[role.strip()] = col.strip()
    return mapping


def to_records(df: "pd.DataFrame", mapping: dict) -> tuple[list, set]:
    """Rename real columns to role fields, keep only those, return JSON records."""
    missing = [c for c in mapping.values() if c not in df.columns]
    if missing:
        raise SystemExit(f"Columns not found in data: {', '.join(missing)}")
    sub = df[list(mapping.values())].rename(columns={v: k for k, v in mapping.items()})
    num = sub.select_dtypes(include="number")
    n_inf = int(np.isinf(num.to_numpy(dtype="float64", na_value=np.nan)).sum()) if num.size else 0
    if n_inf:
        print(f"warning: {n_inf} infinite value(s) in mapped data — they become nulls and are "
              f"NOT plotted; the chart silently omits them", file=sys.stderr)
    records = json.loads(sub.to_json(orient="records", date_format="iso"))
    return records, set(mapping.keys())


def deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, val in override.items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], val)
        else:
            out[key] = val
    return out


def load_theme() -> dict:
    theme = json.loads((ASSETS / "theme.json").read_text(encoding="utf-8"))
    return {k: v for k, v in theme.items() if not k.startswith("$")}


def _layer_cols(layer: dict, main_cols: set, ann_cols: set) -> tuple[set, bool]:
    data = layer.get("data")
    if isinstance(data, dict) and data.get("name") == "annotations":
        return ann_cols, True
    return main_cols, False


def _prune_encoding(enc: dict, cols: set) -> None:
    for channel in list(enc.keys()):
        chan_spec = enc[channel]
        if isinstance(chan_spec, dict) and "field" in chan_spec and chan_spec["field"] not in cols:
            del enc[channel]


def prune(spec: dict, main_cols: set, ann_cols: set) -> None:
    """Drop encodings referencing roles that were not supplied, and dead layers."""
    if "encoding" in spec:
        _prune_encoding(spec["encoding"], main_cols)

    if "layer" not in spec:
        return

    kept = []
    for layer in spec["layer"]:
        cols, is_annotation = _layer_cols(layer, main_cols, ann_cols)
        if is_annotation and not ann_cols:
            continue
        enc = layer.get("encoding", {})
        _prune_encoding(enc, cols | main_cols)
        mark = layer.get("mark")
        mtype = mark.get("type") if isinstance(mark, dict) else mark
        channels = set(enc.keys())
        # Drop a layer that lost the encoding it depends on. Guard each rule
        # with `enc` so a layer that legitimately inherits the top-level
        # encoding (its own `encoding` is empty) is never dropped.
        if mtype == "text" and "text" not in channels:
            continue
        if mtype == "rule" and enc and "x" not in channels:
            # rules here are vertical refs (x datum) or x..x2 intervals — no x is dead
            continue
        if mtype in {"line", "point", "bar"} and enc and not ({"x", "y"} & channels):
            continue
        kept.append(layer)
    spec["layer"] = kept


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--template", required=True, help="template name, e.g. time-trend")
    parser.add_argument("--data", type=Path, required=True, help="csv/tsv/parquet/json/xlsx")
    parser.add_argument("--map", required=True, help="role=column,role=column (canonical roles per template; see references/visualization-assets/charts.md)")
    parser.add_argument("--annotations", type=Path, help="optional second table for annotation layers")
    parser.add_argument("--annotations-map", default="", help="role=column for the annotations table, e.g. at=date,label=note")
    parser.add_argument("--title", default="", help="chart title")
    parser.add_argument("--subtitle", default="", help="subtitle — put units, filters, date range, sample size here")
    parser.add_argument("--width", type=int, help="override chart width")
    parser.add_argument("--height", type=int, help="override chart height")
    parser.add_argument("--format", choices=["svg", "png", "html"], default="svg")
    parser.add_argument("--scale", type=float, default=2.0, help="PNG scale factor")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    template_path = ASSETS / "templates" / f"{args.template}.vl.json"
    if not template_path.exists():
        available = sorted(p.stem for p in (ASSETS / "templates").glob("*.vl.json"))
        raise SystemExit(f"Unknown template '{args.template}'. Available: {', '.join(available)}")
    spec = json.loads(template_path.read_text(encoding="utf-8"))

    df = read_table(args.data)
    main_records, main_cols = to_records(df, parse_map(args.map))
    if len(main_records) > 5000:
        print(f"warning: inlining {len(main_records):,} rows into the chart — output will be large; "
              f"pre-aggregate or sample before plotting (and note it)", file=sys.stderr)

    ann_records, ann_cols = [], set()
    if args.annotations and args.annotations_map:
        ann_df = read_table(args.annotations)
        ann_records, ann_cols = to_records(ann_df, parse_map(args.annotations_map))

    spec["datasets"] = {"main": main_records}
    if ann_records:
        spec["datasets"]["annotations"] = ann_records

    prune(spec, main_cols, ann_cols)

    spec["config"] = deep_merge(load_theme(), spec.get("config", {}))

    title = spec.get("title", {})
    if isinstance(title, dict):
        if args.title:
            title["text"] = args.title
        if args.subtitle:
            title["subtitle"] = args.subtitle
        else:
            title.pop("subtitle", None)
        if not title.get("text"):
            spec.pop("title", None)
    if args.width:
        spec["width"] = args.width
    if args.height:
        spec["height"] = args.height

    spec_json = json.dumps(spec)
    args.out.parent.mkdir(parents=True, exist_ok=True)

    if args.format == "svg":
        args.out.write_text(vlc.vegalite_to_svg(spec_json), encoding="utf-8")
    elif args.format == "png":
        args.out.write_bytes(vlc.vegalite_to_png(spec_json, scale=args.scale))
    else:
        try:
            html = vlc.vegalite_to_html(spec_json, bundle=True)
        except AttributeError as exc:  # pragma: no cover
            raise SystemExit("This vl-convert build has no vegalite_to_html; upgrade vl-convert-python") from exc
        args.out.write_text(html, encoding="utf-8")

    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
