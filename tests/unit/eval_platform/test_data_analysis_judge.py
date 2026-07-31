from __future__ import annotations

import argparse
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evals.judges.data_analysis_judge_adapter import (
    apply_deterministic_overrides,
    audit_artifacts,
    build_source_truth,
    missing_artifact_result,
    run_judge,
)
from evals.judges.model_judge_runtime import (
    ModelJudgeError,
    ModelJudgeOptions,
    judge_output_schema,
    run_blind_model_judge,
    validate_model_judgment,
)
from evals.runners.eval_lib import (
    load_judge_registry,
    resolve_case_judge_adapter,
    validate_case,
)


ROOT = Path(__file__).resolve().parents[3]
CASE_DIR = ROOT / "evals" / "cases" / "analyze-order-revenue"
FAKE_CODEX = ROOT / "tests" / "fixtures" / "evals" / "fake_codex_judge.py"


def oracle() -> dict:
    return json.loads((CASE_DIR / "oracle.yaml").read_text(encoding="utf-8"))


def result(primary_skill: str | None = "data-analysis") -> dict:
    return {
        "status": "completed",
        "route": {
            "primary_skill": primary_skill,
            "selected_skills": [primary_skill] if primary_skill else [],
        },
        "usage": {},
        "executor": {"model": "fixture-model"},
        "artifacts": [
            {"path": "response.md"},
            {"path": "analysis.md"},
            {"path": "findings.tsv"},
        ],
    }


def judgment(value: float = 0.9) -> dict:
    return {
        "scores": [
            {
                "criterion_id": outcome["id"],
                "value": value,
                "passed": value >= 0.75,
                "rationale": "Blind model review passed.",
                "evidence": ["artifacts/analysis.md"],
            }
            for outcome in oracle()["expected"]["outcomes"]
        ],
        "failure_tags": [],
        "summary": "fixture judgment",
    }


def write_good_artifacts(output_dir: Path) -> None:
    (output_dir / "response.md").write_text(
        "Paid revenue is $400.00 across 3 paid orders; AOV is $133.33.\n",
        encoding="utf-8",
    )
    (output_dir / "analysis.md").write_text(
        """# Paid order analysis

Filtering `status = paid` excludes the refunded order. At the `order_id` grain,
paid revenue is 400.00 across 3 paid orders and average paid order value is
133.33. `order_lines` is a one-to-many join that creates fan-out and would inflate
the order-level revenue if summed after joining. An independent aggregation over
orders.csv cross-checks and reconciles all three values.
""",
        encoding="utf-8",
    )
    rows = [
        (
            "paid-revenue",
            "Paid revenue is 400.00",
            "sum revenue where status=paid",
            "orders.csv rows 1001, 1002, 1004",
            "Independent grouped sum reconciles to 400.00",
            "Refunded orders excluded",
            "verified",
        ),
        (
            "paid-orders",
            "There are 3 paid orders",
            "count order_id where status=paid",
            "orders.csv paid rows",
            "Independent distinct order_id count is 3",
            "Status field assumed authoritative",
            "verified",
        ),
        (
            "paid-aov",
            "Average paid order value is 133.33",
            "400.00 divided by 3",
            "paid revenue and order count findings",
            "Independent mean over paid order rows is 133.33",
            "Displayed value rounded to two decimals",
            "verified",
        ),
    ]
    lines = ["\t".join(["id", "claim", "computation", "evidence", "verification", "caveat", "status"])]
    lines.extend("\t".join(row) for row in rows)
    (output_dir / "findings.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")


