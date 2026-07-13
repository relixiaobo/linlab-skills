from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
ROOT = REPO / "presentation"
REFERENCES = ROOT / "references"
SCHEMAS = ROOT / "assets" / "schemas"
FIXTURES = Path(__file__).resolve().parent / "schema-fixtures" / "valid"

EXPECTED_REFERENCES = {
    "asset-intake.md",
    "evidence.md",
    "export.md",
    "layout-library.md",
    "narrative-archetypes.md",
    "precision-edit.md",
    "studio.md",
    "theme-library.md",
    "verification.md",
}
LEGACY_REFERENCE_NAMES = {
    "concept-prototype.md",
    "controlled-redesign.md",
    "creative-studio.md",
    "design-patterns.md",
    "editable-pptx.md",
    "html-deck.md",
    "html-to-pptx.md",
    "layout-compiler.md",
    "layout-recipes.md",
    "layout-safety.md",
    "speaker-notes.md",
    "visual-deck-system.md",
    "visual-review.md",
    "workflow.md",
}
REMOVED_SCHEMA_FIELDS = {
    "buildMode",
    "contractRef",
    "deckPlanRef",
    "deliveryGate",
    "diagnostic",
    "exports",
    "layoutIntent",
    "outputFormat",
    "outputRoute",
    "productionBackend",
    "sourceProject",
    "sourceProjectRef",
}
REMOVED_BACKEND_LABELS = {
    "html-css",
    "native-pptx",
    "hybrid-pptx",
    "flattened-pptx",
    "ooxml-patch",
}


