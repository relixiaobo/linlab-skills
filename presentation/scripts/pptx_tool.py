#!/usr/bin/env python3
"""Portable PPTX inspection helper for the presentation skill."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import math
import posixpath
import re
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
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
INSPECT_REPORT_SCHEMA_VERSION = "1.0"
INSPECT_REPORT_KIND = "pptx-inspect"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
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
REPORT_FINGERPRINT_KEYS = EDIT_REGRESSION_KEYS + ("errors", "warnings")
AFFINE_IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
LEAF_OBJECT_TAGS = (
    f"{P_NS}sp",
    f"{P_NS}pic",
    f"{P_NS}graphicFrame",
    f"{P_NS}cxnSp",
)


def parse_package_xml(
    zf: zipfile.ZipFile,
    package_parts: set[str],
) -> tuple[dict[str, ET.Element], list[dict[str, Any]]]:
    roots: dict[str, ET.Element] = {}
    errors: list[dict[str, Any]] = []
    xml_parts = sorted(
        name
        for name in package_parts
        if name.lower().endswith((".xml", ".rels"))
    )
    for name in xml_parts:
        try:
            roots[name] = ET.fromstring(zf.read(name))
        except ET.ParseError as exc:
            line, column = exc.position
            errors.append(
                {
                    "code": "xml_parse_error",
                    "part": name,
                    "message": str(exc),
                    "line": line,
                    "column": column,
                }
            )
        except Exception as exc:
            errors.append(
                {
                    "code": "xml_part_read_error",
                    "part": name,
                    "message": str(exc),
                }
            )
    return roots, errors


def source_relationship_part(source_part: str) -> str:
    directory = posixpath.dirname(source_part)
    relationship_directory = posixpath.join(directory, "_rels") if directory else "_rels"
    return posixpath.join(relationship_directory, f"{posixpath.basename(source_part)}.rels")


def validate_relationship_references(
    xml_roots: dict[str, ET.Element],
    package_parts: set[str],
) -> tuple[int, list[dict[str, Any]]]:
    checked_reference_count = 0
    errors: list[dict[str, Any]] = []
    for source_part, root in sorted(xml_roots.items()):
        if source_part.lower().endswith(".rels"):
            continue
        relationship_part = source_relationship_part(source_part)
        relationship_root = xml_roots.get(relationship_part)
        if relationship_part in package_parts and relationship_root is None:
            continue
        relationship_ids = {
            relationship.attrib.get("Id", "")
            for relationship in relationship_root.findall(f"{REL_NS}Relationship")
        } if relationship_root is not None else set()
        for element in root.iter():
            for attribute, relationship_id in element.attrib.items():
                if not attribute.startswith(R_NS):
                    continue
                checked_reference_count += 1
                if relationship_id in relationship_ids:
                    continue
                errors.append(
                    {
                        "code": "missing_relationship_reference",
                        "part": source_part,
                        "from": source_part,
                        "relationship_part": relationship_part,
                        "relationship_id": relationship_id,
                        "rid": relationship_id,
                        "attribute": attribute[len(R_NS):],
                        "element": element.tag.rsplit("}", 1)[-1],
                        "reason": (
                            "relationship_part_missing"
                            if relationship_root is None
                            else "relationship_id_missing"
                        ),
                    }
                )
    return checked_reference_count, errors


def relationship_source_part(relationship_part: str) -> str | None:
    if relationship_part == "_rels/.rels":
        return ""
    relationship_directory = posixpath.dirname(relationship_part)
    if posixpath.basename(relationship_directory) != "_rels":
        return None
    filename = posixpath.basename(relationship_part)
    if not filename.endswith(".rels"):
        return None
    source_directory = posixpath.dirname(relationship_directory)
    source_name = filename[: -len(".rels")]
    return posixpath.join(source_directory, source_name) if source_directory else source_name


def validate_relationship_targets(
    xml_roots: dict[str, ET.Element],
    package_parts: set[str],
) -> tuple[int, list[dict[str, Any]]]:
    checked_relationship_count = 0
    errors: list[dict[str, Any]] = []
    for relationship_part, root in sorted(xml_roots.items()):
        if not relationship_part.lower().endswith(".rels"):
            continue
        source_part = relationship_source_part(relationship_part)
        if source_part is None:
            continue
        for relationship in root.findall(f"{REL_NS}Relationship"):
            if relationship.attrib.get("TargetMode", "") == "External":
                continue
            checked_relationship_count += 1
            target = relationship.attrib.get("Target", "")
            resolved_target = normalized_target(source_part, target)
            if resolved_target in package_parts:
                continue
            errors.append(
                {
                    "code": "missing_relationship_target",
                    "part": relationship_part,
                    "from": source_part or "/",
                    "rid": relationship.attrib.get("Id", ""),
                    "target": target,
                    "resolved_target": resolved_target,
                }
            )
    return checked_relationship_count, errors


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_sha256(zf: zipfile.ZipFile) -> str:
    digest = hashlib.sha256()
    for info in sorted(
        (item for item in zf.infolist() if not item.is_dir()),
        key=lambda item: item.filename,
    ):
        name = info.filename.encode("utf-8")
        content_sha256 = hashlib.sha256(zf.read(info)).digest()
        digest.update(len(name).to_bytes(4, "big"))
        digest.update(name)
        digest.update(content_sha256)
    return digest.hexdigest()


def text_from_xml(root: ET.Element | None) -> str:
    if root is None:
        return ""
    paragraphs = []
    for paragraph in root.iter(f"{A_NS}p"):
        parts = []
        for node in paragraph.iter():
            if node.tag == f"{A_NS}t" and node.text:
                parts.append(node.text)
            elif node.tag == f"{A_NS}br":
                parts.append("\n")
            elif node.tag == f"{A_NS}tab":
                parts.append("\t")
        paragraphs.append("".join(parts))
    if paragraphs:
        return "\n".join(paragraphs)
    return "".join(node.text for node in root.iter(f"{A_NS}t") if node.text)


def collapsed_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


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
        "sha256": hashlib.sha256(data).hexdigest(),
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


def affine_compose(
    outer: tuple[float, float, float, float, float, float],
    inner: tuple[float, float, float, float, float, float],
) -> tuple[float, float, float, float, float, float]:
    oa, ob, oc, od, oe, of = outer
    ia, ib, ic, id_, ie, i_f = inner
    return (
        oa * ia + oc * ib,
        ob * ia + od * ib,
        oa * ic + oc * id_,
        ob * ic + od * id_,
        oa * ie + oc * i_f + oe,
        ob * ie + od * i_f + of,
    )


def affine_apply(
    transform: tuple[float, float, float, float, float, float],
    x: float,
    y: float,
) -> tuple[float, float]:
    a, b, c, d, e, f = transform
    return a * x + c * y + e, b * x + d * y + f


def affine_translate(x: float, y: float) -> tuple[float, float, float, float, float, float]:
    return (1.0, 0.0, 0.0, 1.0, x, y)


def orientation_transform(
    xfrm: ET.Element | None,
    x: float,
    y: float,
    cx: float,
    cy: float,
) -> tuple[float, float, float, float, float, float]:
    if xfrm is None:
        return AFFINE_IDENTITY
    flip_h = -1.0 if xfrm.attrib.get("flipH", "0").lower() in ("1", "true") else 1.0
    flip_v = -1.0 if xfrm.attrib.get("flipV", "0").lower() in ("1", "true") else 1.0
    rotation = (int_attr(xfrm, "rot") or 0) / 60000
    if flip_h == 1.0 and flip_v == 1.0 and rotation == 0:
        return AFFINE_IDENTITY
    radians = math.radians(rotation)
    cos_value = math.cos(radians)
    sin_value = math.sin(radians)
    flip = (flip_h, 0.0, 0.0, flip_v, 0.0, 0.0)
    rotate = (cos_value, sin_value, -sin_value, cos_value, 0.0, 0.0)
    center_x = x + cx / 2
    center_y = y + cy / 2
    return affine_compose(
        affine_translate(center_x, center_y),
        affine_compose(
            rotate,
            affine_compose(flip, affine_translate(-center_x, -center_y)),
        ),
    )


def group_transform_from_node(node: ET.Element) -> ET.Element | None:
    properties = node.find(f"{P_NS}grpSpPr")
    if properties is None:
        return None
    return properties.find(f"{A_NS}xfrm")


def group_child_transform(
    node: ET.Element,
) -> tuple[float, float, float, float, float, float]:
    xfrm = group_transform_from_node(node)
    if xfrm is None:
        return AFFINE_IDENTITY
    off = xfrm.find(f"{A_NS}off")
    ext = xfrm.find(f"{A_NS}ext")
    child_off = xfrm.find(f"{A_NS}chOff")
    child_ext = xfrm.find(f"{A_NS}chExt")
    x = int_attr(off, "x")
    y = int_attr(off, "y")
    cx = int_attr(ext, "cx")
    cy = int_attr(ext, "cy")
    child_x = int_attr(child_off, "x")
    child_y = int_attr(child_off, "y")
    child_cx = int_attr(child_ext, "cx")
    child_cy = int_attr(child_ext, "cy")
    values = (x, y, cx, cy, child_x, child_y, child_cx, child_cy)
    if any(value is None for value in values) or child_cx == 0 or child_cy == 0:
        return AFFINE_IDENTITY
    scale_x = cx / child_cx
    scale_y = cy / child_cy
    child_to_parent = (
        scale_x,
        0.0,
        0.0,
        scale_y,
        x - scale_x * child_x,
        y - scale_y * child_y,
    )
    return affine_compose(
        orientation_transform(xfrm, x, y, cx, cy),
        child_to_parent,
    )


def local_box_emu_from_node(node: ET.Element) -> dict[str, int] | None:
    xfrm = transform_from_node(node)
    off = xfrm.find(f"{A_NS}off") if xfrm is not None else None
    ext = xfrm.find(f"{A_NS}ext") if xfrm is not None else None
    x = int_attr(off, "x")
    y = int_attr(off, "y")
    cx = int_attr(ext, "cx")
    cy = int_attr(ext, "cy")
    if x is None or y is None or cx is None or cy is None:
        return None
    return {"x": x, "y": y, "cx": cx, "cy": cy}


def box_emu_from_node(
    node: ET.Element,
    parent_transform: tuple[float, float, float, float, float, float] = AFFINE_IDENTITY,
) -> dict[str, int] | None:
    local_box = local_box_emu_from_node(node)
    if local_box is None:
        return None
    x = local_box["x"]
    y = local_box["y"]
    cx = local_box["cx"]
    cy = local_box["cy"]
    transform = affine_compose(
        parent_transform,
        orientation_transform(transform_from_node(node), x, y, cx, cy),
    )
    corners = [
        affine_apply(transform, x, y),
        affine_apply(transform, x + cx, y),
        affine_apply(transform, x, y + cy),
        affine_apply(transform, x + cx, y + cy),
    ]
    left = round(min(point[0] for point in corners))
    top = round(min(point[1] for point in corners))
    right = round(max(point[0] for point in corners))
    bottom = round(max(point[1] for point in corners))
    return {"x": left, "y": top, "cx": right - left, "cy": bottom - top}


def box_inches_from_emu(box: dict[str, int] | None) -> dict[str, float] | None:
    if box is None:
        return None
    return {
        "x": emu_to_inches(box["x"]),
        "y": emu_to_inches(box["y"]),
        "w": emu_to_inches(box["cx"]),
        "h": emu_to_inches(box["cy"]),
    }


def affine_report(
    transform: tuple[float, float, float, float, float, float],
) -> list[float]:
    return [0.0 if abs(value) < 1e-12 else round(value, 9) for value in transform]


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


def non_visual_properties_from_node(node: ET.Element) -> dict[str, Any]:
    props = node.find(f".//{P_NS}cNvPr")
    if props is None:
        return {"id": None, "name": "", "description": "", "title": "", "hidden": False}
    hidden = props.attrib.get("hidden", "0").lower() in ("1", "true")
    return {
        "id": int_attr(props, "id"),
        "name": props.attrib.get("name", ""),
        "description": props.attrib.get("descr", ""),
        "title": props.attrib.get("title", ""),
        "hidden": hidden,
    }


def object_key(kind: str, identity: dict[str, Any], order: int) -> str:
    object_id = identity.get("id")
    if isinstance(object_id, int):
        return f"{kind}:id:{object_id}"
    name = str(identity.get("name", ""))
    if name:
        return f"{kind}:name:{name}"
    return f"{kind}:order:{order}"


def canonical_element_sha256(node: ET.Element) -> str:
    canonical_xml = ET.canonicalize(ET.tostring(node, encoding="unicode"))
    return sha256_text(canonical_xml)


def element_state(node: ET.Element | None) -> dict[str, Any]:
    if node is None:
        return {"present": False, "sha256": None}
    return {"present": True, "sha256": canonical_element_sha256(node)}


def root_state(root: ET.Element | None) -> dict[str, Any]:
    if root is None:
        return {
            "canonical_xml_sha256": None,
            "root_attributes": {},
            "direct_child_tags": [],
        }
    return {
        "canonical_xml_sha256": canonical_element_sha256(root),
        "root_attributes": dict(sorted(root.attrib.items())),
        "direct_child_tags": [child.tag.rsplit("}", 1)[-1] for child in root],
    }


def slide_state(root: ET.Element | None) -> dict[str, Any]:
    state = root_state(root)
    state["transition"] = element_state(root.find(f"{P_NS}transition") if root is not None else None)
    state["timing"] = element_state(root.find(f"{P_NS}timing") if root is not None else None)
    return state


def non_text_xml_sha256(node: ET.Element) -> str:
    clone = ET.fromstring(ET.tostring(node, encoding="utf-8"))
    for text_node in clone.iter(f"{A_NS}t"):
        text_node.text = ""
    return canonical_element_sha256(clone)


def table_info_from_node(node: ET.Element) -> dict[str, Any] | None:
    table = node.find(f".//{A_NS}tbl")
    if table is None:
        return None
    rows = list(table.findall(f"{A_NS}tr"))
    row_count = len(rows)
    column_count = len(table.findall(f"{A_NS}tblGrid/{A_NS}gridCol"))
    if column_count == 0 and rows:
        column_count = max(len(row.findall(f"{A_NS}tc")) for row in rows)
    cell_count = sum(len(row.findall(f"{A_NS}tc")) for row in rows)
    values = [
        [text_from_xml(cell) for cell in row.findall(f"{A_NS}tc")]
        for row in rows
    ]
    return {
        "rows": row_count,
        "cols": column_count,
        "cells": cell_count,
        "values": values,
        "values_sha256": sha256_text(canonical_json(values)),
    }


def semantic_object_snapshot(obj: dict[str, Any]) -> dict[str, Any]:
    table = obj.get("table") if isinstance(obj.get("table"), dict) else {}
    image = obj.get("image") if isinstance(obj.get("image"), dict) else {}
    text_full = str(obj.get("text_full", obj.get("text", "")))
    return {
        "kind": obj.get("kind"),
        "identity": obj.get("identity"),
        "local_box_emu": obj.get("local_box_emu"),
        "box_emu": obj.get("box_emu"),
        "box": obj.get("box"),
        "group_path": obj.get("group_path", []),
        "composed_parent_transform": obj.get("composed_parent_transform"),
        "group_transform_sha256": obj.get("group_transform_sha256"),
        "non_text_sha256": obj.get("non_text_sha256"),
        "text": text_full,
        "text_sha256": obj.get("text_sha256") or sha256_text(text_full),
        "table_values": table.get("values"),
        "table_values_sha256": table.get("values_sha256"),
        "target": obj.get("target", ""),
        "image_sha256": image.get("sha256"),
        "crop": obj.get("crop"),
    }


def semantic_object_hash(obj: dict[str, Any]) -> str:
    return sha256_text(canonical_json(semantic_object_snapshot(obj)))


def finalize_object_report(report: dict[str, Any]) -> dict[str, Any]:
    report["semantic_sha256"] = semantic_object_hash(report)
    return report


def slide_object_reports(
    root: ET.Element | None,
    slide_rels: dict[str, dict[str, str]],
    slide_part: str,
    media_info: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    if root is None:
        return []

    sp_tree = root.find(f".//{P_NS}spTree")
    container = sp_tree if sp_tree is not None else root
    reports: list[dict[str, Any]] = []
    leaf_order = 0
    group_order = 0

    def visit(
        parent: ET.Element,
        parent_transform: tuple[float, float, float, float, float, float],
        group_context: list[dict[str, Any]],
    ) -> None:
        nonlocal leaf_order, group_order
        for child in list(parent):
            if child.tag == f"{P_NS}grpSp":
                group_order += 1
                group_identity = non_visual_properties_from_node(child)
                properties = child.find(f"{P_NS}grpSpPr")
                context_entry = {
                    "object_key": object_key("group", group_identity, group_order),
                    "identity": group_identity,
                    "properties_sha256": canonical_element_sha256(properties)
                    if properties is not None
                    else None,
                }
                visit(
                    child,
                    affine_compose(parent_transform, group_child_transform(child)),
                    [*group_context, context_entry],
                )
                continue
            if child.tag not in LEAF_OBJECT_TAGS:
                continue

            leaf_order += 1
            identity = non_visual_properties_from_node(child)
            local_box_emu = local_box_emu_from_node(child)
            box_emu = box_emu_from_node(child, parent_transform)
            base_report: dict[str, Any] = {
                "order": leaf_order,
                "identity": identity,
                "object_id": identity.get("id"),
                "object_name": identity.get("name", ""),
                "box": box_inches_from_emu(box_emu),
                "local_box_emu": local_box_emu,
                "box_emu": box_emu,
                "group_path": [entry["object_key"] for entry in group_context],
                "composed_parent_transform": affine_report(parent_transform),
                "group_transform_sha256": sha256_text(canonical_json(group_context))
                if group_context
                else None,
                "non_text_sha256": non_text_xml_sha256(child),
            }

            if child.tag in (f"{P_NS}sp", f"{P_NS}cxnSp"):
                kind = "connector" if child.tag == f"{P_NS}cxnSp" else "shape"
                text_full = text_from_xml(child)
                text = collapsed_text(text_full)
                font_sizes = font_sizes_from_node(child)
                reports.append(
                    finalize_object_report({
                        **base_report,
                        "kind": kind,
                        "object_key": object_key(kind, identity, leaf_order),
                        "text": text,
                        "text_full": text_full,
                        "text_sha256": sha256_text(text_full),
                        "text_chars": len(text),
                        "font_min": min(font_sizes) if font_sizes else None,
                        "font_max": max(font_sizes) if font_sizes else None,
                        "geometry": geometry_name(child),
                        "blank": len(text) == 0,
                    })
                )
                continue

            if child.tag == f"{P_NS}pic":
                rid = picture_rid(child)
                target = ""
                if rid and rid in slide_rels:
                    target = normalized_target(slide_part, slide_rels[rid].get("target", ""))
                image_info = media_info.get(target, {})
                crop = crop_rect_from_picture(child)
                reports.append(
                    finalize_object_report({
                        **base_report,
                        "kind": "picture",
                        "object_key": object_key("picture", identity, leaf_order),
                        "rid": rid,
                        "target": target,
                        "image": image_info,
                        "crop": crop,
                        "visible_fraction": crop_visible_fraction(crop),
                    })
                )
                continue

            text_full = text_from_xml(child)
            text = collapsed_text(text_full)
            font_sizes = font_sizes_from_node(child)
            table_info = table_info_from_node(child)
            kind = "table" if table_info else "graphicFrame"
            reports.append(
                finalize_object_report({
                    **base_report,
                    "kind": kind,
                    "object_key": object_key(kind, identity, leaf_order),
                    "text": text,
                    "text_full": text_full,
                    "text_sha256": sha256_text(text_full),
                    "text_chars": len(text),
                    "font_min": min(font_sizes) if font_sizes else None,
                    "font_max": max(font_sizes) if font_sizes else None,
                    "table": table_info,
                })
            )

    visit(container, AFFINE_IDENTITY, [])

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
                    "picture_key": picture.get("object_key"),
                    "shape_key": text_shape.get("object_key"),
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
                    "picture_key": picture.get("object_key"),
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
            "picture_key": picture.get("object_key"),
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
                "object_key": obj.get("object_key"),
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
                    "object_key": obj.get("object_key"),
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
                "object_key": table_obj.get("object_key"),
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
                    "picture_key": picture.get("object_key"),
                    "shape_key": text_shape.get("object_key"),
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
                    "shape_key": shape.get("object_key"),
                    "picture_key": picture.get("object_key"),
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
                    "picture_key": picture.get("object_key"),
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
    box_emu = shape.get("box_emu") if isinstance(shape.get("box_emu"), dict) else {}
    x = box_emu.get("x", shape.get("x"))
    y = box_emu.get("y", shape.get("y"))
    cy = box_emu.get("cy", shape.get("cy")) or 0
    if not isinstance(slide_height, int) or not isinstance(y, int) or not isinstance(cy, int):
        return None
    if y + cy < int(slide_height * 0.72):
        return None

    text_full = str(shape.get("text_full") or shape.get("text") or "")
    texts = [
        str(shape.get("one_line") or collapsed_text(text_full)),
        str(shape.get("compact") or re.sub(r"\s+", "", text_full)),
        collapsed_text(text_full),
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
            "object_key": shape.get("object_key", ""),
            "x": x,
            "y": y,
        }
    return None


def page_number_matches(candidate: dict[str, object], index: int, total_slides: int) -> bool:
    if candidate.get("number") != index:
        return False
    total = candidate.get("total")
    return total in (None, total_slides)


def rels_for(
    xml_roots: dict[str, ET.Element],
    rels_name: str,
) -> dict[str, dict[str, str]]:
    root = xml_roots.get(rels_name)
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


def relationship_reports(
    source_part: str,
    relationships: dict[str, dict[str, str]],
    package_parts: set[str],
) -> list[dict[str, Any]]:
    reports = []
    for rid, relationship in sorted(relationships.items()):
        target = relationship.get("target", "")
        mode = relationship.get("mode", "")
        external = mode == "External"
        resolved = target if external else normalized_target(source_part, target)
        rel_type = relationship.get("type", "")
        reports.append(
            {
                "rid": rid,
                "type": rel_type,
                "type_name": rel_type.rsplit("/", 1)[-1] if rel_type else "",
                "target": target,
                "mode": mode,
                "resolved_target": resolved,
                "target_exists": None if external else resolved in package_parts,
            }
        )
    return reports


def record_missing_relationship_targets(
    result: dict[str, Any],
    source_part: str,
    relationships: list[dict[str, Any]],
) -> None:
    existing = {
        (item.get("from"), item.get("rid"), item.get("target"))
        for item in result.get("missing_relationship_targets", [])
        if isinstance(item, dict)
    }
    for relationship in relationships:
        if relationship.get("target_exists") is not False:
            continue
        entry = {
            "from": source_part,
            "rid": relationship.get("rid", ""),
            "target": relationship.get("target", ""),
        }
        fingerprint = (entry["from"], entry["rid"], entry["target"])
        if fingerprint not in existing:
            result["missing_relationship_targets"].append(entry)
            existing.add(fingerprint)


def notes_text_from_root(root: ET.Element | None) -> str:
    if root is None:
        return ""
    body_parts = []
    found_body = False
    for shape in root.iter(f"{P_NS}sp"):
        placeholder = shape.find(f"{P_NS}nvSpPr/{P_NS}nvPr/{P_NS}ph")
        if placeholder is not None and placeholder.attrib.get("type", "body") == "body":
            found_body = True
            body_parts.append(text_from_xml(shape))
    if found_body:
        return "\n".join(body_parts)
    return text_from_xml(root)


def finalize_inspection_result(result: dict[str, Any]) -> dict[str, Any]:
    result["issue_fingerprints"] = report_issue_fingerprints(
        result,
        REPORT_FINGERPRINT_KEYS,
    )
    return result


def inspect_pptx(path: Path) -> dict:
    result = {
        "report_schema_version": INSPECT_REPORT_SCHEMA_VERSION,
        "report_kind": INSPECT_REPORT_KIND,
        "file": str(path),
        "artifact_sha256": None,
        "artifact_bytes": None,
        "package_sha256": None,
        "package_part_count": 0,
        "ok": False,
        "errors": [],
        "warnings": [],
        "slides": [],
        "slide_size": {},
        "media_count": 0,
        "chart_count": 0,
        "notes_count": 0,
        "xml_validation": {"checked_part_count": 0, "parse_error_count": 0},
        "relationship_reference_validation": {
            "checked_reference_count": 0,
            "missing_reference_count": 0,
        },
        "relationship_target_validation": {
            "checked_relationship_count": 0,
            "missing_target_count": 0,
        },
        "presentation_state": {},
        "presentation_relationships": [],
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
        "issue_fingerprints": {},
    }

    if not path.exists():
        result["errors"].append("file_not_found")
        return finalize_inspection_result(result)
    if path.suffix.lower() != ".pptx":
        result["errors"].append("not_pptx")
        return finalize_inspection_result(result)

    try:
        result["artifact_sha256"] = file_sha256(path)
        result["artifact_bytes"] = path.stat().st_size
    except OSError as exc:
        result["errors"].append(
            {"code": "artifact_read_error", "part": str(path), "message": str(exc)}
        )
        return finalize_inspection_result(result)

    try:
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
            result["package_sha256"] = package_sha256(zf)
            result["package_part_count"] = len(
                [info for info in zf.infolist() if not info.is_dir()]
            )
            media_names = sorted(name for name in names if name.startswith("ppt/media/"))
            result["media_count"] = len(media_names)
            result["chart_count"] = len([name for name in names if name.startswith("ppt/charts/")])
            result["notes_count"] = len([name for name in names if name.startswith("ppt/notesSlides/") and name.endswith(".xml")])

            required = ["[Content_Types].xml", "ppt/presentation.xml", "ppt/_rels/presentation.xml.rels"]
            for name in required:
                if name not in names:
                    result["errors"].append(f"missing:{name}")
            xml_roots, xml_errors = parse_package_xml(zf, names)
            result["xml_validation"] = {
                "checked_part_count": len(xml_roots) + len(xml_errors),
                "parse_error_count": len(xml_errors),
            }
            result["errors"].extend(xml_errors)
            checked_relationships, relationship_target_errors = validate_relationship_targets(
                xml_roots,
                names,
            )
            result["relationship_target_validation"] = {
                "checked_relationship_count": checked_relationships,
                "missing_target_count": len(relationship_target_errors),
            }
            result["errors"].extend(relationship_target_errors)
            checked_references, relationship_reference_errors = validate_relationship_references(
                xml_roots,
                names,
            )
            result["relationship_reference_validation"] = {
                "checked_reference_count": checked_references,
                "missing_reference_count": len(relationship_reference_errors),
            }
            result["errors"].extend(relationship_reference_errors)
            if result["errors"]:
                return finalize_inspection_result(result)

            pres = xml_roots.get("ppt/presentation.xml")
            slide_size = slide_size_from_presentation(pres)
            result["slide_size"] = slide_size
            result["presentation_state"] = root_state(pres)
            pres_rels = rels_for(xml_roots, "ppt/_rels/presentation.xml.rels")
            result["presentation_relationships"] = relationship_reports(
                "ppt/presentation.xml",
                pres_rels,
                names,
            )
            record_missing_relationship_targets(
                result,
                "ppt/presentation.xml",
                result["presentation_relationships"],
            )
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
                    "text": "",
                    "text_sha256": sha256_text(""),
                    "placeholder_hits": [],
                    "relationship_count": 0,
                    "relationships": [],
                    "picture_count": 0,
                    "table_count": 0,
                    "shape_count": 0,
                    "chart_count": 0,
                    "notes": False,
                    "notes_part": "",
                    "notes_text": "",
                    "notes_text_sha256": sha256_text(""),
                    "notes_details": [],
                    "page_number_candidates": [],
                    "content_bbox": None,
                    "min_font_size": None,
                    "layout_warning_count": 0,
                    "slide_state": {},
                    "objects": [],
                }
                if not slide_part or slide_part not in names:
                    if not rel:
                        result["missing_relationship_targets"].append(
                            {"from": "ppt/presentation.xml", "rid": rid, "target": target}
                        )
                    result["slides"].append(slide_report)
                    continue

                slide_root = xml_roots.get(slide_part)
                slide_report["slide_state"] = slide_state(slide_root)
                text = text_from_xml(slide_root)
                slide_report["text_chars"] = len(text)
                slide_report["text_preview"] = collapsed_text(text)[:300]
                slide_report["text"] = text
                slide_report["text_sha256"] = sha256_text(text)
                if slide_root is not None:
                    slide_report["shape_count"] = len(list(slide_root.iter(f"{P_NS}sp")))
                hits = sorted(set(match.group(0).lower() for match in PLACEHOLDER_RE.finditer(text)))
                slide_report["placeholder_hits"] = hits
                for hit in hits:
                    result["placeholder_hits"].append({"slide": index, "text": hit})

                rels_name = posixpath.join(
                    posixpath.dirname(slide_part),
                    "_rels",
                    f"{posixpath.basename(slide_part)}.rels",
                )
                slide_rels = rels_for(xml_roots, rels_name)
                slide_report["relationship_count"] = len(slide_rels)
                slide_report["relationships"] = relationship_reports(slide_part, slide_rels, names)
                record_missing_relationship_targets(
                    result,
                    slide_part,
                    slide_report["relationships"],
                )
                notes_parts = []
                for slide_rel in slide_rels.values():
                    rel_type = slide_rel.get("type", "")
                    if rel_type.endswith("/notesSlide"):
                        slide_report["notes"] = True
                    if rel_type.endswith("/chart"):
                        slide_report["chart_count"] += 1
                    if slide_rel.get("mode") == "External":
                        continue
                    rel_target = slide_rel.get("target", "")
                    resolved = normalized_target(slide_part, rel_target)
                    if resolved in names and rel_type.endswith("/notesSlide"):
                        notes_parts.append(resolved)

                notes_details = []
                for notes_part in notes_parts:
                    notes_root = xml_roots.get(notes_part)
                    notes_text = notes_text_from_root(notes_root)
                    notes_rels_name = posixpath.join(
                        posixpath.dirname(notes_part),
                        "_rels",
                        f"{posixpath.basename(notes_part)}.rels",
                    )
                    notes_rels = rels_for(xml_roots, notes_rels_name)
                    notes_relationships = relationship_reports(notes_part, notes_rels, names)
                    record_missing_relationship_targets(
                        result,
                        notes_part,
                        notes_relationships,
                    )
                    notes_details.append(
                        {
                            "part": notes_part,
                            "text": notes_text,
                            "text_sha256": sha256_text(notes_text),
                            "relationships": notes_relationships,
                        }
                    )
                if notes_details:
                    combined_notes_text = "\n".join(
                        str(detail.get("text", "")) for detail in notes_details
                    )
                    slide_report["notes_part"] = notes_details[0]["part"]
                    slide_report["notes_text"] = combined_notes_text
                    slide_report["notes_text_sha256"] = sha256_text(combined_notes_text)
                    slide_report["notes_details"] = notes_details

                slide_objects = slide_object_reports(slide_root, slide_rels, slide_part, media_info)
                slide_report["objects"] = slide_objects
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
                for shape in slide_objects:
                    if shape.get("kind") not in ("shape", "connector"):
                        continue
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
                            "object_keys": sorted(
                                str(candidate.get("object_key", ""))
                                for candidate in candidates
                                if candidate.get("object_key")
                            ),
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
            return finalize_inspection_result(result)
    except zipfile.BadZipFile:
        result["errors"].append("bad_zip")
        return finalize_inspection_result(result)


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


def report_issue_items(report: dict[str, Any], key: str) -> list[Any]:
    value = report.get(key)
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [{"key": item_key, "value": value[item_key]} for item_key in sorted(value)]
    if isinstance(value, bool):
        return [value] if value else []
    if isinstance(value, int):
        return [{"ordinal": index + 1} for index in range(max(0, value))]
    return []


def issue_identity(key: str, issue: Any) -> Any:
    if not isinstance(issue, dict):
        return issue
    stable_fields = (
        "slide",
        "next_slide",
        "from",
        "rid",
        "object_key",
        "object_keys",
        "shape_key",
        "picture_key",
        "expected_last_slide",
        "kind",
        "reason",
    )
    order_fields = (
        "order",
        "shape_order",
        "picture_order",
    )
    identity = {
        field: issue[field]
        for field in stable_fields
        if field in issue and issue[field] not in (None, "")
    }
    if not any(
        field in identity
        for field in ("object_key", "object_keys", "shape_key", "picture_key")
    ):
        identity.update({field: issue[field] for field in order_fields if field in issue})
    if key == "missing_relationship_targets" and "target" in issue:
        identity["target"] = issue["target"]
    if key == "placeholder_hits" and "text" in issue:
        identity["text"] = issue["text"]
    return identity or issue


def issue_fingerprint(key: str, issue: Any) -> str:
    return sha256_text(f"{key}\n{canonical_json(issue_identity(key, issue))}")


def report_issue_fingerprints(
    report: dict[str, Any],
    keys: tuple[str, ...] | list[str],
) -> dict[str, list[str]]:
    fingerprints = {}
    for key in keys:
        values = sorted(issue_fingerprint(key, issue) for issue in report_issue_items(report, key))
        if values:
            fingerprints[key] = values
    return fingerprints


def issue_delta_report(
    before: dict[str, Any],
    after: dict[str, Any],
    keys: tuple[str, ...] | list[str],
) -> dict[str, dict[str, Any]]:
    changes = {}
    for key in keys:
        before_records = [
            (issue_fingerprint(key, issue), issue)
            for issue in report_issue_items(before, key)
        ]
        after_records = [
            (issue_fingerprint(key, issue), issue)
            for issue in report_issue_items(after, key)
        ]
        before_counts = Counter(fingerprint for fingerprint, _ in before_records)
        after_counts = Counter(fingerprint for fingerprint, _ in after_records)
        new_counts = after_counts - before_counts
        resolved_counts = before_counts - after_counts
        if not new_counts and not resolved_counts:
            continue

        after_by_fingerprint: dict[str, list[Any]] = defaultdict(list)
        before_by_fingerprint: dict[str, list[Any]] = defaultdict(list)
        for fingerprint, issue in after_records:
            after_by_fingerprint[fingerprint].append(issue)
        for fingerprint, issue in before_records:
            before_by_fingerprint[fingerprint].append(issue)

        new_issues = []
        for fingerprint in sorted(new_counts):
            for issue in after_by_fingerprint[fingerprint][: new_counts[fingerprint]]:
                new_issues.append({"fingerprint": fingerprint, "issue": issue})
        resolved_issues = []
        for fingerprint in sorted(resolved_counts):
            for issue in before_by_fingerprint[fingerprint][: resolved_counts[fingerprint]]:
                resolved_issues.append({"fingerprint": fingerprint, "issue": issue})

        changes[key] = {
            "before": len(before_records),
            "after": len(after_records),
            "delta": len(after_records) - len(before_records),
            "new_issue_count": sum(new_counts.values()),
            "resolved_issue_count": sum(resolved_counts.values()),
            "new_issues": new_issues,
            "resolved_issues": resolved_issues,
        }
    return changes


def technical_gate_report(report: dict[str, Any], include_review: bool = False) -> dict[str, Any]:
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
        "message": "passed" if passed else "failed: repair blocking technical warnings",
    }


def baseline_technical_gate_report(
    baseline: dict[str, Any],
    report: dict[str, Any],
    include_review: bool = False,
    baseline_file: str = "",
) -> dict[str, Any]:
    checked_keys = list(GATE_BLOCKING_KEYS)
    if include_review:
        checked_keys.extend(GATE_REVIEW_KEYS)
    issue_changes = issue_delta_report(baseline, report, checked_keys)
    new_issue_counts = {
        key: int(change["new_issue_count"])
        for key, change in issue_changes.items()
        if int(change["new_issue_count"]) > 0
    }
    resolved_issue_counts = {
        key: int(change["resolved_issue_count"])
        for key, change in issue_changes.items()
        if int(change["resolved_issue_count"]) > 0
    }

    error_changes = issue_delta_report(baseline, report, ["errors"])
    new_errors = error_changes.get("errors", {}).get("new_issues", [])
    baseline_warning_names = {
        str(item) for item in baseline.get("warnings", []) if isinstance(item, str)
    }
    report_warning_names = {
        str(item) for item in report.get("warnings", []) if isinstance(item, str)
    }
    new_blocking_warning_names = sorted(
        (report_warning_names - baseline_warning_names).intersection(GATE_BLOCKING_WARNING_NAMES)
    )

    passed = not new_issue_counts and not new_errors and not new_blocking_warning_names
    return {
        "checked": True,
        "passed": passed,
        "mode": "baseline-no-new-regressions",
        "baseline_file": baseline_file,
        "blocking_counts": {
            key: count
            for key, count in new_issue_counts.items()
            if key in GATE_BLOCKING_KEYS
        },
        "blocking_warnings": sorted(
            [key for key in new_issue_counts if key in GATE_BLOCKING_KEYS]
            + new_blocking_warning_names
        ),
        "review_counts": {
            key: count
            for key, count in new_issue_counts.items()
            if key in GATE_REVIEW_KEYS
        },
        "review_warnings": sorted(
            key for key in new_issue_counts if key in GATE_REVIEW_KEYS
        ),
        "new_issue_counts": new_issue_counts,
        "resolved_issue_counts": resolved_issue_counts,
        "issue_changes": issue_changes,
        "new_error_count": len(new_errors),
        "new_errors": new_errors,
        "message": "passed" if passed else "failed: edit introduced new technical regressions",
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


def object_diff_evidence(obj: dict[str, Any]) -> dict[str, Any]:
    snapshot = semantic_object_snapshot(obj)
    return {
        "object_key": obj.get("object_key", ""),
        "object_id": obj.get("object_id"),
        "object_name": obj.get("object_name", ""),
        "semantic_sha256": semantic_object_hash(obj),
        **snapshot,
    }


def is_sha256(value: Any) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None


def validate_inspect_report(report: dict[str, Any], label: str) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []

    def add(code: str, field: str, message: str, **context: Any) -> None:
        errors.append(
            {
                "report": label,
                "code": code,
                "field": field,
                "message": message,
                **context,
            }
        )

    if report.get("report_schema_version") != INSPECT_REPORT_SCHEMA_VERSION:
        add(
            "unsupported_report_schema",
            "report_schema_version",
            f"expected {INSPECT_REPORT_SCHEMA_VERSION}",
        )
    if report.get("report_kind") != INSPECT_REPORT_KIND:
        add("invalid_report_kind", "report_kind", f"expected {INSPECT_REPORT_KIND}")
    if not isinstance(report.get("file"), str) or not report.get("file"):
        add("missing_core_field", "file", "expected a non-empty source path")
    if not is_sha256(report.get("artifact_sha256")):
        add("missing_core_identity", "artifact_sha256", "expected a SHA-256 digest")
    if not is_sha256(report.get("package_sha256")):
        add("missing_core_identity", "package_sha256", "expected a SHA-256 digest")
    if not isinstance(report.get("artifact_bytes"), int) or report.get("artifact_bytes", -1) < 0:
        add("missing_core_identity", "artifact_bytes", "expected a non-negative byte count")
    if not isinstance(report.get("package_part_count"), int) or report.get("package_part_count", 0) <= 0:
        add("missing_core_identity", "package_part_count", "expected a positive part count")
    if not isinstance(report.get("ok"), bool):
        add("missing_core_field", "ok", "expected a boolean")
    for field in ("errors", "warnings", "slides", "presentation_relationships"):
        if not isinstance(report.get(field), list):
            add("missing_core_field", field, "expected a list")
    for field in (
        "slide_size",
        "presentation_state",
        "xml_validation",
        "relationship_reference_validation",
        "relationship_target_validation",
        "issue_fingerprints",
    ):
        if not isinstance(report.get(field), dict):
            add("missing_core_field", field, "expected an object")

    presentation_state = report.get("presentation_state")
    if not isinstance(presentation_state, dict) or not is_sha256(
        presentation_state.get("canonical_xml_sha256")
    ):
        add(
            "semantic_snapshot_unavailable",
            "presentation_state.canonical_xml_sha256",
            "presentation XML semantic state is unavailable",
        )

    slides = report.get("slides")
    if not isinstance(slides, list):
        return errors
    for slide_position, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict):
            add(
                "semantic_snapshot_unavailable",
                f"slides[{slide_position}]",
                "slide report must be an object",
            )
            continue
        if not isinstance(slide.get("index"), int) or slide.get("index", 0) <= 0:
            add(
                "semantic_snapshot_unavailable",
                f"slides[{slide_position}].index",
                "slide index is unavailable",
            )
        if not isinstance(slide.get("part"), str) or not slide.get("part"):
            add(
                "semantic_snapshot_unavailable",
                f"slides[{slide_position}].part",
                "slide package part is unavailable",
            )
        for field in ("text_sha256", "notes_text_sha256"):
            if not is_sha256(slide.get(field)):
                add(
                    "semantic_snapshot_unavailable",
                    f"slides[{slide_position}].{field}",
                    "expected a SHA-256 digest",
                )
        state = slide.get("slide_state")
        if not isinstance(state, dict) or not is_sha256(state.get("canonical_xml_sha256")):
            add(
                "semantic_snapshot_unavailable",
                f"slides[{slide_position}].slide_state.canonical_xml_sha256",
                "slide XML semantic state is unavailable",
            )
        objects = slide.get("objects")
        if not isinstance(objects, list):
            add(
                "semantic_snapshot_unavailable",
                f"slides[{slide_position}].objects",
                "object semantic snapshots are unavailable",
            )
            continue
        for object_position, obj in enumerate(objects, start=1):
            field_prefix = f"slides[{slide_position}].objects[{object_position}]"
            if not isinstance(obj, dict):
                add(
                    "semantic_snapshot_unavailable",
                    field_prefix,
                    "object snapshot must be an object",
                )
                continue
            if not isinstance(obj.get("object_key"), str) or not obj.get("object_key"):
                add(
                    "semantic_snapshot_unavailable",
                    f"{field_prefix}.object_key",
                    "stable object identity is unavailable",
                )
            if not isinstance(obj.get("kind"), str) or not obj.get("kind"):
                add(
                    "semantic_snapshot_unavailable",
                    f"{field_prefix}.kind",
                    "object kind is unavailable",
                )
            if not isinstance(obj.get("identity"), dict):
                add(
                    "semantic_snapshot_unavailable",
                    f"{field_prefix}.identity",
                    "object identity snapshot is unavailable",
                )
            if not is_sha256(obj.get("non_text_sha256")):
                add(
                    "semantic_snapshot_unavailable",
                    f"{field_prefix}.non_text_sha256",
                    "object property snapshot is unavailable",
                )
            recorded_hash = obj.get("semantic_sha256")
            if not is_sha256(recorded_hash):
                add(
                    "semantic_snapshot_unavailable",
                    f"{field_prefix}.semantic_sha256",
                    "object semantic hash is unavailable",
                )
            elif recorded_hash != semantic_object_hash(obj):
                add(
                    "semantic_snapshot_hash_mismatch",
                    f"{field_prefix}.semantic_sha256",
                    "object semantic hash does not match its snapshot",
                )
    return errors


def invalid_compare_report(validation_errors: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "checked": False,
        "technical_regression_passed": False,
        "scope_verified": False,
        "validation_errors": validation_errors,
        "message": "failed: compare requires complete pptx_tool inspect reports",
    }


def normalized_relationships(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    relationships = []
    for item in value:
        if not isinstance(item, dict):
            continue
        relationships.append(
            {
                "rid": item.get("rid", ""),
                "type": item.get("type", ""),
                "target": item.get("target", ""),
                "mode": item.get("mode", ""),
                "resolved_target": item.get("resolved_target", ""),
            }
        )
    return sorted(relationships, key=canonical_json)


def notes_relationships(slide: dict[str, Any]) -> list[dict[str, Any]]:
    relationships = []
    details = slide.get("notes_details")
    if not isinstance(details, list):
        return relationships
    for detail in details:
        if isinstance(detail, dict):
            relationships.extend(normalized_relationships(detail.get("relationships")))
    return sorted(relationships, key=canonical_json)


def slide_snapshot_key(slide: dict[str, Any], position: int) -> str:
    part = str(slide.get("part", ""))
    if part:
        return f"part:{part}"
    rid = str(slide.get("rid", ""))
    if rid:
        return f"rid:{rid}"
    return f"position:{position}"


def slide_objects_by_key(slide: dict[str, Any]) -> dict[str, dict[str, Any]]:
    objects = slide.get("objects")
    if not isinstance(objects, list):
        return {}
    keyed = {}
    for position, obj in enumerate(objects, start=1):
        if not isinstance(obj, dict):
            continue
        key = str(obj.get("object_key") or f"position:{position}")
        if key in keyed:
            key = f"{key}#{position}"
        keyed[key] = obj
    return keyed


def slide_semantic_changes(
    slide_key: str,
    before_slide: dict[str, Any],
    after_slide: dict[str, Any],
) -> dict[str, Any] | None:
    before_objects = slide_objects_by_key(before_slide)
    after_objects = slide_objects_by_key(after_slide)
    added_keys = sorted(set(after_objects) - set(before_objects))
    removed_keys = sorted(set(before_objects) - set(after_objects))
    modified_objects = []
    for object_key_value in sorted(set(before_objects).intersection(after_objects)):
        before_obj = before_objects[object_key_value]
        after_obj = after_objects[object_key_value]
        before_snapshot = semantic_object_snapshot(before_obj)
        after_snapshot = semantic_object_snapshot(after_obj)
        if semantic_object_hash(before_obj) == semantic_object_hash(after_obj):
            continue
        changed_fields = {
            field: {"before": before_snapshot.get(field), "after": after_snapshot.get(field)}
            for field in before_snapshot
            if before_snapshot.get(field) != after_snapshot.get(field)
        }
        modified_objects.append(
            {
                "object_key": object_key_value,
                "before_semantic_sha256": semantic_object_hash(before_obj),
                "after_semantic_sha256": semantic_object_hash(after_obj),
                "changed_fields": changed_fields,
            }
        )

    before_text = str(before_slide.get("text", before_slide.get("text_preview", "")))
    after_text = str(after_slide.get("text", after_slide.get("text_preview", "")))
    text_changed = (
        before_slide.get("text_sha256") or sha256_text(before_text)
    ) != (
        after_slide.get("text_sha256") or sha256_text(after_text)
    )
    before_notes = str(before_slide.get("notes_text", ""))
    after_notes = str(after_slide.get("notes_text", ""))
    notes_changed = (
        before_slide.get("notes_text_sha256") or sha256_text(before_notes)
    ) != (
        after_slide.get("notes_text_sha256") or sha256_text(after_notes)
    )
    before_relationships = normalized_relationships(before_slide.get("relationships"))
    after_relationships = normalized_relationships(after_slide.get("relationships"))
    before_notes_relationships = notes_relationships(before_slide)
    after_notes_relationships = notes_relationships(after_slide)
    before_slide_state = (
        before_slide.get("slide_state")
        if isinstance(before_slide.get("slide_state"), dict)
        else {}
    )
    after_slide_state = (
        after_slide.get("slide_state")
        if isinstance(after_slide.get("slide_state"), dict)
        else {}
    )
    slide_state_changes = {
        field: {
            "before": before_slide_state.get(field),
            "after": after_slide_state.get(field),
        }
        for field in sorted(set(before_slide_state).union(after_slide_state))
        if before_slide_state.get(field) != after_slide_state.get(field)
    }

    if not any(
        (
            added_keys,
            removed_keys,
            modified_objects,
            text_changed,
            notes_changed,
            before_relationships != after_relationships,
            before_notes_relationships != after_notes_relationships,
            slide_state_changes,
        )
    ):
        return None
    return {
        "slide_key": slide_key,
        "before_index": before_slide.get("index"),
        "after_index": after_slide.get("index"),
        "text_changed": text_changed,
        "text": {"before": before_text, "after": after_text} if text_changed else None,
        "notes_changed": notes_changed,
        "notes": {"before": before_notes, "after": after_notes} if notes_changed else None,
        "relationships_changed": before_relationships != after_relationships,
        "relationships": {
            "before": before_relationships,
            "after": after_relationships,
        } if before_relationships != after_relationships else None,
        "notes_relationships_changed": before_notes_relationships != after_notes_relationships,
        "notes_relationships": {
            "before": before_notes_relationships,
            "after": after_notes_relationships,
        } if before_notes_relationships != after_notes_relationships else None,
        "slide_state_changed": bool(slide_state_changes),
        "slide_state_changes": slide_state_changes,
        "objects_added": [object_diff_evidence(after_objects[key]) for key in added_keys],
        "objects_removed": [object_diff_evidence(before_objects[key]) for key in removed_keys],
        "objects_modified": modified_objects,
    }


def semantic_change_summary(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_slides = [item for item in before.get("slides", []) if isinstance(item, dict)]
    after_slides = [item for item in after.get("slides", []) if isinstance(item, dict)]
    available = isinstance(before.get("slides"), list) and isinstance(after.get("slides"), list)
    before_map = {
        slide_snapshot_key(slide, position): slide
        for position, slide in enumerate(before_slides, start=1)
    }
    after_map = {
        slide_snapshot_key(slide, position): slide
        for position, slide in enumerate(after_slides, start=1)
    }
    before_order = list(before_map)
    after_order = list(after_map)
    added_slides = [key for key in after_order if key not in before_map]
    removed_slides = [key for key in before_order if key not in after_map]
    moved_slides = [
        {
            "slide_key": key,
            "before_index": before_order.index(key) + 1,
            "after_index": after_order.index(key) + 1,
        }
        for key in before_order
        if key in after_map and before_order.index(key) != after_order.index(key)
    ]
    changed_slides = []
    for key in before_order:
        if key not in after_map:
            continue
        change = slide_semantic_changes(key, before_map[key], after_map[key])
        if change:
            changed_slides.append(change)

    before_presentation_relationships = normalized_relationships(before.get("presentation_relationships"))
    after_presentation_relationships = normalized_relationships(after.get("presentation_relationships"))
    presentation_relationships_changed = before_presentation_relationships != after_presentation_relationships
    before_presentation_state = (
        before.get("presentation_state")
        if isinstance(before.get("presentation_state"), dict)
        else {}
    )
    after_presentation_state = (
        after.get("presentation_state")
        if isinstance(after.get("presentation_state"), dict)
        else {}
    )
    presentation_state_changes = {
        field: {
            "before": before_presentation_state.get(field),
            "after": after_presentation_state.get(field),
        }
        for field in sorted(set(before_presentation_state).union(after_presentation_state))
        if before_presentation_state.get(field) != after_presentation_state.get(field)
    }
    return {
        "checked": available,
        "non_blocking": True,
        "before_slide_count": len(before_slides),
        "after_slide_count": len(after_slides),
        "slide_count_changed": len(before_slides) != len(after_slides),
        "slide_order_changed": before_order != after_order,
        "slides_added": added_slides,
        "slides_removed": removed_slides,
        "slides_moved": moved_slides,
        "changed_slide_count": len(changed_slides),
        "changed_slides": changed_slides,
        "presentation_relationships_changed": presentation_relationships_changed,
        "presentation_relationships": {
            "before": before_presentation_relationships,
            "after": after_presentation_relationships,
        } if presentation_relationships_changed else None,
        "presentation_state_changed": bool(presentation_state_changes),
        "presentation_state_changes": presentation_state_changes,
    }


def compare_reports(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    validation_errors = [
        *validate_inspect_report(before, "before"),
        *validate_inspect_report(after, "after"),
    ]
    if validation_errors:
        return invalid_compare_report(validation_errors)
    before_counts = {key: count_report_items(before, key) for key in EDIT_REGRESSION_KEYS}
    after_counts = {key: count_report_items(after, key) for key in EDIT_REGRESSION_KEYS}
    count_increases = {
        key: {
            "before": before_counts[key],
            "after": after_counts[key],
            "delta": after_counts[key] - before_counts[key],
        }
        for key in EDIT_REGRESSION_KEYS
        if after_counts[key] > before_counts[key]
    }
    issue_changes = issue_delta_report(before, after, EDIT_REGRESSION_KEYS)
    regressions = {
        key: {
            "before": int(change["before"]),
            "after": int(change["after"]),
            "delta": int(change["delta"]),
            "new_issue_count": int(change["new_issue_count"]),
        }
        for key, change in issue_changes.items()
        if int(change["new_issue_count"]) > 0
    }
    new_issue_fingerprints = {
        key: [str(item["fingerprint"]) for item in change["new_issues"]]
        for key, change in issue_changes.items()
        if change["new_issues"]
    }
    resolved_issue_fingerprints = {
        key: [str(item["fingerprint"]) for item in change["resolved_issues"]]
        for key, change in issue_changes.items()
        if change["resolved_issues"]
    }
    error_changes = issue_delta_report(before, after, ["errors"])
    new_errors = error_changes.get("errors", {}).get("new_issues", [])
    resolved_errors = error_changes.get("errors", {}).get("resolved_issues", [])
    before_warning_names = {
        str(item) for item in before.get("warnings", []) if isinstance(item, str)
    }
    after_warning_names = {
        str(item) for item in after.get("warnings", []) if isinstance(item, str)
    }
    new_blocking_warning_names = sorted(
        (after_warning_names - before_warning_names).intersection(GATE_BLOCKING_WARNING_NAMES)
    )
    after_errors = list(after.get("errors", [])) if isinstance(after.get("errors"), list) else []
    after_missing_relationships = count_report_items(after, "missing_relationship_targets")
    technical_regression_passed = not regressions and not new_errors and not new_blocking_warning_names
    return {
        "checked": True,
        "technical_regression_passed": technical_regression_passed,
        "scope_verified": False,
        "before_file": before.get("file", ""),
        "after_file": after.get("file", ""),
        "before_artifact_sha256": before.get("artifact_sha256"),
        "after_artifact_sha256": after.get("artifact_sha256"),
        "before_package_sha256": before.get("package_sha256"),
        "after_package_sha256": after.get("package_sha256"),
        "regression_counts": regressions,
        "count_increases": count_increases,
        "issue_changes": issue_changes,
        "new_issue_fingerprints": new_issue_fingerprints,
        "resolved_issue_fingerprints": resolved_issue_fingerprints,
        "new_error_count": len(new_errors),
        "new_errors": new_errors,
        "resolved_error_count": len(resolved_errors),
        "resolved_errors": resolved_errors,
        "new_blocking_warning_names": new_blocking_warning_names,
        "after_error_count": len(after_errors),
        "after_missing_relationship_targets": after_missing_relationships,
        "semantic_changes": semantic_change_summary(before, after),
        "message": (
            "technical regression check passed; requested edit scope was not verified"
            if technical_regression_passed
            else "failed: edit introduced new blocking regressions"
        ),
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
    gate_cmd = sub.add_parser("gate", help="Run the PPTX technical gate.")
    gate_cmd.add_argument("pptx")
    gate_cmd.add_argument("--out", default="-")
    gate_cmd.add_argument(
        "--baseline",
        help="Before-edit inspect report. Fail only technical issues not present in this baseline.",
    )
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
        absolute_technical_gate = technical_gate_report(report, include_review=args.include_review)
        if args.baseline:
            try:
                baseline = load_report(Path(args.baseline))
                if not isinstance(baseline, dict):
                    raise ValueError("baseline report must be a JSON object")
            except Exception as exc:
                write_json({"checked": False, "passed": False, "error": str(exc)}, args.out)
                return 1
            report["absolute_technical_gate"] = absolute_technical_gate
            report["technical_gate"] = baseline_technical_gate_report(
                baseline,
                report,
                include_review=args.include_review,
                baseline_file=args.baseline,
            )
        else:
            report["technical_gate"] = absolute_technical_gate
        write_json(report, args.out)
        if not args.baseline and not report["ok"]:
            return 1
        return 0 if report["technical_gate"]["passed"] else 2

    if args.command == "compare":
        try:
            before = load_report(Path(args.before_report))
            after = load_report(Path(args.after_report))
            if not isinstance(before, dict) or not isinstance(after, dict):
                raise ValueError("compare reports must be JSON objects")
        except Exception as exc:
            write_json(
                {
                    "checked": False,
                    "technical_regression_passed": False,
                    "scope_verified": False,
                    "error": str(exc),
                },
                args.out,
            )
            return 1
        result = compare_reports(before, after)
        write_json(result, args.out)
        if not result["checked"]:
            return 1
        return 0 if result["technical_regression_passed"] else 2

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
