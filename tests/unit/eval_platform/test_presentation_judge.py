from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from evals.judges.presentation_judge_adapter import (
    JudgeError,
    apply_deterministic_overrides,
    build_asset_match_report,
    build_precision_edit_report,
    is_renderer_infrastructure_failure,
    is_transient_codex_failure,
    resolve_structured_output_mode,
    slide_count_bounds,
)


ROOT = Path(__file__).resolve().parents[3]


def oracle() -> dict:
    ids = [
        "correct-route",
        "source-fidelity",
        "visual-plan",
        "image-relevance",
        "image-fit",
        "editable-deliverable",
        "rendered-verification",
    ]
    return {
        "expected": {
            "route": {"acceptable_primary_skills": ["presentation"]},
            "outcomes": [
                {
                    "id": item,
                    "critical": item in {"correct-route", "image-fit"},
                    "description": (
                        "Deliver an editable PPTX with 9-11 coherent slides."
                        if item == "editable-deliverable"
                        else "fixture criterion"
                    ),
                }
                for item in ids
            ],
        }
    }


def judgment() -> dict:
    return {
        "scores": [
            {
                "criterion_id": item["id"],
                "value": 0.9,
                "passed": True,
                "rationale": "model score",
                "evidence": [],
            }
            for item in oracle()["expected"]["outcomes"]
        ],
        "failure_tags": [],
        "summary": "fixture",
    }


def precision_oracle() -> dict:
    path = ROOT / "evals/cases/edit-board-deck-subtitle/oracle.yaml"
    return json.loads(path.read_text(encoding="utf-8"))


def precision_judgment() -> dict:
    return {
        "scores": [
            {
                "criterion_id": item["id"],
                "value": 0.9,
                "passed": True,
                "rationale": "model score",
                "evidence": [],
            }
            for item in precision_oracle()["expected"]["outcomes"]
        ],
        "failure_tags": [],
        "summary": "fixture",
    }


