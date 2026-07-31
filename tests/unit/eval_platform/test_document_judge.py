from __future__ import annotations

import argparse
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evals.judges.document_judge_adapter import (
    apply_deterministic_overrides,
    build_artifact_audit,
    missing_artifact_result,
    prepare_model_workspace,
    run_judge,
    run_markdown_check,
    validate_config,
)
from evals.runners.eval_lib import (
    load_judge_registry,
    resolve_case_judge_adapter,
    validate_case,
)


ROOT = Path(__file__).resolve().parents[3]
CASE_DIR = ROOT / "evals" / "cases" / "create-enterprise-pilot-board-memo"
FAKE_CODEX = ROOT / "tests" / "fixtures" / "evals" / "fake_codex_judge.py"


def oracle() -> dict:
    return json.loads((CASE_DIR / "oracle.yaml").read_text(encoding="utf-8"))


def config() -> dict:
    return oracle()["evaluation"]["config"]


def result(primary_skill: str | None = "document") -> dict:
    return {
        "run_id": "fixture-run",
        "condition": {"id": "document-enabled"},
        "status": "completed",
        "route": {
            "primary_skill": primary_skill,
            "selected_skills": [primary_skill] if primary_skill else [],
        },
        "usage": {},
        "executor": {"model": "fixture-model"},
        "artifacts": [
            {"path": "response.md"},
            {"path": "board-memo.md"},
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
                "evidence": ["artifacts/board-memo.md"],
            }
            for outcome in oracle()["expected"]["outcomes"]
        ],
        "failure_tags": [],
        "summary": "Fixture document judgment.",
    }


def write_good_artifacts(output_dir: Path) -> Path:
    (output_dir / "response.md").write_text(
        "Delivered board-memo.md as the editable source. After approval, convert "
        "that source to Word and inspect the DOCX before handoff.\n",
        encoding="utf-8",
    )
    memo_path = output_dir / "board-memo.md"
    memo_path.write_text(
        """---
title: Enterprise Pilot Decision Memo
audience: Board
status: Draft
version: 1.0
---

# Enterprise Pilot Decision Memo

## Decision Requested

Approve a capped six-month pilot with three enterprise design partners and a
hard exit review after 90 days.

## Recommendation And Guardrails

Authorize the pilot, contingent on named design partners, a 90-day exit review,
and explicit scope control for SSO, audit logs, and admin reporting.

## Evidence

There are 18 current self-serve pilot teams. Seven enterprise teams requested
SSO and audit logs. Estimated work is 6 engineer-weeks for SSO, 3 engineer-weeks
for audit logs, and 2 engineer-weeks for admin reporting. Compliance review adds
$48k of contractor spend.

## Risks And Open Questions

Enterprise controls may delay self-serve onboarding fixes. It remains unknown
which teams are willing to pay during the pilot, what minimum audit log export
is acceptable, and whether legal requires SOC 2 before pilots begin.

## Source Map

All counts, estimates, risks, the recommendation, and open questions come from
`input/board_notes.md` (Board Notes). The approval framing is the memo's synthesis;
it does not resolve any source unknown.

## Predicted Board Reader Questions

- Which teams are willing to pay during the pilot? Unanswered in the source.
- What audit log export is minimally acceptable? Unanswered in the source.
- Does legal require SOC2 before the pilot? Unanswered in the source.
- What is the exit criterion at the 90-day review? Decision still required.
""",
        encoding="utf-8",
    )
    return memo_path


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


