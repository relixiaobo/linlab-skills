from __future__ import annotations

import hashlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from evals.judges.presentation_judge_adapter import (
    JudgeError,
    apply_deterministic_overrides,
    build_asset_match_report,
    is_renderer_infrastructure_failure,
    is_transient_codex_failure,
    resolve_structured_output_mode,
    slide_count_bounds,
)


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


class PresentationJudgeTests(unittest.TestCase):
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
