from __future__ import annotations

import argparse
import copy
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from evals.judges.spreadsheet_judge_adapter import (
    SpreadsheetJudgeError,
    apply_deterministic_overrides,
    audit_calculation_table,
    build_source_truth,
    build_workbook_audit,
    extract_workbook_facts,
    missing_artifact_result,
    prepare_model_workspace,
    run_judge,
    run_recalculation,
    run_source_inspect,
    run_workbook_inspect,
    validate_config,
)
from evals.runners.eval_lib import (
    load_judge_registry,
    resolve_case_judge_adapter,
    validate_case,
)


ROOT = Path(__file__).resolve().parents[3]
CASE_DIR = ROOT / "evals" / "cases" / "build-pricing-model-workbook"
FAKE_CODEX = ROOT / "tests" / "fixtures" / "evals" / "fake_codex_judge.py"


def oracle() -> dict:
    return json.loads((CASE_DIR / "oracle.yaml").read_text(encoding="utf-8"))


def config() -> dict:
    return oracle()["evaluation"]["config"]


def result(primary_skill: str | None = "spreadsheet") -> dict:
    return {
        "run_id": "fixture-run",
        "condition": {"id": "spreadsheet-enabled"},
        "status": "completed",
        "route": {
            "primary_skill": primary_skill,
            "selected_skills": [primary_skill] if primary_skill else [],
        },
        "usage": {},
        "executor": {"model": "fixture-model"},
        "artifacts": [
            {"path": "response.md"},
            {"path": "pricing-model.xlsx"},
        ],
    }


def judgment(value: float = 0.9) -> dict:
    return {
        "scores": [
            {
                "criterion_id": outcome["id"],
                "value": value,
                "passed": value >= 0.75,
                "rationale": "Fixture blind review passed.",
                "evidence": ["workbook-audit.json"],
            }
            for outcome in oracle()["expected"]["outcomes"]
        ],
        "failure_tags": [],
        "summary": "Fixture spreadsheet judgment.",
    }


