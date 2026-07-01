#!/usr/bin/env python3
"""Profile tabular datasets and write JSON/Markdown outputs."""

from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
import warnings
from pathlib import Path
from typing import Any

try:
    import pandas as pd
except ImportError as exc:  # pragma: no cover
    raise SystemExit("pandas is required: pip install pandas pyarrow openpyxl") from exc


PII_PATTERNS = {
    "email": re.compile(r"(^|[_-])e?mail($|[_-])|email", re.I),
    "phone": re.compile(r"phone|mobile|tel|cell", re.I),
    "government_id": re.compile(r"ssn|passport|national[_-]?id|id[_-]?card", re.I),
    "address": re.compile(r"address|street|zipcode|zip|postal", re.I),
    "name": re.compile(r"(^|[_-])(name|first_name|last_name|full_name)($|[_-])", re.I),
    "secret": re.compile(r"password|token|secret|api[_-]?key|credential", re.I),
}


def json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if hasattr(value, "item"):
        return json_safe(value.item())
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def read_csv_with_fallback(path: Path, sample_rows: int | None = None) -> tuple[pd.DataFrame, str]:
    encodings = ["utf-8", "utf-8-sig", "gb18030", "latin1"]
    last_error: Exception | None = None
    for encoding in encodings:
        try:
            return pd.read_csv(path, encoding=encoding, nrows=sample_rows), encoding
        except UnicodeDecodeError as exc:
            last_error = exc
    raise SystemExit(f"Could not decode CSV {path}: {last_error}")


def load_dataframe(path: Path, sheet: str | None, table: str | None, sample_rows: int | None) -> tuple[pd.DataFrame, dict[str, Any]]:
    suffix = path.suffix.lower()
    meta: dict[str, Any] = {"path": str(path), "format": suffix.lstrip(".")}

    if suffix in {".csv", ".tsv"}:
        sep = "\t" if suffix == ".tsv" else ","
        if sep == ",":
            df, encoding = read_csv_with_fallback(path, sample_rows)
        else:
            df = pd.read_csv(path, sep=sep, nrows=sample_rows)
            encoding = "default"
        meta["encoding"] = encoding
        return df, meta

    if suffix in {".parquet", ".pq"}:
        df = pd.read_parquet(path)
        if sample_rows:
            df = df.head(sample_rows)
        return df, meta

    if suffix in {".json", ".jsonl", ".ndjson"}:
        lines = suffix in {".jsonl", ".ndjson"}
        df = pd.read_json(path, lines=lines)
        if sample_rows:
            df = df.head(sample_rows)
        meta["lines"] = lines
        return df, meta

    if suffix in {".xlsx", ".xls"}:
        excel = pd.ExcelFile(path)
        selected_sheet = sheet or excel.sheet_names[0]
        df = pd.read_excel(path, sheet_name=selected_sheet, nrows=sample_rows)
        meta["sheet"] = selected_sheet
        meta["available_sheets"] = excel.sheet_names
        return df, meta

    if suffix in {".sqlite", ".sqlite3", ".db"}:
        with sqlite3.connect(path) as conn:
            tables = pd.read_sql_query(
                "select name from sqlite_master where type='table' order by name",
                conn,
            )["name"].tolist()
            selected_table = table or (tables[0] if tables else None)
            if not selected_table:
                raise SystemExit(f"No tables found in SQLite database: {path}")
            limit = f" limit {int(sample_rows)}" if sample_rows else ""
            df = pd.read_sql_query(f'select * from "{selected_table}"{limit}', conn)
        meta["table"] = selected_table
        meta["available_tables"] = tables
        return df, meta

    raise SystemExit(f"Unsupported file type: {suffix}")


def pii_flags(column: str) -> list[str]:
    return [name for name, pattern in PII_PATTERNS.items() if pattern.search(column)]


DATE_HINT_RE = re.compile(r"\d{4}\D\d{1,2}\D\d{1,2}|\d{1,2}\D\d{1,2}\D\d{2,4}|\d{1,2}:\d{2}")


