#!/usr/bin/env python3
"""Portable XLSX inspection helper for the spreadsheet skill."""

from __future__ import annotations

import argparse
import json
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Optional
from xml.etree import ElementTree as ET

REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
MAIN_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL_DOC_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
FORMULA_ERROR_RE = re.compile(r"#(?:REF!|DIV/0!|VALUE!|NAME\?|N/A|NUM!|NULL!)", re.I)
VOLATILE_RE = re.compile(r"\b(?:NOW|TODAY|RAND|RANDBETWEEN|OFFSET|INDIRECT|INFO)\s*\(", re.I)
EXTERNAL_LINK_RE = re.compile(r"\[[^\]]+\]")


def read_xml(zf: zipfile.ZipFile, name: str) -> Optional[ET.Element]:
    try:
        return ET.fromstring(zf.read(name))
    except Exception:
        return None


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


def relationship_part_for(part: str) -> str:
    directory = posixpath.dirname(part)
    base = posixpath.basename(part)
    return posixpath.join(directory, "_rels", f"{base}.rels")


def text_of(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return "".join(child.text or "" for child in node.iter())


def inspect_xlsx(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "file": str(path),
        "ok": False,
        "errors": [],
        "warnings": [],
        "sheet_count": 0,
        "sheets": [],
        "defined_names": [],
        "formula_count": 0,
        "formula_error_count": 0,
        "volatile_formula_count": 0,
        "external_formula_reference_count": 0,
        "shared_formula_count": 0,
        "array_formula_count": 0,
        "table_count": 0,
        "data_validation_count": 0,
        "merged_cell_count": 0,
        "comment_count": 0,
        "hyperlink_count": 0,
        "drawing_count": 0,
        "chart_part_count": 0,
        "pivot_part_count": 0,
        "external_relationships": [],
        "missing_relationship_targets": [],
        "macro_present": False,
        "calc_mode": "",
        "full_calc_on_load": None,
        "calc_chain_present": False,
        "unsupported_or_risky_parts": [],
    }
    if not path.exists():
        result["errors"].append("file_not_found")
        return result
    if path.suffix.lower() not in {".xlsx", ".xlsm", ".xltx", ".xltm"}:
        result["errors"].append("not_xlsx_package")
        return result

    try:
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
            if "[Content_Types].xml" not in names or "xl/workbook.xml" not in names:
                result["errors"].append("missing_required_xlsx_parts")
                return result

            result["macro_present"] = "xl/vbaProject.bin" in names
            result["calc_chain_present"] = "xl/calcChain.xml" in names
            result["chart_part_count"] = len([name for name in names if name.startswith("xl/charts/") and name.endswith(".xml")])
            result["pivot_part_count"] = len([name for name in names if name.startswith("xl/pivotTables/") or name.startswith("xl/pivotCache/")])
            result["unsupported_or_risky_parts"] = sorted([
                name for name in names
                if name.startswith("xl/slicer")
                or name.startswith("xl/timeline")
                or name.startswith("xl/externalLinks/")
                or name == "xl/vbaProject.bin"
            ])

            workbook = read_xml(zf, "xl/workbook.xml")
            workbook_rels = rels_for(zf, "xl/_rels/workbook.xml.rels")
            sheet_parts: list[tuple[str, str, str]] = []
            if workbook is not None:
                calc_pr = workbook.find(f"{MAIN_NS}calcPr")
                if calc_pr is not None:
                    result["calc_mode"] = calc_pr.attrib.get("calcMode", "")
                    full_calc = calc_pr.attrib.get("fullCalcOnLoad")
                    result["full_calc_on_load"] = full_calc == "1" if full_calc is not None else None
                sheets = workbook.find(f"{MAIN_NS}sheets")
                if sheets is not None:
                    for sheet in sheets.findall(f"{MAIN_NS}sheet"):
                        rid = sheet.attrib.get(f"{REL_DOC_NS}id")
                        rel = workbook_rels.get(rid or "", {})
                        target = rel.get("target", "")
                        part = normalized_target("xl/workbook.xml", target) if target else ""
                        sheet_parts.append((sheet.attrib.get("name", ""), sheet.attrib.get("state", "visible"), part))
                defined_names = workbook.find(f"{MAIN_NS}definedNames")
                if defined_names is not None:
                    for defined_name in defined_names.findall(f"{MAIN_NS}definedName"):
                        result["defined_names"].append({
                            "name": defined_name.attrib.get("name", ""),
                            "scope": defined_name.attrib.get("localSheetId", "workbook"),
                            "refers_to": (defined_name.text or "")[:200],
                        })

            result["sheet_count"] = len(sheet_parts)
            for sheet_name, state, part in sheet_parts:
                sheet_report = inspect_sheet(zf, names, sheet_name, state, part)
                result["sheets"].append(sheet_report)
                result["formula_count"] += sheet_report["formula_count"]
                result["formula_error_count"] += sheet_report["formula_error_count"]
                result["volatile_formula_count"] += sheet_report["volatile_formula_count"]
                result["external_formula_reference_count"] += sheet_report["external_formula_reference_count"]
                result["shared_formula_count"] += sheet_report["shared_formula_count"]
                result["array_formula_count"] += sheet_report["array_formula_count"]
                result["table_count"] += sheet_report["table_count"]
                result["data_validation_count"] += sheet_report["data_validation_count"]
                result["merged_cell_count"] += sheet_report["merged_cell_count"]
                result["comment_count"] += sheet_report["comment_count"]
                result["hyperlink_count"] += sheet_report["hyperlink_count"]
                result["drawing_count"] += sheet_report["drawing_count"]

            for part in ["xl/workbook.xml", *[sheet_part for _, _, sheet_part in sheet_parts if sheet_part]]:
                rels_name = relationship_part_for(part)
                if rels_name not in names:
                    continue
                for rid, rel in rels_for(zf, rels_name).items():
                    target = rel.get("target", "")
                    if rel.get("mode") == "External":
                        result["external_relationships"].append({"from": part, "rid": rid, "target": target})
                        continue
                    resolved = normalized_target(part, target)
                    if resolved not in names:
                        result["missing_relationship_targets"].append({"from": part, "rid": rid, "target": target})

            add_warnings(result)
            result["ok"] = not result["errors"] and not result["missing_relationship_targets"]
            return result
    except zipfile.BadZipFile:
        result["errors"].append("bad_zip")
        return result


def office_command() -> Optional[str]:
    for candidate in ("soffice", "libreoffice"):
        found = shutil.which(candidate)
        if found:
            return found
    return None


def recalc_xlsx(path: Path, output: Optional[Path], timeout: int) -> dict[str, Any]:
    result: dict[str, Any] = {
        "file": str(path),
        "ok": False,
        "engine": "libreoffice",
        "output": str(output) if output else "",
        "errors": [],
        "warnings": [],
        "inspect": None,
    }
    if not path.exists():
        result["errors"].append("file_not_found")
        return result
    if path.suffix.lower() not in {".xlsx", ".xltx"}:
        result["errors"].append("recalc_cli_supports_xlsx_only")
        return result

    office = office_command()
    if not office:
        result["errors"].append("libreoffice_not_found")
        return result

    out_path = output or path.with_name(f"{path.stem}.recalculated.xlsx")
    result["output"] = str(out_path)
    if out_path.resolve() == path.resolve():
        result["errors"].append("output_would_overwrite_source")
        return result

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        cmd = [
            office,
            "--headless",
            "--nologo",
            "--nolockcheck",
            "--nodefault",
            "--norestore",
            "--convert-to",
            "xlsx",
            "--outdir",
            str(tmp_path),
            str(path.resolve()),
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            result["errors"].append("libreoffice_timeout")
            return result

        if proc.returncode != 0:
            result["errors"].append("libreoffice_recalc_failed")
            if proc.stderr:
                result["warnings"].append(proc.stderr.strip()[:500])
            elif proc.stdout:
                result["warnings"].append(proc.stdout.strip()[:500])
            return result

        converted = tmp_path / path.with_suffix(".xlsx").name
        if not converted.exists():
            candidates = sorted(tmp_path.glob("*.xlsx"))
            if not candidates:
                result["errors"].append("recalculated_output_not_found")
                if proc.stdout:
                    result["warnings"].append(proc.stdout.strip()[:500])
                return result
            converted = candidates[0]

        out_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(converted, out_path)

    inspect_report = inspect_xlsx(out_path)
    result["inspect"] = inspect_report
    result["warnings"].extend(inspect_report.get("warnings", []))
    result["ok"] = bool(inspect_report.get("ok")) and not inspect_report.get("formula_error_count")
    if inspect_report.get("formula_error_count"):
        result["errors"].append("formula_errors_after_recalc")
    return result


def inspect_sheet(zf: zipfile.ZipFile, names: set[str], sheet_name: str, state: str, part: str) -> dict[str, Any]:
    root = read_xml(zf, part)
    report: dict[str, Any] = {
        "name": sheet_name,
        "state": state,
        "part": part,
        "dimension": "",
        "row_count_hint": 0,
        "cell_count_hint": 0,
        "formula_count": 0,
        "formula_error_count": 0,
        "volatile_formula_count": 0,
        "external_formula_reference_count": 0,
        "shared_formula_count": 0,
        "array_formula_count": 0,
        "table_count": 0,
        "data_validation_count": 0,
        "merged_cell_count": 0,
        "comment_count": 0,
        "hyperlink_count": 0,
        "drawing_count": 0,
        "protected": False,
        "autofilter": False,
        "formula_samples": [],
    }
    if root is None:
        return report
    dimension = root.find(f"{MAIN_NS}dimension")
    if dimension is not None:
        report["dimension"] = dimension.attrib.get("ref", "")
    rows = list(root.iter(f"{MAIN_NS}row"))
    report["row_count_hint"] = len(rows)
    cells = list(root.iter(f"{MAIN_NS}c"))
    report["cell_count_hint"] = len(cells)
    for formula in root.iter(f"{MAIN_NS}f"):
        formula_text = formula.text or ""
        report["formula_count"] += 1
        if formula.attrib.get("t") == "shared":
            report["shared_formula_count"] += 1
        if formula.attrib.get("t") == "array":
            report["array_formula_count"] += 1
        if FORMULA_ERROR_RE.search(formula_text):
            report["formula_error_count"] += 1
        if VOLATILE_RE.search(formula_text):
            report["volatile_formula_count"] += 1
        if EXTERNAL_LINK_RE.search(formula_text):
            report["external_formula_reference_count"] += 1
        if len(report["formula_samples"]) < 12:
            report["formula_samples"].append(formula_text[:160])
    for value in root.iter(f"{MAIN_NS}v"):
        if value.text and FORMULA_ERROR_RE.search(value.text):
            report["formula_error_count"] += 1
    data_validations = root.find(f"{MAIN_NS}dataValidations")
    if data_validations is not None:
        report["data_validation_count"] = len(list(data_validations.findall(f"{MAIN_NS}dataValidation")))
    merge_cells = root.find(f"{MAIN_NS}mergeCells")
    if merge_cells is not None:
        report["merged_cell_count"] = len(list(merge_cells.findall(f"{MAIN_NS}mergeCell")))
    report["protected"] = root.find(f"{MAIN_NS}sheetProtection") is not None
    report["autofilter"] = root.find(f"{MAIN_NS}autoFilter") is not None
    report["hyperlink_count"] = len(list(root.iter(f"{MAIN_NS}hyperlink")))
    report["drawing_count"] = len(list(root.iter(f"{MAIN_NS}drawing")))

    rels_name = relationship_part_for(part)
    if rels_name in names:
        for rel in rels_for(zf, rels_name).values():
            rel_type = rel.get("type", "")
            target = rel.get("target", "")
            if rel_type.endswith("/table"):
                report["table_count"] += 1
            if rel_type.endswith("/comments") or "comments" in target:
                comment_part = normalized_target(part, target)
                comments = read_xml(zf, comment_part)
                if comments is not None:
                    report["comment_count"] += len(list(comments.iter(f"{MAIN_NS}comment")))
    return report


def add_warnings(result: dict[str, Any]) -> None:
    if any(sheet["state"] != "visible" for sheet in result["sheets"]):
        result["warnings"].append("hidden_sheets_present")
    if any(sheet["protected"] for sheet in result["sheets"]):
        result["warnings"].append("protected_sheets_present")
    if result["formula_error_count"]:
        result["warnings"].append("formula_error_markers_present")
    if result["volatile_formula_count"]:
        result["warnings"].append("volatile_formulas_present")
    if result["external_formula_reference_count"] or result["external_relationships"]:
        result["warnings"].append("external_links_present")
    if result["missing_relationship_targets"]:
        result["warnings"].append("missing_relationship_targets")
    if result["macro_present"]:
        result["warnings"].append("macro_present")
    if result["pivot_part_count"]:
        result["warnings"].append("pivot_parts_present")
    if result["chart_part_count"]:
        result["warnings"].append("chart_parts_present")
    if result["unsupported_or_risky_parts"]:
        result["warnings"].append("advanced_or_risky_parts_present")
    if result["formula_count"] and not result["calc_chain_present"]:
        result["warnings"].append("formula_workbook_without_calc_chain")


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect or recalculate an XLSX workbook package.")
    sub = parser.add_subparsers(dest="command", required=True)
    inspect_cmd = sub.add_parser("inspect", help="Inspect XLSX package structure.")
    inspect_cmd.add_argument("workbook")
    inspect_cmd.add_argument("--out", default="-")
    recalc_cmd = sub.add_parser("recalc", help="Recalculate formulas with LibreOffice when available, then inspect the result.")
    recalc_cmd.add_argument("workbook")
    recalc_cmd.add_argument("--output")
    recalc_cmd.add_argument("--timeout", type=int, default=60)
    recalc_cmd.add_argument("--out", default="-", help="Write the JSON report to this path, or '-' for stdout.")
    args = parser.parse_args()

    if args.command == "inspect":
        report = inspect_xlsx(Path(args.workbook))
    else:
        report = recalc_xlsx(
            Path(args.workbook),
            Path(args.output) if args.output else None,
            args.timeout,
        )

    data = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out == "-":
        print(data)
    else:
        Path(args.out).write_text(data + "\n", encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
