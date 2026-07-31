#!/usr/bin/env python3
"""Judge formula-driven spreadsheet artifacts with deterministic workbook evidence."""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evals.judges.common import anonymized_result, trace_summary  # noqa: E402
from evals.judges.model_judge_runtime import (  # noqa: E402
    ModelJudgeError,
    ModelJudgeOptions,
    run_blind_model_judge,
)
from evals.runners.eval_lib import EvalConfigError, safe_child  # noqa: E402


REQUIRED_ENV = {
    "EVAL_ORACLE_FILE",
    "EVAL_RESULT_FILE",
    "EVAL_PAYLOAD_DIR",
    "EVAL_OUTPUT_DIR",
    "EVAL_JUDGE_RESULT_FILE",
}
TABLE_TOOL = ROOT / "skills" / "spreadsheet" / "scripts" / "table_tool.py"
WORKBOOK_TOOL = ROOT / "skills" / "spreadsheet" / "scripts" / "workbook_tool.py"
MAIN_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
REL_DOC_NS = (
    "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
)
CELL_REF_RE = re.compile(r"^([A-Z]+)([1-9][0-9]*)$")
CELL_RANGE_RE = re.compile(
    r"^\$?([A-Z]+)\$?([1-9][0-9]*):\$?([A-Z]+)\$?([1-9][0-9]*)$"
)
DEFINED_CELL_RE = re.compile(
    r"^'?((?:[^']|'')+)'?!\$?([A-Z]+)\$?([1-9][0-9]*)$"
)
LITERAL_FORMULA_RE = re.compile(r"^\s*[+-]?(?:\d+(?:\.\d*)?|\.\d+)\s*$")