def worksheet_xml(rows: str, dimension: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <dimension ref="{dimension}"/>
  <sheetData>{rows}</sheetData>
</worksheet>"""


def inline_cell(ref: str, value: str) -> str:
    return f'<c r="{ref}" t="inlineStr"><is><t>{value}</t></is></c>'


def number_cell(ref: str, value: str) -> str:
    return f'<c r="{ref}"><v>{value}</v></c>'


def formula_cell(ref: str, formula: str, value: str) -> str:
    return f'<c r="{ref}"><f>{formula}</f><v>{value}</v></c>'


def typed_formula_cell(
    ref: str, formula: str, value: str, attributes: str
) -> str:
    return f'<c r="{ref}"><f {attributes}>{formula}</f><v>{value}</v></c>'


def row(number: int, cells: list[str]) -> str:
    return f'<row r="{number}">{"".join(cells)}</row>'


CACHED_RESULTS = [
    ("Starter", "1225", "0", "1225", "14700"),
    ("Team", "2388", "238.8", "2149.2", "26290.4"),
    ("Enterprise", "3995", "719.1", "3275.9", "41810.8"),
]


def calculation_sheet_xml(formula_mode: str = "individual") -> str:
    calculation_rows = [
        row(
            1,
            [
                inline_cell("A1", "Plan"),
                inline_cell("B1", "Gross Monthly Revenue"),
                inline_cell("C1", "Discount Amount"),
                inline_cell("D1", "Net Monthly Revenue"),
                inline_cell("E1", "First-Year Total"),
            ],
        )
    ]
    columns = ["B", "C", "D", "E"]
    array_formulas = [
        "Inputs!B2:B4*Inputs!C2:C4",
        "B2:B4*Inputs!D2:D4",
        "B2:B4-C2:C4",
        "D2:D4*AnnualMonths+Inputs!E2:E4",
    ]
    for row_number, values in enumerate(CACHED_RESULTS, start=2):
        formulas = [
            f"Inputs!B{row_number}*Inputs!C{row_number}",
            f"B{row_number}*Inputs!D{row_number}",
            f"B{row_number}-C{row_number}",
            f"D{row_number}*AnnualMonths+Inputs!E{row_number}",
        ]
        formula_cells: list[str] = []
        for index, (column, formula, value) in enumerate(
            zip(columns, formulas, values[1:])
        ):
            reference = f"{column}{row_number}"
            if formula_mode == "individual":
                formula_cells.append(formula_cell(reference, formula, value))
            elif formula_mode == "shared":
                attributes = f't="shared" si="{index}"'
                if row_number == 2:
                    attributes += f' ref="{column}2:{column}4"'
                formula_cells.append(
                    typed_formula_cell(
                        reference,
                        formula if row_number == 2 else "",
                        value,
                        attributes,
                    )
                )
            elif formula_mode == "array":
                if row_number == 2:
                    formula_cells.append(
                        typed_formula_cell(
                            reference,
                            array_formulas[index],
                            value,
                            f't="array" ref="{column}2:{column}4"',
                        )
                    )
                else:
                    formula_cells.append(number_cell(reference, value))
            else:
                raise ValueError(f"unknown formula mode: {formula_mode}")
        calculation_rows.append(
            row(
                row_number,
                [inline_cell(f"A{row_number}", values[0]), *formula_cells],
            )
        )
    return worksheet_xml("".join(calculation_rows), "A1:E4")


def replace_zip_entry(path: Path, name: str, content: str) -> None:
    replacement = path.with_suffix(".replacement.xlsx")
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(
        replacement, "w", zipfile.ZIP_DEFLATED
    ) as destination:
        for info in source.infolist():
            destination.writestr(
                info,
                content.encode("utf-8")
                if info.filename == name
                else source.read(info.filename),
            )
    replacement.replace(path)


def write_good_artifacts(output_dir: Path) -> Path:
    (output_dir / "response.md").write_text(
        "Delivered pricing-model.xlsx. Structural formula checks passed, but no "
        "real spreadsheet engine was available, so cached values were not treated "
        "as proof of recalculation. Open and recalculate in Excel or LibreOffice "
        "before relying on final outputs.\n",
        encoding="utf-8",
    )
    workbook_path = output_dir / "pricing-model.xlsx"
    sheet_names = ["README", "Inputs", "Calculations", "Outputs", "Checks"]
    with zipfile.ZipFile(workbook_path, "w", zipfile.ZIP_DEFLATED) as zf:
        overrides = "".join(
            f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.'
            'spreadsheetml.worksheet+xml"/>'
            for index in range(1, 6)
        )
        zf.writestr(
            "[Content_Types].xml",
            f"""<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  {overrides}
</Types>""",
        )
        sheets = "".join(
            f'<sheet name="{name}" sheetId="{index}" r:id="rId{index}"/>'
            for index, name in enumerate(sheet_names, start=1)
        )
        zf.writestr(
            "xl/workbook.xml",
            f"""<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>{sheets}</sheets>
  <definedNames><definedName name="AnnualMonths">README!$B$2</definedName></definedNames>
  <calcPr calcMode="auto" fullCalcOnLoad="1"/>
</workbook>""",
        )
        relationships = "".join(
            f'<Relationship Id="rId{index}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
            f'relationships/worksheet" Target="worksheets/sheet{index}.xml"/>'
            for index in range(1, 6)
        )
        zf.writestr(
            "xl/_rels/workbook.xml.rels",
            f"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  {relationships}
</Relationships>""",
        )

        readme_rows = "".join(
            [
                row(1, [inline_cell("A1", "Pricing Model")]),
                row(
                    2,
                    [inline_cell("A2", "Annual Months"), number_cell("B2", "12")],
                ),
            ]
        )
        zf.writestr(
            "xl/worksheets/sheet1.xml", worksheet_xml(readme_rows, "A1:B2")
        )

        input_rows = [
            row(
                1,
                [
                    inline_cell("A1", "plan"),
                    inline_cell("B1", "base_price"),
                    inline_cell("C1", "seats"),
                    inline_cell("D1", "discount"),
                    inline_cell("E1", "setup_fee"),
                ],
            ),
            row(
                2,
                [
                    inline_cell("A2", "Starter"),
                    number_cell("B2", "49"),
                    number_cell("C2", "25"),
                    number_cell("D2", "0"),
                    number_cell("E2", "0"),
                ],
            ),
            row(
                3,
                [
                    inline_cell("A3", "Team"),
                    number_cell("B3", "199"),
                    number_cell("C3", "12"),
                    number_cell("D3", "0.10"),
                    number_cell("E3", "500"),
                ],
            ),
            row(
                4,
                [
                    inline_cell("A4", "Enterprise"),
                    number_cell("B4", "799"),
                    number_cell("C4", "5"),
                    number_cell("D4", "0.18"),
                    number_cell("E4", "2500"),
                ],
            ),
        ]
        zf.writestr(
            "xl/worksheets/sheet2.xml", worksheet_xml("".join(input_rows), "A1:E4")
        )

        zf.writestr(
            "xl/worksheets/sheet3.xml",
            calculation_sheet_xml(),
        )

        output_rows = "".join(
            [
                row(
                    1,
                    [
                        inline_cell("A1", "Plan"),
                        inline_cell("B1", "First-Year Total"),
                    ],
                ),
                *[
                    row(
                        index,
                        [
                            inline_cell(f"A{index}", values[0]),
                            formula_cell(
                                f"B{index}", f"Calculations!E{index}", values[4]
                            ),
                        ],
                    )
                    for index, values in enumerate(CACHED_RESULTS, start=2)
                ],
            ]
        )
        zf.writestr(
            "xl/worksheets/sheet4.xml", worksheet_xml(output_rows, "A1:B4")
        )

        check_rows = "".join(
            [
                row(
                    1,
                    [inline_cell("A1", "Check"), inline_cell("B1", "Passed")],
                ),
                row(
                    2,
                    [
                        inline_cell("A2", "Source row count"),
                        formula_cell("B2", "COUNTA(Inputs!A2:A4)=3", "1"),
                    ],
                ),
                row(
                    3,
                    [
                        inline_cell("A3", "Positive outputs"),
                        formula_cell("B3", "MIN(Calculations!D2:D4)>0", "1"),
                    ],
                ),
            ]
        )
        zf.writestr(
            "xl/worksheets/sheet5.xml", worksheet_xml(check_rows, "A1:B3")
        )
    return workbook_path


