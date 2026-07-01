"""Shared table I/O: read tabular files and render a DataFrame to text.

One reader used by render_chart / render_table / triangulate (was duplicated in
all three). `DataFrame.to_markdown` requires the optional `tabulate` package, so
`render` falls back to a built-in markdown renderer when it is absent.
"""

from __future__ import annotations

from pathlib import Path


def read_table(path):
    """Read csv/tsv/parquet/json/xlsx into a DataFrame. Pandas imported lazily."""
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("pandas is required: pip install pandas") from exc
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in {".tsv", ".tab"}:
        return pd.read_csv(path, sep="\t")
    if suffix in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    if suffix == ".json":
        return pd.read_json(path)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    raise SystemExit(f"Unsupported data format: {path.suffix}")


def _cell(value: object) -> str:
    if value is None:
        return ""
    # NaN is the only value not equal to itself.
    if isinstance(value, float) and value != value:
        return ""
    return str(value)


def _markdown_fallback(df) -> str:
    cols = [str(c) for c in df.columns]
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    rows = [
        "| " + " | ".join(_cell(v) for v in record) + " |"
        for record in df.itertuples(index=False, name=None)
    ]
    return "\n".join([header, sep, *rows])


def render(df, fmt: str = "markdown") -> str:
    """Render `df` as 'markdown', 'csv', or 'json'."""
    if fmt == "json":
        return df.to_json(orient="records", indent=2, force_ascii=False)
    if fmt == "csv":
        return df.to_csv(index=False)
    try:
        return df.to_markdown(index=False)
    except ImportError:
        return _markdown_fallback(df)