class SpreadsheetJudgeError(RuntimeError):
    """Raised when spreadsheet evidence cannot be produced safely."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SpreadsheetJudgeError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SpreadsheetJudgeError(f"{path} must contain an object")
    return value


def environment() -> dict[str, Path]:
    missing = sorted(name for name in REQUIRED_ENV if not os.environ.get(name))
    if missing:
        raise SpreadsheetJudgeError(
            f"missing judge environment variables: {', '.join(missing)}"
        )
    return {name: Path(os.environ[name]).resolve() for name in REQUIRED_ENV}


def judge_config() -> dict[str, Any]:
    try:
        value = json.loads(os.environ.get("EVAL_JUDGE_CONFIG", "{}"))
    except json.JSONDecodeError as exc:
        raise SpreadsheetJudgeError(f"invalid EVAL_JUDGE_CONFIG: {exc}") from exc
    if not isinstance(value, dict):
        raise SpreadsheetJudgeError("EVAL_JUDGE_CONFIG must contain an object")
    required = {
        "artifact",
        "source",
        "calculations",
        "workbook",
        "criterion_failure_tags",
    }
    missing = sorted(required - set(value))
    unknown = sorted(set(value) - required)
    if missing or unknown:
        raise SpreadsheetJudgeError(
            f"spreadsheet config mismatch; missing={missing}, unknown={unknown}"
        )
    return value


def require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise SpreadsheetJudgeError(f"{label} must be a non-empty string")
    return value


def require_string_list(value: Any, label: str) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or not item for item in value)
    ):
        raise SpreadsheetJudgeError(f"{label} must be a non-empty string array")
    if len(value) != len(set(value)):
        raise SpreadsheetJudgeError(f"{label} must not contain duplicates")
    return value


def expression_tree(expression: str) -> ast.Expression:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise SpreadsheetJudgeError(f"invalid calculation expression: {expression}") from exc
    allowed = (
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Name,
        ast.Constant,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.UAdd,
        ast.USub,
        ast.Load,
    )
    for node in ast.walk(tree):
        if not isinstance(node, allowed):
            raise SpreadsheetJudgeError(
                f"unsupported calculation expression node: {type(node).__name__}"
            )
        if isinstance(node, ast.Constant) and (
            isinstance(node.value, bool) or not isinstance(node.value, (int, float))
        ):
            raise SpreadsheetJudgeError(
                "calculation expression constants must be numeric"
            )
    return tree


def expression_names(expression: str) -> set[str]:
    return {
        node.id
        for node in ast.walk(expression_tree(expression))
        if isinstance(node, ast.Name)
    }


def evaluate_expression(expression: str, values: dict[str, Decimal]) -> Decimal:
    def evaluate(node: ast.AST) -> Decimal:
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Name):
            if node.id not in values:
                raise SpreadsheetJudgeError(
                    f"calculation expression references unknown value {node.id}"
                )
            return values[node.id]
        if isinstance(node, ast.Constant):
            return Decimal(str(node.value))
        if isinstance(node, ast.UnaryOp):
            operand = evaluate(node.operand)
            return operand if isinstance(node.op, ast.UAdd) else -operand
        if isinstance(node, ast.BinOp):
            left = evaluate(node.left)
            right = evaluate(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
        raise SpreadsheetJudgeError("unsupported calculation expression")

    return evaluate(expression_tree(expression))


def validate_config(config: dict[str, Any], oracle: dict[str, Any]) -> None:
    if oracle.get("job") != "create-spreadsheet":
        raise SpreadsheetJudgeError(
            "spreadsheet adapter requires oracle job create-spreadsheet"
        )
    outcome_ids = {item["id"] for item in oracle["expected"]["outcomes"]}
    allowed_tags = set(oracle.get("failure_taxonomy", []))

    artifact = config["artifact"]
    if not isinstance(artifact, dict) or set(artifact) != {"path", "criterion"}:
        raise SpreadsheetJudgeError("artifact config has an invalid shape")
    artifact_path_value = require_string(artifact["path"], "artifact.path")
    if Path(artifact_path_value).suffix.lower() != ".xlsx":
        raise SpreadsheetJudgeError("spreadsheet artifact must be an .xlsx file")
    artifact_criterion = require_string(
        artifact["criterion"], "artifact.criterion"
    )

    source = config["source"]
    if not isinstance(source, dict) or set(source) != {
        "path",
        "sheet",
        "key_column",
        "columns",
        "criterion",
    }:
        raise SpreadsheetJudgeError("source config has an invalid shape")
    require_string(source["path"], "source.path")
    require_string(source["sheet"], "source.sheet")
    key_column = require_string(source["key_column"], "source.key_column")
    source_criterion = require_string(source["criterion"], "source.criterion")
    columns = source["columns"]
    if not isinstance(columns, list) or not columns:
        raise SpreadsheetJudgeError("source.columns must be a non-empty array")
    column_ids: list[str] = []
    for column in columns:
        if not isinstance(column, dict) or set(column) != {"id", "headers", "type"}:
            raise SpreadsheetJudgeError("source column has an invalid shape")
        column_id = require_string(column["id"], "source column id")
        column_ids.append(column_id)
        require_string_list(column["headers"], f"source column {column_id} headers")
        if column["type"] not in {"string", "decimal"}:
            raise SpreadsheetJudgeError(
                f"source column {column_id} type must be string or decimal"
            )
    if len(column_ids) != len(set(column_ids)):
        raise SpreadsheetJudgeError("source column ids must be unique")
    if key_column not in column_ids:
        raise SpreadsheetJudgeError("source.key_column must name a source column")

    calculations = config["calculations"]
    if not isinstance(calculations, dict) or set(calculations) != {
        "sheet",
        "constants",
        "outputs",
        "criterion",
    }:
        raise SpreadsheetJudgeError("calculations config has an invalid shape")
    require_string(calculations["sheet"], "calculations.sheet")
    calculation_criterion = require_string(
        calculations["criterion"], "calculations.criterion"
    )
    constants = calculations["constants"]
    if not isinstance(constants, dict):
        raise SpreadsheetJudgeError("calculations.constants must be an object")
    for name, value in constants.items():
        require_string(name, "calculation constant name")
        require_string(value, f"calculation constant {name}")
        try:
            Decimal(value)
        except InvalidOperation as exc:
            raise SpreadsheetJudgeError(
                f"calculation constant {name} must be decimal"
            ) from exc
    outputs = calculations["outputs"]
    if not isinstance(outputs, list) or not outputs:
        raise SpreadsheetJudgeError("calculations.outputs must be non-empty")
    output_ids: list[str] = []
    allowed_expression_names = set(column_ids) | set(constants)
    for output in outputs:
        if not isinstance(output, dict) or set(output) != {
            "id",
            "headers",
            "expression",
        }:
            raise SpreadsheetJudgeError("calculation output has an invalid shape")
        output_id = require_string(output["id"], "calculation output id")
        output_ids.append(output_id)
        require_string_list(output["headers"], f"output {output_id} headers")
        expression = require_string(
            output["expression"], f"output {output_id} expression"
        )
        unknown_names = expression_names(expression) - allowed_expression_names
        if unknown_names:
            raise SpreadsheetJudgeError(
                f"output {output_id} references unknown names: {sorted(unknown_names)}"
            )
    if len(output_ids) != len(set(output_ids)):
        raise SpreadsheetJudgeError("calculation output ids must be unique")

    workbook = config["workbook"]
    if not isinstance(workbook, dict) or set(workbook) != {
        "required_sheets",
        "required_defined_names",
        "checks_sheet",
        "minimum_check_formula_count",
        "architecture_criterion",
        "input_criterion",
        "verification_criterion",
    }:
        raise SpreadsheetJudgeError("workbook config has an invalid shape")
    required_sheets = require_string_list(
        workbook["required_sheets"], "workbook.required_sheets"
    )
    for required_sheet in (source["sheet"], calculations["sheet"]):
        if required_sheet not in required_sheets:
            raise SpreadsheetJudgeError(
                f"required sheets must include {required_sheet}"
            )
    checks_sheet = require_string(workbook["checks_sheet"], "workbook.checks_sheet")
    if checks_sheet not in required_sheets:
        raise SpreadsheetJudgeError("required sheets must include checks_sheet")
    minimum_checks = workbook["minimum_check_formula_count"]
    if not isinstance(minimum_checks, int) or isinstance(minimum_checks, bool) or minimum_checks < 1:
        raise SpreadsheetJudgeError(
            "workbook.minimum_check_formula_count must be positive"
        )
    names = workbook["required_defined_names"]
    if not isinstance(names, list) or not names:
        raise SpreadsheetJudgeError(
            "workbook.required_defined_names must be non-empty"
        )
    defined_names: list[str] = []
    for item in names:
        if not isinstance(item, dict) or set(item) != {"name", "value"}:
            raise SpreadsheetJudgeError("required defined name has an invalid shape")
        name = require_string(item["name"], "required defined name")
        defined_names.append(name.casefold())
        value = require_string(item["value"], f"defined name {name} value")
        try:
            Decimal(value)
        except InvalidOperation as exc:
            raise SpreadsheetJudgeError(
                f"defined name {name} value must be decimal"
            ) from exc
    if len(defined_names) != len(set(defined_names)):
        raise SpreadsheetJudgeError("required defined names must be unique")

    workbook_criteria = {
        require_string(
            workbook["architecture_criterion"], "workbook.architecture_criterion"
        ),
        require_string(workbook["input_criterion"], "workbook.input_criterion"),
        require_string(
            workbook["verification_criterion"], "workbook.verification_criterion"
        ),
    }
    configured_criteria = {
        artifact_criterion,
        source_criterion,
        calculation_criterion,
        *workbook_criteria,
    }
    unknown_criteria = sorted(configured_criteria - outcome_ids)
    if unknown_criteria:
        raise SpreadsheetJudgeError(
            f"config references unknown criteria: {unknown_criteria}"
        )
    tag_map = config["criterion_failure_tags"]
    if not isinstance(tag_map, dict) or set(tag_map) != configured_criteria:
        raise SpreadsheetJudgeError(
            "criterion_failure_tags must cover every configured criterion"
        )
    invalid_tags = sorted(
        repr(tag)
        for tag in tag_map.values()
        if not isinstance(tag, str) or tag not in allowed_tags
    )
    if invalid_tags:
        raise SpreadsheetJudgeError(
            f"criterion_failure_tags contains unsupported tags: {invalid_tags}"
        )


def decimal_text(value: Decimal) -> str:
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def build_source_truth(config: dict[str, Any], payload_dir: Path) -> dict[str, Any]:
    source_config = config["source"]
    source_path = safe_child(payload_dir, source_config["path"])
    try:
        with source_path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = list(reader.fieldnames or [])
            raw_rows = list(reader)
    except OSError as exc:
        raise SpreadsheetJudgeError(f"cannot read source CSV: {exc}") from exc
    expected_columns = [item["id"] for item in source_config["columns"]]
    if fields != expected_columns:
        raise SpreadsheetJudgeError(
            f"source CSV columns mismatch: expected {expected_columns}, got {fields}"
        )
    if not raw_rows:
        raise SpreadsheetJudgeError("source CSV must contain at least one data row")

    typed_rows: list[dict[str, str]] = []
    calculations = config["calculations"]
    constants = {
        name: Decimal(value) for name, value in calculations["constants"].items()
    }
    for row_number, raw_row in enumerate(raw_rows, start=2):
        values: dict[str, Decimal] = dict(constants)
        serialized: dict[str, str] = {}
        for column in source_config["columns"]:
            column_id = column["id"]
            raw_value = raw_row.get(column_id, "")
            if column["type"] == "string":
                if not raw_value:
                    raise SpreadsheetJudgeError(
                        f"source row {row_number} has an empty {column_id}"
                    )
                serialized[column_id] = raw_value
            else:
                try:
                    decimal_value = Decimal(raw_value)
                except InvalidOperation as exc:
                    raise SpreadsheetJudgeError(
                        f"source row {row_number} has invalid decimal {column_id}"
                    ) from exc
                values[column_id] = decimal_value
                serialized[column_id] = decimal_text(decimal_value)
        serialized["expected_outputs"] = {
            output["id"]: decimal_text(
                evaluate_expression(output["expression"], values)
            )
            for output in calculations["outputs"]
        }
        typed_rows.append(serialized)

    return {
        "source": source_config["path"],
        "columns": source_config["columns"],
        "key_column": source_config["key_column"],
        "constants": {
            name: decimal_text(value) for name, value in constants.items()
        },
        "output_contracts": calculations["outputs"],
        "rows": typed_rows,
    }


def artifact_path(output_dir: Path, relative: str) -> Path:
    unresolved = output_dir / relative
    if unresolved.is_symlink():
        raise SpreadsheetJudgeError(f"artifact must not be a symlink: {relative}")
    return safe_child(output_dir, relative)


def run_report_tool(
    command: list[str],
    *,
    report_path: Path,
    evidence_dir: Path,
    log_prefix: str,
    timeout: int = 60,
) -> dict[str, Any]:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SpreadsheetJudgeError(f"cannot run {log_prefix}: {exc}") from exc
    (evidence_dir / f"{log_prefix}.stdout.log").write_text(
        proc.stdout, encoding="utf-8"
    )
    (evidence_dir / f"{log_prefix}.stderr.log").write_text(
        proc.stderr, encoding="utf-8"
    )
    if proc.returncode not in {0, 1} or not report_path.is_file():
        tail = f"{proc.stderr}\n{proc.stdout}"[-2000:]
        raise SpreadsheetJudgeError(
            f"{log_prefix} failed with code {proc.returncode}: {tail}"
        )
    return load_json(report_path)


def run_source_inspect(
    source_path: Path, relative: str, evidence_dir: Path
) -> dict[str, Any]:
    report_path = evidence_dir / "source-inspect.json"
    report = run_report_tool(
        [
            sys.executable,
            str(TABLE_TOOL),
            "inspect",
            str(source_path),
            "--out",
            str(report_path),
        ],
        report_path=report_path,
        evidence_dir=evidence_dir,
        log_prefix="source-inspect",
        timeout=30,
    )
    report["file"] = f"source/{relative}"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if not report.get("ok"):
        raise SpreadsheetJudgeError("source CSV inspection failed")
    return report


def run_workbook_inspect(
    workbook_path: Path, relative: str, evidence_dir: Path
) -> dict[str, Any]:
    report_path = evidence_dir / "workbook-inspect.json"
    report = run_report_tool(
        [
            sys.executable,
            str(WORKBOOK_TOOL),
            "inspect",
            str(workbook_path),
            "--out",
            str(report_path),
        ],
        report_path=report_path,
        evidence_dir=evidence_dir,
        log_prefix="workbook-inspect",
    )
    report["file"] = f"artifacts/{Path(relative).name}"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def run_recalculation(
    workbook_path: Path, relative: str, evidence_dir: Path
) -> dict[str, Any]:
    report_path = evidence_dir / "recalc-report.json"
    office = shutil.which("soffice") or shutil.which("libreoffice")
    if not office:
        report = {
            "ran": False,
            "ok": None,
            "engine": None,
            "file": f"artifacts/{Path(relative).name}",
            "output": None,
            "errors": [],
            "limitations": ["real_spreadsheet_engine_unavailable"],
            "inspect": None,
        }
        report_path.write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        return report

    recalculated = evidence_dir / f"{Path(relative).stem}.recalculated.xlsx"
    recalculated.unlink(missing_ok=True)
    report = run_report_tool(
        [
            sys.executable,
            str(WORKBOOK_TOOL),
            "recalc",
            str(workbook_path),
            "--output",
            str(recalculated),
            "--out",
            str(report_path),
        ],
        report_path=report_path,
        evidence_dir=evidence_dir,
        log_prefix="workbook-recalc",
        timeout=120,
    )
    recalculation_ran = recalculated.is_file() and isinstance(
        report.get("inspect"), dict
    )
    report["ran"] = recalculation_ran
    report["file"] = f"artifacts/{Path(relative).name}"
    report["output"] = (
        f"judge-evidence/{recalculated.name}"
        if recalculated.is_file()
        else None
    )
    if isinstance(report.get("inspect"), dict):
        report["inspect"]["file"] = report["output"]
    limitations = report.setdefault("limitations", [])
    if not isinstance(limitations, list):
        raise SpreadsheetJudgeError("recalculation limitations must be a list")
    if not recalculation_ran:
        for error in report.get("errors", []):
            limitation = f"recalculation_not_completed:{error}"
            if limitation not in limitations:
                limitations.append(limitation)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def read_xml(zf: zipfile.ZipFile, name: str) -> ET.Element | None:
    try:
        return ET.fromstring(zf.read(name))
    except (KeyError, ET.ParseError):
        return None


def relationships(zf: zipfile.ZipFile, name: str) -> dict[str, str]:
    root = read_xml(zf, name)
    if root is None:
        return {}
    return {
        rel.attrib["Id"]: rel.attrib.get("Target", "")
        for rel in root.findall(f"{REL_NS}Relationship")
        if rel.attrib.get("Id")
    }


def normalized_relationship_target(source_part: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join(posixpath.dirname(source_part), target))


def column_number(letters: str) -> int:
    number = 0
    for character in letters:
        number = number * 26 + ord(character) - ord("A") + 1
    return number


def cell_coordinate(reference: str) -> tuple[int, int] | None:
    match = CELL_REF_RE.fullmatch(reference.upper())
    if not match:
        return None
    return int(match.group(2)), column_number(match.group(1))


def range_coordinates(reference: str) -> tuple[int, int, int, int] | None:
    match = CELL_RANGE_RE.fullmatch(reference.upper())
    if not match:
        return None
    first_column = column_number(match.group(1))
    first_row = int(match.group(2))
    last_column = column_number(match.group(3))
    last_row = int(match.group(4))
    return (
        min(first_row, last_row),
        min(first_column, last_column),
        max(first_row, last_row),
        max(first_column, last_column),
    )


def range_contains(reference: str, coordinate: tuple[int, int]) -> bool:
    bounds = range_coordinates(reference)
    if bounds is None:
        return False
    row, column = coordinate
    return bounds[0] <= row <= bounds[2] and bounds[1] <= column <= bounds[3]


def xml_text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return "".join(child.text or "" for child in node.iter(f"{MAIN_NS}t"))


def shared_strings(zf: zipfile.ZipFile) -> list[str]:
    root = read_xml(zf, "xl/sharedStrings.xml")
    if root is None:
        return []
    return [xml_text(item) for item in root.findall(f"{MAIN_NS}si")]


def extract_workbook_facts(path: Path) -> dict[str, Any]:
    facts: dict[str, Any] = {"ok": False, "errors": [], "defined_names": [], "sheets": []}
    try:
        with zipfile.ZipFile(path) as zf:
            workbook = read_xml(zf, "xl/workbook.xml")
            if workbook is None:
                facts["errors"].append("missing_or_invalid_workbook_xml")
                return facts
            rels = relationships(zf, "xl/_rels/workbook.xml.rels")
            strings = shared_strings(zf)
            defined_names = workbook.find(f"{MAIN_NS}definedNames")
            if defined_names is not None:
                facts["defined_names"] = [
                    {
                        "name": item.attrib.get("name", ""),
                        "scope": item.attrib.get("localSheetId", "workbook"),
                        "refers_to": item.text or "",
                    }
                    for item in defined_names.findall(f"{MAIN_NS}definedName")
                ]
            sheets = workbook.find(f"{MAIN_NS}sheets")
            for sheet in sheets.findall(f"{MAIN_NS}sheet") if sheets is not None else []:
                sheet_name = sheet.attrib.get("name", "")
                rid = sheet.attrib.get(f"{REL_DOC_NS}id", "")
                target = rels.get(rid, "")
                part = (
                    normalized_relationship_target("xl/workbook.xml", target)
                    if target
                    else ""
                )
                root = read_xml(zf, part) if part else None
                if root is None:
                    facts["errors"].append(
                        f"missing_or_invalid_sheet_xml:{sheet_name or rid or 'unknown'}"
                    )
                cells: list[dict[str, Any]] = []
                if root is not None:
                    shared_formulas: dict[str, dict[str, str]] = {}
                    array_formulas: list[dict[str, str]] = []
                    for formula_cell in root.iter(f"{MAIN_NS}c"):
                        formula_node = formula_cell.find(f"{MAIN_NS}f")
                        if formula_node is None or not (formula_node.text or "").strip():
                            continue
                        formula_type = formula_node.attrib.get("t", "normal")
                        if formula_type == "shared" and formula_node.attrib.get("si"):
                            shared_formulas[formula_node.attrib["si"]] = {
                                "formula": formula_node.text or "",
                                "range": formula_node.attrib.get("ref", ""),
                                "master_cell": formula_cell.attrib.get("r", ""),
                            }
                        elif formula_type == "array" and formula_node.attrib.get("ref"):
                            array_formulas.append(
                                {
                                    "formula": formula_node.text or "",
                                    "range": formula_node.attrib["ref"],
                                    "master_cell": formula_cell.attrib.get("r", ""),
                                }
                            )
                    for cell in root.iter(f"{MAIN_NS}c"):
                        reference = cell.attrib.get("r", "")
                        coordinate = cell_coordinate(reference)
                        if coordinate is None:
                            continue
                        cell_type = cell.attrib.get("t", "")
                        value_node = cell.find(f"{MAIN_NS}v")
                        raw_value = value_node.text if value_node is not None else ""
                        if cell_type == "inlineStr":
                            value = xml_text(cell.find(f"{MAIN_NS}is"))
                        elif cell_type == "s":
                            try:
                                value = strings[int(raw_value)]
                            except (ValueError, IndexError):
                                value = raw_value
                        else:
                            value = raw_value
                        formula_node = cell.find(f"{MAIN_NS}f")
                        formula = None
                        formula_type = None
                        formula_origin = None
                        formula_range = None
                        formula_master_cell = None
                        shared_index = None
                        if formula_node is not None:
                            formula_type = formula_node.attrib.get("t", "normal")
                            formula = formula_node.text or ""
                            formula_origin = "cell"
                            formula_range = formula_node.attrib.get("ref")
                            if formula_type == "shared":
                                shared_index = formula_node.attrib.get("si")
                                shared = shared_formulas.get(shared_index or "")
                                if shared is not None:
                                    formula_master_cell = shared["master_cell"]
                                    formula_range = formula_range or shared["range"]
                                    if not formula.strip():
                                        formula = shared["formula"]
                                        formula_origin = "shared-master"
                            elif formula_type == "array":
                                array_match = next(
                                    (
                                        item
                                        for item in array_formulas
                                        if range_contains(item["range"], coordinate)
                                    ),
                                    None,
                                )
                                if array_match is not None:
                                    formula_master_cell = array_match["master_cell"]
                                    formula_range = formula_range or array_match["range"]
                                    if not formula.strip():
                                        formula = array_match["formula"]
                                        formula_origin = "array-master"
                                else:
                                    formula_master_cell = reference
                        else:
                            array_match = next(
                                (
                                    item
                                    for item in array_formulas
                                    if range_contains(item["range"], coordinate)
                                ),
                                None,
                            )
                            if array_match is not None:
                                formula = array_match["formula"]
                                formula_type = "array"
                                formula_origin = "array-master"
                                formula_range = array_match["range"]
                                formula_master_cell = array_match["master_cell"]
                        cells.append(
                            {
                                "ref": reference,
                                "row": coordinate[0],
                                "column": coordinate[1],
                                "type": cell_type,
                                "value": value,
                                "formula": formula,
                                "formula_type": formula_type,
                                "formula_origin": formula_origin,
                                "formula_range": formula_range,
                                "formula_master_cell": formula_master_cell,
                                "shared_index": shared_index,
                            }
                        )
                facts["sheets"].append(
                    {
                        "name": sheet_name,
                        "state": sheet.attrib.get("state", "visible"),
                        "part": part,
                        "cells": cells,
                    }
                )
            facts["ok"] = not facts["errors"]
            return facts
    except zipfile.BadZipFile:
        facts["errors"].append("bad_zip")
        return facts


def normalize_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def sheet_named(facts: dict[str, Any], name: str) -> dict[str, Any] | None:
    return next(
        (
            sheet
            for sheet in facts.get("sheets", [])
            if sheet.get("name", "").casefold() == name.casefold()
        ),
        None,
    )


def cells_by_row(sheet: dict[str, Any]) -> dict[int, dict[int, dict[str, Any]]]:
    rows: dict[int, dict[int, dict[str, Any]]] = {}
    for cell in sheet.get("cells", []):
        rows.setdefault(cell["row"], {})[cell["column"]] = cell
    return rows


def find_table_header(
    sheet: dict[str, Any], specs: list[tuple[str, list[str]]]
) -> tuple[int | None, dict[str, int]]:
    aliases = {
        identifier: {normalize_label(value) for value in values}
        for identifier, values in specs
    }
    for row_number, cells in sorted(cells_by_row(sheet).items()):
        found: dict[str, int] = {}
        for column_number_value, cell in cells.items():
            normalized = normalize_label(str(cell.get("value", "")))
            for identifier, accepted in aliases.items():
                if identifier not in found and normalized in accepted:
                    found[identifier] = column_number_value
        if set(found) == set(aliases):
            return row_number, found
    return None, {}


def comparable_decimal(value: str) -> Decimal | None:
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def audit_source_table(
    config: dict[str, Any], source_truth: dict[str, Any], facts: dict[str, Any]
) -> dict[str, Any]:
    source_config = config["source"]
    sheet = sheet_named(facts, source_config["sheet"])
    if sheet is None:
        return {
            "sheet": source_config["sheet"],
            "sheet_found": False,
            "header_row": None,
            "headers": {},
            "rows": [],
            "passed": False,
        }
    specs = [(item["id"], item["headers"]) for item in source_config["columns"]]
    header_row, headers = find_table_header(sheet, specs)
    if header_row is None:
        return {
            "sheet": sheet["name"],
            "sheet_found": True,
            "header_row": None,
            "headers": {},
            "rows": [],
            "passed": False,
        }
    rows = cells_by_row(sheet)
    key_column = source_config["key_column"]
    audited_rows: list[dict[str, Any]] = []
    column_config = {item["id"]: item for item in source_config["columns"]}
    for expected in source_truth["rows"]:
        expected_key = expected[key_column]
        matched_row = next(
            (
                (row_number, cells)
                for row_number, cells in sorted(rows.items())
                if row_number > header_row
                and str(cells.get(headers[key_column], {}).get("value", "")).casefold()
                == expected_key.casefold()
            ),
            None,
        )
        comparisons: dict[str, Any] = {}
        if matched_row is not None:
            row_number, row_cells = matched_row
            for column_id, column_number_value in headers.items():
                cell = row_cells.get(column_number_value, {})
                actual = str(cell.get("value", ""))
                expected_value = expected[column_id]
                if column_config[column_id]["type"] == "decimal":
                    parsed = comparable_decimal(actual)
                    passed = parsed is not None and parsed == Decimal(expected_value)
                else:
                    passed = actual == expected_value
                comparisons[column_id] = {
                    "cell": cell.get("ref"),
                    "expected": expected_value,
                    "actual": actual,
                    "passed": passed,
                }
        else:
            row_number = None
        audited_rows.append(
            {
                "key": expected_key,
                "row": row_number,
                "comparisons": comparisons,
                "passed": bool(comparisons)
                and all(item["passed"] for item in comparisons.values()),
            }
        )
    return {
        "sheet": sheet["name"],
        "sheet_found": True,
        "header_row": header_row,
        "headers": headers,
        "rows": audited_rows,
        "passed": bool(audited_rows) and all(row["passed"] for row in audited_rows),
    }


def audit_calculation_table(
    config: dict[str, Any], source_truth: dict[str, Any], facts: dict[str, Any]
) -> dict[str, Any]:
    calculations = config["calculations"]
    source_config = config["source"]
    sheet = sheet_named(facts, calculations["sheet"])
    if sheet is None:
        return {
            "sheet": calculations["sheet"],
            "sheet_found": False,
            "header_row": None,
            "headers": {},
            "rows": [],
            "passed": False,
        }
    key_column = source_config["key_column"]
    key_headers = next(
        item["headers"] for item in source_config["columns"] if item["id"] == key_column
    )
    specs = [(key_column, key_headers)] + [
        (item["id"], item["headers"]) for item in calculations["outputs"]
    ]
    header_row, headers = find_table_header(sheet, specs)
    if header_row is None:
        return {
            "sheet": sheet["name"],
            "sheet_found": True,
            "header_row": None,
            "headers": {},
            "rows": [],
            "passed": False,
        }
    rows = cells_by_row(sheet)
    audited_rows: list[dict[str, Any]] = []
    for expected in source_truth["rows"]:
        expected_key = expected[key_column]
        matched_row = next(
            (
                (row_number, cells)
                for row_number, cells in sorted(rows.items())
                if row_number > header_row
                and str(cells.get(headers[key_column], {}).get("value", "")).casefold()
                == expected_key.casefold()
            ),
            None,
        )
        outputs: dict[str, Any] = {}
        if matched_row is not None:
            row_number, row_cells = matched_row
            for output in calculations["outputs"]:
                cell = row_cells.get(headers[output["id"]], {})
                formula = cell.get("formula")
                live_formula = (
                    isinstance(formula, str)
                    and bool(formula.strip())
                    and LITERAL_FORMULA_RE.fullmatch(formula) is None
                )
                outputs[output["id"]] = {
                    "cell": cell.get("ref"),
                    "formula": formula,
                    "formula_type": cell.get("formula_type"),
                    "formula_origin": cell.get("formula_origin"),
                    "formula_range": cell.get("formula_range"),
                    "formula_master_cell": cell.get("formula_master_cell"),
                    "shared_index": cell.get("shared_index"),
                    "cached_value": cell.get("value"),
                    "expected_value": expected["expected_outputs"][output["id"]],
                    "expression": output["expression"],
                    "live_formula": live_formula,
                }
        else:
            row_number = None
        audited_rows.append(
            {
                "key": expected_key,
                "row": row_number,
                "outputs": outputs,
                "passed": bool(outputs)
                and all(item["live_formula"] for item in outputs.values()),
            }
        )
    return {
        "sheet": sheet["name"],
        "sheet_found": True,
        "header_row": header_row,
        "headers": headers,
        "rows": audited_rows,
        "passed": bool(audited_rows) and all(row["passed"] for row in audited_rows),
    }


def resolve_defined_name_value(
    defined_name: dict[str, Any], facts: dict[str, Any]
) -> str | None:
    target = str(defined_name.get("refers_to", "")).removeprefix("=")
    direct = comparable_decimal(target)
    if direct is not None:
        return decimal_text(direct)
    match = DEFINED_CELL_RE.fullmatch(target)
    if not match:
        return None
    sheet_name = match.group(1).replace("''", "'")
    reference = f"{match.group(2)}{match.group(3)}"
    sheet = sheet_named(facts, sheet_name)
    if sheet is None:
        return None
    cell = next(
        (cell for cell in sheet.get("cells", []) if cell.get("ref") == reference),
        None,
    )
    if cell is None or cell.get("formula"):
        return None
    parsed = comparable_decimal(str(cell.get("value", "")))
    return decimal_text(parsed) if parsed is not None else None


def build_workbook_audit(
    config: dict[str, Any],
    result: dict[str, Any],
    workbook_path: Path,
    inspect_report: dict[str, Any],
    recalc_report: dict[str, Any],
    facts: dict[str, Any],
    source_truth: dict[str, Any],
) -> dict[str, Any]:
    relative = config["artifact"]["path"]
    declared = {
        item.get("path")
        for item in result.get("artifacts", [])
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    workbook_config = config["workbook"]
    sheet_reports = {
        str(item.get("name", "")).casefold(): item
        for item in inspect_report.get("sheets", [])
        if isinstance(item, dict)
    }
    required_sheets = []
    for name in workbook_config["required_sheets"]:
        report = sheet_reports.get(name.casefold())
        required_sheets.append(
            {
                "expected": name,
                "actual": report.get("name") if report else None,
                "exists": report is not None,
                "visible": bool(report and report.get("state") == "visible"),
            }
        )
    defined_names = []
    for requirement in workbook_config["required_defined_names"]:
        candidates = [
            item
            for item in facts.get("defined_names", [])
            if isinstance(item, dict)
            and str(item.get("name", "")).casefold()
            == requirement["name"].casefold()
        ]
        found = next(
            (item for item in candidates if item.get("scope") == "workbook"), None
        )
        actual_value = (
            resolve_defined_name_value(found, facts) if found is not None else None
        )
        defined_names.append(
            {
                "expected_name": requirement["name"],
                "expected_value": requirement["value"],
                "found": bool(candidates),
                "workbook_scope_found": found is not None,
                "scope": found.get("scope") if found else None,
                "refers_to": found.get("refers_to") if found else None,
                "actual_value": actual_value,
                "passed": bool(
                    found
                    and found.get("scope") == "workbook"
                    and comparable_decimal(actual_value or "")
                    == Decimal(requirement["value"])
                ),
            }
        )
    checks_report = sheet_reports.get(workbook_config["checks_sheet"].casefold())
    package_integrity = {
        "inspect_ok": bool(inspect_report.get("ok")),
        "facts_ok": bool(facts.get("ok")),
        "formula_error_count": inspect_report.get("formula_error_count", 0),
        "external_formula_reference_count": inspect_report.get(
            "external_formula_reference_count", 0
        ),
        "external_relationship_count": len(
            inspect_report.get("external_relationships", [])
        ),
        "missing_relationship_target_count": len(
            inspect_report.get("missing_relationship_targets", [])
        ),
    }
    package_integrity["structure_passed"] = bool(
        package_integrity["inspect_ok"]
        and package_integrity["facts_ok"]
        and package_integrity["missing_relationship_target_count"] == 0
    )
    package_integrity["formula_safety_passed"] = bool(
        package_integrity["formula_error_count"] == 0
        and package_integrity["external_formula_reference_count"] == 0
        and package_integrity["external_relationship_count"] == 0
    )
    package_integrity["passed"] = bool(
        package_integrity["structure_passed"]
        and package_integrity["formula_safety_passed"]
    )
    return {
        "artifact": {
            "path": relative,
            "exists": True,
            "declared": relative in declared,
            "bytes": workbook_path.stat().st_size,
            "sha256": hashlib.sha256(workbook_path.read_bytes()).hexdigest(),
        },
        "package_integrity": package_integrity,
        "architecture": {
            "required_sheets": required_sheets,
            "passed": all(
                item["exists"] and item["visible"] for item in required_sheets
            ),
        },
        "source_table": audit_source_table(config, source_truth, facts),
        "calculation_table": audit_calculation_table(config, source_truth, facts),
        "defined_names": {
            "requirements": defined_names,
            "passed": all(item["passed"] for item in defined_names),
        },
        "checks": {
            "sheet": workbook_config["checks_sheet"],
            "sheet_found": checks_report is not None,
            "formula_count": checks_report.get("formula_count", 0)
            if checks_report
            else 0,
            "minimum_formula_count": workbook_config[
                "minimum_check_formula_count"
            ],
            "passed": bool(
                checks_report
                and checks_report.get("formula_count", 0)
                >= workbook_config["minimum_check_formula_count"]
            ),
        },
        "recalculation": recalc_report,
    }


def missing_workbook_audit(
    config: dict[str, Any], result: dict[str, Any]
) -> dict[str, Any]:
    relative = config["artifact"]["path"]
    declared = {
        item.get("path")
        for item in result.get("artifacts", [])
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    return {
        "artifact": {
            "path": relative,
            "exists": False,
            "declared": relative in declared,
            "bytes": 0,
            "sha256": None,
        },
        "package_integrity": {"passed": False},
        "architecture": {"required_sheets": [], "passed": False},
        "source_table": {"rows": [], "passed": False},
        "calculation_table": {"rows": [], "passed": False},
        "defined_names": {"requirements": [], "passed": False},
        "checks": {"passed": False},
        "recalculation": {
            "ran": False,
            "ok": None,
            "errors": [],
            "limitations": ["artifact_missing"],
        },
    }


def persist_evidence(
    evidence_dir: Path,
    source_truth: dict[str, Any],
    workbook_audit: dict[str, Any],
    trace: dict[str, Any],
) -> None:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for name, value in (
        ("source-truth.json", source_truth),
        ("workbook-audit.json", workbook_audit),
        ("agent-trace-summary.json", trace),
    ):
        (evidence_dir / name).write_text(
            json.dumps(value, indent=2) + "\n", encoding="utf-8"
        )


def judge_prompt(oracle: dict[str, Any]) -> str:
    rubric = "\n".join(
        f"- {item['id']} ({item['weight']:.2f}, critical={str(item['critical']).lower()}): "
        f"{item['description']}"
        for item in oracle["expected"]["outcomes"]
    )
    criterion_ids = [item["id"] for item in oracle["expected"]["outcomes"]]
    failure_tags = oracle.get("failure_taxonomy", [])
    return f"""Act as a blind spreadsheet evaluator. You do not know which
