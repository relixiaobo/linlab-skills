from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
EVALCTL = ROOT / "evals" / "runners" / "evalctl.py"
SUITE = "tests/fixtures/evals/suites/runner-smoke.json"


class EvalRunnerTests(unittest.TestCase):
    def run_evalctl(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(EVALCTL), *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_fixture_suite_validates(self) -> None:
        result = self.run_evalctl("validate", "--suite", SUITE)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["ok"])
        self.assertEqual(report["planned_run_count"], 3)

    def test_materialization_isolates_oracle_and_applies_ablation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="eval_materialize_") as temp:
            result = self.run_evalctl(
                "materialize",
                "--suite",
                SUITE,
                "--results-dir",
                temp,
                "--run-id",
                "materialize-test",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            run_root = Path(temp) / "materialize-test" / "tiny-case"
            baseline = run_root / "baseline" / "rep-01"
            enabled = run_root / "tiny-enabled" / "rep-01"
            ablated = run_root / "tiny-ablated" / "rep-01"

            self.assertEqual(list((baseline / "payload" / "skills").iterdir()), [])
            original = enabled / "payload" / "skills" / "tiny-skill" / "references" / "detail.md"
            replacement = ablated / "payload" / "skills" / "tiny-skill" / "references" / "detail.md"
            self.assertIn("original fixture guidance", original.read_text(encoding="utf-8"))
            self.assertIn("ablated replacement guidance", replacement.read_text(encoding="utf-8"))

            for run_dir in (baseline, enabled, ablated):
                payload_files = [path for path in (run_dir / "payload").rglob("*") if path.is_file()]
                self.assertFalse(any(path.name == "oracle.yaml" for path in payload_files))
                joined = "\n".join(path.read_text(encoding="utf-8") for path in payload_files)
                self.assertNotIn("HIDDEN_ORACLE_SENTINEL", joined)
                manifest = json.loads((run_dir / "agent-manifest.json").read_text(encoding="utf-8"))
                self.assertNotIn("oracle", json.dumps(manifest).lower())
                self.assertNotIn("condition", manifest)

            enabled_result = json.loads((enabled / "result.json").read_text(encoding="utf-8"))
            ablated_result = json.loads((ablated / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(
                enabled_result["condition"]["skills"][0]["source_sha256"],
                ablated_result["condition"]["skills"][0]["source_sha256"],
            )
            self.assertNotEqual(
                enabled_result["condition"]["skills"][0]["materialized_sha256"],
                ablated_result["condition"]["skills"][0]["materialized_sha256"],
            )

    def test_run_records_scores_costs_and_paired_deltas(self) -> None:
        with tempfile.TemporaryDirectory(prefix="eval_run_") as temp:
            agent = f"{sys.executable} {{repo}}/tests/fixtures/evals/fake_agent.py"
            judge = f"{sys.executable} {{repo}}/tests/fixtures/evals/fake_judge.py"
            result = self.run_evalctl(
                "run",
                "--suite",
                SUITE,
                "--results-dir",
                temp,
                "--run-id",
                "execution-test",
                "--agent-command",
                agent,
                "--judge-command",
                judge,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            run_root = Path(temp) / "execution-test"
            summary = json.loads((run_root / "run-summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["result_count"], 3)
            self.assertEqual(len(summary["comparisons"]), 2)
            for comparison in summary["comparisons"]:
                self.assertEqual(comparison["deltas"]["score"], 1.0)
                self.assertEqual(comparison["deltas"]["input_tokens"], 10)
                self.assertEqual(comparison["deltas"]["total_tokens"], 10)

            enabled_result = json.loads(
                (
                    run_root
                    / "tiny-case"
                    / "tiny-enabled"
                    / "rep-01"
                    / "result.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(enabled_result["status"], "completed")
            self.assertEqual(enabled_result["judging"]["status"], "completed")
            self.assertEqual(enabled_result["judging"]["overall_score"], 1.0)
            self.assertTrue(enabled_result["judging"]["passed"])
            self.assertEqual(enabled_result["judging"]["critical_failures"], [])
            self.assertEqual(enabled_result["route"]["primary_skill"], "tiny-skill")
            self.assertEqual(enabled_result["executor"]["model"], "fixture-model")
            self.assertEqual({item["kind"] for item in enabled_result["artifacts"]}, {"response", "artifact"})

    def test_agent_command_cannot_reference_hidden_oracle(self) -> None:
        with tempfile.TemporaryDirectory(prefix="eval_oracle_guard_") as temp:
            result = self.run_evalctl(
                "run",
                "--suite",
                SUITE,
                "--results-dir",
                temp,
                "--run-id",
                "oracle-guard-test",
                "--agent-command",
                "echo {oracle}",
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("unknown command placeholder: oracle", result.stderr)


if __name__ == "__main__":
    unittest.main()
