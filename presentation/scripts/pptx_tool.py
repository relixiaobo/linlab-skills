#!/usr/bin/env python3
"""Portable PPTX inspection helper for the presentation skill."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
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
MIN_REVIEW_IMAGE_PPI = 120
MIN_SEVERE_IMAGE_PPI = 80
ASPECT_DISTORTION_TOLERANCE = 0.12
SEVERE_CROP_FRACTION = 0.55
GATE_BLOCKING_KEYS = (
    "placeholder_hits",
    "missing_relationship_targets",
    "page_number_candidate_mismatches",
    "shape_overflows",
    "picture_overflows",
    "table_overflows",
    "crowded_tables",
    "tiny_text",
    "timeline_many_nodes",
    "sparse_stub_slides",
    "closing_slide_not_last",
    "text_picture_overlaps",
    "section_picture_collisions",
    "blank_shape_over_pictures",
    "full_slide_picture_over_text",
    "image_aspect_distortions",
    "severe_image_resolution_warnings",
)
GATE_REVIEW_KEYS = (
    "image_only_slide_candidates",
    "image_resolution_warnings",
    "image_crop_warnings",
    "missing_image_dimensions",
)
GATE_BLOCKING_WARNING_NAMES = (
    "no_slides_found",
)
EDIT_REGRESSION_KEYS = (
    "placeholder_hits",
    "missing_relationship_targets",
    "page_number_candidate_mismatches",
    "shape_overflows",
    "picture_overflows",
    "table_overflows",
    "crowded_tables",
    "tiny_text",
    "timeline_many_nodes",
    "sparse_stub_slides",
    "closing_slide_not_last",
    "text_picture_overlaps",
    "section_picture_collisions",
    "blank_shape_over_pictures",
    "full_slide_picture_over_text",
    "image_aspect_distortions",
    "severe_image_resolution_warnings",
    "image_resolution_warnings",
    "image_crop_warnings",
    "missing_image_dimensions",
)


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


def aspect_class(width: int | None, height: int | None) -> str:
    if not width or not height or height <= 0:
        return "unknown"
    ratio = width / height
    if ratio >= 2.2:
        return "panoramic"
    if ratio >= 1.55:
        return "wide"
    if ratio >= 1.18:
        return "landscape"
    if ratio >= 0.85:
        return "square"
    if ratio >= 0.58:
        return "portrait"
    return "tall"


def read_png_size(data: bytes) -> tuple[int, int] | None:
    if len(data) < 24 or not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


def read_gif_size(data: bytes) -> tuple[int, int] | None:
    if len(data) < 10 or data[:6] not in (b"GIF87a", b"GIF89a"):
        return None
    return int.from_bytes(data[6:8], "little"), int.from_bytes(data[8:10], "little")


def read_bmp_size(data: bytes) -> tuple[int, int] | None:
    if len(data) < 26 or not data.startswith(b"BM"):
        return None
    width = int.from_bytes(data[18:22], "little", signed=True)
    height = abs(int.from_bytes(data[22:26], "little", signed=True))
    if width <= 0 or height <= 0:
        return None
    return width, height


def read_jpeg_size(data: bytes) -> tuple[int, int] | None:
    if len(data) < 4 or not data.startswith(b"\xff\xd8"):
        return None
    idx = 2
    sof_markers = set(range(0xC0, 0xD0)) - {0xC4, 0xC8, 0xCC}
    while idx + 3 < len(data):
        if data[idx] != 0xFF:
            idx += 1
            continue
        while idx < len(data) and data[idx] == 0xFF:
            idx += 1
        if idx >= len(data):
            return None
        marker = data[idx]
        idx += 1
        if marker in (0xD8, 0xD9):
            continue
        if marker == 0xDA:
            return None
        if idx + 2 > len(data):
            return None
        length = int.from_bytes(data[idx : idx + 2], "big")
        if length < 2 or idx + length > len(data):
            return None
        if marker in sof_markers and length >= 7:
            height = int.from_bytes(data[idx + 3 : idx + 5], "big")
            width = int.from_bytes(data[idx + 5 : idx + 7], "big")
            return width, height
        idx += length
    return None


def read_webp_size(data: bytes) -> tuple[int, int] | None:
    if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return None
    chunk = data[12:16]
    if chunk == b"VP8X":
        width = 1 + int.from_bytes(data[24:27], "little")
        height = 1 + int.from_bytes(data[27:30], "little")
        return width, height
    if chunk == b"VP8L" and len(data) >= 25 and data[20] == 0x2F:
        b0, b1, b2, b3 = data[21], data[22], data[23], data[24]
        width = 1 + (((b1 & 0x3F) << 8) | b0)
        height = 1 + (((b3 & 0x0F) << 10) | (b2 << 2) | ((b1 & 0xC0) >> 6))
        return width, height
    if chunk == b"VP8 " and len(data) >= 30 and data[23:26] == b"\x9d\x01\x2a":
        width = int.from_bytes(data[26:28], "little") & 0x3FFF
        height = int.from_bytes(data[28:30], "little") & 0x3FFF
        return width, height
    return None


def read_svg_size(data: bytes) -> tuple[int, int] | None:
    try:
        root = ET.fromstring(data)
    except Exception:
        return None
    view_box = root.attrib.get("viewBox") or root.attrib.get("viewbox")
    if view_box:
        parts = re.split(r"[\s,]+", view_box.strip())
        if len(parts) == 4:
            try:
                width = int(round(float(parts[2])))
                height = int(round(float(parts[3])))
                if width > 0 and height > 0:
                    return width, height
            except ValueError:
                pass
    width_text = root.attrib.get("width", "")
    height_text = root.attrib.get("height", "")
    try:
        width = int(round(float(re.sub(r"[^0-9.]+", "", width_text))))
        height = int(round(float(re.sub(r"[^0-9.]+", "", height_text))))
    except ValueError:
        return None
    if width <= 0 or height <= 0:
        return None
    return width, height


def image_info_from_bytes(name: str, data: bytes) -> dict[str, Any]:
    ext = Path(name).suffix.lower().lstrip(".")
    readers = [
        ("png", read_png_size),
        ("jpeg", read_jpeg_size),
        ("gif", read_gif_size),
        ("bmp", read_bmp_size),
        ("webp", read_webp_size),
        ("svg", read_svg_size),
    ]
    size: tuple[int, int] | None = None
    detected = ext or "unknown"
    for fmt, reader in readers:
        size = reader(data)
        if size:
            detected = "jpg" if fmt == "jpeg" else fmt
            break
    width, height = size if size else (None, None)
    info: dict[str, Any] = {
        "format": detected,
        "bytes": len(data),
        "width_px": width,
        "height_px": height,
        "aspect_class": aspect_class(width, height),
    }
    if width and height:
        info["aspect_ratio"] = round(width / height, 4)
    return info


def crop_rect_from_picture(node: ET.Element) -> dict[str, int] | None:
    src_rect = node.find(f".//{A_NS}srcRect")
    if src_rect is None:
        return None
    crop = {
        "l": int_attr(src_rect, "l") or 0,
        "t": int_attr(src_rect, "t") or 0,
        "r": int_attr(src_rect, "r") or 0,
        "b": int_attr(src_rect, "b") or 0,
    }
    return crop if any(crop.values()) else None


def crop_visible_fraction(crop: dict[str, int] | None) -> dict[str, float]:
    if not crop:
        return {"w": 1.0, "h": 1.0, "area": 1.0, "cropped": 0.0}
    visible_w = max(0.01, 1.0 - (crop.get("l", 0) + crop.get("r", 0)) / 100000)
    visible_h = max(0.01, 1.0 - (crop.get("t", 0) + crop.get("b", 0)) / 100000)
    area = visible_w * visible_h
    return {
        "w": round(visible_w, 4),
        "h": round(visible_h, 4),
        "area": round(area, 4),
        "cropped": round(1.0 - area, 4),
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
    media_info: dict[str, dict[str, Any]],
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
            image_info = media_info.get(target, {})
            crop = crop_rect_from_picture(child)
            visible = crop_visible_fraction(crop)
            reports.append(
                {
                    "kind": "picture",
                    "order": order,
                    "box": box,
                    "rid": rid,
                    "target": target,
                    "image": image_info,
                    "crop": crop,
                    "visible_fraction": visible,
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


def picture_display_metrics(picture: dict[str, Any]) -> dict[str, Any]:
    box = picture.get("box")
    image = picture.get("image")
    if not isinstance(box, dict) or not isinstance(image, dict):
        return {}
    width = image.get("width_px")
    height = image.get("height_px")
    if not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0:
        return {}
    visible = picture.get("visible_fraction")
    if not isinstance(visible, dict):
        visible = {"w": 1.0, "h": 1.0, "area": 1.0, "cropped": 0.0}
    visible_w = float(visible.get("w", 1.0))
    visible_h = float(visible.get("h", 1.0))
    display_aspect = box["w"] / box["h"] if box["h"] else 0.0
    image_aspect = width / height
    effective_aspect = (width * visible_w) / (height * visible_h) if visible_h else image_aspect
    ppi_x = (width * visible_w) / box["w"] if box["w"] else 0.0
    ppi_y = (height * visible_h) / box["h"] if box["h"] else 0.0
    return {
        "display_aspect": round(display_aspect, 4),
        "image_aspect": round(image_aspect, 4),
        "effective_image_aspect": round(effective_aspect, 4),
        "aspect_delta": round(abs(display_aspect - effective_aspect) / effective_aspect, 4)
        if effective_aspect
        else 0.0,
        "effective_ppi_x": round(ppi_x, 1),
        "effective_ppi_y": round(ppi_y, 1),
        "effective_ppi_min": round(min(ppi_x, ppi_y), 1),
    }


def picture_asset_warnings_for_slide(
    slide_index: int,
    pictures: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    warnings = {
        "image_aspect_distortions": [],
        "severe_image_resolution_warnings": [],
        "image_resolution_warnings": [],
        "image_crop_warnings": [],
        "missing_image_dimensions": [],
    }
    for picture in pictures:
        image = picture.get("image")
        box = picture.get("box")
        target = picture.get("target", "")
        if not isinstance(image, dict) or not isinstance(box, dict):
            continue
        width = image.get("width_px")
        height = image.get("height_px")
        if target and (not isinstance(width, int) or not isinstance(height, int)):
            warnings["missing_image_dimensions"].append(
                {
                    "slide": slide_index,
                    "picture_order": picture["order"],
                    "picture": target,
                    "format": image.get("format", "unknown"),
                    "reason": "image_dimensions_unavailable",
                }
            )
            continue

        metrics = picture_display_metrics(picture)
        if not metrics:
            continue
        entry = {
            "slide": slide_index,
            "picture_order": picture["order"],
            "picture": target,
            "box": box,
            "image": {
                "width_px": width,
                "height_px": height,
                "aspect_class": image.get("aspect_class", "unknown"),
            },
            "metrics": metrics,
        }

        if metrics["aspect_delta"] > ASPECT_DISTORTION_TOLERANCE:
            warnings["image_aspect_distortions"].append(
                {
                    **entry,
                    "crop": picture.get("crop"),
                    "reason": "display_box_distorts_image_aspect",
                }
            )

        display_area = box_area(box)
        if display_area >= 2.0:
            if metrics["effective_ppi_min"] < MIN_SEVERE_IMAGE_PPI:
                warnings["severe_image_resolution_warnings"].append(
                    {**entry, "reason": "effective_image_resolution_below_severe_threshold"}
                )
            elif metrics["effective_ppi_min"] < MIN_REVIEW_IMAGE_PPI:
                warnings["image_resolution_warnings"].append(
                    {**entry, "reason": "effective_image_resolution_below_review_threshold"}
                )

        visible = picture.get("visible_fraction")
        cropped = float(visible.get("cropped", 0.0)) if isinstance(visible, dict) else 0.0
        if cropped > SEVERE_CROP_FRACTION:
            warnings["image_crop_warnings"].append(
                {
                    **entry,
                    "crop": picture.get("crop"),
                    "visible_fraction": visible,
                    "reason": "large_crop_fraction_requires_visual_review",
                }
            )

    return warnings


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
        "image_aspect_distortions": [],
        "severe_image_resolution_warnings": [],
        "image_resolution_warnings": [],
        "image_crop_warnings": [],
        "missing_image_dimensions": [],
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

    picture_warnings = picture_asset_warnings_for_slide(slide_index, pictures)
    for key, items in picture_warnings.items():
        warnings[key].extend(items)

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
        "image_aspect_distortions": [],
        "severe_image_resolution_warnings": [],
        "image_resolution_warnings": [],
        "image_crop_warnings": [],
        "missing_image_dimensions": [],
        "layout_warning_summary": {},
        "media_dimensions": {},
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
            media_names = sorted(name for name in names if name.startswith("ppt/media/"))
            result["media_count"] = len(media_names)
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
            media_info = {
                name: image_info_from_bytes(name, zf.read(name))
                for name in media_names
            }
            result["media_dimensions"] = media_info

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

                slide_objects = slide_object_reports(slide_root, slide_rels, slide_part, media_info)
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
                        "image": obj.get("image", {}),
                        "crop": obj.get("crop"),
                        "visible_fraction": obj.get("visible_fraction"),
                        "metrics": picture_display_metrics(obj),
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
                "image_aspect_distortions": len(result["image_aspect_distortions"]),
                "severe_image_resolution_warnings": len(result["severe_image_resolution_warnings"]),
                "image_resolution_warnings": len(result["image_resolution_warnings"]),
                "image_crop_warnings": len(result["image_crop_warnings"]),
                "missing_image_dimensions": len(result["missing_image_dimensions"]),
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
            if result["image_aspect_distortions"]:
                result["warnings"].append("image_aspect_distortions")
            if result["severe_image_resolution_warnings"]:
                result["warnings"].append("severe_image_resolution_warnings")
            if result["image_resolution_warnings"]:
                result["warnings"].append("image_resolution_warnings")
            if result["image_crop_warnings"]:
                result["warnings"].append("image_crop_warnings")
            if result["missing_image_dimensions"]:
                result["warnings"].append("missing_image_dimensions")
            result["ok"] = len(result["errors"]) == 0 and len(result["missing_relationship_targets"]) == 0
            return result
    except zipfile.BadZipFile:
        result["errors"].append("bad_zip")
        return result


def count_report_items(report: dict[str, Any], key: str) -> int:
    value = report.get(key)
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        return len(value)
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    return 0


def delivery_gate_report(report: dict[str, Any], include_review: bool = False) -> dict[str, Any]:
    blocking_counts = {
        key: count_report_items(report, key)
        for key in GATE_BLOCKING_KEYS
        if count_report_items(report, key) > 0
    }
    warning_names = set(str(item) for item in report.get("warnings", []) if isinstance(item, str))
    blocking_warning_names = sorted(warning_names.intersection(GATE_BLOCKING_WARNING_NAMES))
    review_counts = {
        key: count_report_items(report, key)
        for key in GATE_REVIEW_KEYS
        if count_report_items(report, key) > 0
    }
    errors = list(report.get("errors", [])) if isinstance(report.get("errors"), list) else []

    passed = not errors and not blocking_counts and not blocking_warning_names
    if include_review and review_counts:
        passed = False

    return {
        "checked": True,
        "passed": passed,
        "blocking_counts": blocking_counts,
        "blocking_warnings": sorted(list(blocking_counts.keys()) + blocking_warning_names),
        "review_counts": review_counts,
        "review_warnings": sorted(review_counts.keys()),
        "error_count": len(errors),
        "errors": errors,
        "message": "passed" if passed else "failed: repair blocking warnings before delivery",
    }


def load_report(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def pptx_part_hashes(path: Path) -> dict[str, dict[str, Any]]:
    with zipfile.ZipFile(path) as zf:
        hashes = {}
        for info in zf.infolist():
            if info.is_dir():
                continue
            data = zf.read(info.filename)
            hashes[info.filename] = {
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        return hashes


def part_allowed(part: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(part, pattern) for pattern in patterns)


def package_diff(before_path: Path, after_path: Path, allow_patterns: list[str]) -> dict[str, Any]:
    before_hashes = pptx_part_hashes(before_path)
    after_hashes = pptx_part_hashes(after_path)
    before_parts = set(before_hashes)
    after_parts = set(after_hashes)

    changes = []
    for part in sorted(before_parts - after_parts):
        changes.append({"part": part, "change": "removed"})
    for part in sorted(after_parts - before_parts):
        changes.append({"part": part, "change": "added", "after": after_hashes[part]})
    for part in sorted(before_parts & after_parts):
        if before_hashes[part]["sha256"] == after_hashes[part]["sha256"]:
            continue
        changes.append(
            {
                "part": part,
                "change": "modified",
                "before": before_hashes[part],
                "after": after_hashes[part],
            }
        )

    allowed = [change for change in changes if part_allowed(str(change["part"]), allow_patterns)]
    unexpected = [change for change in changes if not part_allowed(str(change["part"]), allow_patterns)]
    return {
        "checked": True,
        "passed": not unexpected,
        "before_file": str(before_path),
        "after_file": str(after_path),
        "allow_patterns": allow_patterns,
        "before_part_count": len(before_hashes),
        "after_part_count": len(after_hashes),
        "change_count": len(changes),
        "allowed_change_count": len(allowed),
        "unexpected_change_count": len(unexpected),
        "allowed_changes": allowed,
        "unexpected_changes": unexpected,
        "message": "passed" if not unexpected else "failed: unexpected PPTX package parts changed",
    }


def compare_reports(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_counts = {key: count_report_items(before, key) for key in EDIT_REGRESSION_KEYS}
    after_counts = {key: count_report_items(after, key) for key in EDIT_REGRESSION_KEYS}
    regressions = {
        key: {
            "before": before_counts[key],
            "after": after_counts[key],
            "delta": after_counts[key] - before_counts[key],
        }
        for key in EDIT_REGRESSION_KEYS
        if after_counts[key] > before_counts[key]
    }
    after_errors = list(after.get("errors", [])) if isinstance(after.get("errors"), list) else []
    after_missing_relationships = count_report_items(after, "missing_relationship_targets")
    passed = not regressions and not after_errors and after_missing_relationships == 0
    return {
        "checked": True,
        "passed": passed,
        "before_file": before.get("file", ""),
        "after_file": after.get("file", ""),
        "regression_counts": regressions,
        "after_error_count": len(after_errors),
        "after_missing_relationship_targets": after_missing_relationships,
        "message": "passed" if passed else "failed: edit introduced or retained blocking regressions",
    }


def image_treatment_recommendation(info: dict[str, Any]) -> dict[str, Any]:
    cls = str(info.get("aspect_class", "unknown"))
    if cls == "panoramic":
        return {"default_fit": "cover-or-contain-by-role", "slots": ["hero", "banner", "background"]}
    if cls in ("wide", "landscape"):
        return {"default_fit": "contain-for-detail-cover-for-photo", "slots": ["split", "hero", "image-led"]}
    if cls == "square":
        return {"default_fit": "contain", "slots": ["gallery-tile", "thumbnail", "card"]}
    if cls in ("portrait", "tall"):
        return {"default_fit": "contain-or-vertical-crop", "slots": ["vertical-split", "profile", "side-panel"]}
    return {"default_fit": "inspect-manually", "slots": []}


def inspect_image_paths(paths: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {"ok": True, "images": [], "errors": []}
    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists():
            result["ok"] = False
            result["errors"].append({"file": raw_path, "error": "file_not_found"})
            continue
        if not path.is_file():
            result["ok"] = False
            result["errors"].append({"file": raw_path, "error": "not_file"})
            continue
        try:
            data = path.read_bytes()
        except Exception as exc:
            result["ok"] = False
            result["errors"].append({"file": raw_path, "error": str(exc)})
            continue
        info = image_info_from_bytes(path.name, data)
        info["file"] = str(path)
        info["recommendation"] = image_treatment_recommendation(info)
        result["images"].append(info)
    return result


def write_json(data: dict[str, Any], output_path: str) -> None:
    text = json.dumps(data, indent=2, ensure_ascii=False)
    if output_path == "-":
        print(text)
    else:
        Path(output_path).write_text(text + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect and gate a PPTX package.")
    sub = parser.add_subparsers(dest="command", required=True)
    inspect_cmd = sub.add_parser("inspect", help="Inspect PPTX package structure.")
    inspect_cmd.add_argument("pptx")
    inspect_cmd.add_argument("--out", default="-")
    gate_cmd = sub.add_parser("gate", help="Run the PPTX delivery gate.")
    gate_cmd.add_argument("pptx")
    gate_cmd.add_argument("--out", default="-")
    gate_cmd.add_argument(
        "--include-review",
        action="store_true",
        help="Treat review-level warnings as gate failures.",
    )
    compare_cmd = sub.add_parser("compare", help="Compare before/after inspect reports for edit regressions.")
    compare_cmd.add_argument("before_report")
    compare_cmd.add_argument("after_report")
    compare_cmd.add_argument("--out", default="-")
    package_diff_cmd = sub.add_parser(
        "package-diff",
        help="Compare before/after PPTX package parts and fail on changes outside allowed globs.",
    )
    package_diff_cmd.add_argument("before_pptx")
    package_diff_cmd.add_argument("after_pptx")
    package_diff_cmd.add_argument(
        "--allow",
        action="append",
        default=[],
        help="Allowed changed PPTX part glob, for example ppt/slides/slide5.xml. Repeat as needed.",
    )
    package_diff_cmd.add_argument("--out", default="-")
    image_cmd = sub.add_parser("image-info", help="Inspect image dimensions before PPTX insertion.")
    image_cmd.add_argument("images", nargs="+")
    image_cmd.add_argument("--out", default="-")
    args = parser.parse_args()

    if args.command == "inspect":
        report = inspect_pptx(Path(args.pptx))
        write_json(report, args.out)
        return 0 if report["ok"] else 1

    if args.command == "gate":
        report = inspect_pptx(Path(args.pptx))
        report["delivery_gate"] = delivery_gate_report(report, include_review=args.include_review)
        write_json(report, args.out)
        if not report["ok"]:
            return 1
        return 0 if report["delivery_gate"]["passed"] else 2

    if args.command == "compare":
        try:
            before = load_report(Path(args.before_report))
            after = load_report(Path(args.after_report))
        except Exception as exc:
            write_json({"checked": False, "passed": False, "error": str(exc)}, args.out)
            return 1
        result = compare_reports(before, after)
        write_json(result, args.out)
        return 0 if result["passed"] else 2

    if args.command == "package-diff":
        try:
            result = package_diff(Path(args.before_pptx), Path(args.after_pptx), list(args.allow))
        except Exception as exc:
            write_json({"checked": False, "passed": False, "error": str(exc)}, args.out)
            return 1
        write_json(result, args.out)
        return 0 if result["passed"] else 2

    if args.command == "image-info":
        result = inspect_image_paths(args.images)
        write_json(result, args.out)
        return 0 if result["ok"] else 1

    return 1


if __name__ == "__main__":
    sys.exit(main())
