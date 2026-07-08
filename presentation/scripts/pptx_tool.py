#!/usr/bin/env python3
"""Portable PPTX inspection helper for the presentation skill."""

from __future__ import annotations

import argparse
import json
import posixpath
import re
import sys
import zipfile
from pathlib import Path
from typing import Any, Optional
from xml.etree import ElementTree as ET

PLACEHOLDER_RE = re.compile(r"\b(lorem|ipsum|todo|placeholder|sample|dummy|xxxx)\b", re.I)
PAGE_NUMBER_RE = re.compile(r"^\s*(\d{1,4})(?:\s*/\s*(\d{1,4}))?\s*$")
CLOSING_RE = re.compile("(thank\\s*you|terima\\s*kasih|\u8c22\u8c22|q\\s*&\\s*a|questions?)", re.I)
DATE_LABEL_RE = re.compile(r"^(?:19\d{2}|20\d{2}|1980s|1990s|2000s|2010s|2020s)\b", re.I)
REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
P_NS = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
A_NS = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
R_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
DEFAULT_SLIDE_SIZE = {"cx": 12192000, "cy": 6858000, "source": "default-16:9"}
EMU_PER_INCH = 914400
OVERFLOW_TOLERANCE_IN = 0.03
TINY_TEXT_PT = 8.0


def read_xml(zf: zipfile.ZipFile, name: str) -> Optional[ET.Element]:
    try:
        return ET.fromstring(zf.read(name))
    except Exception:
        return None


def text_from_xml(root: ET.Element | None) -> str:
    if root is None:
        return ""
    parts = []
    for node in root.iter():
        if node.tag == f"{A_NS}t" and node.text:
            parts.append(node.text)
    return "\n".join(parts)


def collapsed_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def int_attr(node: ET.Element | None, name: str) -> int | None:
    if node is None:
        return None
    value = node.attrib.get(name)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def slide_size_from_presentation(root: ET.Element | None) -> dict[str, int | str]:
    if root is None:
        return dict(DEFAULT_SLIDE_SIZE)
    size = root.find(f"{P_NS}sldSz")
    cx = int_attr(size, "cx")
    cy = int_attr(size, "cy")
    if cx is None or cy is None:
        return dict(DEFAULT_SLIDE_SIZE)
    return {"cx": cx, "cy": cy, "source": "presentation.xml"}


def shape_text_reports(root: ET.Element | None) -> list[dict[str, object]]:
    if root is None:
        return []
    reports = []
    for shape in root.iter(f"{P_NS}sp"):
        text_runs = [node.text for node in shape.iter(f"{A_NS}t") if node.text]
        if not text_runs:
            continue
        text = "\n".join(text_runs)
        one_line = collapsed_text(" ".join(text_runs))
        compact = "".join(part.strip() for part in text_runs if part.strip())
        xfrm = transform_from_node(shape)
        off = xfrm.find(f"{A_NS}off") if xfrm is not None else None
        ext = xfrm.find(f"{A_NS}ext") if xfrm is not None else None
        reports.append(
            {
                "text": text,
                "one_line": one_line,
                "compact": compact,
                "x": int_attr(off, "x"),
                "y": int_attr(off, "y"),
                "cx": int_attr(ext, "cx"),
                "cy": int_attr(ext, "cy"),
            }
        )
    return reports


def emu_to_inches(value: int | None) -> float | None:
    if value is None:
        return None
    return round(value / EMU_PER_INCH, 4)


def slide_dimensions_inches(slide_size: dict[str, int | str]) -> dict[str, float]:
    cx = slide_size.get("cx")
    cy = slide_size.get("cy")
    return {
        "w": round(cx / EMU_PER_INCH, 4) if isinstance(cx, int) else 13.333,
        "h": round(cy / EMU_PER_INCH, 4) if isinstance(cy, int) else 7.5,
    }


def transform_from_node(node: ET.Element) -> ET.Element | None:
    xfrm = node.find(f"{P_NS}xfrm")
    if xfrm is not None:
        return xfrm
    xfrm = node.find(f".//{A_NS}xfrm")
    if xfrm is not None:
        return xfrm
    return node.find(f".//{P_NS}xfrm")


