from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evals.judges.product_spec_judge_adapter import (
    apply_deterministic_overrides,
    build_artifact_audit,
    missing_artifact_result,
    run_judge,
    run_spec_check,
    validate_config,
)
from evals.runners.eval_lib import (
    load_judge_registry,
    resolve_case_judge_adapter,
    validate_case,
)


ROOT = Path(__file__).resolve().parents[3]
CASE_DIR = ROOT / "evals" / "cases" / "shape-merchant-addon-controls"
GOOD_SPEC = ROOT / "tests" / "fixtures" / "shape-product-spec" / "good_product_spec.md"
FAKE_CODEX = ROOT / "tests" / "fixtures" / "evals" / "fake_codex_judge.py"


def oracle() -> dict:
    return json.loads((CASE_DIR / "oracle.yaml").read_text(encoding="utf-8"))


def config() -> dict:
    return oracle()["evaluation"]["config"]


def result(primary_skill: str | None = "shape-product-spec") -> dict:
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
            {"path": "product-spec.md"},
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
                "evidence": ["artifacts/product-spec.md"],
            }
            for outcome in oracle()["expected"]["outcomes"]
        ],
        "failure_tags": [],
        "summary": "Fixture product-spec judgment.",
    }


def write_good_artifacts(output_dir: Path) -> Path:
    (output_dir / "response.md").write_text(
        "Delivered the decision-ready product specification.\n",
        encoding="utf-8",
    )
    spec_path = output_dir / "product-spec.md"
    shutil.copy2(GOOD_SPEC, spec_path)
    with spec_path.open("a", encoding="utf-8") as handle:
        handle.write(
            "\n### Empty approval queue state\n\n"
            "When there are no pending requests, finance admins see an empty state "
            "that says there are no requests awaiting review.\n"
        )
    return spec_path


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