def write_precision_manifest(path: Path, source_sha256: str) -> None:
    path.write_text(
        json.dumps(
            {
                "taskContract": "surgeon",
                "sourceArtifact": {
                    "path": "input/board_deck.pptx",
                    "sha256": source_sha256,
                    "slideCount": 10,
                },
                "outputArtifact": "edited.pptx",
                "request": "Change one slide 7 subtitle.",
                "preservation": {
                    "policy": "preserve-everything-except-listed-operations",
                    "verificationScopes": [
                        "package-parts",
                        "slide-structure",
                        "content",
                        "style",
                        "geometry",
                        "relationships",
                        "timing",
                        "metadata",
                    ],
                },
                "operations": [
                    {
                        "id": "slide7-subtitle",
                        "action": "replace-text",
                        "target": {
                            "slidePart": "ppt/slides/slide7.xml",
                            "textMatch": "Q3 pipeline",
                            "expectedMatchCount": 1,
                            "matchPolicy": "exactly-one",
                        },
                        "changeField": "object-content",
                        "property": "a:t text",
                        "expectedBefore": "Q3 pipeline",
                        "intendedAfter": "Q4 pipeline",
                        "requestedChange": "Replace the target subtitle.",
                    }
                ],
                "allowedPackageParts": [
                    {
                        "part": "ppt/slides/slide7.xml",
                        "reason": "Contains the target subtitle.",
                        "operationIds": ["slide7-subtitle"],
                    }
                ],
                "acceptanceChecks": ["Only the declared target changes."],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


class PresentationJudgeTests(unittest.TestCase):
    def test_precision_edit_report_proves_one_package_part_change(self) -> None:
        source_fixture = ROOT / "evals/cases/edit-board-deck-subtitle/input/board_deck.pptx"
        with TemporaryDirectory(prefix="precision_edit_") as temp:
            temporary = Path(temp)
            payload = temporary / "payload"
            input_dir = payload / "input"
            evidence = temporary / "evidence"
            output_dir = temporary / "output"
            input_dir.mkdir(parents=True)
            evidence.mkdir()
            output_dir.mkdir()
            source = input_dir / "board_deck.pptx"
            edited = output_dir / "edited.pptx"
            shutil.copy2(source_fixture, source)

            with zipfile.ZipFile(source) as before, zipfile.ZipFile(edited, "w") as after:
                for info in before.infolist():
                    data = before.read(info.filename)
                    if info.filename == "ppt/slides/slide7.xml":
                        data = data.replace(b"Q3 pipeline", b"Q4 pipeline")
                    after.writestr(info, data)
            write_precision_manifest(
                output_dir / "edit-manifest.json",
                hashlib.sha256(source.read_bytes()).hexdigest(),
            )

            inspect = subprocess.run(
                [
                    "python3",
                    str(ROOT / "skills/presentation/scripts/pptx_tool.py"),
                    "inspect",
                    str(edited),
                    "--out",
                    str(evidence / "pptx-inspect.json"),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(inspect.returncode, 0, inspect.stderr or inspect.stdout)

            report = build_precision_edit_report(
                oracle=precision_oracle(),
                payload_dir=payload,
                output_dir=output_dir,
                edited_pptx=edited,
                evidence_dir=evidence,
            )
            self.assertTrue(report["configured"])
            self.assertEqual(report["target_counts"]["source_before"], 1)
            self.assertEqual(report["target_counts"]["edited_after"], 1)
            self.assertTrue(report["checks"]["exact_target"])
            self.assertTrue(report["checks"]["normalized_target_matches"])
            self.assertTrue(report["checks"]["package_scope_passed"])
            self.assertTrue(report["checks"]["semantic_preservation_passed"])
            self.assertTrue(report["checks"]["final_gate_passed"])
            self.assertTrue(report["checks"]["reports_complete"])
            self.assertTrue(report["checks"]["edit_manifest_passed"])
            self.assertTrue(report["edit_manifest"]["schema_valid"])
            self.assertTrue(report["edit_manifest"]["matches_expectations"])

    def test_precision_edit_failures_are_deterministic_vetoes(self) -> None:
        output = apply_deterministic_overrides(
            precision_judgment(),
            oracle=precision_oracle(),
            result={"route": {"primary_skill": "presentation"}},
            inspect={
                "ok": True,
                "slides": [{} for _ in range(10)],
                "notes_count": 10,
                "image_aspect_distortions": [],
                "severe_image_resolution_warnings": [],
                "missing_image_dimensions": [],
            },
            commands={"inspect_exit": 0, "render_exit": 0},
            precision_edit={
                "configured": True,
                "checks": {
                    "exact_target": False,
                    "package_scope_passed": False,
                    "semantic_preservation_passed": False,
                    "reports_complete": False,
                    "edit_manifest_passed": False,
                    "final_gate_passed": False,
                },
            },
        )
        scores = {item["criterion_id"]: item for item in output["scores"]}
        self.assertEqual(scores["exact-target"]["value"], 0.0)
        self.assertEqual(scores["package-scope"]["value"], 0.0)
        self.assertEqual(scores["semantic-preservation"]["value"], 0.0)
        self.assertEqual(scores["verification-evidence"]["value"], 0.0)
        self.assertEqual(scores["editable-deliverable"]["value"], 0.25)
        self.assertIn("target-mismatch", output["failure_tags"])
        self.assertIn("scope-violation", output["failure_tags"])
        self.assertIn("semantic-regression", output["failure_tags"])

    def test_asset_match_report_joins_source_hashes_to_pptx_media(self) -> None:
        with TemporaryDirectory(prefix="asset_match_") as temp:
            payload = Path(temp)
            source_dir = payload / "input" / "assets"
            source_dir.mkdir(parents=True)
            required = source_dir / "required.png"
            forbidden = source_dir / "forbidden.png"
            required.write_bytes(b"required-image")
            forbidden.write_bytes(b"forbidden-image")
            required_sha = hashlib.sha256(required.read_bytes()).hexdigest()
            report = build_asset_match_report(
                oracle={
                    "metadata": {
                        "presentation_asset_expectations": {
                            "required": [
                                {
                                    "path": "input/assets/required.png",
                                    "treatment": "contain",
                                    "max_cropped_fraction": 0.0,
                                }
                            ],
                            "forbidden": ["input/assets/forbidden.png"],
                        }
                    }
                },
                payload_dir=payload,
                inspect={
                    "slides": [
                        {
                            "index": 2,
                            "pictures": [
                                {
                                    "order": 3,
                                    "target": "ppt/media/image1.png",
                                    "image": {"sha256": required_sha},
                                    "visible_fraction": {"cropped": 0.0},
                                }
                            ],
                        }
                    ]
                },
            )
            self.assertTrue(report["configured"])
            self.assertEqual(report["required"][0]["matched_uses"], 1)
            self.assertEqual(report["required"][0]["matches"][0]["slide"], 2)
            self.assertEqual(report["forbidden"][0]["matched_uses"], 0)

    def test_custom_provider_uses_prompt_json_mode_by_default(self) -> None:
        self.assertEqual(resolve_structured_output_mode("custom", "auto"), "prompt")
        self.assertEqual(resolve_structured_output_mode("openai", "auto"), "schema")
        self.assertEqual(resolve_structured_output_mode("custom", "schema"), "schema")

    def test_macos_library_policy_is_a_renderer_infrastructure_failure(self) -> None:
        self.assertTrue(
            is_renderer_infrastructure_failure(
                "Library load denied by system policy because code signature is invalid"
            )
        )
        self.assertFalse(is_renderer_infrastructure_failure("PPTX conversion rejected input"))

    def test_transient_provider_failures_are_retryable(self) -> None:
        self.assertTrue(is_transient_codex_failure(1, "502 Bad Gateway", ""))
        self.assertTrue(is_transient_codex_failure(124, "", "timed out"))
        self.assertFalse(is_transient_codex_failure(1, "schema validation failed", ""))

    def test_route_and_image_distortion_are_deterministic_vetoes(self) -> None:
        result = {"route": {"primary_skill": None}}
        inspect = {
            "ok": True,
            "slides": [{} for _ in range(10)],
            "notes_count": 10,
            "image_aspect_distortions": [{"slide": 2}],
            "severe_image_resolution_warnings": [],
            "missing_image_dimensions": [],
        }
        output = apply_deterministic_overrides(
            judgment(),
            oracle=oracle(),
            result=result,
            inspect=inspect,
            commands={"inspect_exit": 0, "render_exit": 0},
        )
        scores = {item["criterion_id"]: item for item in output["scores"]}
        self.assertEqual(scores["correct-route"]["value"], 0.0)
        self.assertFalse(scores["correct-route"]["passed"])
        self.assertEqual(scores["image-fit"]["value"], 0.0)
        self.assertFalse(scores["image-fit"]["passed"])
        self.assertIn("route-error", output["failure_tags"])
        self.assertIn("image-distortion", output["failure_tags"])

    def test_required_and_forbidden_asset_rules_cap_image_relevance(self) -> None:
        clean_inspect = {
            "ok": True,
            "slides": [{} for _ in range(10)],
            "notes_count": 10,
            "image_aspect_distortions": [],
            "severe_image_resolution_warnings": [],
            "missing_image_dimensions": [],
        }
        output = apply_deterministic_overrides(
            judgment(),
            oracle=oracle(),
            result={"route": {"primary_skill": "presentation"}},
            inspect=clean_inspect,
            commands={"inspect_exit": 0, "render_exit": 0},
            asset_matches={
                "configured": True,
                "required": [
                    {"path": "input/required.png", "matched_uses": 0, "matches": []}
                ],
                "forbidden": [
                    {"path": "input/forbidden.png", "matched_uses": 1, "matches": [{}]}
                ],
            },
        )
        scores = {item["criterion_id"]: item for item in output["scores"]}
        self.assertEqual(scores["image-relevance"]["value"], 0.0)
        self.assertFalse(scores["image-relevance"]["passed"])
        self.assertIn("image-relevance", output["failure_tags"])

    def test_slide_count_and_missing_notes_cap_editability(self) -> None:
        result = {"route": {"primary_skill": "presentation"}}
        inspect = {
            "ok": True,
            "slides": [{} for _ in range(7)],
            "notes_count": 2,
            "image_aspect_distortions": [],
            "severe_image_resolution_warnings": [],
            "missing_image_dimensions": [],
        }
        output = apply_deterministic_overrides(
            judgment(),
            oracle=oracle(),
            result=result,
            inspect=inspect,
            commands={"inspect_exit": 0, "render_exit": 0},
        )
        scores = {item["criterion_id"]: item for item in output["scores"]}
        self.assertEqual(scores["editable-deliverable"]["value"], 0.5)
        self.assertFalse(scores["editable-deliverable"]["passed"])

    def test_case_specific_slide_range_accepts_eight_slides(self) -> None:
        case_oracle = oracle()
        editable = next(
            item
            for item in case_oracle["expected"]["outcomes"]
            if item["id"] == "editable-deliverable"
        )
        editable["description"] = (
            "Deliver an editable PPTX with 8-10 coherent slides and speaker notes."
        )
        output = apply_deterministic_overrides(
            judgment(),
            oracle=case_oracle,
            result={"route": {"primary_skill": "presentation"}},
            inspect={
                "ok": True,
                "slides": [{} for _ in range(8)],
                "notes_count": 8,
                "image_aspect_distortions": [],
                "severe_image_resolution_warnings": [],
                "missing_image_dimensions": [],
            },
            commands={"inspect_exit": 0, "render_exit": 0},
        )
        scores = {item["criterion_id"]: item for item in output["scores"]}
        self.assertEqual(scores["editable-deliverable"]["value"], 0.9)
        self.assertTrue(scores["editable-deliverable"]["passed"])

    def test_structured_slide_range_overrides_description_fallback(self) -> None:
        case_oracle = oracle()
        case_oracle["evaluation"] = {
            "config": {"slide_count": {"minimum": 8, "maximum": 10}}
        }
        self.assertEqual(slide_count_bounds(case_oracle), (8, 10))

    def test_missing_slide_range_does_not_apply_a_global_default(self) -> None:
        case_oracle = oracle()
        editable = next(
            item
            for item in case_oracle["expected"]["outcomes"]
            if item["id"] == "editable-deliverable"
        )
        editable["description"] = "Deliver an editable presentation with notes."
        output = apply_deterministic_overrides(
            judgment(),
            oracle=case_oracle,
            result={"route": {"primary_skill": "presentation"}},
            inspect={
                "ok": True,
                "slides": [{} for _ in range(7)],
                "notes_count": 7,
                "image_aspect_distortions": [],
                "severe_image_resolution_warnings": [],
                "missing_image_dimensions": [],
            },
            commands={"inspect_exit": 0, "render_exit": 0},
        )
        scores = {item["criterion_id"]: item for item in output["scores"]}
        self.assertEqual(scores["editable-deliverable"]["value"], 0.9)

    def test_invalid_structured_slide_range_is_rejected(self) -> None:
        case_oracle = oracle()
        case_oracle["evaluation"] = {
            "config": {"slide_count": {"minimum": 11, "maximum": 9}}
        }
        with self.assertRaisesRegex(JudgeError, "positive integer minimum/maximum"):
            slide_count_bounds(case_oracle)


if __name__ == "__main__":
    unittest.main()