def box_from_node(node: ET.Element) -> dict[str, float] | None:
    xfrm = transform_from_node(node)
    off = xfrm.find(f"{A_NS}off") if xfrm is not None else None
    ext = xfrm.find(f"{A_NS}ext") if xfrm is not None else None
    x = emu_to_inches(int_attr(off, "x"))
    y = emu_to_inches(int_attr(off, "y"))
    w = emu_to_inches(int_attr(ext, "cx"))
    h = emu_to_inches(int_attr(ext, "cy"))
    if x is None or y is None or w is None or h is None:
        return None
    return {"x": x, "y": y, "w": w, "h": h}


def text_runs_from_node(node: ET.Element) -> list[str]:
    return [text.text for text in node.iter(f"{A_NS}t") if text.text]


def font_sizes_from_node(node: ET.Element) -> list[float]:
    sizes = []
    for text_props in node.iter():
        if text_props.tag not in (f"{A_NS}rPr", f"{A_NS}defRPr", f"{A_NS}endParaRPr"):
            continue
        size = int_attr(text_props, "sz")
        if size is not None:
            sizes.append(round(size / 100, 2))
    return sizes


def geometry_name(node: ET.Element) -> str:
    sp_pr = node.find(f"{P_NS}spPr")
    geom = sp_pr.find(f"{A_NS}prstGeom") if sp_pr is not None else None
    return geom.attrib.get("prst", "") if geom is not None else ""


def picture_rid(node: ET.Element) -> str:
    blip = node.find(f".//{A_NS}blip")
    if blip is None:
        return ""
    return blip.attrib.get(f"{R_NS}embed") or blip.attrib.get(f"{R_NS}link") or ""


def table_info_from_node(node: ET.Element) -> dict[str, int] | None:
    table = node.find(f".//{A_NS}tbl")
    if table is None:
        return None
    rows = list(table.findall(f"{A_NS}tr"))
    row_count = len(rows)
    column_count = len(table.findall(f"{A_NS}tblGrid/{A_NS}gridCol"))
    if column_count == 0 and rows:
        column_count = max(len(row.findall(f"{A_NS}tc")) for row in rows)
    cell_count = sum(len(row.findall(f"{A_NS}tc")) for row in rows)
    return {"rows": row_count, "cols": column_count, "cells": cell_count}


def slide_object_reports(
    root: ET.Element | None,
    slide_rels: dict[str, dict[str, str]],
    slide_part: str,
) -> list[dict[str, Any]]:
    if root is None:
        return []

    sp_tree = root.find(f".//{P_NS}spTree")
    children = list(sp_tree) if sp_tree is not None else list(root)
    reports: list[dict[str, Any]] = []
    order = 0

    for child in children:
        if child.tag not in (f"{P_NS}sp", f"{P_NS}pic", f"{P_NS}graphicFrame"):
            continue
        order += 1
        box = box_from_node(child)
        if child.tag == f"{P_NS}sp":
            text_runs = text_runs_from_node(child)
            text = collapsed_text(" ".join(text_runs))
            font_sizes = font_sizes_from_node(child)
            reports.append(
                {
                    "kind": "shape",
                    "order": order,
                    "box": box,
                    "text": text,
                    "text_chars": len(text),
                    "font_min": min(font_sizes) if font_sizes else None,
                    "font_max": max(font_sizes) if font_sizes else None,
                    "geometry": geometry_name(child),
                    "blank": len(text) == 0,
                }
            )
            continue

        if child.tag == f"{P_NS}pic":
            rid = picture_rid(child)
            target = ""
            if rid and rid in slide_rels:
                target = normalized_target(slide_part, slide_rels[rid].get("target", ""))
            reports.append(
                {
                    "kind": "picture",
                    "order": order,
                    "box": box,
                    "rid": rid,
                    "target": target,
                }
            )
            continue

        if child.tag == f"{P_NS}graphicFrame":
            text_runs = text_runs_from_node(child)
            text = collapsed_text(" ".join(text_runs))
            font_sizes = font_sizes_from_node(child)
            table_info = table_info_from_node(child)
            reports.append(
                {
                    "kind": "table" if table_info else "graphicFrame",
                    "order": order,
                    "box": box,
                    "text": text,
                    "text_chars": len(text),
                    "font_min": min(font_sizes) if font_sizes else None,
                    "font_max": max(font_sizes) if font_sizes else None,
                    "table": table_info,
                }
            )

    return reports


