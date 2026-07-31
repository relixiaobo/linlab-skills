from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
EVALCTL = ROOT / "evals" / "runners" / "evalctl.py"
SUITE = "tests/fixtures/evals/suites/runner-smoke.json"
ADAPTER_SUITE = "tests/fixtures/evals/suites/adapter-routing.json"
ADAPTER_REGISTRY = "tests/fixtures/evals/judge-registry.json"
REQUIRED_JUDGING_SUITE = (
    "tests/fixtures/evals/suites/judging-required-missing-adapter.json"
)
UNACTIVATED_ABLATION_SUITE = (
    "tests/fixtures/evals/suites/unactivated-ablation.json"
)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evals.runners.eval_lib import EvalConfigError, validate_case  # noqa: E402
from evals.runners.evalctl import load_judge_protocol  # noqa: E402
from evals.runners.schema_validation import validate_document  # noqa: E402


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
        self.assertFalse(report["judging_required"])
        self.assertIsNone(report["judge_adapters"]["tiny-case"])
        self.assertEqual(
            report["intervention_activations"]["tiny-case"],
            {
                "declared_behaviors": ["tiny-detail-guidance"],
                "condition_behaviors": {
                    "tiny-ablated": ["tiny-detail-guidance"]
                },
            },
        )

    def test_unactivated_ablation_is_rejected_before_materialization(self) -> None:
        validation = self.run_evalctl(
            "validate",
            "--suite",
            UNACTIVATED_ABLATION_SUITE,
        )
        self.assertEqual(validation.returncode, 2)
        self.assertIn(
            "condition tiny-unactivated has unactivated ablation behaviors: "
            "['tiny-unactivated-guidance']",
            validation.stderr,
        )

        with tempfile.TemporaryDirectory(prefix="unactivated_ablation_") as temp:
            materialization = self.run_evalctl(
                "materialize",
                "--suite",
                UNACTIVATED_ABLATION_SUITE,
                "--results-dir",
                temp,
                "--run-id",
                "must-not-materialize",
            )
            self.assertEqual(materialization.returncode, 2)
            self.assertFalse((Path(temp) / "must-not-materialize").exists())

    def test_case_intervention_triggers_and_outcomes_are_validated(self) -> None:
        source = ROOT / "tests/fixtures/evals/cases/tiny-case"
        with tempfile.TemporaryDirectory(prefix="intervention_case_") as temp:
            root = Path(temp)
            case_dir = root / "tiny-case"
            shutil.copytree(source, case_dir)
            oracle_path = case_dir / "oracle.yaml"
            oracle = json.loads(oracle_path.read_text(encoding="utf-8"))
            activation = oracle["intervention_activations"][0]

            activation["trigger_files"] = ["prompt.md"]
            oracle_path.write_text(json.dumps(oracle), encoding="utf-8")
            with self.assertRaisesRegex(
                EvalConfigError,
                "trigger must be Agent-visible under input/",
            ):
                validate_case(case_dir, root)

            activation["trigger_files"] = ["input/missing.txt"]
            oracle_path.write_text(json.dumps(oracle), encoding="utf-8")
            with self.assertRaisesRegex(
                EvalConfigError,
                "trigger is not a regular input file",
            ):
                validate_case(case_dir, root)

            activation["trigger_files"] = ["input/request.txt"]
            activation["observable_outcomes"] = ["missing-outcome"]
            oracle_path.write_text(json.dumps(oracle), encoding="utf-8")
            with self.assertRaisesRegex(
                EvalConfigError,
                r"references unknown outcomes: \['missing-outcome'\]",
            ):
                validate_case(case_dir, root)

    def test_validate_applies_suite_wide_repetitions_override(self) -> None:
        result = self.run_evalctl(
            "validate",
            "--suite",
            SUITE,
            "--repetitions",
            "2",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["planned_run_count"], 8)
        self.assertEqual(report["repetitions_override"], 2)

    def test_required_judging_rejects_a_case_without_an_adapter(self) -> None:
        result = self.run_evalctl("validate", "--suite", REQUIRED_JUDGING_SUITE)
        self.assertEqual(result.returncode, 2)
        self.assertIn("requires judging", result.stderr)
        self.assertIn("tiny-case", result.stderr)

        with tempfile.TemporaryDirectory(prefix="required_judging_run_") as temp:
            run = self.run_evalctl(
                "run",
                "--suite",
                REQUIRED_JUDGING_SUITE,
                "--results-dir",
                temp,
                "--run-id",
                "must-not-materialize",
                "--agent-command",
                f"{sys.executable} {{repo}}/tests/fixtures/evals/fake_agent.py",
            )
            self.assertEqual(run.returncode, 2)
            self.assertFalse((Path(temp) / "must-not-materialize").exists())

    def test_declared_adapter_must_exist_in_the_selected_registry(self) -> None:
        result = self.run_evalctl("validate", "--suite", ADAPTER_SUITE)
        self.assertEqual(result.returncode, 2)
        self.assertIn("unknown judge adapter: fixture-primary", result.stderr)

    def test_judge_result_schema_requires_auditable_fields(self) -> None:
        oracle = json.loads(
            (ROOT / "tests/fixtures/evals/cases/tiny-case/oracle.yaml").read_text(
                encoding="utf-8"
            )
        )
        raw = {"scores": [{"criterion_id": "route-and-output", "value": 1.0}]}
        with tempfile.TemporaryDirectory(prefix="invalid_judge_protocol_") as temp:
            path = Path(temp) / "judge-result.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(EvalConfigError, "required property"):
                load_judge_protocol(path, oracle)

    def test_case_schema_rejects_a_second_judge_dispatch_model(self) -> None:
        oracle = json.loads(
            (ROOT / "tests/fixtures/evals/cases/tiny-case/oracle.yaml").read_text(
                encoding="utf-8"
            )
        )
        oracle["judges"] = []
        with self.assertRaisesRegex(EvalConfigError, "Additional properties"):
            validate_document(oracle, "eval-case.schema.json", "fixture case")

    def test_ablation_schema_requires_behavior_and_reason(self) -> None:
        path = ROOT / "tests/fixtures/evals/conditions/tiny-ablated.json"
        for key in ("behavior", "reason"):
            with self.subTest(key=key):
                condition = json.loads(path.read_text(encoding="utf-8"))
                del condition["skills"][0]["ablations"][0][key]
                with self.assertRaisesRegex(
                    EvalConfigError,
                    f"'{key}' is a required property",
                ):
                    validate_document(
                        condition,
                        "eval-condition.schema.json",
                        "fixture condition",
                    )

    def test_case_defined_domain_failure_tag_is_accepted(self) -> None:
        oracle = json.loads(
            (ROOT / "tests/fixtures/evals/cases/tiny-case/oracle.yaml").read_text(
                encoding="utf-8"
            )
        )
        raw = {
            "scores": [
                {
                    "criterion_id": "route-and-output",
                    "value": 0.0,
                    "passed": False,
                    "rationale": "Fixture domain check failed.",
                    "evidence": ["artifact.txt"],
                }
            ],
            "failure_tags": ["fixture-domain-check"],
            "summary": "fixture domain failure",
        }
        with tempfile.TemporaryDirectory(prefix="domain_failure_tag_") as temp:
            path = Path(temp) / "judge-result.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            normalized = load_judge_protocol(path, oracle)
        self.assertEqual(normalized["failure_tags"], ["fixture-domain-check"])

    def test_task_score_excludes_correct_route_and_renormalizes(self) -> None:
        oracle = json.loads(
            (
                ROOT
                / "evals/cases/analyze-order-revenue/oracle.yaml"
            ).read_text(encoding="utf-8")
        )
        raw = {
            "scores": [
                {
                    "criterion_id": outcome["id"],
                    "value": 0.0 if outcome["id"] == "correct-route" else 1.0,
                    "passed": outcome["id"] != "correct-route",
                    "rationale": "Fixture score.",
                    "evidence": ["fixture"],
                }
                for outcome in oracle["expected"]["outcomes"]
            ],
            "failure_tags": ["route-error"],
            "summary": "Route failed; task quality passed.",
        }
        with tempfile.TemporaryDirectory(prefix="task_score_protocol_") as temp:
            path = Path(temp) / "judge-result.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            normalized = load_judge_protocol(path, oracle)

        self.assertAlmostEqual(normalized["overall_score"], 0.9)
        self.assertAlmostEqual(normalized["task_score"], 1.0)

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
                self.assertEqual(comparison["deltas"]["task_score"], 1.0)
                self.assertEqual(comparison["deltas"]["input_tokens"], 10)
                self.assertEqual(comparison["deltas"]["total_tokens"], 10)
            behaviors_by_condition = {
                item["condition_id"]: item["intervention_behaviors"]
                for item in summary["results"]
            }
            self.assertEqual(
                behaviors_by_condition["tiny-ablated"],
                ["tiny-detail-guidance"],
            )
            self.assertEqual(behaviors_by_condition["baseline"], [])
            ablation_comparison = next(
                item
                for item in summary["comparisons"]
                if item["treatment_condition"] == "tiny-ablated"
            )
            self.assertEqual(
                ablation_comparison["intervention_behaviors"],
                ["tiny-detail-guidance"],
            )

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
            self.assertEqual(enabled_result["judging"]["task_score"], 1.0)
            self.assertTrue(enabled_result["judging"]["passed"])
            self.assertEqual(enabled_result["judging"]["critical_failures"], [])
            self.assertEqual(enabled_result["route"]["primary_skill"], "tiny-skill")
            self.assertEqual(enabled_result["executor"]["model"], "fixture-model")
            self.assertEqual({item["kind"] for item in enabled_result["artifacts"]}, {"response", "artifact"})
            self.assertEqual(enabled_result["judge"]["adapter_id"], "command-override")
            self.assertEqual(enabled_result["judge"]["kind"], "override")
            self.assertRegex(
                enabled_result["judge"]["evidence_manifest_sha256"],
                r"^[a-f0-9]{64}$",
            )
            self.assertIsInstance(
                enabled_result["judge"]["timestamps"]["duration_ms"],
                int,
            )
            self.assertIsNotNone(
                enabled_result["judge"]["timestamps"]["completed_at"]
            )
            judge_provenance = enabled_result["judge"]["provenance"]
            self.assertEqual(
                judge_provenance["entrypoint_path"],
                "tests/fixtures/evals/fake_judge.py",
            )
            self.assertRegex(
                judge_provenance["entrypoint_sha256"],
                r"^[a-f0-9]{64}$",
            )

    def test_run_override_is_recorded_and_rejudge_recovers_it(self) -> None:
        with tempfile.TemporaryDirectory(prefix="eval_repetitions_override_") as temp:
            agent = f"{sys.executable} {{repo}}/tests/fixtures/evals/fake_agent.py"
            judge = f"{sys.executable} {{repo}}/tests/fixtures/evals/fake_judge.py"
            run = self.run_evalctl(
                "run",
                "--suite",
                SUITE,
                "--results-dir",
                temp,
                "--run-id",
                "override-test",
                "--repetitions",
                "2",
                "--agent-command",
                agent,
                "--judge-command",
                judge,
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            run_root = Path(temp) / "override-test"
            summary_path = run_root / "run-summary.json"
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary["repetitions_override"], 2)
            self.assertEqual(summary["planned_run_count"], 8)
            self.assertEqual(summary["result_count"], 8)

            summary_before = summary_path.read_bytes()
            mismatch = self.run_evalctl(
                "rejudge",
                "--suite",
                SUITE,
                "--run-root",
                str(run_root),
                "--repetitions",
                "1",
                "--judge-command",
                judge,
            )
            self.assertEqual(mismatch.returncode, 2)
            self.assertIn("does not match the existing run", mismatch.stderr)
            self.assertEqual(summary_path.read_bytes(), summary_before)

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
            rejudged_summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(rejudged_summary["mode"], "rejudge")
            self.assertEqual(rejudged_summary["repetitions_override"], 2)
            self.assertEqual(rejudged_summary["result_count"], 8)

    def test_registry_routes_each_case_to_its_declared_judge_adapter(self) -> None:
        with tempfile.TemporaryDirectory(prefix="eval_adapter_routing_") as temp:
            agent = f"{sys.executable} {{repo}}/tests/fixtures/evals/fake_agent.py"
            result = self.run_evalctl(
                "run",
                "--suite",
                ADAPTER_SUITE,
                "--judge-registry",
                ADAPTER_REGISTRY,
                "--results-dir",
                temp,
                "--run-id",
                "adapter-routing-test",
                "--agent-command",
                agent,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            root = Path(temp) / "adapter-routing-test"
            alpha = json.loads(
                (root / "adapter-alpha" / "tiny-enabled" / "rep-01" / "result.json").read_text(
                    encoding="utf-8"
                )
            )
            beta = json.loads(
                (root / "adapter-beta" / "tiny-enabled" / "rep-01" / "result.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(alpha["judge"]["adapter_id"], "fixture-primary")
            self.assertEqual(alpha["judging"]["overall_score"], 1.0)
            self.assertEqual(beta["judge"]["adapter_id"], "fixture-secondary")
            self.assertEqual(beta["judging"]["overall_score"], 0.8)
            self.assertEqual(beta["judge"]["config"]["score"], 0.8)
            self.assertEqual(beta["judge"]["config"]["case_marker"], "beta")
            manifest_path = root / "adapter-beta" / "tiny-enabled" / "rep-01" / beta["judge"][
                "evidence_manifest_path"
            ]
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["adapter_id"], "fixture-secondary")
            self.assertEqual(
                [record["path"] for record in manifest["records"]],
                ["secondary-evidence.json"],
            )
            summary = json.loads((root / "run-summary.json").read_text(encoding="utf-8"))
            enabled_adapters = {
                item["case_id"]: item["judge_adapter"]
                for item in summary["results"]
                if item["condition_id"] == "tiny-enabled"
            }
            self.assertEqual(
                enabled_adapters,
                {
                    "adapter-alpha": "fixture-primary",
                    "adapter-beta": "fixture-secondary",
                },
            )

            rejudge = self.run_evalctl(
                "rejudge",
                "--suite",
                ADAPTER_SUITE,
                "--judge-registry",
                ADAPTER_REGISTRY,
                "--run-root",
                str(root),
            )
            self.assertEqual(rejudge.returncode, 0, rejudge.stderr)
            beta_after_rejudge = json.loads(
                (root / "adapter-beta" / "tiny-enabled" / "rep-01" / "result.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                beta_after_rejudge["judge"]["adapter_id"],
                "fixture-secondary",
            )
            self.assertEqual(beta_after_rejudge["judging"]["overall_score"], 0.8)

    def test_judge_adapter_cannot_mutate_agent_output(self) -> None:
        with tempfile.TemporaryDirectory(prefix="eval_mutating_judge_") as temp:
            agent = f"{sys.executable} {{repo}}/tests/fixtures/evals/fake_agent.py"
            judge = (
                f"{sys.executable} "
                "{repo}/tests/fixtures/evals/fake_mutating_judge.py"
            )
            result = self.run_evalctl(
                "run",
                "--suite",
                SUITE,
                "--results-dir",
                temp,
                "--run-id",
                "mutating-judge-test",
                "--agent-command",
                agent,
                "--judge-command",
                judge,
            )
            self.assertEqual(result.returncode, 1, result.stderr)
            run_result = json.loads(
                (
                    Path(temp)
                    / "mutating-judge-test"
                    / "tiny-case"
                    / "tiny-enabled"
                    / "rep-01"
                    / "result.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(run_result["status"], "failed")
            self.assertEqual(run_result["failure"]["category"], "artifact-mutation")

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

    def test_rejudge_preflight_does_not_mutate_when_adapter_is_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="eval_rejudge_preflight_") as temp:
            agent = f"{sys.executable} {{repo}}/tests/fixtures/evals/fake_agent.py"
            judge = f"{sys.executable} {{repo}}/tests/fixtures/evals/fake_judge.py"
            initial = self.run_evalctl(
                "run",
                "--suite",
                SUITE,
                "--results-dir",
                temp,
                "--run-id",
                "rejudge-preflight-source",
                "--agent-command",
                agent,
                "--judge-command",
                judge,
            )
            self.assertEqual(initial.returncode, 0, initial.stderr)
            run_dir = (
                Path(temp)
                / "rejudge-preflight-source"
                / "tiny-case"
                / "tiny-enabled"
                / "rep-01"
            )
            result_before = (run_dir / "result.json").read_bytes()

            rejudge = self.run_evalctl(
                "rejudge",
                "--suite",
                SUITE,
                "--run-root",
                str(Path(temp) / "rejudge-preflight-source"),
            )
            self.assertEqual(rejudge.returncode, 2)
            self.assertIn("requires judging", rejudge.stderr)
            self.assertEqual((run_dir / "result.json").read_bytes(), result_before)
            self.assertFalse((run_dir / "attempts").exists())

    def test_rejudge_rejects_mutated_case_payload_before_mutating_run(self) -> None:
        with tempfile.TemporaryDirectory(prefix="eval_rejudge_payload_") as temp:
            agent = f"{sys.executable} {{repo}}/tests/fixtures/evals/fake_agent.py"
            judge = f"{sys.executable} {{repo}}/tests/fixtures/evals/fake_judge.py"
            initial = self.run_evalctl(
                "run",
                "--suite",
                SUITE,
                "--results-dir",
                temp,
                "--run-id",
                "rejudge-payload-source",
                "--agent-command",
                agent,
                "--judge-command",
                judge,
            )
            self.assertEqual(initial.returncode, 0, initial.stderr)
            run_root = Path(temp) / "rejudge-payload-source"
            run_dir = run_root / "tiny-case" / "tiny-enabled" / "rep-01"
            result_before = (run_dir / "result.json").read_bytes()
            summary_before = (run_root / "run-summary.json").read_bytes()
            (run_dir / "payload" / "input" / "request.txt").write_text(
                "mutated after materialization\n",
                encoding="utf-8",
            )

            rejudge = self.run_evalctl(
                "rejudge",
                "--suite",
                SUITE,
                "--run-root",
                str(run_root),
                "--judge-command",
                judge,
            )
            self.assertEqual(rejudge.returncode, 2)
            self.assertIn("materialized case payload changed", rejudge.stderr)
            self.assertEqual((run_dir / "result.json").read_bytes(), result_before)
            self.assertEqual((run_root / "run-summary.json").read_bytes(), summary_before)
            self.assertFalse((run_dir / "attempts").exists())

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

    def test_resume_rejects_mutated_skill_payload_before_cloning(self) -> None:
        with tempfile.TemporaryDirectory(prefix="eval_resume_payload_") as temp:
            agent = f"{sys.executable} {{repo}}/tests/fixtures/evals/fake_agent.py"
            judge = f"{sys.executable} {{repo}}/tests/fixtures/evals/fake_judge.py"
            initial = self.run_evalctl(
                "run",
                "--suite",
                SUITE,
                "--results-dir",
                temp,
                "--run-id",
                "resume-payload-source",
                "--agent-command",
                agent,
                "--judge-command",
                judge,
            )
            self.assertEqual(initial.returncode, 0, initial.stderr)
            source_root = Path(temp) / "resume-payload-source"
            skill_file = (
                source_root
                / "tiny-case"
                / "tiny-enabled"
                / "rep-01"
                / "payload"
                / "skills"
                / "tiny-skill"
                / "SKILL.md"
            )
            skill_file.write_text(
                skill_file.read_text(encoding="utf-8") + "\nmutated after materialization\n",
                encoding="utf-8",
            )

            resumed = self.run_evalctl(
                "resume",
                "--suite",
                SUITE,
                "--source-run",
                str(source_root),
                "--results-dir",
                temp,
                "--run-id",
                "resume-payload-target",
                "--agent-command",
                agent,
                "--judge-command",
                judge,
            )
            self.assertEqual(resumed.returncode, 2)
            self.assertIn("materialized Skill payload changed", resumed.stderr)
            self.assertFalse((Path(temp) / "resume-payload-target").exists())


if __name__ == "__main__":
    unittest.main()
