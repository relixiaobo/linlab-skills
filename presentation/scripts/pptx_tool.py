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
REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
P_NS = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
A_NS = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
R_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
DEFAULT_SLIDE_SIZE = {"cx": 12192000, "cy": 6858000, "source": "default-16:9"}
EMU_PER_INCH = 914400
OVERFLOW_TOLERANCE_IN = 0.03


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
        xfrm = shape.find(f".//{A_NS}xfrm")
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


def box_from_node(node: ET.Element) -> dict[str, float] | None:
    xfrm = node.find(f".//{A_NS}xfrm")
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


def geometry_name(node: ET.Element) -> str:
    sp_pr = node.find(f"{P_NS}spPr")
    geom = sp_pr.find(f"{A_NS}prstGeom") if sp_pr is not None else None
    return geom.attrib.get("prst", "") if geom is not None else ""


def picture_rid(node: ET.Element) -> str:
    blip = node.find(f".//{A_NS}blip")
    if blip is None:
        return ""
    return blip.attrib.get(f"{R_NS}embed") or blip.attrib.get(f"{R_NS}link") or ""


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
        if child.tag not in (f"{P_NS}sp", f"{P_NS}pic"):
            continue
        order += 1
        box = box_from_node(child)
        if child.tag == f"{P_NS}sp":
            text_runs = text_runs_from_node(child)
            text = collapsed_text(" ".join(text_runs))
            reports.append(
                {
                    "kind": "shape",
                    "order": order,
                    "box": box,
                    "text": text,
                    "text_chars": len(text),
                    "geometry": geometry_name(child),
                    "blank": len(text) == 0,
                }
            )
            continue

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


def layout_warnings_for_slide(
    slide_index: int,
    objects: list[dict[str, Any]],
    slide_size: dict[str, int | str],
) -> dict[str, list[dict[str, Any]]]:
    warnings = {
        "shape_overflows": [],
        "picture_overflows": [],
        "text_picture_overlaps": [],
        "blank_shape_over_pictures": [],
        "full_slide_picture_over_text": [],
    }

    text_shapes = [obj for obj in objects if obj["kind"] == "shape" and obj.get("text_chars", 0) > 0]
    blank_shapes = [obj for obj in objects if obj["kind"] == "shape" and obj.get("blank")]
    pictures = [obj for obj in objects if obj["kind"] == "picture"]

    for obj in objects:
        if not box_overflows_slide(obj.get("box"), slide_size):
            continue
        entry = {
            "slide": slide_index,
            "order": obj["order"],
            "box": obj.get("box"),
        }
        if obj["kind"] == "picture":
            entry["target"] = obj.get("target", "")
            warnings["picture_overflows"].append(entry)
        else:
            entry["text"] = str(obj.get("text", ""))[:80]
            warnings["shape_overflows"].append(entry)

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
    slide_height = slide_size.get("cy")
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
        return {
            "text": text,
            "number": number,
            "total": total,
            "x": shape.get("x"),
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
        "text_picture_overlaps": [],
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
                    "shape_count": 0,
                    "chart_count": 0,
                    "notes": False,
                    "page_number_candidates": [],
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
                slide_report["picture_count"] = len(pictures)
                slide_report["pictures"] = [
                    {
                        "order": obj["order"],
                        "target": obj.get("target", ""),
                        "box": obj.get("box"),
                    }
                    for obj in pictures
                ]
                slide_layout_warnings = layout_warnings_for_slide(index, slide_objects, slide_size)
                slide_report["layout_warning_count"] = sum(len(items) for items in slide_layout_warnings.values())
                for key, items in slide_layout_warnings.items():
                    result[key].extend(items)

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

            if not result["slides"]:
                result["warnings"].append("no_slides_found")
            result["layout_warning_summary"] = {
                "shape_overflows": len(result["shape_overflows"]),
                "picture_overflows": len(result["picture_overflows"]),
                "text_picture_overlaps": len(result["text_picture_overlaps"]),
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
            if result["text_picture_overlaps"]:
                result["warnings"].append("text_picture_overlaps")
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