def box_area(box: dict[str, float] | None) -> float:
    if not box:
        return 0.0
    return max(0.0, box["w"]) * max(0.0, box["h"])


def intersection_area(a: dict[str, float] | None, b: dict[str, float] | None) -> float:
    if not a or not b:
        return 0.0
    left = max(a["x"], b["x"])
    top = max(a["y"], b["y"])
    right = min(a["x"] + a["w"], b["x"] + b["w"])
    bottom = min(a["y"] + a["h"], b["y"] + b["h"])
    return max(0.0, right - left) * max(0.0, bottom - top)


def overlap_ratio(a: dict[str, float] | None, b: dict[str, float] | None) -> float:
    inter = intersection_area(a, b)
    denom = min(box_area(a), box_area(b))
    if denom <= 0:
        return 0.0
    return round(inter / denom, 4)


def is_full_slide_box(box: dict[str, float] | None, slide_size: dict[str, int | str]) -> bool:
    if not box:
        return False
    dims = slide_dimensions_inches(slide_size)
    tol = OVERFLOW_TOLERANCE_IN
    return (
        box["x"] <= tol
        and box["y"] <= tol
        and box["x"] + box["w"] >= dims["w"] - tol
        and box["y"] + box["h"] >= dims["h"] - tol
    )


def box_overflows_slide(box: dict[str, float] | None, slide_size: dict[str, int | str]) -> bool:
    if not box or is_full_slide_box(box, slide_size):
        return False
    dims = slide_dimensions_inches(slide_size)
    tol = OVERFLOW_TOLERANCE_IN
    return (
        box["x"] < -tol
        or box["y"] < -tol
        or box["x"] + box["w"] > dims["w"] + tol
        or box["y"] + box["h"] > dims["h"] + tol
    )


def union_boxes(boxes: list[dict[str, float]]) -> dict[str, float] | None:
    if not boxes:
        return None
    left = min(box["x"] for box in boxes)
    top = min(box["y"] for box in boxes)
    right = max(box["x"] + box["w"] for box in boxes)
    bottom = max(box["y"] + box["h"] for box in boxes)
    return {
        "x": round(left, 4),
        "y": round(top, 4),
        "w": round(right - left, 4),
        "h": round(bottom - top, 4),
        "right": round(right, 4),
        "bottom": round(bottom, 4),
    }


def content_bbox_from_objects(
    objects: list[dict[str, Any]],
    slide_size: dict[str, int | str],
) -> dict[str, float] | None:
    boxes = []
    dims = slide_dimensions_inches(slide_size)
    for obj in objects:
        box = obj.get("box")
        if not isinstance(box, dict) or is_full_slide_box(box, slide_size):
            continue
        kind = obj.get("kind")
        text = collapsed_text(str(obj.get("text", "")))
        if kind == "shape":
            if not text:
                continue
            if PAGE_NUMBER_RE.match(text) and box["y"] > dims["h"] * 0.78:
                continue
        elif kind not in ("picture", "table", "graphicFrame"):
            continue
        boxes.append(box)
    return union_boxes(boxes)


def crowded_table_reason(obj: dict[str, Any]) -> str | None:
    table = obj.get("table")
    if not isinstance(table, dict):
        return None
    rows = int(table.get("rows", 0))
    cols = int(table.get("cols", 0))
    min_font = obj.get("font_min")
    if rows >= 9 and cols >= 6:
        return "too_many_rows_and_columns"
    if rows >= 12:
        return "too_many_rows"
    if cols >= 8 and rows >= 7:
        return "too_many_columns"
    if isinstance(min_font, (int, float)) and min_font < 9 and rows >= 6 and cols >= 5:
        return "small_font_dense_table"
    return None


def object_text_preview(obj: dict[str, Any], limit: int = 120) -> str:
    return str(obj.get("text", ""))[:limit]


