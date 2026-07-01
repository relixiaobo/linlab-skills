#!/usr/bin/env python3
"""Portable PDF helper for the pdf skill."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

try:
    from pypdf import PdfReader, PdfWriter
except Exception:  # pragma: no cover - import availability is environment-specific
    PdfReader = None
    PdfWriter = None


PDF_ERROR_RE = re.compile(r"(error|syntax|damaged|invalid|xref|trailer)", re.I)


def run_command(cmd: list[str], timeout: int = 60) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return {"ok": False, "error": "command_not_found", "cmd": cmd}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout", "cmd": cmd}
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "cmd": cmd,
    }


def parse_pdfinfo(text: str) -> dict[str, Any]:
    info: dict[str, Any] = {}
    page_sizes = []
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        normalized = key.lower().replace(" ", "_")
        if normalized.startswith("page_") and "size" in normalized:
            page_sizes.append(value)
        else:
            info[normalized] = value
    if page_sizes:
        info["page_sizes"] = page_sizes
    return info


def inspect_with_pypdf(path: Path, password: Optional[str]) -> dict[str, Any]:
    report: dict[str, Any] = {
        "available": PdfReader is not None,
        "ok": False,
        "errors": [],
        "page_count": None,
        "metadata": {},
        "pages": [],
        "encrypted": None,
        "form_field_count": 0,
        "outline_count": 0,
        "attachment_count": 0,
        "text_sample_chars": 0,
        "annotation_count": 0,
    }
    if PdfReader is None:
        report["errors"].append("pypdf_not_installed")
        return report
    try:
        reader = PdfReader(str(path))
        report["encrypted"] = reader.is_encrypted
        if reader.is_encrypted:
            if password is None:
                report["errors"].append("encrypted_password_required")
                return report
            if not reader.decrypt(password):
                report["errors"].append("decrypt_failed")
                return report

        report["page_count"] = len(reader.pages)
        report["metadata"] = {str(k): str(v) for k, v in (reader.metadata or {}).items()}
        for index, page in enumerate(reader.pages):
            media = [float(x) for x in page.mediabox]
            crop = [float(x) for x in page.cropbox]
            rotate = int(page.get("/Rotate", 0) or 0)
            annots = page.get("/Annots") or []
            text_sample = ""
            try:
                text_sample = page.extract_text() or ""
            except Exception:
                text_sample = ""
            report["annotation_count"] += len(annots)
            report["text_sample_chars"] += len(text_sample[:2000])
            report["pages"].append({
                "page": index + 1,
                "mediabox": media,
                "cropbox": crop,
                "rotate": rotate,
                "annotation_count": len(annots),
                "text_sample_chars": len(text_sample[:2000]),
            })

        try:
            fields = reader.get_fields() or {}
            report["form_field_count"] = len(fields)
        except Exception:
            pass
        try:
            outline = reader.outline
            report["outline_count"] = len(outline) if isinstance(outline, list) else 1
        except Exception:
            pass
        try:
            attachments = getattr(reader, "attachments", {}) or {}
            report["attachment_count"] = len(attachments)
        except Exception:
            pass
        report["ok"] = not report["errors"]
        return report
    except Exception as exc:
        report["errors"].append(type(exc).__name__)
        report["detail"] = str(exc)[:500]
        return report


def inspect_pdf(path: Path, password: Optional[str]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "file": str(path),
        "ok": False,
        "errors": [],
        "warnings": [],
        "tools": {},
        "pdfinfo": {},
        "pypdf": {},
        "risk_markers": [],
    }
    if not path.exists():
        result["errors"].append("file_not_found")
        return result
    if path.suffix.lower() != ".pdf":
        result["errors"].append("not_pdf_extension")
        return result

    pdfinfo = shutil.which("pdfinfo")
    result["tools"]["pdfinfo"] = bool(pdfinfo)
    if pdfinfo:
        cmd = [pdfinfo, "-box", str(path)]
        if password:
            cmd = [pdfinfo, "-upw", password, "-box", str(path)]
        proc = run_command(cmd)
        if proc["ok"]:
            result["pdfinfo"] = parse_pdfinfo(proc["stdout"])
        else:
            result["warnings"].append("pdfinfo_failed")
            stderr = proc.get("stderr", "")
            if stderr:
                result["risk_markers"].append(stderr.strip()[:500])
    else:
        result["warnings"].append("pdfinfo_not_found")

    py_report = inspect_with_pypdf(path, password)
    result["pypdf"] = py_report
    if py_report["errors"]:
        result["warnings"].extend(py_report["errors"])
    if py_report.get("encrypted"):
        result["risk_markers"].append("encrypted")
    if py_report.get("form_field_count"):
        result["risk_markers"].append("form_fields_present")
    if py_report.get("annotation_count"):
        result["risk_markers"].append("annotations_present")
    if py_report.get("attachment_count"):
        result["risk_markers"].append("attachments_present")
    if py_report.get("page_count") and not py_report.get("text_sample_chars"):
        result["risk_markers"].append("no_extractable_text_sample")
    page_rotations = {page["rotate"] for page in py_report.get("pages", [])}
    if len(page_rotations) > 1 or any(rotation for rotation in page_rotations):
        result["risk_markers"].append("page_rotations_present")
    if PDF_ERROR_RE.search("\n".join(result.get("risk_markers", []))):
        result["warnings"].append("possible_pdf_structure_issue")

    result["ok"] = not result["errors"] and py_report.get("ok", False)
    return result


def render_pdf(path: Path, out_dir: Path, dpi: int, pages: Optional[str], password: Optional[str]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "file": str(path),
        "ok": False,
        "output_dir": str(out_dir),
        "files": [],
        "errors": [],
        "warnings": [],
        "tool": "pdftoppm",
    }
    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm:
        result["errors"].append("pdftoppm_not_found")
        return result
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = out_dir / path.stem
    cmd = [pdftoppm, "-r", str(dpi), "-png"]
    if password:
        cmd.extend(["-upw", password])
    if pages:
        first, last = parse_page_range(pages)
        if first:
            cmd.extend(["-f", str(first)])
        if last:
            cmd.extend(["-l", str(last)])
    cmd.extend([str(path), str(prefix)])
    proc = run_command(cmd, timeout=180)
    if not proc["ok"]:
        result["errors"].append("render_failed")
        if proc.get("stderr"):
            result["warnings"].append(proc["stderr"].strip()[:500])
        return result
    files = sorted(out_dir.glob(f"{path.stem}-*.png"))
    result["files"] = [str(file) for file in files]
    result["ok"] = bool(files)
    if not files:
        result["errors"].append("no_rendered_pages")
    return result


def parse_page_range(value: str) -> tuple[Optional[int], Optional[int]]:
    if "-" in value:
        first, last = value.split("-", 1)
        return int(first) if first else None, int(last) if last else None
    page = int(value)
    return page, page


def extract_text(path: Path, out: Path, layout: bool, password: Optional[str]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "file": str(path),
        "ok": False,
        "output": str(out),
        "errors": [],
        "warnings": [],
        "tool": "",
        "char_count": 0,
    }
    pdftotext = shutil.which("pdftotext")
    if pdftotext:
        cmd = [pdftotext]
        if password:
            cmd.extend(["-upw", password])
        if layout:
            cmd.append("-layout")
        cmd.extend([str(path), str(out)])
        proc = run_command(cmd)
        if proc["ok"] and out.exists():
            text = out.read_text(errors="replace")
            result["tool"] = "pdftotext"
            result["char_count"] = len(text)
            result["ok"] = True
            if not text.strip():
                result["warnings"].append("empty_text_output")
            return result
        result["warnings"].append("pdftotext_failed")

    if PdfReader is None:
        result["errors"].append("no_text_extractor_available")
        return result
    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            if password is None or not reader.decrypt(password):
                result["errors"].append("decrypt_failed")
                return result
        chunks = []
        for index, page in enumerate(reader.pages):
            chunks.append(f"\n\n--- Page {index + 1} ---\n")
            chunks.append(page.extract_text() or "")
        text = "".join(chunks)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        result["tool"] = "pypdf"
        result["char_count"] = len(text)
        result["ok"] = True
        if not text.strip():
            result["warnings"].append("empty_text_output")
        return result
    except Exception as exc:
        result["errors"].append(type(exc).__name__)
        result["warnings"].append(str(exc)[:500])
        return result


def require_pypdf() -> Optional[str]:
    if PdfReader is None or PdfWriter is None:
        return "pypdf_not_installed"
    return None


def merge_pdfs(output: Path, inputs: list[Path]) -> dict[str, Any]:
    result = {"ok": False, "output": str(output), "inputs": [str(p) for p in inputs], "errors": [], "warnings": []}
    missing = require_pypdf()
    if missing:
        result["errors"].append(missing)
        return result
    try:
        writer = PdfWriter()
        for path in inputs:
            reader = PdfReader(str(path))
            for page in reader.pages:
                writer.add_page(page)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("wb") as fh:
            writer.write(fh)
        result["ok"] = True
        return result
    except Exception as exc:
        result["errors"].append(type(exc).__name__)
        result["warnings"].append(str(exc)[:500])
        return result


def split_pdf(input_pdf: Path, out_dir: Path, ranges: Optional[list[str]]) -> dict[str, Any]:
    result = {"ok": False, "file": str(input_pdf), "output_dir": str(out_dir), "files": [], "errors": [], "warnings": []}
    missing = require_pypdf()
    if missing:
        result["errors"].append(missing)
        return result
    try:
        reader = PdfReader(str(input_pdf))
        out_dir.mkdir(parents=True, exist_ok=True)
        requested = ranges or [str(i + 1) for i in range(len(reader.pages))]
        for spec in requested:
            first, last = parse_page_range(spec)
            start = (first or 1) - 1
            stop = last or len(reader.pages)
            writer = PdfWriter()
            for page_index in range(start, stop):
                writer.add_page(reader.pages[page_index])
            safe = spec.replace("-", "_")
            out_path = out_dir / f"{input_pdf.stem}_pages_{safe}.pdf"
            with out_path.open("wb") as fh:
                writer.write(fh)
            result["files"].append(str(out_path))
        result["ok"] = True
        return result
    except Exception as exc:
        result["errors"].append(type(exc).__name__)
        result["warnings"].append(str(exc)[:500])
        return result


def rotate_pdf(input_pdf: Path, output: Path, rotation: int, pages: Optional[str]) -> dict[str, Any]:
    result = {"ok": False, "file": str(input_pdf), "output": str(output), "errors": [], "warnings": []}
    missing = require_pypdf()
    if missing:
        result["errors"].append(missing)
        return result
    try:
        reader = PdfReader(str(input_pdf))
        writer = PdfWriter()
        first, last = parse_page_range(pages) if pages else (1, len(reader.pages))
        for index, page in enumerate(reader.pages, start=1):
            if (first or 1) <= index <= (last or len(reader.pages)):
                page.rotate(rotation)
            writer.add_page(page)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("wb") as fh:
            writer.write(fh)
        result["ok"] = True
        return result
    except Exception as exc:
        result["errors"].append(type(exc).__name__)
        result["warnings"].append(str(exc)[:500])
        return result


def emit(report: dict[str, Any], out: str) -> int:
    data = json.dumps(report, indent=2, ensure_ascii=False)
    if out == "-":
        print(data)
    else:
        Path(out).write_text(data + "\n", encoding="utf-8")
    return 0 if report.get("ok") else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect, render, extract, and perform baseline PDF operations.")
    sub = parser.add_subparsers(dest="command", required=True)

    inspect_cmd = sub.add_parser("inspect", help="Inspect a PDF.")
    inspect_cmd.add_argument("pdf")
    inspect_cmd.add_argument("--password")
    inspect_cmd.add_argument("--out", default="-")

    render_cmd = sub.add_parser("render", help="Render PDF pages to PNG files with Poppler.")
    render_cmd.add_argument("pdf")
    render_cmd.add_argument("--dir", required=True)
    render_cmd.add_argument("--dpi", type=int, default=150)
    render_cmd.add_argument("--pages", help="Single page or range, such as 1 or 2-5.")
    render_cmd.add_argument("--password")
    render_cmd.add_argument("--out", default="-")

    text_cmd = sub.add_parser("extract-text", help="Extract PDF text.")
    text_cmd.add_argument("pdf")
    text_cmd.add_argument("--out", required=True)
    text_cmd.add_argument("--layout", action="store_true")
    text_cmd.add_argument("--password")
    text_cmd.add_argument("--report", default="-")

    merge_cmd = sub.add_parser("merge", help="Merge PDFs with pypdf.")
    merge_cmd.add_argument("output")
    merge_cmd.add_argument("inputs", nargs="+")
    merge_cmd.add_argument("--report", default="-")

    split_cmd = sub.add_parser("split", help="Split a PDF with pypdf.")
    split_cmd.add_argument("pdf")
    split_cmd.add_argument("--dir", required=True)
    split_cmd.add_argument("--ranges", nargs="*", help="Page ranges such as 1 2-4 5-.")
    split_cmd.add_argument("--report", default="-")

    rotate_cmd = sub.add_parser("rotate", help="Rotate pages with pypdf.")
    rotate_cmd.add_argument("pdf")
    rotate_cmd.add_argument("--output", required=True)
    rotate_cmd.add_argument("--degrees", type=int, required=True, choices=[90, 180, 270, -90, -180, -270])
    rotate_cmd.add_argument("--pages", help="Single page or range, default all pages.")
    rotate_cmd.add_argument("--report", default="-")

    args = parser.parse_args()
    if args.command == "inspect":
        return emit(inspect_pdf(Path(args.pdf), args.password), args.out)
    if args.command == "render":
        return emit(render_pdf(Path(args.pdf), Path(args.dir), args.dpi, args.pages, args.password), args.out)
    if args.command == "extract-text":
        return emit(extract_text(Path(args.pdf), Path(args.out), args.layout, args.password), args.report)
    if args.command == "merge":
        return emit(merge_pdfs(Path(args.output), [Path(p) for p in args.inputs]), args.report)
    if args.command == "split":
        return emit(split_pdf(Path(args.pdf), Path(args.dir), args.ranges), args.report)
    if args.command == "rotate":
        return emit(rotate_pdf(Path(args.pdf), Path(args.output), args.degrees, args.pages), args.report)
    return 2


if __name__ == "__main__":
    sys.exit(main())