def infer_datetime(series: pd.Series) -> dict[str, Any] | None:
    """Best-effort: detect string columns that are really dates and report their range.

    pandas reads dates as object dtype unless told otherwise, so the workflow's
    "date range / timezone" profile item would otherwise be silently missing.
    """
    sample = series.dropna().astype(str)
    if sample.empty:
        return None
    hint_rate = sample.head(500).map(lambda value: bool(DATE_HINT_RE.search(value))).mean()
    if hint_rate < 0.8:
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            parsed = pd.to_datetime(series.dropna(), errors="coerce", format="mixed")
    except Exception:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                parsed = pd.to_datetime(series.dropna(), errors="coerce")
        except Exception:
            return None
    parse_rate = float(parsed.notna().mean()) if len(parsed) else 0.0
    if parse_rate < 0.9:
        return None
    valid = parsed.dropna()
    return {
        "inferred": True,
        "parse_rate": round(parse_rate, 3),
        "min": json_safe(valid.min()) if len(valid) else None,
        "max": json_safe(valid.max()) if len(valid) else None,
    }


def profile_column(series: pd.Series) -> dict[str, Any]:
    non_null = series.dropna()
    result: dict[str, Any] = {
        "dtype": str(series.dtype),
        "null_count": int(series.isna().sum()),
        "null_rate": float(series.isna().mean()) if len(series) else None,
        "non_null_count": int(non_null.shape[0]),
        "unique_count": int(non_null.nunique(dropna=True)),
        "sample_values": [json_safe(v) for v in non_null.head(5).tolist()],
    }

    if pd.api.types.is_numeric_dtype(series):
        desc = non_null.describe()
        result["numeric"] = {key: json_safe(desc.get(key)) for key in ["mean", "std", "min", "25%", "50%", "75%", "max"]}
        if len(non_null) > 0:
            zeros = int((non_null == 0).sum())
            result["zero_count"] = zeros
            result["zero_rate"] = float(zeros / len(non_null))
            q1 = non_null.quantile(0.25)
            q3 = non_null.quantile(0.75)
            iqr = q3 - q1
            if iqr:
                low = q1 - 1.5 * iqr
                high = q3 + 1.5 * iqr
                result["outlier_count_iqr"] = int(((non_null < low) | (non_null > high)).sum())

    elif pd.api.types.is_datetime64_any_dtype(series):
        result["datetime"] = {
            "min": json_safe(non_null.min()) if len(non_null) else None,
            "max": json_safe(non_null.max()) if len(non_null) else None,
        }
    else:
        value_counts = non_null.astype(str).value_counts(dropna=True).head(10)
        result["top_values"] = {str(k): int(v) for k, v in value_counts.items()}
        result["max_length"] = int(non_null.astype(str).map(len).max()) if len(non_null) else 0
        inferred = infer_datetime(non_null)
        if inferred:
            result["datetime"] = inferred

    return result


def build_profile(df: pd.DataFrame, meta: dict[str, Any]) -> dict[str, Any]:
    profile: dict[str, Any] = {
        "meta": meta,
        "shape": {"rows": int(df.shape[0]), "columns": int(df.shape[1])},
        "columns": {},
        "duplicate_rows": int(df.duplicated().sum()) if df.shape[0] else 0,
        "pii_candidates": {},
    }

    for column in df.columns:
        flags = pii_flags(str(column))
        if flags:
            profile["pii_candidates"][str(column)] = flags
        profile["columns"][str(column)] = profile_column(df[column])

    # Surface signals the model would otherwise have to reverse-engineer column by column.
    zero_heavy = []
    datetime_columns = []
    for name, info in profile["columns"].items():
        zero_rate = info.get("zero_rate")
        if zero_rate is not None and zero_rate >= 0.1:
            zero_heavy.append({"column": name, "zero_count": info["zero_count"], "zero_rate": round(zero_rate, 4)})
        if "datetime" in info:
            datetime_columns.append(name)
    if zero_heavy:
        # Heavy zeros in a measurement column often mean "0 == missing"; flag for the analyst.
        profile["zero_heavy_columns"] = sorted(zero_heavy, key=lambda item: item["zero_rate"], reverse=True)
    if datetime_columns:
        profile["datetime_columns"] = datetime_columns

    numeric_df = df.select_dtypes(include="number")
    if numeric_df.shape[1] > 1:
        corr = numeric_df.corr(numeric_only=True).round(4)
        strong_pairs = []
        cols = list(corr.columns)
        for i, left in enumerate(cols):
            for right in cols[i + 1 :]:
                value = corr.loc[left, right]
                if pd.notna(value) and abs(value) >= 0.8:
                    strong_pairs.append({"left": left, "right": right, "correlation": float(value)})
        profile["strong_correlations_abs_ge_0_8"] = strong_pairs

    return profile