def timeline_many_nodes_warning(
    slide_index: int,
    objects: list[dict[str, Any]],
    slide_size: dict[str, int | str],
) -> dict[str, Any] | None:
    date_labels = []
    for obj in objects:
        if obj.get("kind") != "shape":
            continue
        text = collapsed_text(str(obj.get("text", "")))
        box = obj.get("box")
        if not text or not isinstance(box, dict):
            continue
        if DATE_LABEL_RE.match(text):
            date_labels.append({"text": text[:40], "box": box, "order": obj.get("order")})

    if len(date_labels) < 8:
        return None

    dims = slide_dimensions_inches(slide_size)
    y_values = [item["box"]["y"] for item in date_labels]
    x_values = [item["box"]["x"] for item in date_labels]
    same_band = max(y_values) - min(y_values) <= 1.2
    wide_span = max(x_values) - min(x_values) >= dims["w"] * 0.65
    if not (same_band or wide_span):
        return None
    return {
        "slide": slide_index,
        "date_label_count": len(date_labels),
        "labels": [item["text"] for item in date_labels[:12]],
        "reason": "timeline_has_many_single_row_nodes",
    }


def preview_is_section_like(preview_text: str) -> bool:
    preview = collapsed_text(preview_text).lower()
    if not preview:
        return False
    return (
        preview.startswith("part ")
        or preview.startswith("section ")
        or preview.startswith("\u76ee \u5f55")
        or preview.startswith("\u76ee\u5f55")
        or "table of contents" in preview
    )


def is_section_like_slide(report: dict[str, Any]) -> bool:
    return preview_is_section_like(str(report.get("text_preview", "")))