experimental condition produced the work. Review source/prompt.md,
source/input/, agent-result.json, agent-response.md,
agent-trace-summary.json, source-inspect.json, source-truth.json,
workbook-inspect.json, workbook-audit.json, and recalc-report.json.

Treat source-truth.json as evaluator-computed arithmetic ground truth and
workbook-audit.json as the extracted cell/formula map. Check whether formulas
implement the requested equations rather than merely existing. Cached formula
values do not prove recalculation. If recalc-report.json says ran=false, judge
whether the delivery response states that limitation honestly; do not infer an
artifact defect from a Judge-side recalculation limit unless deterministic
package evidence supports it. Shared or array formula followers may show their
master formula template together with the master cell and covered range;
interpret relative references at the follower cell rather than treating the
repeated template as a copied-value defect.
Use workbook-inspect.json for package facts such as names, links, formula errors,
sheet state, and calculation settings. Judge maintainability and usability from
the evidence rather than rewarding sheet names alone.

Score every criterion from 0.0 to 1.0. Set passed=true only at 0.75 or higher
with no blocking failure. Ground every score in concrete source rows, cells,
formula strings, defined names, check formulas, delivery statements, or
deterministic report fields.

Rubric:
{rubric}

Return exactly one score for every criterion id and only a JSON object shaped as:
{{"scores":[{{"criterion_id":"...","value":0.0,"passed":false,
"rationale":"...","evidence":["..."]}}],"failure_tags":[],"summary":"..."}}
Allowed criterion ids: {json.dumps(criterion_ids)}
Allowed failure tags: {json.dumps(failure_tags)}
"""


def path_spellings(path: Path) -> set[str]:
    spellings = {str(path), str(path.resolve())}
    for value in list(spellings):
        if value.startswith("/private/tmp/"):
            spellings.add(value.removeprefix("/private"))
        elif value.startswith("/tmp/"):
            spellings.add(f"/private{value}")
    return {value for value in spellings if value}


def blind_redactions(
    *, env: dict[str, Path], result: dict[str, Any], evidence_dir: Path
) -> dict[str, str]:
    result_file = env["EVAL_RESULT_FILE"]
    run_dir = result_file.parent
    run_root = result_file.parents[3] if len(result_file.parents) > 3 else run_dir
    path_replacements = (
        (env["EVAL_PAYLOAD_DIR"], "source"),
        (env["EVAL_OUTPUT_DIR"], "agent-output"),
        (evidence_dir, "judge-evidence"),
        (run_dir, "run"),
        (run_root, "run-root"),
        (ROOT, "repository"),
    )
    redactions: dict[str, str] = {}
    for path, replacement in path_replacements:
        for spelling in path_spellings(path):
            redactions[spelling] = replacement
    condition_id = (result.get("condition") or {}).get("id")
    if isinstance(condition_id, str) and condition_id and condition_id != "baseline":
        redactions[condition_id] = "condition"
    return redactions


def sanitize_blind_value(value: Any, redactions: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {
            key: sanitize_blind_value(item, redactions)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize_blind_value(item, redactions) for item in value]
    if not isinstance(value, str):
        return value
    sanitized = value
    for sensitive, replacement in sorted(
        redactions.items(), key=lambda item: len(item[0]), reverse=True
    ):
        sanitized = sanitized.replace(sensitive, replacement)
    return sanitized


def assert_blind_workspace_clean(
    workspace: Path, *, forbidden_markers: set[str]
) -> None:
    encoded_markers = {
        marker: marker.encode("utf-8") for marker in sorted(forbidden_markers)
    }
    for path in sorted(workspace.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        content = path.read_bytes()
        for marker, encoded in encoded_markers.items():
            if encoded in content:
                relative = path.relative_to(workspace).as_posix()
                raise SpreadsheetJudgeError(
                    f"blind-review input leaked experimental provenance in {relative}: "
                    f"{marker}"
                )


def prepare_model_workspace(
    *,
    workspace: Path,
    env: dict[str, Path],
    result: dict[str, Any],
    source_truth: dict[str, Any],
    source_inspect: dict[str, Any],
    workbook_inspect: dict[str, Any],
    workbook_audit: dict[str, Any],
    recalc_report: dict[str, Any],
    trace: dict[str, Any],
    evidence_dir: Path,
) -> None:
    redactions = blind_redactions(env=env, result=result, evidence_dir=evidence_dir)
    source_dir = workspace / "source"
    source_dir.mkdir()
    payload = env["EVAL_PAYLOAD_DIR"]
    shutil.copy2(payload / "prompt.md", source_dir / "prompt.md")
    shutil.copytree(payload / "input", source_dir / "input")
    (workspace / "agent-result.json").write_text(
        json.dumps(
            sanitize_blind_value(anonymized_result(result), redactions), indent=2
        )
        + "\n",
        encoding="utf-8",
    )
    response = env["EVAL_OUTPUT_DIR"] / "response.md"
    (workspace / "agent-response.md").write_text(
        sanitize_blind_value(
            response.read_text(encoding="utf-8", errors="replace")
            if response.is_file()
            else "",
            redactions,
        ),
        encoding="utf-8",
    )
    for name, value in (
        ("agent-trace-summary.json", trace),
        ("source-truth.json", source_truth),
        ("source-inspect.json", source_inspect),
        ("workbook-inspect.json", workbook_inspect),
        ("workbook-audit.json", workbook_audit),
        ("recalc-report.json", recalc_report),
    ):
        (workspace / name).write_text(
            json.dumps(sanitize_blind_value(value, redactions), indent=2) + "\n",
            encoding="utf-8",
        )
    assert_blind_workspace_clean(workspace, forbidden_markers=set(redactions))


def score_index(judgment: dict[str, Any]) -> dict[str, dict[str, Any]]:
    scores = judgment.get("scores")
    if not isinstance(scores, list):
        raise SpreadsheetJudgeError("model judgment has no scores list")
    indexed: dict[str, dict[str, Any]] = {}
    for score in scores:
        if not isinstance(score, dict) or not isinstance(
            score.get("criterion_id"), str
        ):
            raise SpreadsheetJudgeError("model judgment contains an invalid score")
        indexed[score["criterion_id"]] = score
    return indexed


def cap_score(score: dict[str, Any], cap: float, rationale: str, evidence: str) -> None:
    value = score.get("value")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise SpreadsheetJudgeError("model score value must be numeric")
    if float(value) > cap:
        score["value"] = cap
    score["passed"] = float(score["value"]) >= 0.75
    score["rationale"] = (
        f"{score.get('rationale', '')} Deterministic check: {rationale}".strip()
    )
    evidence_items = score.setdefault("evidence", [])
    if not isinstance(evidence_items, list):
        raise SpreadsheetJudgeError("model score evidence must be a list")
    if evidence not in evidence_items:
        evidence_items.append(evidence)


def apply_deterministic_overrides(
    judgment: dict[str, Any],
    *,
    oracle: dict[str, Any],
    config: dict[str, Any],
    result: dict[str, Any],
    workbook_audit: dict[str, Any],
) -> dict[str, Any]:
    scores = score_index(judgment)
    expected_ids = [item["id"] for item in oracle["expected"]["outcomes"]]
    if set(scores) != set(expected_ids):
        raise SpreadsheetJudgeError(
            f"model judgment criterion mismatch: expected {sorted(expected_ids)}, "
            f"got {sorted(scores)}"
        )
    failure_tags = set(judgment.get("failure_tags", []))
    tag_map = config["criterion_failure_tags"]

    acceptable = oracle["expected"]["route"]["acceptable_primary_skills"]
    route_ok = (result.get("route") or {}).get("primary_skill") in acceptable
    scores["correct-route"].update(
        {
            "value": 1.0 if route_ok else 0.0,
            "passed": route_ok,
            "rationale": (
                "Recorded primary Skill matches the expected spreadsheet route."
                if route_ok
                else "Recorded primary Skill does not match the expected spreadsheet route."
            ),
            "evidence": ["agent-result.json route"],
        }
    )
    if not route_ok:
        failure_tags.add("route-error")

    artifact = workbook_audit["artifact"]
    artifact_criterion = config["artifact"]["criterion"]
    if not artifact["declared"]:
        cap_score(
            scores[artifact_criterion],
            0.0,
            f"the required {artifact['path']} was not declared as an Agent artifact",
            "workbook-audit.json artifact.declared",
        )
        failure_tags.add("missing-artifact")

    architecture_criterion = config["workbook"]["architecture_criterion"]
    if not workbook_audit["architecture"]["passed"]:
        cap_score(
            scores[architecture_criterion],
            0.5,
            "one or more required workbook sheets are missing or hidden",
            "workbook-audit.json architecture.required_sheets",
        )
        failure_tags.add(tag_map[architecture_criterion])

    package_integrity = workbook_audit["package_integrity"]
    if not package_integrity.get("structure_passed", False):
        cap_score(
            scores[architecture_criterion],
            0.0,
            "the XLSX package or one of its required worksheet parts is invalid",
            "workbook-audit.json package_integrity.structure_passed",
        )
        failure_tags.add(tag_map[architecture_criterion])

    source_criterion = config["source"]["criterion"]
    if not workbook_audit["source_table"]["passed"]:
        cap_score(
            scores[source_criterion],
            0.25,
            "the Inputs table does not preserve every source row and value",
            "workbook-audit.json source_table",
        )
        failure_tags.add(tag_map[source_criterion])

    formula_criterion = config["calculations"]["criterion"]
    if not workbook_audit["calculation_table"]["passed"]:
        cap_score(
            scores[formula_criterion],
            0.25,
            "one or more required plan outputs are missing live formulas",
            "workbook-audit.json calculation_table",
        )
        failure_tags.add(tag_map[formula_criterion])
    if not package_integrity.get("formula_safety_passed", False):
        cap_score(
            scores[formula_criterion],
            0.0,
            "the workbook has formula-error or external-link failures",
            "workbook-audit.json package_integrity.formula_safety_passed",
        )
        failure_tags.add(tag_map[formula_criterion])

    input_criterion = config["workbook"]["input_criterion"]
    if not workbook_audit["defined_names"]["passed"]:
        cap_score(
            scores[input_criterion],
            0.5,
            "required workbook-level named inputs are missing or have wrong values",
            "workbook-audit.json defined_names",
        )
        failure_tags.add(tag_map[input_criterion])

    verification_criterion = config["workbook"]["verification_criterion"]
    if not workbook_audit["checks"]["passed"]:
        cap_score(
            scores[verification_criterion],
            0.5,
            "the Checks sheet lacks the required formula-based verification",
            "workbook-audit.json checks",
        )
        failure_tags.add(tag_map[verification_criterion])
    recalc = workbook_audit["recalculation"]
    if recalc.get("ran") and "formula_errors_after_recalc" in recalc.get("errors", []):
        cap_score(
            scores[verification_criterion],
            0.0,
            "a real spreadsheet-engine recalculation found formula errors",
            "recalc-report.json errors",
        )
        failure_tags.add(tag_map[verification_criterion])

    judgment["scores"] = [scores[criterion] for criterion in expected_ids]
    judgment["failure_tags"] = sorted(failure_tags)
    return judgment


def missing_artifact_result(
    oracle: dict[str, Any], result: dict[str, Any]
) -> dict[str, Any]:
    acceptable = oracle["expected"]["route"]["acceptable_primary_skills"]
    route_ok = (result.get("route") or {}).get("primary_skill") in acceptable
    scores: list[dict[str, Any]] = []
    for outcome in oracle["expected"]["outcomes"]:
        is_route = outcome["id"] == "correct-route"
        value = 1.0 if is_route and route_ok else 0.0
        scores.append(
            {
                "criterion_id": outcome["id"],
                "value": value,
                "passed": value >= 0.75,
                "rationale": (
                    "The recorded primary Skill matches the expected route."
                    if value == 1.0
                    else "The required workbook artifact was not available."
                ),
                "evidence": [
                    "agent-result.json route"
                    if is_route
                    else "agent-result.json artifacts"
                ],
            }
        )
    tags = ["missing-artifact"]
    if not route_ok:
        tags.append("route-error")
    return {
        "scores": scores,
        "failure_tags": tags,
        "summary": "The required workbook artifact was missing.",
    }


def run_judge(args: argparse.Namespace) -> dict[str, Any]:
    env = environment()
    oracle = load_json(env["EVAL_ORACLE_FILE"])
    config = judge_config()
    validate_config(config, oracle)
    result = load_json(env["EVAL_RESULT_FILE"])
    evidence_dir = Path(
        os.environ.get(
            "EVAL_JUDGE_EVIDENCE_DIR",
            str(env["EVAL_JUDGE_RESULT_FILE"].parent / "judge-evidence"),
        )
    ).resolve()
    trace_dir = Path(
        os.environ.get(
            "EVAL_JUDGE_TRACE_DIR",
            str(env["EVAL_JUDGE_RESULT_FILE"].parent / "judge-trace"),
        )
    ).resolve()
    source_truth = build_source_truth(config, env["EVAL_PAYLOAD_DIR"])
    source_path = safe_child(env["EVAL_PAYLOAD_DIR"], config["source"]["path"])
    source_inspect = run_source_inspect(
        source_path, config["source"]["path"], evidence_dir
    )
    trace = trace_summary(env["EVAL_OUTPUT_DIR"])
    relative = config["artifact"]["path"]
    workbook_path = artifact_path(env["EVAL_OUTPUT_DIR"], relative)

    if not workbook_path.is_file():
        workbook_inspect = {
            "file": f"artifacts/{Path(relative).name}",
            "ok": False,
            "errors": ["artifact_missing"],
            "warnings": [],
            "sheets": [],
        }
        recalc_report = {
            "ran": False,
            "ok": None,
            "errors": [],
            "limitations": ["artifact_missing"],
        }
        (evidence_dir / "workbook-inspect.json").write_text(
            json.dumps(workbook_inspect, indent=2) + "\n", encoding="utf-8"
        )
        (evidence_dir / "recalc-report.json").write_text(
            json.dumps(recalc_report, indent=2) + "\n", encoding="utf-8"
        )
        workbook_audit = missing_workbook_audit(config, result)
        persist_evidence(evidence_dir, source_truth, workbook_audit, trace)
        judgment = missing_artifact_result(oracle, result)
    else:
        workbook_inspect = run_workbook_inspect(
            workbook_path, relative, evidence_dir
        )
        recalc_report = run_recalculation(workbook_path, relative, evidence_dir)
        facts = extract_workbook_facts(workbook_path)
        workbook_audit = build_workbook_audit(
            config,
            result,
            workbook_path,
            workbook_inspect,
            recalc_report,
            facts,
            source_truth,
        )
        persist_evidence(evidence_dir, source_truth, workbook_audit, trace)
        with tempfile.TemporaryDirectory(prefix="linlab-spreadsheet-judge-") as temp:
            workspace = Path(temp) / "blind-review"
            workspace.mkdir()
            prepare_model_workspace(
                workspace=workspace,
                env=env,
                result=result,
                source_truth=source_truth,
                source_inspect=source_inspect,
                workbook_inspect=workbook_inspect,
                workbook_audit=workbook_audit,
                recalc_report=recalc_report,
                trace=trace,
                evidence_dir=evidence_dir,
            )
            options = ModelJudgeOptions(
                codex_bin=args.codex_bin,
                model=args.model,
                reasoning_effort=args.reasoning_effort,
                timeout_seconds=args.timeout_seconds,
                max_attempts=args.max_attempts,
                retry_delay_seconds=args.retry_delay_seconds,
                structured_output=args.structured_output,
            )
            judgment = run_blind_model_judge(
                options=options,
                prompt=judge_prompt(oracle),
                workspace=workspace,
                trace_root=trace_dir,
                criterion_ids=[
                    item["id"] for item in oracle["expected"]["outcomes"]
                ],
                failure_tags=oracle.get("failure_taxonomy", []),
            )
        judgment = apply_deterministic_overrides(
            judgment,
            oracle=oracle,
            config=config,
            result=result,
            workbook_audit=workbook_audit,
        )
    env["EVAL_JUDGE_RESULT_FILE"].write_text(
        json.dumps(judgment, indent=2) + "\n", encoding="utf-8"
    )
    return judgment


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--model", default="gpt-5.6-sol")
    parser.add_argument("--reasoning-effort", default="medium")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--retry-delay-seconds", type=float, default=2.0)
    parser.add_argument(
        "--structured-output",
        choices=("auto", "schema", "prompt"),
        default="auto",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        judgment = run_judge(args)
    except (
        SpreadsheetJudgeError,
        EvalConfigError,
        ModelJudgeError,
        subprocess.TimeoutExpired,
    ) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, "judgment": judgment}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
