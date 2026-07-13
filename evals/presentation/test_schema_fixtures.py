#!/usr/bin/env python3

import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
ROOT = REPO / "presentation"
SCHEMAS = ROOT / "assets" / "schemas"
FIXTURES = Path(__file__).resolve().parent / "schema-fixtures"


def run_ajv(command, schema, data=None):
    args = [
        "npx",
        "-y",
        "ajv-cli@5",
        command,
        "--strict=false",
        "--spec=draft2020",
        "-s",
        str(schema),
    ]
    if data is not None:
        args.extend(["-d", str(data)])
    return subprocess.run(args, cwd=REPO, capture_output=True, text=True)


class SchemaFixtureTests(unittest.TestCase):
    def assert_valid(self, schema, data):
        result = run_ajv("validate", schema, data)
        self.assertEqual(
            result.returncode,
            0,
            msg=f"Expected valid: {data}\n{result.stdout}\n{result.stderr}",
        )

    def assert_invalid(self, schema, data, expected_text):
        result = run_ajv("validate", schema, data)
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, msg=f"Unexpectedly valid: {data}")
        self.assertIn(expected_text, output)

    def assert_payload_invalid(self, name, schema_name, payload, expected_text):
        with tempfile.TemporaryDirectory() as directory:
            data_path = Path(directory) / f"{name}.json"
            data_path.write_text(json.dumps(payload, indent=2) + "\n")
            self.assert_invalid(SCHEMAS / schema_name, data_path, expected_text)

    def test_all_schemas_compile(self):
        result = run_ajv("compile", SCHEMAS / "*.schema.json")
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)

    def test_committed_valid_fixtures(self):
        cases = [
            ("studio-brief.schema.json", "studio-brief.constrained.json"),
            ("studio-brief.schema.json", "studio-brief.unconstrained.json"),
            ("edit-manifest.schema.json", "edit-manifest.json"),
            ("preservation-matrix.schema.json", "preservation-matrix.json"),
            ("verification-report.schema.json", "verification-report.studio-constrained.json"),
            ("verification-report.schema.json", "verification-report.studio-unconstrained.json"),
            ("verification-report.schema.json", "verification-report.surgeon.json"),
        ]
        for schema_name, fixture_name in cases:
            with self.subTest(fixture=fixture_name):
                self.assert_valid(
                    SCHEMAS / schema_name,
                    FIXTURES / "valid" / fixture_name,
                )

        template = ROOT / "assets" / "templates" / "html-studio"
        self.assert_valid(
            SCHEMAS / "studio-config.schema.json",
            template / "studio.config.json",
        )
        self.assert_valid(
            SCHEMAS / "evidence-ledger.schema.json",
            template / "evidence-ledger.json",
        )

    def test_committed_invalid_fixtures(self):
        cases = [
            (
                "edit-manifest.schema.json",
                "edit-manifest.exactly-one-count-two.json",
                "expectedMatchCount",
            ),
            (
                "verification-report.schema.json",
                "verification-report.studio-concept-only-passed.json",
                "/aestheticGate/stage",
            ),
            (
                "verification-report.schema.json",
                "verification-report.studio-constrained-missing-semantic-review-passed.json",
                "semanticReview",
            ),
            (
                "verification-report.schema.json",
                "verification-report.surgeon-failed-diffs-passed.json",
                "/accuracyGate/packageDiff/status",
            ),
        ]
        for schema_name, fixture_name, expected_text in cases:
            with self.subTest(fixture=fixture_name):
                self.assert_invalid(
                    SCHEMAS / schema_name,
                    FIXTURES / "invalid" / fixture_name,
                    expected_text,
                )

    def test_final_pass_bypass_mutations_are_rejected(self):
        controlled = json.loads(
            (FIXTURES / "valid" / "verification-report.studio-constrained.json").read_text()
        )
        creative = json.loads(
            (FIXTURES / "valid" / "verification-report.studio-unconstrained.json").read_text()
        )
        precision = json.loads(
            (FIXTURES / "valid" / "verification-report.surgeon.json").read_text()
        )

        mutations = []

        missing_baseline = copy.deepcopy(controlled)
        del missing_baseline["technicalGate"]["baselineArtifact"]
        mutations.append(("accepted-missing-baseline", missing_baseline, "baselineArtifact"))

        missing_acceptance = copy.deepcopy(controlled)
        del missing_acceptance["technicalGate"]["baselineAcceptanceRef"]
        mutations.append(
            ("accepted-missing-acceptance", missing_acceptance, "baselineAcceptanceRef")
        )

        missing_regression_evidence = copy.deepcopy(controlled)
        del missing_regression_evidence["technicalGate"]["regressionEvidence"]
        mutations.append(
            (
                "accepted-missing-regression-evidence",
                missing_regression_evidence,
                "regressionEvidence",
            )
        )

        new_regression = copy.deepcopy(controlled)
        new_regression["technicalGate"]["newRegressions"] = 1
        mutations.append(
            ("accepted-new-regression", new_regression, "/technicalGate/newRegressions")
        )

        failed_visual_sanity = copy.deepcopy(precision)
        failed_visual_sanity["accuracyGate"]["visualSanity"]["status"] = "failed"
        mutations.append(
            ("precision-failed-visual-sanity", failed_visual_sanity, "/accuracyGate/visualSanity")
        )

        failed_deliverable = copy.deepcopy(creative)
        failed_deliverable["deliverables"]["pptx"]["status"] = "failed"
        mutations.append(("failed-deliverable", failed_deliverable, "/deliverables/pptx/status"))

        failed_editability = copy.deepcopy(creative)
        failed_editability["pptxEditability"]["status"] = "failed"
        mutations.append(("failed-editability", failed_editability, "/pptxEditability/status"))

        failed_notes = copy.deepcopy(creative)
        failed_notes["pptxEditability"]["notesStatus"] = "failed"
        mutations.append(("failed-notes", failed_notes, "/pptxEditability/notesStatus"))

        warning_links = copy.deepcopy(creative)
        warning_links["pptxEditability"]["hyperlinksStatus"] = "warning"
        mutations.append(("warning-links", warning_links, "/pptxEditability/hyperlinksStatus"))

        missing_editability = copy.deepcopy(creative)
        del missing_editability["pptxEditability"]
        mutations.append(("missing-editability", missing_editability, "pptxEditability"))

        open_error = copy.deepcopy(creative)
        open_error["issues"] = [
            {
                "gate": "accuracy",
                "severity": "error",
                "description": "Unresolved mismatch",
                "status": "open",
            }
        ]
        mutations.append(("passed-with-open-error", open_error, "/issues"))

        empty_evidence = copy.deepcopy(creative)
        empty_evidence["deliveryEvidence"] = []
        mutations.append(("passed-with-empty-evidence", empty_evidence, "/deliveryEvidence"))

        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            for name, payload, expected_text in mutations:
                data_path = directory / f"{name}.json"
                data_path.write_text(json.dumps(payload, indent=2) + "\n")
                with self.subTest(mutation=name):
                    self.assert_invalid(
                        SCHEMAS / "verification-report.schema.json",
                        data_path,
                        expected_text,
                    )

    def test_direction_and_layout_decision_rules_are_enforced(self):
        creative = json.loads(
            (FIXTURES / "valid" / "studio-brief.unconstrained.json").read_text()
        )
        controlled = json.loads(
            (FIXTURES / "valid" / "studio-brief.constrained.json").read_text()
        )

        library_without_id = copy.deepcopy(creative)
        del library_without_id["visualDirection"]["themeDecision"]["themeId"]

        user_selection_without_ref = copy.deepcopy(creative)
        user_selection_without_ref["visualDirection"]["decisionMode"] = "user-selected"

        reference_without_source = copy.deepcopy(controlled)
        del reference_without_source["visualDirection"]["themeDecision"]["sourceRefs"]

        narrative_library_without_id = copy.deepcopy(creative)
        del narrative_library_without_id["narrativeDirection"]["archetypeId"]

        narrative_reference_without_source = copy.deepcopy(controlled)
        del narrative_reference_without_source["narrativeDirection"]["sourceRefs"]

        layout_without_core_set = copy.deepcopy(creative)
        layout_without_core_set["layoutStrategy"]["coreLayoutIds"] = ["cover"]

        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            cases = [
                ("library-without-id.json", library_without_id, "themeId"),
                ("user-selection-without-ref.json", user_selection_without_ref, "userDecisionRef"),
                ("reference-without-source.json", reference_without_source, "sourceRefs"),
                ("narrative-library-without-id.json", narrative_library_without_id, "archetypeId"),
                ("narrative-reference-without-source.json", narrative_reference_without_source, "sourceRefs"),
                ("layout-without-core-set.json", layout_without_core_set, "/layoutStrategy/coreLayoutIds"),
            ]
            for filename, payload, expected_text in cases:
                data_path = directory / filename
                data_path.write_text(json.dumps(payload, indent=2) + "\n")
                with self.subTest(fixture=filename):
                    self.assert_invalid(
                        SCHEMAS / "studio-brief.schema.json",
                        data_path,
                        expected_text,
                    )

    def test_contract_semantic_mutations_are_rejected(self):
        full_brief = json.loads(
            (FIXTURES / "valid" / "studio-brief.unconstrained.json").read_text()
        )
        controlled_brief = json.loads(
            (FIXTURES / "valid" / "studio-brief.constrained.json").read_text()
        )
        controlled_report = json.loads(
            (FIXTURES / "valid" / "verification-report.studio-constrained.json").read_text()
        )
        creative_report = json.loads(
            (FIXTURES / "valid" / "verification-report.studio-unconstrained.json").read_text()
        )
        precision_report = json.loads(
            (FIXTURES / "valid" / "verification-report.surgeon.json").read_text()
        )
        manifest = json.loads((FIXTURES / "valid" / "edit-manifest.json").read_text())

        cases = []

        brief_without_mode = copy.deepcopy(full_brief)
        del brief_without_mode["studioMode"]
        cases.append(("brief-without-mode", "studio-brief.schema.json", brief_without_mode, "studioMode"))

        report_without_mode = copy.deepcopy(creative_report)
        del report_without_mode["studioMode"]
        cases.append(("report-without-mode", "verification-report.schema.json", report_without_mode, "studioMode"))

        surgeon_with_mode = copy.deepcopy(precision_report)
        surgeon_with_mode["studioMode"] = "unconstrained"
        cases.append(("surgeon-with-mode", "verification-report.schema.json", surgeon_with_mode, "must NOT be valid"))

        brief_without_html = copy.deepcopy(full_brief)
        brief_without_html["delivery"]["deliverables"] = ["pptx", "pdf"]
        cases.append(("brief-without-html", "studio-brief.schema.json", brief_without_html, "/delivery/deliverables"))

        brief_with_backend = copy.deepcopy(full_brief)
        brief_with_backend["delivery"]["productionBackend"] = "native-pptx"
        cases.append(("brief-with-backend", "studio-brief.schema.json", brief_with_backend, "additionalProperties"))

        report_without_html = copy.deepcopy(creative_report)
        del report_without_html["deliverables"]["html"]
        cases.append(("report-without-html", "verification-report.schema.json", report_without_html, "/deliverables"))

        unknown_format = copy.deepcopy(creative_report)
        unknown_format["deliverables"]["powerpoint"] = {
            "artifact": "output/duplicate.pptx",
            "status": "passed",
            "evidence": ["verification/unknown-format.json"],
        }
        cases.append(("unknown-deliverable-format", "verification-report.schema.json", unknown_format, "/deliverables"))

        irrelevant_reference = copy.deepcopy(creative_report)
        irrelevant_reference["references"]["editManifestRef"] = "contracts/edit-manifest.json"
        cases.append(("irrelevant-reference", "verification-report.schema.json", irrelevant_reference, "/references"))

        missing_visual_comparison = copy.deepcopy(creative_report)
        del missing_visual_comparison["deliverables"]["pptx"]["visualComparisonRef"]
        cases.append(("missing-visual-comparison", "verification-report.schema.json", missing_visual_comparison, "visualComparisonRef"))

        html_only_with_editability = copy.deepcopy(creative_report)
        html_only_with_editability["deliverables"] = {
            "html": html_only_with_editability["deliverables"]["html"]
        }
        cases.append(("html-only-with-editability", "verification-report.schema.json", html_only_with_editability, "must NOT be valid"))

        wrong_extension = copy.deepcopy(creative_report)
        wrong_extension["deliverables"]["pdf"]["artifact"] = "output/strategy-deck.pptx"
        cases.append(("wrong-deliverable-extension", "verification-report.schema.json", wrong_extension, "/deliverables/pdf/artifact"))

        incomplete_render = copy.deepcopy(creative_report)
        incomplete_render["aestheticGate"]["renderCoverage"].update(
            {"renderedSlides": 11, "missingSlides": 1, "complete": False}
        )
        cases.append(("incomplete-render", "verification-report.schema.json", incomplete_render, "/aestheticGate/renderCoverage"))

        zero_expected_matches = copy.deepcopy(precision_report)
        zero_expected_matches["accuracyGate"]["targetAssertions"][0]["expectedMatchCount"] = 0
        cases.append(("zero-expected-matches", "verification-report.schema.json", zero_expected_matches, "/accuracyGate/targetAssertions/0/expectedMatchCount"))

        bad_preservation_policy = copy.deepcopy(manifest)
        bad_preservation_policy["preservation"]["policy"] = "preserve-most-things"
        cases.append(("bad-preservation-policy", "edit-manifest.schema.json", bad_preservation_policy, "/preservation/policy"))

        missing_core_scope = copy.deepcopy(manifest)
        missing_core_scope["preservation"]["verificationScopes"].remove("geometry")
        cases.append(("missing-core-scope", "edit-manifest.schema.json", missing_core_scope, "/preservation/verificationScopes"))

        operation_side_effects = copy.deepcopy(manifest)
        operation_side_effects["operations"][0]["allowedSideEffects"] = []
        cases.append(("operation-side-effects", "edit-manifest.schema.json", operation_side_effects, "/operations/0"))

        mismatched_canonical_action = copy.deepcopy(manifest)
        mismatched_canonical_action["operations"][0]["changeField"] = "geometry"
        cases.append(("mismatched-canonical-action", "edit-manifest.schema.json", mismatched_canonical_action, "/operations/0/changeField"))

        controlled_second_authority = copy.deepcopy(controlled_brief)
        controlled_second_authority["contentGuardrails"] = copy.deepcopy(full_brief["contentGuardrails"])
        cases.append(("controlled-second-authority", "studio-brief.schema.json", controlled_second_authority, "must NOT be valid"))

        creative_missing_guardrails = copy.deepcopy(full_brief)
        del creative_missing_guardrails["contentGuardrails"]
        cases.append(("creative-missing-guardrails", "studio-brief.schema.json", creative_missing_guardrails, "contentGuardrails"))

        controlled_report_exceptions = copy.deepcopy(controlled_report)
        controlled_report_exceptions["accuracyGate"]["approvedExceptions"] = [
            "contracts/preservation-matrix.json#/approvedExceptions/0"
        ]
        cases.append(("controlled-report-exceptions", "verification-report.schema.json", controlled_report_exceptions, "/accuracyGate"))

        missing_direction_preview = copy.deepcopy(full_brief)
        missing_direction_preview["visualDirection"]["previewRefs"] = []
        cases.append(("missing-direction-preview", "studio-brief.schema.json", missing_direction_preview, "/visualDirection/previewRefs"))

        missing_theme_adaptation = copy.deepcopy(full_brief)
        missing_theme_adaptation["visualDirection"]["themeDecision"]["adaptations"] = []
        cases.append(("missing-theme-adaptation", "studio-brief.schema.json", missing_theme_adaptation, "/visualDirection/themeDecision/adaptations"))

        empty_success_criteria = copy.deepcopy(full_brief)
        empty_success_criteria["successCriteria"]["content"] = []
        cases.append(("empty-success-criteria", "studio-brief.schema.json", empty_success_criteria, "/successCriteria/content"))

        empty_sources = copy.deepcopy(full_brief)
        empty_sources["sourceMaterials"] = []
        cases.append(("empty-sources", "studio-brief.schema.json", empty_sources, "/sourceMaterials"))

        matrix = json.loads(
            (FIXTURES / "valid" / "preservation-matrix.json").read_text()
        )
        missing_bindings = copy.deepcopy(matrix)
        del missing_bindings["slideBindings"]
        cases.append(("exact-assignment-missing-bindings", "preservation-matrix.schema.json", missing_bindings, "slideBindings"))

        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            for name, schema_name, payload, expected_text in cases:
                data_path = directory / f"{name}.json"
                data_path.write_text(json.dumps(payload, indent=2) + "\n")
                with self.subTest(case=name):
                    self.assert_invalid(SCHEMAS / schema_name, data_path, expected_text)


if __name__ == "__main__":
    unittest.main()