class DataAnalysisJudgeTests(unittest.TestCase):
    def test_source_truth_recomputes_metrics_and_join_inflation(self) -> None:
        truth = build_source_truth(oracle()["evaluation"]["config"], CASE_DIR)
        metrics = {item["id"]: item for item in truth["metrics"]}
        self.assertEqual(metrics["paid-revenue"]["computed"], "400.00")
        self.assertEqual(metrics["paid-order-count"]["computed"], "3")
        self.assertTrue(metrics["average-paid-order-value"]["computed"].startswith("133.333"))
        self.assertTrue(all(item["contract_matches_source"] for item in truth["metrics"]))
        self.assertTrue(truth["metric_source"]["grain_unique"])
        self.assertTrue(truth["join"]["fanout_risk"])
        self.assertEqual(truth["join"]["join_to_left_row_ratio"], "1.5")
        self.assertEqual(truth["join"]["naive_joined_left_measure"], "720.00")

    def test_artifact_audit_requires_metrics_grain_fanout_and_verification(self) -> None:
        with tempfile.TemporaryDirectory(prefix="data_judge_artifacts_") as temp:
            output_dir = Path(temp)
            write_good_artifacts(output_dir)
            truth = build_source_truth(oracle()["evaluation"]["config"], CASE_DIR)
            audit = audit_artifacts(
                oracle()["evaluation"]["config"],
                result(),
                output_dir,
                truth,
            )
        self.assertTrue(all(audit["metric_mentions"].values()))
        self.assertTrue(all(audit["concepts"].values()))
        self.assertTrue(audit["findings"]["ledger"]["valid"])
        self.assertEqual(audit["findings"]["ledger"]["rows"], 3)

    def test_artifact_audit_recognizes_join_expansion_without_magic_word(self) -> None:
        with tempfile.TemporaryDirectory(prefix="data_judge_join_expansion_") as temp:
            output_dir = Path(temp)
            write_good_artifacts(output_dir)
            (output_dir / "analysis.md").write_text(
                """# Join control

At the unique `order_id` grain, metrics are computed before the join. A direct
join expands three paid orders to five rows and would produce an incorrect sum
of 720.00 when order revenue is summed afterward. An independent grouped line
aggregation reconciles to 400.00 for `status = paid`.
""",
                encoding="utf-8",
            )
            truth = build_source_truth(oracle()["evaluation"]["config"], CASE_DIR)
            audit = audit_artifacts(
                oracle()["evaluation"]["config"],
                result(),
                output_dir,
                truth,
            )

        self.assertTrue(audit["concepts"]["fanout"])

    def test_only_structured_deterministic_failures_cap_model_scores(self) -> None:
        with tempfile.TemporaryDirectory(prefix="data_judge_overrides_") as temp:
            output_dir = Path(temp)
            write_good_artifacts(output_dir)
            truth = build_source_truth(oracle()["evaluation"]["config"], CASE_DIR)
            audit = audit_artifacts(
                oracle()["evaluation"]["config"],
                result(primary_skill=None),
                output_dir,
                truth,
            )
        broken = copy.deepcopy(audit)
        broken["metric_mentions"] = {
            metric_id: False for metric_id in broken["metric_mentions"]
        }
        broken["concepts"]["grain"] = False
        broken["concepts"]["fanout"] = False
        broken["concepts"]["independent_verification"] = False
        broken["findings"]["ledger"]["valid"] = False
        output = apply_deterministic_overrides(
            judgment(),
            oracle=oracle(),
            result=result(primary_skill=None),
            source_truth=truth,
            artifact_audit=broken,
        )
        scores = {item["criterion_id"]: item for item in output["scores"]}
        self.assertEqual(scores["correct-route"]["value"], 0.0)
        self.assertEqual(scores["correct-metrics"]["value"], 0.25)
        self.assertEqual(scores["fanout-control"]["value"], 0.9)
        self.assertEqual(scores["independent-verification"]["value"], 0.9)
        self.assertEqual(scores["auditable-delivery"]["value"], 0.4)
        self.assertEqual(
            set(output["failure_tags"]),
            {"factuality", "process-compliance", "route-error"},
        )

    def test_missing_artifacts_skip_model_review(self) -> None:
        output = missing_artifact_result(oracle(), result())
        scores = {item["criterion_id"]: item for item in output["scores"]}
        self.assertEqual(scores["correct-route"]["value"], 1.0)
        self.assertEqual(scores["correct-metrics"]["value"], 0.0)
        self.assertIn("missing-artifact", output["failure_tags"])

    def test_run_judge_persists_evidence_without_calling_model_when_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="data_judge_run_") as temp:
            root = Path(temp)
            output_dir = root / "output"
            output_dir.mkdir()
            (output_dir / "response.md").write_text("No artifacts.\n", encoding="utf-8")
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
                "EVAL_JUDGE_CONFIG": json.dumps(oracle()["evaluation"]["config"]),
                "EVAL_JUDGE_EVIDENCE_DIR": str(evidence_dir),
                "EVAL_JUDGE_TRACE_DIR": str(trace_dir),
            }
            args = argparse.Namespace(
                codex_bin="must-not-run",
                model="fixture",
                reasoning_effort="low",
                timeout_seconds=1,
                max_attempts=1,
                retry_delay_seconds=0,
                structured_output="prompt",
            )
            with patch.dict(os.environ, env, clear=False):
                output = run_judge(args)
            self.assertIn("missing-artifact", output["failure_tags"])
            self.assertTrue(judge_result.is_file())
            self.assertTrue((evidence_dir / "source-truth.json").is_file())
            self.assertTrue((evidence_dir / "artifact-audit.json").is_file())
            self.assertFalse(trace_dir.exists())

    def test_run_judge_exercises_isolated_blind_model_review(self) -> None:
        with tempfile.TemporaryDirectory(prefix="data_judge_model_") as temp:
            root = Path(temp)
            output_dir = root / "output"
            output_dir.mkdir()
            write_good_artifacts(output_dir)
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
                "EVAL_JUDGE_CONFIG": json.dumps(oracle()["evaluation"]["config"]),
                "EVAL_JUDGE_EVIDENCE_DIR": str(evidence_dir),
                "EVAL_JUDGE_TRACE_DIR": str(trace_dir),
            }
            args = argparse.Namespace(
                codex_bin=str(FAKE_CODEX),
                model="fixture-model",
                reasoning_effort="low",
                timeout_seconds=5,
                max_attempts=1,
                retry_delay_seconds=0,
                structured_output="auto",
            )
            with patch.dict(os.environ, env, clear=False):
                output = run_judge(args)

            scores = {item["criterion_id"]: item for item in output["scores"]}
            self.assertEqual(scores["correct-route"]["value"], 1.0)
            self.assertEqual(scores["correct-metrics"]["value"], 0.9)
            self.assertEqual(output["failure_tags"], [])
            self.assertEqual(json.loads(judge_result.read_text(encoding="utf-8")), output)
            usage = json.loads((trace_dir / "usage.json").read_text(encoding="utf-8"))
            self.assertEqual(usage["usage"]["total_tokens"], 18)
            self.assertIsInstance(usage["duration_ms"], int)
            self.assertGreaterEqual(usage["duration_ms"], 0)
            self.assertEqual(usage["structured_output_mode"], "schema")
            self.assertTrue((trace_dir / "attempt-01" / "codex-events.jsonl").is_file())

    def test_shared_runtime_normalizes_missing_authentication_error(self) -> None:
        with tempfile.TemporaryDirectory(prefix="model_judge_error_") as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            original_codex_home = root / "original-codex-home"
            original_codex_home.mkdir()
            options = ModelJudgeOptions(
                codex_bin="must-not-run",
                model="fixture-model",
                reasoning_effort="low",
                timeout_seconds=1,
                max_attempts=1,
                retry_delay_seconds=0,
                structured_output="auto",
            )
            with patch.dict(
                os.environ,
                {"CODEX_HOME": str(original_codex_home)},
                clear=False,
            ):
                with self.assertRaisesRegex(ModelJudgeError, "authentication file is missing"):
                    run_blind_model_judge(
                        options=options,
                        prompt="Review the fixture.",
                        workspace=workspace,
                        trace_root=root / "trace",
                        criterion_ids=["criterion"],
                        failure_tags=["domain-tag"],
                    )

    def test_production_registry_resolves_data_analysis_job(self) -> None:
        case = validate_case(CASE_DIR, ROOT)
        registry = load_judge_registry(ROOT / "evals" / "judges" / "registry.json", ROOT)
        adapter = resolve_case_judge_adapter(case, registry)
        self.assertIsNotNone(adapter)
        assert adapter is not None
        self.assertEqual(adapter.id, "data-analysis")
        self.assertIn("analyze-tabular-data", adapter.jobs)

    def test_shared_model_schema_is_derived_from_raw_result_contract(self) -> None:
        schema = judge_output_schema(["criterion"], ["domain-tag"])
        score = schema["properties"]["scores"]["items"]
        self.assertEqual(score["properties"]["criterion_id"]["enum"], ["criterion"])
        self.assertIn("passed", score["required"])
        self.assertEqual(score["properties"]["evidence"]["minItems"], 1)
        self.assertEqual(
            schema["properties"]["failure_tags"]["items"]["enum"],
            ["domain-tag"],
        )

    def test_shared_model_schema_supports_an_empty_failure_taxonomy(self) -> None:
        schema = judge_output_schema(["criterion"], [])
        failure_tags = schema["properties"]["failure_tags"]
        self.assertEqual(failure_tags["maxItems"], 0)
        self.assertNotIn("enum", failure_tags["items"])

    def test_shared_runtime_rejects_duplicate_model_criteria(self) -> None:
        duplicate = {
            "scores": [
                {
                    "criterion_id": "first",
                    "value": 0.9,
                    "passed": True,
                    "rationale": "Fixture score.",
                    "evidence": ["fixture"],
                },
                {
                    "criterion_id": "first",
                    "value": 0.8,
                    "passed": True,
                    "rationale": "Duplicate fixture score.",
                    "evidence": ["fixture"],
                },
            ],
            "failure_tags": [],
            "summary": "Invalid duplicate judgment.",
        }
        with self.assertRaisesRegex(ModelJudgeError, "more than once"):
            validate_model_judgment(duplicate, ["first", "second"], [])


if __name__ == "__main__":
    unittest.main()
