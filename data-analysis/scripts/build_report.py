#!/usr/bin/env python3
"""Build a self-contained HTML analysis report from a JSON context.

The report format. Charts and tables are referenced by path and **inlined**, so the
result is a single shareable file (no external assets, works offline, prints
clean). Paths resolve relative to --base (default: the context file's folder).

Context (all optional unless noted):
  title, eyebrow, subtitle, direct_answer, method, privacy,
  sources, date_range, grain, filters, limitations (str or list),
  generated, artifacts: [{label, path}],
  audience: "consumer" (default — method/verification collapsed) | "analyst"
            (everything expanded for audit). Visibility only; the rigor is
            always done. trust: a one-line reassurance shown as a badge.
  kpis: [{label, value, delta?, tone?: good|bad|neutral}],
  findings: [{
    claim|title (one required), body?, evidence?,
    chart?: "charts/x.svg",       # inlined as <svg>
    table?: "tables/x.html",      # inlined as HTML
    verification?, caveat?,
    status?: verified|refuted|needs_followup   # colors the verification chip
  }]

Example:
  python3 build_report.py \\
    --context analysis_runs/<id>/report_context.json \\
    --out analysis_runs/<id>/report.html
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from jinja2 import Environment, FileSystemLoader
except ImportError as exc:  # pragma: no cover
    raise SystemExit("jinja2 is required: pip install jinja2") from exc

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "templates" / "report.html"


def inline_svg(path: Path) -> str:
    """Read an SVG and strip any XML prolog so it embeds cleanly in HTML."""
    text = path.read_text(encoding="utf-8")
    start = text.find("<svg")
    return text[start:] if start != -1 else text


def resolve(base: Path, ref: str) -> Path:
    p = Path(ref)
    return p if p.is_absolute() else base / p


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--base", type=Path, help="root for chart/table paths (default: context folder)")
    parser.add_argument("--template", type=Path, default=TEMPLATE, help="override the HTML template")
    args = parser.parse_args()

    context = json.loads(args.context.read_text(encoding="utf-8"))
    base = args.base or args.context.resolve().parent

    for finding in context.get("findings", []):
        chart_ref = finding.get("chart")
        if chart_ref:
            chart_path = resolve(base, chart_ref)
            if not chart_path.exists():
                raise SystemExit(f"Chart not found for finding '{finding.get('claim', finding.get('title', '?'))}': {chart_path}")
            finding["chart_svg"] = inline_svg(chart_path)
        table_ref = finding.get("table")
        if table_ref:
            table_path = resolve(base, table_ref)
            if not table_path.exists():
                raise SystemExit(f"Table not found: {table_path}")
            finding["table_html"] = table_path.read_text(encoding="utf-8")

    # Trust badge is driven by ACTUAL verification, never by "findings exist".
    # A finding counts as verified only if status == verified AND verification is non-empty.
    findings = context.get("findings", [])
    context["_n_findings"] = len(findings)
    context["_n_verified"] = sum(
        1 for f in findings
        if f.get("status") == "verified" and (f.get("verification") or "").strip()
    )
    context["_verified_all"] = context["_n_findings"] > 0 and context["_n_verified"] == context["_n_findings"]

    env = Environment(
        loader=FileSystemLoader(str(args.template.parent)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template(args.template.name)
    html = template.render(**context)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html, encoding="utf-8")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