class ProductSpecJudgeTests(unittest.TestCase):
    def test_case_contract_accepts_complete_product_spec_evidence(self) -> None:
        validate_config(config(), oracle())
        with tempfile.TemporaryDirectory(prefix="product_spec_audit_") as temp:
            root = Path(temp)
            output_dir = root / "output"
            output_dir.mkdir()
            spec_path = write_good_artifacts(output_dir)
            report, check_run = run_spec_check(
                spec_path,
                "product-spec.md",
                root / "evidence",
            )
            audit = build_artifact_audit(
                config(),
                result(),
                spec_path,
                report,
                check_run,
            )

        self.assertTrue(report["ok"])
        self.assertEqual(report["path"], "artifacts/product-spec.md")
        self.assertGreater(audit["artifact"]["bytes"], 0)
        self.assertTrue(
            all(check["passed"] for check in audit["criterion_checks"].values())
        )
        self.assertGreaterEqual(
            report["summary"]["stable_id_counts"]["AC"],
            4,
        )

    def test_deterministic_failures_cap_corresponding_model_scores(self) -> None:
        with tempfile.TemporaryDirectory(prefix="product_spec_caps_") as temp:
            root = Path(temp)
            output_dir = root / "output"
            output_dir.mkdir()
            spec_path = write_good_artifacts(output_dir)
            report, check_run = run_spec_check(
                spec_path,
                "product-spec.md",
                root / "evidence",
            )
            audit = build_artifact_audit(
                config(),
                result(primary_skill=None),
                spec_path,
                report,
                check_run,
            )

        broken = copy.deepcopy(audit)
        for criterion, check in broken["criterion_checks"].items():
            check["passed"] = False
            check["concepts"]["missing"] = [f"missing-{criterion}"]
        broken["spec_check"]["ok"] = False
        broken["spec_check"]["errors"] = ["Duplicate stable IDs found: FR-1."]
        output = apply_deterministic_overrides(
            judgment(),
            oracle=oracle(),
            config=config(),
            result=result(primary_skill=None),
            artifact_audit=broken,
        )
        scores = {item["criterion_id"]: item for item in output["scores"]}
        self.assertEqual(scores["correct-route"]["value"], 0.0)
        self.assertEqual(scores["evidence-fidelity"]["value"], 0.5)
        self.assertEqual(scores["target-options"]["value"], 0.5)
        self.assertEqual(scores["flows-and-states"]["value"], 0.5)
        self.assertEqual(scores["scope-and-open-policy"]["value"], 0.5)
        self.assertEqual(scores["testable-acceptance"]["value"], 0.25)
        self.assertEqual(
            set(output["failure_tags"]),
            {"factuality", "process-compliance", "route-error", "task-understanding"},
        )

    def test_section_warnings_do_not_become_template_vetoes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="product_spec_sections_") as temp:
            root = Path(temp)
            output_dir = root / "output"
            output_dir.mkdir()
            spec_path = write_good_artifacts(output_dir)
            report, check_run = run_spec_check(
                spec_path,
                "product-spec.md",
                root / "evidence",
            )
            report["sections"]["groups"] = {
                group: False for group in report["sections"]["groups"]
            }
            audit = build_artifact_audit(
                config(),
                result(),
                spec_path,
                report,
                check_run,
            )

        self.assertTrue(
            all(check["passed"] for check in audit["criterion_checks"].values())
        )

    def test_missing_artifact_result_preserves_deterministic_route_score(self) -> None:
        output = missing_artifact_result(oracle(), result())
        scores = {item["criterion_id"]: item for item in output["scores"]}
        self.assertEqual(scores["correct-route"]["value"], 1.0)
        self.assertEqual(scores["evidence-fidelity"]["value"], 0.0)
        self.assertIn("missing-artifact", output["failure_tags"])

    def test_run_judge_skips_model_when_product_spec_is_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="product_spec_missing_") as temp:
            root = Path(temp)
            output_dir = root / "output"
            output_dir.mkdir()
            (output_dir / "response.md").write_text(
                "No product spec.\n",
                encoding="utf-8",
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
            self.assertTrue(judge_result.is_file())
            self.assertTrue((evidence_dir / "artifact-audit.json").is_file())
            self.assertFalse((evidence_dir / "spec-check.json").exists())
            self.assertFalse(trace_dir.exists())

    def test_run_judge_exercises_full_blind_model_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="product_spec_model_") as temp:
            root = Path(temp)
            output_dir = root / "output"
            output_dir.mkdir()
            spec_path = write_good_artifacts(output_dir)
            spec_before = spec_path.read_bytes()
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
            with patch.dict(os.environ, env, clear=False):
                output = run_judge(args(str(FAKE_CODEX)))

            scores = {item["criterion_id"]: item for item in output["scores"]}
            self.assertEqual(scores["correct-route"]["value"], 1.0)
            self.assertEqual(scores["evidence-fidelity"]["value"], 0.9)
            self.assertEqual(output["failure_tags"], [])
            self.assertEqual(json.loads(judge_result.read_text(encoding="utf-8")), output)
            self.assertEqual(spec_path.read_bytes(), spec_before)
            self.assertTrue((evidence_dir / "spec-check.json").is_file())
            self.assertTrue((evidence_dir / "artifact-audit.json").is_file())
            usage = json.loads((trace_dir / "usage.json").read_text(encoding="utf-8"))
            self.assertEqual(usage["usage"]["total_tokens"], 18)

    def test_registry_resolves_product_spec_and_suite_requires_judging(self) -> None:
        case = validate_case(CASE_DIR, ROOT)
        registry = load_judge_registry(ROOT / "evals" / "judges" / "registry.json", ROOT)
        adapter = resolve_case_judge_adapter(case, registry)
        self.assertIsNotNone(adapter)
        assert adapter is not None
        self.assertEqual(adapter.id, "product-spec")
        self.assertIn("shape-product-decision", adapter.jobs)
        suite = json.loads(
            (ROOT / "evals" / "suites" / "representative-ab.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertTrue(suite["judging"]["required"])


if __name__ == "__main__":
    unittest.main()