def args(codex_bin: str = "must-not-run") -> argparse.Namespace:
    return argparse.Namespace(
        codex_bin=codex_bin,
        model="fixture-model",
        reasoning_effort="low",
        timeout_seconds=5,
        max_attempts=1,
        retry_delay_seconds=0,
        structured_output="auto",
    )


def build_audit(root: Path, current_result: dict | None = None) -> tuple[dict, dict]:
    output_dir = root / "output"
    output_dir.mkdir()
    workbook_path = write_good_artifacts(output_dir)
    evidence_dir = root / "evidence"
    truth = build_source_truth(config(), CASE_DIR)
    source_report = run_source_inspect(
        CASE_DIR / "input" / "pricing_inputs.csv",
        "input/pricing_inputs.csv",
        evidence_dir,
    )
    inspect_report = run_workbook_inspect(
        workbook_path, "pricing-model.xlsx", evidence_dir
    )
    with patch(
        "evals.judges.spreadsheet_judge_adapter.shutil.which", return_value=None
    ):
        recalc_report = run_recalculation(
            workbook_path, "pricing-model.xlsx", evidence_dir
        )
    facts = extract_workbook_facts(workbook_path)
    audit = build_workbook_audit(
        config(),
        current_result or result(),
        workbook_path,
        inspect_report,
        recalc_report,
        facts,
        truth,
    )
    return {
        "truth": truth,
        "source_report": source_report,
        "inspect_report": inspect_report,
        "recalc_report": recalc_report,
        "facts": facts,
        "workbook_path": workbook_path,
    }, audit


