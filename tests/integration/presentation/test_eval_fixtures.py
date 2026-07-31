from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
TOOL = REPO / "skills" / "presentation" / "scripts" / "pptx_tool.py"
EVALS = REPO / "tests" / "fixtures" / "artifact-skills" / "presentation" / "evals.json"

EXPECTED = {
    "presentation-studio-full-restructure": (
        "tests/fixtures/artifact-skills/presentation/source/annual_strategy_source.pptx",
        14,
    ),
    "presentation-studio-constrained-redesign": (
        "tests/fixtures/artifact-skills/presentation/source/sales_redesign_source.pptx",
        18,
    ),
    "presentation-surgeon-single-target": (
        "tests/fixtures/artifact-skills/presentation/source/board_deck.pptx",
        10,
    ),
}


class PresentationEvalFixtureTests(unittest.TestCase):
    def test_existing_deck_evals_attach_complex_pptx_fixtures(self) -> None:
        payload = json.loads(EVALS.read_text(encoding="utf-8"))
        by_id = {item["id"]: item for item in payload["evals"]}

        with tempfile.TemporaryDirectory() as temporary:
            temporary = Path(temporary)
            for eval_id, (relative_path, slide_count) in EXPECTED.items():
                with self.subTest(eval_id=eval_id):
                    self.assertEqual(by_id[eval_id]["files"], [relative_path])
                    source = REPO / relative_path
                    self.assertTrue(source.is_file())

                    report_path = temporary / f"{source.stem}.json"
                    result = subprocess.run(
                        ["python3", str(TOOL), "inspect", str(source), "--out", str(report_path)],
                        cwd=REPO,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
                    report = json.loads(report_path.read_text(encoding="utf-8"))
                    self.assertEqual(len(report["slides"]), slide_count)
                    self.assertEqual(report["notes_count"], slide_count)
                    self.assertEqual(report["chart_count"], 1)
                    self.assertEqual(report["media_count"], 1)
                    self.assertEqual(report["slides"][5]["slide_state"]["root_attributes"]["show"], "0")
                    self.assertTrue(report["slides"][6]["slide_state"]["transition"]["present"])
                    self.assertTrue(report["slides"][6]["slide_state"]["timing"]["present"])

                    with zipfile.ZipFile(source) as package:
                        names = set(package.namelist())
                        self.assertIn("ppt/slideMasters/slideMaster1.xml", names)
                        self.assertIn("ppt/slideLayouts/slideLayout1.xml", names)
                        self.assertIn("ppt/theme/theme1.xml", names)
                        custom = package.read("docProps/custom.xml").decode("utf-8")
                        self.assertIn("PrecisionSentinel", custom)
                        self.assertIn("preserve-me", custom)

    def test_precision_fixture_has_one_exact_target(self) -> None:
        source = REPO / EXPECTED["presentation-surgeon-single-target"][0]
        with zipfile.ZipFile(source) as package:
            matches = []
            for name in package.namelist():
                if not name.startswith("ppt/slides/slide") or not name.endswith(".xml"):
                    continue
                text = package.read(name).decode("utf-8")
                if "Q3 pipeline" in text:
                    matches.append(name)
            self.assertEqual(matches, ["ppt/slides/slide7.xml"])

    def test_precision_route_forward_edit_proves_target_and_scope(self) -> None:
        before = REPO / EXPECTED["presentation-surgeon-single-target"][0]
        with tempfile.TemporaryDirectory() as temporary:
            temporary = Path(temporary)
            after = temporary / "board_deck_q4.pptx"
            before_report = temporary / "before.json"
            after_report = temporary / "after.json"
            comparison = temporary / "compare.json"
            package_diff = temporary / "package-diff.json"
            gate = temporary / "gate.json"

            replacements = 0
            with zipfile.ZipFile(before) as source, zipfile.ZipFile(after, "w") as output:
                for info in source.infolist():
                    data = source.read(info.filename)
                    if info.filename == "ppt/slides/slide7.xml":
                        replacements = data.count(b"Q3 pipeline")
                        data = data.replace(b"Q3 pipeline", b"Q4 pipeline")
                    output.writestr(info, data)
            self.assertEqual(replacements, 1)

            commands = [
                ["inspect", str(before), "--out", str(before_report)],
                ["inspect", str(after), "--out", str(after_report)],
                [
                    "package-diff",
                    str(before),
                    str(after),
                    "--allow",
                    "ppt/slides/slide7.xml",
                    "--out",
                    str(package_diff),
                ],
                ["compare", str(before_report), str(after_report), "--out", str(comparison)],
                [
                    "gate",
                    str(after),
                    "--baseline",
                    str(before_report),
                    "--out",
                    str(gate),
                ],
            ]
            for command in commands:
                result = subprocess.run(
                    ["python3", str(TOOL), *command],
                    cwd=REPO,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

            diff_report = json.loads(package_diff.read_text(encoding="utf-8"))
            self.assertEqual(diff_report["unexpected_changes"], [])
            self.assertEqual(
                [item["part"] for item in diff_report["allowed_changes"]],
                ["ppt/slides/slide7.xml"],
            )

            compare_report = json.loads(comparison.read_text(encoding="utf-8"))
            self.assertTrue(compare_report["technical_regression_passed"])
            self.assertFalse(compare_report["scope_verified"])
            changed = compare_report["semantic_changes"]["changed_slides"]
            self.assertEqual([item["slide_key"] for item in changed], ["part:ppt/slides/slide7.xml"])

            gate_report = json.loads(gate.read_text(encoding="utf-8"))
            self.assertTrue(gate_report["technical_gate"]["passed"])
            with zipfile.ZipFile(after) as package:
                slide = package.read("ppt/slides/slide7.xml")
                self.assertEqual(slide.count(b"Q4 pipeline"), 1)
                self.assertEqual(slide.count(b"Q3 pipeline"), 0)


if __name__ == "__main__":
    unittest.main()
