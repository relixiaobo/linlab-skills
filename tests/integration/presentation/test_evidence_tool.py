from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
TOOL = REPO / "presentation" / "scripts" / "evidence_tool.py"


class EvidenceToolTests(unittest.TestCase):
    def run_tool(self, directory: Path, ledger: dict, html: str):
        ledger_path = directory / "evidence-ledger.json"
        html_path = directory / "deck.html"
        report_path = directory / "report.json"
        ledger_path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
        html_path.write_text(html, encoding="utf-8")
        result = subprocess.run(
            [
                "python3",
                str(TOOL),
                "check",
                str(ledger_path),
                "--html",
                str(html_path),
                "--out",
                str(report_path),
            ],
            cwd=REPO,
            capture_output=True,
            text=True,
        )
        return result, json.loads(report_path.read_text(encoding="utf-8"))

    def valid_ledger(self) -> dict:
        return {
            "schemaVersion": "1.0",
            "cutoffDate": "2026-06-30",
            "sources": [
                {
                    "id": "source-regulator",
                    "title": "Annual report",
                    "publisher": "Regulator",
                    "type": "regulatory",
                    "status": "core",
                    "publishedAt": "2026-05-31",
                    "accessedAt": "2026-07-01",
                    "url": "https://example.com/report",
                    "authority": "Primary regulator disclosure",
                }
            ],
            "claims": [
                {
                    "id": "claim-growth",
                    "statement": "Output grew by 25%.",
                    "kind": "fact",
                    "status": "verified",
                    "value": {"display": "25%", "number": 25, "unit": "%"},
                    "sourceRefs": ["source-regulator"],
                    "usedBy": ["slide-1"],
                }
            ],
            "definitions": [],
            "assets": [
                {
                    "id": "asset-chart",
                    "type": "chart",
                    "sourceRef": "source-regulator",
                    "localFile": "assets/chart.svg",
                    "factualRole": "Shows the reported growth value",
                    "rights": "Internal review",
                }
            ],
        }

    def test_valid_bindings_and_process_indexes_do_not_create_metric_noise(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "assets").mkdir()
            (directory / "assets" / "chart.svg").write_text("<svg/>", encoding="utf-8")
            html = """<main><section class="slide" id="slide-1">
              <div>01 Evidence</div><strong data-claim-id="claim-growth">25%</strong>
              <span data-source-id="source-regulator">Source</span>
              <img data-asset-id="asset-chart" src="assets/chart.svg">
            </section></main>"""
            result, report = self.run_tool(directory, self.valid_ledger(), html)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(report["ok"])
            self.assertEqual(report["bindings"]["unboundNumericSlides"], [])
            self.assertEqual(report["counts"]["boundClaims"], 1)

    def test_post_cutoff_source_requires_explicit_retrospective_use(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            ledger = self.valid_ledger()
            ledger["assets"] = []
            ledger["sources"][0]["publishedAt"] = "2026-07-10"
            html = '<section class="slide" id="slide-1" data-claim-id="claim-growth">25%</section>'
            result, report = self.run_tool(directory, ledger, html)
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(any("exceeds cutoff" in item for item in report["errors"]))

            ledger["sources"][0]["cutoffUse"] = "retrospective"
            result, report = self.run_tool(directory, ledger, html)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(any("retrospective" in item for item in report["warnings"]))

    def test_rejected_source_cannot_reenter_through_html_or_assets(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "assets").mkdir()
            (directory / "assets" / "chart.svg").write_text("<svg/>", encoding="utf-8")
            ledger = self.valid_ledger()
            ledger["sources"][0]["status"] = "rejected"
            ledger["claims"][0]["status"] = "rejected"
            html = """<section class="slide" id="slide-1" data-claim-id="claim-growth"
              data-source-id="source-regulator" data-asset-id="asset-chart">25%</section>"""
            result, report = self.run_tool(directory, ledger, html)
            self.assertNotEqual(result.returncode, 0)
            joined = "\n".join(report["errors"])
            self.assertIn("HTML references rejected source", joined)
            self.assertIn("asset uses rejected source", joined)


if __name__ == "__main__":
    unittest.main()