def markdown_report(profile: dict[str, Any]) -> str:
    lines = [
        "# Dataset Profile",
        "",
        f"- Source: `{profile['meta']['path']}`",
        f"- Format: `{profile['meta'].get('format', 'unknown')}`",
        f"- Rows: {profile['shape']['rows']}",
        f"- Columns: {profile['shape']['columns']}",
        f"- Duplicate rows: {profile['duplicate_rows']}",
        "",
    ]

    if profile.get("pii_candidates"):
        lines.extend(["## PII Candidates", ""])
        for column, flags in profile["pii_candidates"].items():
            lines.append(f"- `{column}`: {', '.join(flags)}")
        lines.append("")

    if profile.get("zero_heavy_columns"):
        lines.extend([
            "## Possible Missing-as-Zero",
            "",
            "Numeric columns where >=10% of values are exactly 0. If 0 is not a real "
            "measurement (e.g. blood pressure, price, insulin), these zeros are likely a "
            "missing-value code and will bias means/sums. Verify before aggregating.",
            "",
        ])
        for item in profile["zero_heavy_columns"]:
            lines.append(f"- `{item['column']}`: {item['zero_count']} zeros ({item['zero_rate']:.1%})")
        lines.append("")

    lines.extend(["## Columns", ""])
    lines.append("| Column | Type | Nulls | Null rate | Unique | Notes |")
    lines.append("| --- | --- | ---: | ---: | ---: | --- |")
    for column, info in profile["columns"].items():
        notes = []
        if "outlier_count_iqr" in info:
            notes.append(f"IQR outliers: {info['outlier_count_iqr']}")
        zero_rate = info.get("zero_rate")
        if zero_rate is not None and zero_rate >= 0.1:
            notes.append(f"zeros: {info['zero_count']} ({zero_rate:.1%})")
        if "datetime" in info:
            dt = info["datetime"]
            span = f"{dt.get('min')} -> {dt.get('max')}"
            notes.append(f"dates {span}" + (" (inferred)" if dt.get("inferred") else ""))
        if column in profile.get("pii_candidates", {}):
            notes.append("PII candidate")
        null_rate = info["null_rate"]
        null_rate_text = "" if null_rate is None else f"{null_rate:.2%}"
        lines.append(
            f"| `{column}` | `{info['dtype']}` | {info['null_count']} | {null_rate_text} | {info['unique_count']} | {'; '.join(notes)} |"
        )

    strong = profile.get("strong_correlations_abs_ge_0_8") or []
    if strong:
        lines.extend(["", "## Strong Numeric Correlations", ""])
        for item in strong:
            lines.append(f"- `{item['left']}` vs `{item['right']}`: {item['correlation']}")

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--sheet", help="Excel sheet name")
    parser.add_argument("--table", help="SQLite table name")
    parser.add_argument("--sample-rows", type=int, default=None, help="Profile only the first N rows")
    parser.add_argument("--out", type=Path, help="Output prefix or directory")
    args = parser.parse_args()

    df, meta = load_dataframe(args.path, args.sheet, args.table, args.sample_rows)
    profile = build_profile(df, meta)

    if args.out:
        out = args.out
        if out.suffix:
            out.parent.mkdir(parents=True, exist_ok=True)
            json_path = out.with_suffix(".json")
            md_path = out.with_suffix(".md")
        else:
            out.mkdir(parents=True, exist_ok=True)
            json_path = out / "profile.json"
            md_path = out / "profile.md"
        json_path.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")
        md_path.write_text(markdown_report(profile), encoding="utf-8")
        print(f"Wrote {json_path}")
        print(f"Wrote {md_path}")
    else:
        print(json.dumps(profile, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