class DocumentJudgeTests(unittest.TestCase):
    def test_case_contract_accepts_complete_board_memo(self) -> None:
        validate_config(config(), oracle())
        with tempfile.TemporaryDirectory(prefix="document_audit_") as temp:
            root = Path(temp)
            output_dir = root / "output"
            output_dir.mkdir()
            memo_path = write_good_artifacts(output_dir)
            report, check_run = run_markdown_check(
                memo_path,
                "board-memo.md",
                root / "evidence",
            )
            audit = build_artifact_audit(
                config(),
                result(),
                memo_path,
                report,
                check_run,
            )

        self.assertTrue(report["ok"])
        self.assertEqual(report["file"], "artifacts/board-memo.md")
        self.assertGreater(audit["artifact"]["bytes"], 0)
        self.assertEqual(len(audit["artifact"]["sha256"]), 64)
        self.assertTrue(
            all(
                check["semantic_hints_passed"]
                for check in audit["criterion_checks"].values()
            )
        )
        self.assertTrue(
            audit["criterion_checks"]["reader-readiness"]["structure"][
                "hints_passed"
            ]
        )

    def test_semantic_term_misses_do_not_cap_blind_scores(self) -> None:
        with tempfile.TemporaryDirectory(prefix="document_caps_") as temp:
            root = Path(temp)
            output_dir = root / "output"
            output_dir.mkdir()
            memo_path = write_good_artifacts(output_dir)
            report, check_run = run_markdown_check(
                memo_path,
                "board-memo.md",
                root / "evidence",
            )
            audit = build_artifact_audit(
                config(),
                result(primary_skill=None),
                memo_path,
                report,
                check_run,
            )

        broken = copy.deepcopy(audit)
        for check in broken["criterion_checks"].values():
            check["semantic_hints_passed"] = False
            check["concepts"]["missing"] = ["semantic-review-required"]
        output = apply_deterministic_overrides(
            judgment(),
            oracle=oracle(),
            config=config(),
            result=result(primary_skill=None),
            artifact_audit=broken,
        )
        scores = {item["criterion_id"]: item for item in output["scores"]}
        self.assertEqual(scores["correct-route"]["value"], 0.0)
        for criterion in (
            "decision-recommendation",
            "evidence-fidelity",
            "risk-and-unknowns",
            "source-traceability",
            "reader-readiness",
        ):
            self.assertEqual(scores[criterion]["value"], 0.9)
        self.assertEqual(output["failure_tags"], ["route-error"])

    def test_structure_hints_do_not_veto_but_placeholders_do(self) -> None:
        with tempfile.TemporaryDirectory(prefix="document_structure_") as temp:
            root = Path(temp)
            output_dir = root / "output"
            output_dir.mkdir()
            memo_path = write_good_artifacts(output_dir)
            report, check_run = run_markdown_check(
                memo_path,
                "board-memo.md",
                root / "evidence",
            )
            audit = build_artifact_audit(
                config(),
                result(),
                memo_path,
                report,
                check_run,
            )

        structure = audit["criterion_checks"]["reader-readiness"]["structure"]
        structure["first_heading_is_h1"] = False
        structure["heading_count"] = 1
        structure["heading_count_passed"] = False
        structure["word_count_passed"] = False
        structure["hints_passed"] = False
        hints_only = apply_deterministic_overrides(
            judgment(),
            oracle=oracle(),
            config=config(),
            result=result(),
            artifact_audit=audit,
        )
        hints_score = next(
            item
            for item in hints_only["scores"]
            if item["criterion_id"] == "reader-readiness"
        )
        self.assertEqual(hints_score["value"], 0.9)
        self.assertNotIn("process-compliance", hints_only["failure_tags"])

        structure["placeholder_hits"] = ["todo"]
        structure["placeholder_free"] = False
        output = apply_deterministic_overrides(
            judgment(),
            oracle=oracle(),
            config=config(),
            result=result(),
            artifact_audit=audit,
        )
        score = next(
            item
            for item in output["scores"]
            if item["criterion_id"] == "reader-readiness"
        )
        self.assertEqual(score["value"], 0.5)
        self.assertFalse(score["passed"])
        self.assertIn("process-compliance", output["failure_tags"])
        self.assertIn("Deterministic check", score["rationale"])

    def test_sample_prose_is_only_an_inspection_hint(self) -> None:
        with tempfile.TemporaryDirectory(prefix="document_sample_") as temp:
            root = Path(temp)
            output_dir = root / "output"
            output_dir.mkdir()
            memo_path = write_good_artifacts(output_dir)
            memo_path.write_text(
                memo_path.read_text(encoding="utf-8")
                + "\nThe pilot sample contains the complete invited cohort.\n",
                encoding="utf-8",
            )
            report, check_run = run_markdown_check(
                memo_path,
                "board-memo.md",
                root / "evidence",
            )
            audit = build_artifact_audit(
                config(),
                result(),
                memo_path,
                report,
                check_run,
            )

        self.assertIn("sample", report["placeholder_hits"])
        structure = audit["criterion_checks"]["reader-readiness"]["structure"]
        self.assertEqual(structure["placeholder_hits"], [])
        self.assertTrue(structure["placeholder_free"])
        output = apply_deterministic_overrides(
            judgment(),
            oracle=oracle(),
            config=config(),
            result=result(),
            artifact_audit=audit,
        )
        score = next(
            item
            for item in output["scores"]
            if item["criterion_id"] == "reader-readiness"
        )
        self.assertEqual(score["value"], 0.9)
        self.assertNotIn("process-compliance", output["failure_tags"])

    def test_missing_artifact_result_preserves_deterministic_route_score(self) -> None:
        output = missing_artifact_result(oracle(), result())
        scores = {item["criterion_id"]: item for item in output["scores"]}
        self.assertEqual(scores["correct-route"]["value"], 1.0)
        self.assertEqual(scores["evidence-fidelity"]["value"], 0.0)
        self.assertIn("missing-artifact", output["failure_tags"])

    def test_undeclared_or_broken_artifact_is_a_deterministic_veto(self) -> None:
        with tempfile.TemporaryDirectory(prefix="document_integrity_") as temp:
            root = Path(temp)
            output_dir = root / "output"
            output_dir.mkdir()
            memo_path = write_good_artifacts(output_dir)
            report, check_run = run_markdown_check(
                memo_path,
                "board-memo.md",
                root / "evidence",
            )
            audit = build_artifact_audit(
                config(),
                result(),
                memo_path,
                report,
                check_run,
            )

        audit["artifact"]["declared"] = False
        audit["markdown_check"]["ok"] = False
        audit["markdown_check"]["errors"] = [
            "broken_local_asset_reference_found"
        ]
        output = apply_deterministic_overrides(
            judgment(),
            oracle=oracle(),
            config=config(),
            result=result(),
            artifact_audit=audit,
        )
        score = next(
            item
            for item in output["scores"]
            if item["criterion_id"] == "source-traceability"
        )
        self.assertEqual(score["value"], 0.0)
        self.assertFalse(score["passed"])
        self.assertIn("artifact-audit.json artifact.declared", score["evidence"])
        self.assertIn("markdown-inspect.json errors", score["evidence"])
        self.assertEqual(
            set(output["failure_tags"]),
            {"missing-artifact", "verification"},
        )

    def test_blind_workspace_redacts_paths_and_preserves_common_run_id_text(self) -> None:
        with tempfile.TemporaryDirectory(prefix="document_blind_workspace_") as temp:
            root = Path(temp)
            run_dir = root / "test" / "case" / "document-enabled" / "rep-01"
            payload = run_dir / "payload"
            output_dir = run_dir / "output"
            (payload / "input").mkdir(parents=True)
            output_dir.mkdir()
            (payload / "prompt.md").write_text(
                "Please test the memo.\n", encoding="utf-8"
            )
            (payload / "input" / "board_notes.md").write_text(
                "Test input.\n", encoding="utf-8"
            )
            memo_path = write_good_artifacts(output_dir)
            leaked_path = str(output_dir / "board-memo.md")
            memo_path.write_text(
                memo_path.read_text(encoding="utf-8")
                + f"\nSource map artifact: {leaked_path}\n",
                encoding="utf-8",
            )
            (output_dir / "response.md").write_text(
                f"I tested {leaked_path}.\n", encoding="utf-8"
            )
            evidence_dir = root / "judge-evidence"
            report, check_run = run_markdown_check(
                memo_path,
                "board-memo.md",
                evidence_dir,
            )
            current_result = result()
            current_result["run_id"] = "test"
            audit = build_artifact_audit(
                config(),
                current_result,
                memo_path,
                report,
                check_run,
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
                result=current_result,
                config=config(),
                artifact_audit=audit,
                markdown_report=report,
                trace={"items": [{"text": leaked_path}]},
                evidence_dir=evidence_dir,
            )

            self.assertEqual(
                (workspace / "source" / "prompt.md").read_text(encoding="utf-8"),
                "Please test the memo.\n",
            )
            self.assertIn(
                "I tested agent-output/board-memo.md.",
                (workspace / "agent-response.md").read_text(encoding="utf-8"),
            )
            blind_memo = (
                workspace / "artifacts" / "board-memo.md"
            ).read_text(encoding="utf-8")
            self.assertIn(
                "Source map artifact: agent-output/board-memo.md", blind_memo
            )
            self.assertIn(leaked_path, memo_path.read_text(encoding="utf-8"))
            workspace_bytes = b"\n".join(
                path.read_bytes()
                for path in sorted(workspace.rglob("*"))
                if path.is_file()
            )
            self.assertNotIn(b"document-enabled", workspace_bytes)
            self.assertNotIn(str(run_dir).encode(), workspace_bytes)

    def test_run_judge_skips_model_when_board_memo_is_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="document_missing_") as temp:
            root = Path(temp)
            output_dir = root / "output"
            output_dir.mkdir()
            (output_dir / "response.md").write_text(
                "No board memo.\n",
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
            self.assertFalse((evidence_dir / "markdown-inspect.json").exists())
            self.assertFalse(trace_dir.exists())

    def test_run_judge_exercises_full_blind_model_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="document_model_") as temp:
            root = Path(temp)
            output_dir = root / "output"
            output_dir.mkdir()
            memo_path = write_good_artifacts(output_dir)
            memo_before = memo_path.read_bytes()
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
            self.assertEqual(memo_path.read_bytes(), memo_before)
            self.assertTrue((evidence_dir / "markdown-inspect.json").is_file())
            self.assertTrue((evidence_dir / "artifact-audit.json").is_file())
            usage = json.loads((trace_dir / "usage.json").read_text(encoding="utf-8"))
            self.assertEqual(usage["usage"]["total_tokens"], 18)
            self.assertIsInstance(usage["duration_ms"], int)

    def test_registry_resolves_document_and_suite_requires_judging(self) -> None:
        case = validate_case(CASE_DIR, ROOT)
        registry = load_judge_registry(
            ROOT / "evals" / "judges" / "registry.json", ROOT
        )
        adapter = resolve_case_judge_adapter(case, registry)
        self.assertIsNotNone(adapter)
        assert adapter is not None
        self.assertEqual(adapter.id, "document")
        self.assertEqual(adapter.jobs, ("create-document",))
        suite = json.loads(
            (ROOT / "evals" / "suites" / "document-board-memo-ab.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertTrue(suite["judging"]["required"])
        self.assertEqual(suite["defaults"]["repetitions"], 1)
        legacy = json.loads(
            (
                ROOT
                / "tests"
                / "fixtures"
                / "artifact-skills"
                / "document"
                / "evals.json"
            ).read_text(encoding="utf-8")
        )
        self.assertNotIn(
            "document-board-memo",
            {item["id"] for item in legacy["evals"]},
        )


if __name__ == "__main__":
    unittest.main()