def section_picture_collision_warnings(
    slide_index: int,
    slide_preview: str,
    objects: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not preview_is_section_like(slide_preview):
        return []

    warnings = []
    text_shapes = [
        obj
        for obj in objects
        if obj["kind"] == "shape" and obj.get("text_chars", 0) > 0
    ]
    pictures = [obj for obj in objects if obj["kind"] == "picture"]
    for picture in pictures:
        for text_shape in text_shapes:
            if picture["order"] <= text_shape["order"]:
                continue
            ratio = overlap_ratio(picture.get("box"), text_shape.get("box"))
            if ratio < 0.1:
                continue
            warnings.append(
                {
                    "slide": slide_index,
                    "picture_order": picture["order"],
                    "shape_order": text_shape["order"],
                    "ratio": ratio,
                    "picture": picture.get("target", ""),
                    "text": object_text_preview(text_shape, 120),
                    "reason": "picture_above_section_text",
                }
            )
    return warnings


def sparse_stub_warning(
    report: dict[str, Any],
    next_report: dict[str, Any] | None,
    total_slides: int,
) -> dict[str, Any] | None:
    index = int(report.get("index", 0))
    preview = collapsed_text(str(report.get("text_preview", "")))
    if index in (1, total_slides) or not preview:
        return None
    if CLOSING_RE.search(preview) or is_section_like_slide(report):
        return None
    if report.get("table_count", 0) or report.get("picture_count", 0) or report.get("chart_count", 0):
        return None
    if int(report.get("text_chars", 0)) >= 90:
        return None
    content_bbox = report.get("content_bbox")
    if isinstance(content_bbox, dict) and float(content_bbox.get("bottom", 0.0)) > 2.7:
        return None
    if next_report is None:
        return None
    next_has_payload = (
        int(next_report.get("table_count", 0)) > 0
        or int(next_report.get("picture_count", 0)) > 0
        or int(next_report.get("text_chars", 0)) > 160
    )
    if not next_has_payload:
        return None
    return {
        "slide": index,
        "next_slide": next_report.get("index"),
        "text": preview[:120],
        "reason": "sparse_title_or_stub_before_content_slide",
    }


def closing_slide_not_last_warning(report: dict[str, Any], total_slides: int) -> dict[str, Any] | None:
    index = int(report.get("index", 0))
    if index >= total_slides:
        return None
    preview = collapsed_text(str(report.get("text_preview", "")))
    if not CLOSING_RE.search(preview):
        return None
    if int(report.get("text_chars", 0)) > 220:
        return None
    return {
        "slide": index,
        "expected_last_slide": total_slides,
        "text": preview[:120],
        "reason": "closing_slide_before_end_of_deck",
    }


def layout_warnings_for_slide(
    slide_index: int,
    objects: list[dict[str, Any]],
    slide_size: dict[str, int | str],
) -> dict[str, list[dict[str, Any]]]:
    warnings = {
        "shape_overflows": [],
        "picture_overflows": [],
        "table_overflows": [],
        "crowded_tables": [],
        "tiny_text": [],
        "text_picture_overlaps": [],
        "blank_shape_over_pictures": [],
        "full_slide_picture_over_text": [],
    }

    text_shapes = [obj for obj in objects if obj["kind"] in ("shape", "table") and obj.get("text_chars", 0) > 0]
    blank_shapes = [obj for obj in objects if obj["kind"] == "shape" and obj.get("blank")]
    pictures = [obj for obj in objects if obj["kind"] == "picture"]
    tables = [obj for obj in objects if obj["kind"] == "table"]

    for obj in objects:
        if box_overflows_slide(obj.get("box"), slide_size):
            entry = {
                "slide": slide_index,
                "order": obj["order"],
                "box": obj.get("box"),
            }
            if obj["kind"] == "picture":
                entry["target"] = obj.get("target", "")
                warnings["picture_overflows"].append(entry)
            elif obj["kind"] == "table":
                table = obj.get("table") or {}
                entry["rows"] = table.get("rows")
                entry["cols"] = table.get("cols")
                entry["text"] = object_text_preview(obj, 80)
                warnings["table_overflows"].append(entry)
            else:
                entry["text"] = object_text_preview(obj, 80)
                warnings["shape_overflows"].append(entry)

        font_min = obj.get("font_min")
        if isinstance(font_min, (int, float)) and font_min < TINY_TEXT_PT and obj.get("text_chars", 0) > 0:
            warnings["tiny_text"].append(
                {
                    "slide": slide_index,
                    "order": obj["order"],
                    "kind": obj.get("kind"),
                    "font_min": font_min,
                    "text": object_text_preview(obj, 120),
                }
            )

    for table_obj in tables:
        reason = crowded_table_reason(table_obj)
        if reason is None:
            continue
        table = table_obj.get("table") or {}
        warnings["crowded_tables"].append(
            {
                "slide": slide_index,
                "order": table_obj["order"],
                "rows": table.get("rows"),
                "cols": table.get("cols"),
                "font_min": table_obj.get("font_min"),
                "box": table_obj.get("box"),
                "reason": reason,
            }
        )

    for picture in pictures:
        for text_shape in text_shapes:
            if picture["order"] <= text_shape["order"]:
                continue
            ratio = overlap_ratio(picture.get("box"), text_shape.get("box"))
            if ratio < 0.15:
                continue
            warnings["text_picture_overlaps"].append(
                {
                    "slide": slide_index,
                    "picture_order": picture["order"],
                    "shape_order": text_shape["order"],
                    "ratio": ratio,
                    "picture": picture.get("target", ""),
                    "text": str(text_shape.get("text", ""))[:120],
                }
            )

    for shape in blank_shapes:
        for picture in pictures:
            if shape["order"] <= picture["order"]:
                continue
            ratio = overlap_ratio(shape.get("box"), picture.get("box"))
            if ratio < 0.85:
                continue
            warnings["blank_shape_over_pictures"].append(
                {
                    "slide": slide_index,
                    "shape_order": shape["order"],
                    "picture_order": picture["order"],
                    "ratio": ratio,
                    "picture": picture.get("target", ""),
                    "shape_geometry": shape.get("geometry", ""),
                }
            )

    for picture in pictures:
        if not is_full_slide_box(picture.get("box"), slide_size):
            continue
        covered_text = [
            shape
            for shape in text_shapes
            if picture["order"] > shape["order"] and overlap_ratio(picture.get("box"), shape.get("box")) >= 0.15
        ]
        if covered_text:
            warnings["full_slide_picture_over_text"].append(
                {
                    "slide": slide_index,
                    "picture_order": picture["order"],
                    "picture": picture.get("target", ""),
                    "covered_text_shapes": len(covered_text),
                }
            )

    return warnings


def page_number_candidate(shape: dict[str, object], slide_size: dict[str, int | str]) -> dict[str, object] | None:
    slide_width = slide_size.get("cx")
    slide_height = slide_size.get("cy")
    x = shape.get("x")
    y = shape.get("y")
    cy = shape.get("cy") or 0
    if not isinstance(slide_height, int) or not isinstance(y, int) or not isinstance(cy, int):
        return None
    if y + cy < int(slide_height * 0.72):
        return None

    texts = [
        str(shape.get("one_line") or ""),
        str(shape.get("compact") or ""),
        collapsed_text(str(shape.get("text") or "")),
    ]
    for text in texts:
        match = PAGE_NUMBER_RE.match(text)
        if not match:
            continue
        number = int(match.group(1))
        total = int(match.group(2)) if match.group(2) else None
        if total is None:
            if not isinstance(slide_width, int) or not isinstance(x, int):
                continue
            if x < int(slide_width * 0.65):
                continue
        return {
            "text": text,
            "number": number,
            "total": total,
            "x": x,
            "y": y,
        }
    return None


def page_number_matches(candidate: dict[str, object], index: int, total_slides: int) -> bool:
    if candidate.get("number") != index:
        return False
    total = candidate.get("total")
    return total in (None, total_slides)


def rels_for(zf: zipfile.ZipFile, rels_name: str) -> dict[str, dict[str, str]]:
    root = read_xml(zf, rels_name)
    if root is None:
        return {}
    rels = {}
    for rel in root.findall(f"{REL_NS}Relationship"):
        rid = rel.attrib.get("Id")
        if rid:
            rels[rid] = {
                "type": rel.attrib.get("Type", ""),
                "target": rel.attrib.get("Target", ""),
                "mode": rel.attrib.get("TargetMode", ""),
            }
    return rels


def normalized_target(source_part: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join(posixpath.dirname(source_part), target))


def inspect_pptx(path: Path) -> dict:
    result = {
        "file": str(path),
        "ok": False,
        "errors": [],
        "warnings": [],
        "slides": [],
        "slide_size": {},
        "media_count": 0,
        "chart_count": 0,
        "notes_count": 0,
        "placeholder_hits": [],
        "missing_relationship_targets": [],
        "image_only_slide_candidates": [],
        "page_number_candidate_mismatches": [],
        "shape_overflows": [],
        "picture_overflows": [],
        "table_overflows": [],
        "crowded_tables": [],
        "tiny_text": [],
        "timeline_many_nodes": [],
        "sparse_stub_slides": [],
        "closing_slide_not_last": [],
        "text_picture_overlaps": [],
        "section_picture_collisions": [],
        "blank_shape_over_pictures": [],
        "full_slide_picture_over_text": [],
        "layout_warning_summary": {},
    }

    if not path.exists():
        result["errors"].append("file_not_found")
        return result
    if path.suffix.lower() != ".pptx":
        result["errors"].append("not_pptx")
        return result

    try:
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
            result["media_count"] = len([name for name in names if name.startswith("ppt/media/")])
            result["chart_count"] = len([name for name in names if name.startswith("ppt/charts/")])
            result["notes_count"] = len([name for name in names if name.startswith("ppt/notesSlides/") and name.endswith(".xml")])

            required = ["[Content_Types].xml", "ppt/presentation.xml", "ppt/_rels/presentation.xml.rels"]
            for name in required:
                if name not in names:
                    result["errors"].append(f"missing:{name}")
            if result["errors"]:
                return result

            pres = read_xml(zf, "ppt/presentation.xml")
            slide_size = slide_size_from_presentation(pres)
            result["slide_size"] = slide_size
            pres_rels = rels_for(zf, "ppt/_rels/presentation.xml.rels")

            slide_ids = []
            if pres is not None:
                for sld_id in pres.iter(f"{P_NS}sldId"):
                    rid = sld_id.attrib.get(f"{R_NS}id")
                    if rid:
                        slide_ids.append(rid)
            total_slides = len(slide_ids)

            for index, rid in enumerate(slide_ids, start=1):
                rel = pres_rels.get(rid, {})
                target = rel.get("target", "")
                slide_part = normalized_target("ppt/presentation.xml", target) if target else ""
                slide_report = {
                    "index": index,
                    "rid": rid,
                    "part": slide_part,
                    "text_chars": 0,
                    "text_preview": "",
                    "placeholder_hits": [],
                    "relationship_count": 0,
                    "picture_count": 0,
                    "table_count": 0,
                    "shape_count": 0,
                    "chart_count": 0,
                    "notes": False,
                    "page_number_candidates": [],
                    "content_bbox": None,
                    "min_font_size": None,
                    "layout_warning_count": 0,
                }
                if not slide_part or slide_part not in names:
                    result["missing_relationship_targets"].append({"from": "ppt/presentation.xml", "rid": rid, "target": target})
                    result["slides"].append(slide_report)
                    continue

                slide_root = read_xml(zf, slide_part)
                text = text_from_xml(slide_root)
                slide_report["text_chars"] = len(text)
                slide_report["text_preview"] = collapsed_text(text)[:300]
                if slide_root is not None:
                    slide_report["shape_count"] = len(list(slide_root.iter(f"{P_NS}sp")))
                hits = sorted(set(match.group(0).lower() for match in PLACEHOLDER_RE.finditer(text)))
                slide_report["placeholder_hits"] = hits
                for hit in hits:
                    result["placeholder_hits"].append({"slide": index, "text": hit})

                rels_name = str(Path(slide_part).parent / "_rels" / f"{Path(slide_part).name}.rels")
                slide_rels = rels_for(zf, rels_name)
                slide_report["relationship_count"] = len(slide_rels)
                for rel_id, slide_rel in slide_rels.items():
                    rel_type = slide_rel.get("type", "")
                    if rel_type.endswith("/notesSlide"):
                        slide_report["notes"] = True
                    if rel_type.endswith("/chart"):
                        slide_report["chart_count"] += 1
                    if slide_rel.get("mode") == "External":
                        continue
                    rel_target = slide_rel.get("target", "")
                    resolved = normalized_target(slide_part, rel_target)
                    if resolved not in names:
                        result["missing_relationship_targets"].append({"from": slide_part, "rid": rel_id, "target": rel_target})

                slide_objects = slide_object_reports(slide_root, slide_rels, slide_part)
                pictures = [obj for obj in slide_objects if obj["kind"] == "picture"]
                tables = [obj for obj in slide_objects if obj["kind"] == "table"]
                font_sizes = [
                    obj.get("font_min")
                    for obj in slide_objects
                    if isinstance(obj.get("font_min"), (int, float)) and obj.get("text_chars", 0) > 0
                ]
                slide_report["picture_count"] = len(pictures)
                slide_report["table_count"] = len(tables)
                slide_report["min_font_size"] = min(font_sizes) if font_sizes else None
                slide_report["content_bbox"] = content_bbox_from_objects(slide_objects, slide_size)
                slide_report["pictures"] = [
                    {
                        "order": obj["order"],
                        "target": obj.get("target", ""),
                        "box": obj.get("box"),
                    }
                    for obj in pictures
                ]
                slide_report["tables"] = [
                    {
                        "order": obj["order"],
                        "rows": (obj.get("table") or {}).get("rows"),
                        "cols": (obj.get("table") or {}).get("cols"),
                        "box": obj.get("box"),
                        "font_min": obj.get("font_min"),
                    }
                    for obj in tables
                ]
                slide_layout_warnings = layout_warnings_for_slide(index, slide_objects, slide_size)
                slide_report["layout_warning_count"] = sum(len(items) for items in slide_layout_warnings.values())
                for key, items in slide_layout_warnings.items():
                    result[key].extend(items)
                timeline_warning = timeline_many_nodes_warning(index, slide_objects, slide_size)
                if timeline_warning:
                    result["timeline_many_nodes"].append(timeline_warning)
                    slide_report["layout_warning_count"] += 1
                section_picture_warnings = section_picture_collision_warnings(
                    index,
                    str(slide_report["text_preview"]),
                    slide_objects,
                )
                if section_picture_warnings:
                    result["section_picture_collisions"].extend(section_picture_warnings)
                    slide_report["layout_warning_count"] += len(section_picture_warnings)

                if slide_report["text_chars"] < 20 and slide_report["picture_count"] >= 1 and slide_report["shape_count"] <= 1:
                    result["image_only_slide_candidates"].append(index)

                candidates = []
                for shape in shape_text_reports(slide_root):
                    candidate = page_number_candidate(shape, slide_size)
                    if candidate:
                        candidates.append(candidate)
                slide_report["page_number_candidates"] = candidates
                if candidates and not any(page_number_matches(candidate, index, total_slides) for candidate in candidates):
                    result["page_number_candidate_mismatches"].append(
                        {
                            "slide": index,
                            "expected": str(index),
                            "candidates": [candidate["text"] for candidate in candidates],
                        }
                    )

                result["slides"].append(slide_report)

            for pos, slide_report in enumerate(result["slides"]):
                next_report = result["slides"][pos + 1] if pos + 1 < len(result["slides"]) else None
                sparse_warning = sparse_stub_warning(slide_report, next_report, total_slides)
                if sparse_warning:
                    result["sparse_stub_slides"].append(sparse_warning)
                    slide_report["layout_warning_count"] = int(slide_report.get("layout_warning_count", 0)) + 1
                closing_warning = closing_slide_not_last_warning(slide_report, total_slides)
                if closing_warning:
                    result["closing_slide_not_last"].append(closing_warning)
                    slide_report["layout_warning_count"] = int(slide_report.get("layout_warning_count", 0)) + 1

            if not result["slides"]:
                result["warnings"].append("no_slides_found")
            result["layout_warning_summary"] = {
                "shape_overflows": len(result["shape_overflows"]),
                "picture_overflows": len(result["picture_overflows"]),
                "table_overflows": len(result["table_overflows"]),
                "crowded_tables": len(result["crowded_tables"]),
                "tiny_text": len(result["tiny_text"]),
                "timeline_many_nodes": len(result["timeline_many_nodes"]),
                "sparse_stub_slides": len(result["sparse_stub_slides"]),
                "closing_slide_not_last": len(result["closing_slide_not_last"]),
                "text_picture_overlaps": len(result["text_picture_overlaps"]),
                "section_picture_collisions": len(result["section_picture_collisions"]),
                "blank_shape_over_pictures": len(result["blank_shape_over_pictures"]),
                "full_slide_picture_over_text": len(result["full_slide_picture_over_text"]),
            }
            if result["placeholder_hits"]:
                result["warnings"].append("placeholder_text_found")
            if result["missing_relationship_targets"]:
                result["warnings"].append("missing_relationship_targets")
            if result["image_only_slide_candidates"]:
                result["warnings"].append("image_only_slide_candidates")
            if result["page_number_candidate_mismatches"]:
                result["warnings"].append("page_number_candidate_mismatches")
            if result["shape_overflows"]:
                result["warnings"].append("shape_overflows")
            if result["picture_overflows"]:
                result["warnings"].append("picture_overflows")
            if result["table_overflows"]:
                result["warnings"].append("table_overflows")
            if result["crowded_tables"]:
                result["warnings"].append("crowded_tables")
            if result["tiny_text"]:
                result["warnings"].append("tiny_text")
            if result["timeline_many_nodes"]:
                result["warnings"].append("timeline_many_nodes")
            if result["sparse_stub_slides"]:
                result["warnings"].append("sparse_stub_slides")
            if result["closing_slide_not_last"]:
                result["warnings"].append("closing_slide_not_last")
            if result["text_picture_overlaps"]:
                result["warnings"].append("text_picture_overlaps")
            if result["section_picture_collisions"]:
                result["warnings"].append("section_picture_collisions")
            if result["blank_shape_over_pictures"]:
                result["warnings"].append("blank_shape_over_pictures")
            if result["full_slide_picture_over_text"]:
                result["warnings"].append("full_slide_picture_over_text")
            result["ok"] = len(result["errors"]) == 0 and len(result["missing_relationship_targets"]) == 0
            return result
    except zipfile.BadZipFile:
        result["errors"].append("bad_zip")
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a PPTX package.")
    sub = parser.add_subparsers(dest="command", required=True)
    inspect_cmd = sub.add_parser("inspect", help="Inspect PPTX package structure.")
    inspect_cmd.add_argument("pptx")
    inspect_cmd.add_argument("--out", default="-")
    args = parser.parse_args()

    report = inspect_pptx(Path(args.pptx))
    data = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out == "-":
        print(data)
    else:
        Path(args.out).write_text(data + "\n", encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