class SpreadsheetJudgeTests(unittest.TestCase):
    def test_case_contract_and_source_truth(self) -> None:
        validate_config(config(), oracle())
        truth = build_source_truth(config(), CASE_DIR)
        outputs = {
            row_value["plan"]: row_value["expected_outputs"]
            for row_value in truth["rows"]
        }
        self.assertEqual(outputs["Starter"]["gross-monthly-revenue"], "1225")
        self.assertEqual(outputs["Team"]["first-year-total"], "26290.4")
        self.assertEqual(outputs["Enterprise"]["first-year-total"], "41810.8")

        invalid = copy.deepcopy(config())
        invalid["calculations"]["outputs"][0]["expression"] = "unknown * seats"
        with self.assertRaisesRegex(SpreadsheetJudgeError, "unknown names"):
            validate_config(invalid, oracle())

    def test_complete_workbook_passes_deterministic_audit(self) -> None:
        with tempfile.TemporaryDirectory(prefix="spreadsheet_audit_") as temp:
            evidence, audit = build_audit(Path(temp))

        self.assertTrue(evidence["source_report"]["ok"])
        self.assertTrue(evidence["inspect_report"]["ok"])
        self.assertTrue(evidence["facts"]["ok"])
        self.assertFalse(evidence["recalc_report"]["ran"])
        self.assertTrue(audit["package_integrity"]["passed"])
        self.assertTrue(audit["architecture"]["passed"])
        self.assertTrue(audit["source_table"]["passed"])
        self.assertTrue(audit["calculation_table"]["passed"])
        self.assertTrue(audit["defined_names"]["passed"])
        self.assertTrue(audit["checks"]["passed"])
        self.assertEqual(
            sum(len(row_value["outputs"]) for row_value in audit["calculation_table"]["rows"]),
            12,
        )

    def test_shared_and_array_formula_followers_are_live_formulas(self) -> None:
        truth = build_source_truth(config(), CASE_DIR)
        with tempfile.TemporaryDirectory(prefix="spreadsheet_formula_types_") as temp:
            root = Path(temp)
            for formula_mode in ("shared", "array"):
                with self.subTest(formula_mode=formula_mode):
                    output_dir = root / formula_mode
                    output_dir.mkdir()
                    workbook_path = write_good_artifacts(output_dir)
                    replace_zip_entry(
                        workbook_path,
                        "xl/worksheets/sheet3.xml",
                        calculation_sheet_xml(formula_mode),
                    )
                    facts = extract_workbook_facts(workbook_path)
                    calculation_audit = audit_calculation_table(
                        config(), truth, facts
                    )

                    self.assertTrue(facts["ok"])
                    self.assertTrue(calculation_audit["passed"])
                    follower = calculation_audit["rows"][1]["outputs"][
                        "gross-monthly-revenue"
                    ]
                    self.assertEqual(follower["formula_type"], formula_mode)
                    self.assertEqual(
                        follower["formula_origin"], f"{formula_mode}-master"
                    )
                    self.assertEqual(follower["formula_master_cell"], "B2")
                    self.assertEqual(follower["formula_range"], "B2:B4")

    def test_workbook_scope_name_wins_over_same_named_local_scope(self) -> None:
        with tempfile.TemporaryDirectory(prefix="spreadsheet_defined_name_") as temp:
            root = Path(temp)
            output_dir = root / "output"
            output_dir.mkdir()
            workbook_path = write_good_artifacts(output_dir)
            with zipfile.ZipFile(workbook_path) as zf:
                workbook_xml = zf.read("xl/workbook.xml").decode("utf-8")
            workbook_xml = workbook_xml.replace(
                '<definedName name="AnnualMonths">README!$B$2</definedName>',
                '<definedName name="AnnualMonths">README!$B$2</definedName>'
                '<definedName name="AnnualMonths" localSheetId="0">'
                "README!$B$99</definedName>",
            )
            replace_zip_entry(workbook_path, "xl/workbook.xml", workbook_xml)
            evidence_dir = root / "evidence"
            inspect_report = run_workbook_inspect(
                workbook_path, "pricing-model.xlsx", evidence_dir
            )
            audit = build_workbook_audit(
                config(),
                result(),
                workbook_path,
                inspect_report,
                {"ran": False, "ok": None, "errors": [], "limitations": []},
                extract_workbook_facts(workbook_path),
                build_source_truth(config(), CASE_DIR),
            )

            requirement = audit["defined_names"]["requirements"][0]
            self.assertTrue(requirement["found"])
            self.assertTrue(requirement["workbook_scope_found"])
            self.assertEqual(requirement["scope"], "workbook")
            self.assertEqual(requirement["actual_value"], "12")
            self.assertTrue(requirement["passed"])

    def test_invalid_required_sheet_xml_fails_package_architecture(self) -> None:
        with tempfile.TemporaryDirectory(prefix="spreadsheet_invalid_sheet_") as temp:
            root = Path(temp)
            output_dir = root / "output"
            output_dir.mkdir()
            workbook_path = write_good_artifacts(output_dir)
            replace_zip_entry(
                workbook_path, "xl/worksheets/sheet1.xml", "<worksheet"
            )
            evidence_dir = root / "evidence"
            inspect_report = run_workbook_inspect(
                workbook_path, "pricing-model.xlsx", evidence_dir
            )
            facts = extract_workbook_facts(workbook_path)
            audit = build_workbook_audit(
                config(),
                result(),
                workbook_path,
                inspect_report,
                {"ran": False, "ok": None, "errors": [], "limitations": []},
                facts,
                build_source_truth(config(), CASE_DIR),
            )
            output = apply_deterministic_overrides(
                judgment(),
                oracle=oracle(),
                config=config(),
                result=result(),
                workbook_audit=audit,
            )

            scores = {item["criterion_id"]: item for item in output["scores"]}
            self.assertFalse(facts["ok"])
            self.assertFalse(audit["package_integrity"]["structure_passed"])
            self.assertEqual(scores["workbook-architecture"]["value"], 0.0)
            self.assertIn("workbook-integrity", output["failure_tags"])

    def test_failed_office_conversion_is_not_reported_as_recalculated(self) -> None:
        with tempfile.TemporaryDirectory(prefix="spreadsheet_recalc_failure_") as temp:
            root = Path(temp)
            output_dir = root / "output"
            output_dir.mkdir()
            workbook_path = write_good_artifacts(output_dir)
            evidence_dir = root / "evidence"
            evidence_dir.mkdir()
            stale_recalculation = evidence_dir / "pricing-model.recalculated.xlsx"
            stale_recalculation.write_bytes(b"stale")
            failed_report = {
                "ok": False,
                "engine": "libreoffice",
                "output": "",
                "errors": ["libreoffice_recalc_failed"],
                "warnings": [],
                "inspect": None,
            }
            with patch(
                "evals.judges.spreadsheet_judge_adapter.shutil.which",
                return_value="/usr/bin/soffice",
            ), patch(
                "evals.judges.spreadsheet_judge_adapter.run_report_tool",
                return_value=failed_report,
            ):
                report = run_recalculation(
                    workbook_path, "pricing-model.xlsx", evidence_dir
                )

            self.assertFalse(report["ran"])
            self.assertIsNone(report["output"])
            self.assertFalse(stale_recalculation.exists())
            self.assertIn(
                "recalculation_not_completed:libreoffice_recalc_failed",
                report["limitations"],
            )

    def test_deterministic_failures_recompute_pass_state_and_tags(self) -> None:
        with tempfile.TemporaryDirectory(prefix="spreadsheet_caps_") as temp:
            _, audit = build_audit(Path(temp), result(primary_skill=None))

        broken = copy.deepcopy(audit)
        broken["architecture"]["passed"] = False
        broken["source_table"]["passed"] = False
        broken["calculation_table"]["passed"] = False
        broken["defined_names"]["passed"] = False
        broken["checks"]["passed"] = False
        output = apply_deterministic_overrides(
            judgment(),
            oracle=oracle(),
            config=config(),
            result=result(primary_skill=None),
            workbook_audit=broken,
        )
        scores = {item["criterion_id"]: item for item in output["scores"]}
        self.assertEqual(scores["correct-route"]["value"], 0.0)
        self.assertEqual(scores["source-fidelity"]["value"], 0.25)
        self.assertEqual(scores["live-formula-model"]["value"], 0.25)
        self.assertEqual(scores["workbook-architecture"]["value"], 0.5)
        self.assertEqual(scores["input-usability"]["value"], 0.5)
        self.assertEqual(scores["qa-and-verification"]["value"], 0.5)
        self.assertTrue(all(not item["passed"] for item in scores.values()))
        self.assertEqual(
            set(output["failure_tags"]),
            {
                "factuality",
                "formula-integrity",
                "process-compliance",
                "route-error",
                "verification",
                "workbook-integrity",
            },
        )

    def test_missing_workbook_skips_model_review(self) -> None:
        output = missing_artifact_result(oracle(), result())
        scores = {item["criterion_id"]: item for item in output["scores"]}
        self.assertEqual(scores["correct-route"]["value"], 1.0)
        self.assertEqual(scores["source-fidelity"]["value"], 0.0)
        self.assertIn("missing-artifact", output["failure_tags"])

    def test_blind_workspace_redacts_paths_and_omits_binary_workbook(self) -> None:
        with tempfile.TemporaryDirectory(prefix="spreadsheet_blind_") as temp:
            root = Path(temp)
            run_dir = root / "case" / "spreadsheet-enabled" / "rep-01"
            payload = run_dir / "payload"
            output_dir = run_dir / "output"
            (payload / "input").mkdir(parents=True)
            output_dir.mkdir()
            (payload / "prompt.md").write_text("Build the model.\n", encoding="utf-8")
            (payload / "input" / "pricing_inputs.csv").write_text(
                (CASE_DIR / "input" / "pricing_inputs.csv").read_text(
                    encoding="utf-8"
                ),
                encoding="utf-8",
            )
            workbook_path = write_good_artifacts(output_dir)
            leaked_path = str(workbook_path)
            (output_dir / "response.md").write_text(
                f"Inspected {leaked_path}.\n", encoding="utf-8"
            )
            evidence_dir = root / "evidence"
            source_truth = build_source_truth(config(), payload)
            source_report = run_source_inspect(
                payload / "input" / "pricing_inputs.csv",
                "input/pricing_inputs.csv",
                evidence_dir,
            )
            inspect_report = run_workbook_inspect(
                workbook_path, "pricing-model.xlsx", evidence_dir
            )
            with patch(
                "evals.judges.spreadsheet_judge_adapter.shutil.which",
                return_value=None,
            ):
                recalc_report = run_recalculation(
                    workbook_path, "pricing-model.xlsx", evidence_dir
                )
            audit = build_workbook_audit(
                config(),
                result(),
                workbook_path,
                inspect_report,
                recalc_report,
                extract_workbook_facts(workbook_path),
                source_truth,
            )
            workspace = root / "blind-review"
            workspace.mkdir()
            prepare_model_workspace(
                workspace=workspace,
                env={
                    "EVAL_RESULT_FILE": run_dir / "result.json",
                    "EVAL_PAYLOAD_DIR": payload,
                    "EVAL_OUTPUT_DIR": output_dir,
                },
                result=result(),
                source_truth=source_truth,
                source_inspect=source_report,
                workbook_inspect=inspect_report,
                workbook_audit=audit,
                recalc_report=recalc_report,
                trace={"items": [{"text": leaked_path}]},
                evidence_dir=evidence_dir,
            )

            self.assertFalse((workspace / "artifacts").exists())
            workspace_bytes = b"\n".join(
                path.read_bytes()
                for path in sorted(workspace.rglob("*"))
                if path.is_file()
            )
            self.assertNotIn(b"spreadsheet-enabled", workspace_bytes)
            self.assertNotIn(str(run_dir).encode(), workspace_bytes)
            self.assertIn(b"agent-output/pricing-model.xlsx", workspace_bytes)

    def test_run_judge_persists_evidence_without_model_when_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="spreadsheet_missing_") as temp:
            root = Path(temp)
            output_dir = root / "output"
            output_dir.mkdir()
            (output_dir / "response.md").write_text(
                "No workbook.\n", encoding="utf-8"
            )
            result_path = root / "result.json"
            result_path.write_text(json.dumps(result()), encoding="utf-8")
            judge_result = root / "judge-result.json"
            evidence_dir = root / "judge-evidence"
            trace_dir = root / "judge-trace"
            env = {
                "EVAL_ORACLE_FILE": str(CASE_DIR / "oracle.yaml"),
                "EVAL_RESULT_FILE": str(result_path),
                "EVAL_PAYLOAD_DIR": str(CASE_DIR),
                "EVAL_OUTPUT_DIR": str(output_dir),
                "EVAL_JUDGE_RESULT_FILE": str(judge_result),
                "EVAL_JUDGE_CONFIG": json.dumps(config()),
                "EVAL_JUDGE_EVIDENCE_DIR": str(evidence_dir),
                "EVAL_JUDGE_TRACE_DIR": str(trace_dir),
            }
            with patch.dict(os.environ, env, clear=False):
                output = run_judge(args())

            self.assertIn("missing-artifact", output["failure_tags"])
            self.assertTrue((evidence_dir / "source-inspect.json").is_file())
            self.assertTrue((evidence_dir / "source-truth.json").is_file())
            self.assertTrue((evidence_dir / "workbook-inspect.json").is_file())
            self.assertFalse(trace_dir.exists())

    def test_run_judge_exercises_full_blind_model_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="spreadsheet_model_") as temp:
            root = Path(temp)
            output_dir = root / "output"
            output_dir.mkdir()
            workbook_path = write_good_artifacts(output_dir)
            workbook_before = workbook_path.read_bytes()
            result_path = root / "result.json"
            result_path.write_text(json.dumps(result()), encoding="utf-8")
            judge_result = root / "judge-result.json"
            evidence_dir = root / "judge-evidence"
            trace_dir = root / "judge-trace"
            codex_home = root / "original-codex-home"
            codex_home.mkdir()
            (codex_home / "auth.json").write_text("{}\n", encoding="utf-8")
            env = {
                "CODEX_HOME": str(codex_home),
                "EVAL_ORACLE_FILE": str(CASE_DIR / "oracle.yaml"),
                "EVAL_RESULT_FILE": str(result_path),
                "EVAL_PAYLOAD_DIR": str(CASE_DIR),
                "EVAL_OUTPUT_DIR": str(output_dir),
                "EVAL_JUDGE_RESULT_FILE": str(judge_result),
                "EVAL_JUDGE_CONFIG": json.dumps(config()),
                "EVAL_JUDGE_EVIDENCE_DIR": str(evidence_dir),
                "EVAL_JUDGE_TRACE_DIR": str(trace_dir),
            }
            with patch.dict(os.environ, env, clear=False), patch(
                "evals.judges.spreadsheet_judge_adapter.shutil.which",
                return_value=None,
            ):
                output = run_judge(args(str(FAKE_CODEX)))

            scores = {item["criterion_id"]: item for item in output["scores"]}
            self.assertEqual(scores["correct-route"]["value"], 1.0)
            self.assertEqual(scores["live-formula-model"]["value"], 0.9)
            self.assertEqual(output["failure_tags"], [])
            self.assertEqual(workbook_path.read_bytes(), workbook_before)
            self.assertEqual(
                json.loads(judge_result.read_text(encoding="utf-8")), output
            )
            usage = json.loads(
                (trace_dir / "usage.json").read_text(encoding="utf-8")
            )
            self.assertEqual(usage["usage"]["total_tokens"], 18)

    def test_registry_resolves_spreadsheet_and_suite_requires_judging(self) -> None:
        case = validate_case(CASE_DIR, ROOT)
        registry = load_judge_registry(
            ROOT / "evals" / "judges" / "registry.json", ROOT
        )
        adapter = resolve_case_judge_adapter(case, registry)
        self.assertIsNotNone(adapter)
        assert adapter is not None
        self.assertEqual(adapter.id, "spreadsheet")
        self.assertEqual(adapter.jobs, ("create-spreadsheet",))
        suite = json.loads(
            (
                ROOT
                / "evals"
                / "suites"
                / "spreadsheet-pricing-model-ab.json"
            ).read_text(encoding="utf-8")
        )
        self.assertTrue(suite["judging"]["required"])
        self.assertEqual(suite["defaults"]["repetitions"], 1)
        legacy = json.loads(
            (
                ROOT
                / "tests"
                / "fixtures"
                / "artifact-skills"
                / "spreadsheet"
                / "evals.json"
            ).read_text(encoding="utf-8")
        )
        self.assertNotIn(
            "spreadsheet-pricing-model",
            {item["id"] for item in legacy["evals"]},
        )


if __name__ == "__main__":
    unittest.main()
