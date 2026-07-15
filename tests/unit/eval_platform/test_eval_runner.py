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
        self.assertEqual(report["planned_run_count"], 4)

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
            revision = run_root / "tiny-revision" / "rep-01"

            self.assertEqual(list((baseline / "payload" / "skills").iterdir()), [])
            original = enabled / "payload" / "skills" / "tiny-skill" / "references" / "detail.md"
            replacement = ablated / "payload" / "skills" / "tiny-skill" / "references" / "detail.md"
            self.assertIn("original fixture guidance", original.read_text(encoding="utf-8"))
            self.assertIn("ablated replacement guidance", replacement.read_text(encoding="utf-8"))

            for run_dir in (baseline, enabled, ablated, revision):
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
            revision_result = json.loads((revision / "result.json").read_text(encoding="utf-8"))
            revision_skill = revision_result["condition"]["skills"][0]
            self.assertEqual(revision_skill["requested_revision"], "HEAD")
            self.assertRegex(revision_skill["resolved_revision"], r"^[a-f0-9]{40}$")
            self.assertEqual(revision_skill["path"], "tests/fixtures/evals/skill")

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
            self.assertEqual(summary["result_count"], 4)
            self.assertEqual(len(summary["comparisons"]), 3)
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

    def test_rejudge_reuses_intact_executor_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="eval_rejudge_") as temp:
            agent = f"{sys.executable} {{repo}}/tests/fixtures/evals/fake_agent.py"
            judge = f"{sys.executable} {{repo}}/tests/fixtures/evals/fake_judge.py"
            initial = self.run_evalctl(
                "run",
                "--suite",
                SUITE,
                "--results-dir",
                temp,
                "--run-id",
                "rejudge-source",
                "--agent-command",
                agent,
                "--judge-command",
                judge,
            )
            self.assertEqual(initial.returncode, 0, initial.stderr)
            run_root = Path(temp) / "rejudge-source"
            rejudge = self.run_evalctl(
                "rejudge",
                "--suite",
                SUITE,
                "--run-root",
                str(run_root),
                "--judge-command",
                judge,
            )
            self.assertEqual(rejudge.returncode, 0, rejudge.stderr)
            summary = json.loads((run_root / "run-summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["mode"], "rejudge")
            attempt_root = run_root / "tiny-case" / "tiny-enabled" / "rep-01" / "attempts"
            self.assertTrue(any(attempt_root.iterdir()))

    def test_resume_clones_source_and_reruns_only_failed_executors(self) -> None:
        with tempfile.TemporaryDirectory(prefix="eval_resume_") as temp:
            agent = f"{sys.executable} {{repo}}/tests/fixtures/evals/fake_agent.py"
            judge = f"{sys.executable} {{repo}}/tests/fixtures/evals/fake_judge.py"
            initial = self.run_evalctl(
                "run",
                "--suite",
                SUITE,
                "--results-dir",
                temp,
                "--run-id",
                "resume-source",
                "--agent-command",
                agent,
                "--judge-command",
                judge,
            )
            self.assertEqual(initial.returncode, 0, initial.stderr)
            source_root = Path(temp) / "resume-source"
            baseline_path = source_root / "tiny-case" / "baseline" / "rep-01" / "result.json"
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            baseline["status"] = "failed"
            baseline["executor"]["exit_code"] = 1
            baseline["failure"] = {
                "stage": "executor",
                "category": "executor-error",
                "message": "simulated transport failure",
            }
            baseline_path.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")
            immutable_source = baseline_path.read_bytes()

            resumed = self.run_evalctl(
                "resume",
                "--suite",
                SUITE,
                "--source-run",
                str(source_root),
                "--results-dir",
                temp,
                "--run-id",
                "resume-target",
                "--agent-command",
                agent,
                "--judge-command",
                judge,
            )
            self.assertEqual(resumed.returncode, 0, resumed.stderr)
            self.assertEqual(baseline_path.read_bytes(), immutable_source)

            target_root = Path(temp) / "resume-target"
            target_baseline = json.loads(
                (target_root / "tiny-case" / "baseline" / "rep-01" / "result.json").read_text(
                    encoding="utf-8"
                )
            )
            target_enabled = json.loads(
                (
                    target_root
                    / "tiny-case"
                    / "tiny-enabled"
                    / "rep-01"
                    / "result.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(target_baseline["lineage"]["action"], "reran-executor")
            self.assertEqual(target_enabled["lineage"]["action"], "reused-executor-output")
            self.assertEqual(target_baseline["status"], "completed")
            self.assertEqual(target_enabled["status"], "completed")
            summary = json.loads((target_root / "run-summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["mode"], "resume")


if __name__ == "__main__":
    unittest.main()