def load_schema(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def property_names(value: object) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        properties = value.get("properties")
        if isinstance(properties, dict):
            found.update(str(key) for key in properties)
        for child in value.values():
            found.update(property_names(child))
    elif isinstance(value, list):
        for child in value:
            found.update(property_names(child))
    return found


def resolve_json_pointer(document: object, pointer: str) -> object:
    if not pointer:
        return document
    if not pointer.startswith("/"):
        raise ValueError(f"invalid JSON pointer: {pointer}")

    current = document
    for raw_token in pointer[1:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            current = current[int(token)]
        elif isinstance(current, dict):
            current = current[token]
        else:
            raise KeyError(token)
    return current


class PresentationSkillStructureTests(unittest.TestCase):
    def test_reference_set_is_consolidated_and_links_resolve(self) -> None:
        self.assertFalse((ROOT / "tests").exists())
        self.assertFalse((SCHEMAS / "fixtures").exists())
        actual = {path.name for path in REFERENCES.glob("*.md")}
        self.assertEqual(actual, EXPECTED_REFERENCES)

        markdown_files = [ROOT / "SKILL.md", *sorted(REFERENCES.glob("*.md"))]
        reference_pattern = re.compile(r"`references/([a-z0-9-]+\.md)`")
        for source in markdown_files:
            text = source.read_text(encoding="utf-8")
            for target in reference_pattern.findall(text):
                self.assertIn(target, actual, f"{source.name} references missing {target}")
            for legacy in LEGACY_REFERENCE_NAMES:
                self.assertNotIn(legacy, text, f"{source.name} still references {legacy}")

    def test_schema_taxonomy_has_two_technical_sources(self) -> None:
        self.assertFalse((SCHEMAS / "deck-plan.schema.json").exists())

        brief = load_schema("studio-brief.schema.json")
        manifest = load_schema("edit-manifest.schema.json")
        matrix = load_schema("preservation-matrix.schema.json")
        report = load_schema("verification-report.schema.json")

        self.assertEqual(brief["properties"]["taskContract"]["const"], "studio")
        self.assertEqual(
            set(brief["properties"]["studioMode"]["enum"]),
            {"unconstrained", "constrained"},
        )
        self.assertEqual(manifest["properties"]["taskContract"]["const"], "surgeon")
        self.assertIn("preservation", manifest["properties"])
        self.assertNotIn("invariants", manifest["properties"])
        self.assertEqual(
            manifest["properties"]["preservation"]["properties"]["policy"]["const"],
            "preserve-everything-except-listed-operations",
        )
        self.assertEqual(matrix["properties"]["taskContract"]["const"], "studio")
        self.assertEqual(matrix["properties"]["studioMode"]["const"], "constrained")
        self.assertEqual(
            set(report["properties"]["taskContract"]["enum"]),
            {"studio", "surgeon"},
        )

        brief_delivery = brief["properties"]["delivery"]["properties"]
        self.assertIn("deliverables", brief_delivery)
        self.assertIn("html", brief_delivery["deliverables"]["items"]["enum"])
        self.assertEqual(brief_delivery["deliverables"]["contains"]["const"], "html")
        self.assertIn("pptxEditability", report["properties"])
        self.assertNotIn("artifact", report["properties"])
        self.assertIn("visualDirection", brief["properties"])
        self.assertIn("narrativeDirection", brief["properties"])
        self.assertIn("layoutStrategy", brief["properties"])
        self.assertNotIn("conceptDepth", brief["properties"])
        self.assertNotIn("styleFrames", brief["properties"])
        self.assertNotIn("selection", brief["properties"])

    def test_removed_backend_state_is_absent(self) -> None:
        schemas = [load_schema(path.name) for path in sorted(SCHEMAS.glob("*.schema.json"))]
        all_properties: set[str] = set()
        for schema in schemas:
            all_properties.update(property_names(schema))
        self.assertTrue(REMOVED_SCHEMA_FIELDS.isdisjoint(all_properties))

        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [ROOT / "SKILL.md", *sorted(REFERENCES.glob("*.md"))]
        )
        for label in REMOVED_BACKEND_LABELS:
            self.assertNotIn(label, text)

    def test_final_report_is_final_only(self) -> None:
        report = load_schema("verification-report.schema.json")
        self.assertEqual(report["properties"]["reportStage"]["const"], "final-delivery")
        aesthetic = report["$defs"]["fullDeckAestheticGate"]
        self.assertEqual(aesthetic["properties"]["stage"]["const"], "full-deck")

    def test_canonical_speaker_notes_markup_is_consistent(self) -> None:
        template = (ROOT / "assets" / "templates" / "html-studio" / "deck.html").read_text(
            encoding="utf-8"
        )
        studio_reference = (REFERENCES / "studio.md").read_text(encoding="utf-8")
        export_reference = (REFERENCES / "export.md").read_text(encoding="utf-8")
        self.assertIn('class="speaker-notes"', template)
        self.assertNotIn('class="notes"', template)
        self.assertIn('class="speaker-notes"', studio_reference)
        self.assertIn('class="speaker-notes"', export_reference)

    def test_studio_tool_template_and_catalogs_are_executable(self) -> None:
        self.assertTrue((ROOT / "scripts" / "studio_tool.mjs").is_file())
        self.assertTrue((ROOT / "scripts" / "render_theme_previews.mjs").is_file())
        template = ROOT / "assets" / "templates" / "html-studio"
        for name in (
            "deck.html",
            "studio.config.json",
            "evidence-ledger.json",
            "package.json",
            "studio.mjs",
            "styles/studio.css",
        ):
            self.assertTrue((template / name).is_file(), name)

        theme_index = json.loads((ROOT / "assets" / "themes" / "index.json").read_text())
        self.assertEqual(
            {theme["id"] for theme in theme_index["themes"]},
            {
                "analytical-ledger",
                "dark-technology",
                "expressive-neo-grid",
                "institutional-editorial",
                "modern-swiss",
                "photo-editorial",
                "soft-humanist",
                "stage-keynote",
                "technical-blueprint",
            },
        )
        theme_ids = {theme["id"] for theme in theme_index["themes"]}
        for theme in theme_index["themes"]:
            self.assertIn("energy", theme)
            self.assertIn("density", theme)
            self.assertIn("assetBias", theme)
            directory = ROOT / "assets" / "themes" / theme["id"]
            for name in ("tokens.css", "design.md", "preview.webp"):
                self.assertTrue((directory / name).is_file(), f"{theme['id']}/{name}")

        archetype_index = json.loads(
            (ROOT / "assets" / "archetypes" / "index.json").read_text()
        )
        layout_index = json.loads(
            (ROOT / "assets" / "layouts" / "index.json").read_text()
        )
        archetype_ids = {item["id"] for item in archetype_index["archetypes"]}
        layout_ids = {item["id"] for item in layout_index["layouts"]}
        self.assertEqual(len(archetype_ids), 7)
        self.assertEqual(len(layout_ids), 20)
        self.assertIn("research-report", archetype_ids)
        self.assertIn("custom-composition", layout_ids)
        for archetype in archetype_index["archetypes"]:
            self.assertTrue(set(archetype["defaultThemeIds"]).issubset(theme_ids))
            for phase in archetype["sequence"]:
                self.assertTrue(set(phase["layoutIds"]).issubset(layout_ids))

    def test_route_bundles_match_deliverables_and_sources(self) -> None:
        creative_brief = json.loads((FIXTURES / "studio-brief.unconstrained.json").read_text())
        creative_report = json.loads(
            (FIXTURES / "verification-report.studio-unconstrained.json").read_text()
        )
        controlled_brief = json.loads(
            (FIXTURES / "studio-brief.constrained.json").read_text()
        )
        controlled_report = json.loads(
            (FIXTURES / "verification-report.studio-constrained.json").read_text()
        )
        manifest = json.loads((FIXTURES / "edit-manifest.json").read_text())
        precision_report = json.loads(
            (FIXTURES / "verification-report.surgeon.json").read_text()
        )

        for brief, report in (
            (creative_brief, creative_report),
            (controlled_brief, controlled_report),
        ):
            expected_formats = set(brief["delivery"]["deliverables"])
            actual_formats = set(report["deliverables"])
            self.assertEqual(actual_formats, expected_formats)
            html_deliverable = report["deliverables"]["html"]
            self.assertTrue(html_deliverable["artifact"].endswith(".html"))
            self.assertEqual(report["taskContract"], brief["taskContract"])
            self.assertEqual(report["studioMode"], brief["studioMode"])
            self.assertIn("pptxEditability", report)

        self.assertNotIn("contentGuardrails", controlled_brief)
        self.assertEqual(manifest["taskContract"], precision_report["taskContract"])
        self.assertEqual(list(precision_report["deliverables"]), ["pptx"])
        self.assertTrue(
            precision_report["deliverables"]["pptx"]["artifact"].endswith(".pptx")
        )
        self.assertNotIn("pptxEditability", precision_report)

    def test_cross_artifact_references_and_fragments_resolve(self) -> None:
        creative_brief = json.loads((FIXTURES / "studio-brief.unconstrained.json").read_text())
        controlled_brief = json.loads(
            (FIXTURES / "studio-brief.constrained.json").read_text()
        )
        matrix = json.loads((FIXTURES / "preservation-matrix.json").read_text())
        manifest = json.loads((FIXTURES / "edit-manifest.json").read_text())
        creative_report = json.loads(
            (FIXTURES / "verification-report.studio-unconstrained.json").read_text()
        )
        controlled_report = json.loads(
            (FIXTURES / "verification-report.studio-constrained.json").read_text()
        )
        precision_report = json.loads(
            (FIXTURES / "verification-report.surgeon.json").read_text()
        )

        bundles = [
            (
                creative_report,
                {"contracts/studio-brief.json": creative_brief},
            ),
            (
                controlled_report,
                {
                    "contracts/studio-brief.json": controlled_brief,
                    "contracts/preservation-matrix.json": matrix,
                },
            ),
            (
                precision_report,
                {"contracts/edit-manifest.json": manifest},
            ),
        ]

        for report, bundle in bundles:
            for name, reference in report["references"].items():
                path, _, pointer = reference.partition("#")
                with self.subTest(report=report["taskContract"], reference=name):
                    self.assertIn(path, bundle)
                    resolve_json_pointer(bundle[path], pointer)

        baseline_reference = controlled_report["technicalGate"]["baselineAcceptanceRef"]
        baseline_path, separator, baseline_pointer = baseline_reference.partition("#")
        self.assertEqual(separator, "#")
        self.assertEqual(
            baseline_path,
            controlled_report["references"]["preservationMatrixRef"],
        )
        accepted_condition = resolve_json_pointer(
            {"contracts/preservation-matrix.json": matrix}[baseline_path], baseline_pointer
        )
        self.assertIsInstance(accepted_condition, dict)
        self.assertTrue(accepted_condition["reason"])
        self.assertTrue(accepted_condition["approvedBy"])

        slide_count = matrix["sourceArtifact"]["slideCount"]
        bindings = matrix["slideBindings"]
        self.assertEqual(len(bindings), slide_count)
        self.assertEqual(
            {item["sourceSlide"] for item in bindings},
            set(range(1, slide_count + 1)),
        )
        self.assertEqual(
            {item["outputSlide"] for item in bindings},
            set(range(1, slide_count + 1)),
        )


if __name__ == "__main__":
    unittest.main()
