#!/usr/bin/env python3
"""Focused regression tests for presentation/scripts/pptx_tool.py."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
TOOL = ROOT / "presentation" / "scripts" / "pptx_tool.py"


CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/ppt/slides/slide1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>
</Types>"""

PRESENTATION_RELS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/>
</Relationships>"""


def presentation_xml(root_attribute: str = "") -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" {root_attribute}>
  <p:sldIdLst><p:sldId id="256" r:id="rId1"/></p:sldIdLst>
</p:presentation>"""


def slide_xml(
    objects: str,
    *,
    root_attribute: str = "",
    transition: str = "",
    timing: str = "",
) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" {root_attribute}>
  <p:cSld><p:spTree>{objects}</p:spTree></p:cSld>
  {transition}
  {timing}
</p:sld>"""


def plain_shape(text: str = "Stable text") -> str:
    return f"""
<p:sp>
  <p:nvSpPr><p:cNvPr id="2" name="Text"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
  <p:spPr><a:xfrm><a:off x="500000" y="500000"/><a:ext cx="2000000" cy="500000"/></a:xfrm></p:spPr>
  <p:txBody><a:bodyPr/><a:p><a:r><a:rPr sz="2400"/><a:t>{text}</a:t></a:r></a:p></p:txBody>
</p:sp>"""


def picture_with_embed(relationship_id: str) -> str:
    return f"""
<p:pic>
  <p:nvPicPr><p:cNvPr id="2" name="Dangling Picture"/><p:cNvPicPr/><p:nvPr/></p:nvPicPr>
  <p:blipFill><a:blip r:embed="{relationship_id}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>
  <p:spPr><a:xfrm><a:off x="500000" y="500000"/><a:ext cx="2000000" cy="1000000"/></a:xfrm></p:spPr>
</p:pic>"""


def nested_group(outer_x: int, text: str) -> str:
    return f"""
<p:grpSp>
  <p:nvGrpSpPr><p:cNvPr id="2" name="Outer Group"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
  <p:grpSpPr><a:xfrm>
    <a:off x="{outer_x}" y="500000"/><a:ext cx="4000000" cy="2000000"/>
    <a:chOff x="0" y="0"/><a:chExt cx="2000000" cy="1000000"/>
  </a:xfrm></p:grpSpPr>
  <p:grpSp>
    <p:nvGrpSpPr><p:cNvPr id="3" name="Inner Group"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
    <p:grpSpPr><a:xfrm>
      <a:off x="200000" y="100000"/><a:ext cx="1000000" cy="500000"/>
      <a:chOff x="0" y="0"/><a:chExt cx="1000000" cy="500000"/>
    </a:xfrm></p:grpSpPr>
    <p:sp>
      <p:nvSpPr><p:cNvPr id="4" name="Grouped Label"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
      <p:spPr><a:xfrm><a:off x="100000" y="50000"/><a:ext cx="400000" cy="200000"/></a:xfrm></p:spPr>
      <p:txBody><a:bodyPr/><a:p><a:r><a:rPr sz="2400"/><a:t>{text}</a:t></a:r></a:p></p:txBody>
    </p:sp>
  </p:grpSp>
</p:grpSp>"""


def write_pptx(
    path: Path,
    slide: str,
    *,
    presentation: str | None = None,
    extra_parts: dict[str, str] | None = None,
) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", CONTENT_TYPES)
        zf.writestr("ppt/presentation.xml", presentation or presentation_xml())
        zf.writestr("ppt/_rels/presentation.xml.rels", PRESENTATION_RELS)
        zf.writestr("ppt/slides/slide1.xml", slide)
        for name, value in (extra_parts or {}).items():
            zf.writestr(name, value)


def run_tool(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(TOOL), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


class PptxToolRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.work = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def inspect(self, pptx: Path, stem: str) -> dict:
        output = self.work / f"{stem}.json"
        process = run_tool("inspect", str(pptx), "--out", str(output))
        self.assertEqual(process.returncode, 0, process.stderr or process.stdout)
        return json.loads(output.read_text(encoding="utf-8"))

    def compare(self, before: dict, after: dict, stem: str) -> dict:
        before_path = self.work / f"{stem}-before.json"
        after_path = self.work / f"{stem}-after.json"
        output = self.work / f"{stem}-compare.json"
        before_path.write_text(json.dumps(before), encoding="utf-8")
        after_path.write_text(json.dumps(after), encoding="utf-8")
        process = run_tool(
            "compare",
            str(before_path),
            str(after_path),
            "--out",
            str(output),
        )
        self.assertEqual(process.returncode, 0, process.stderr or process.stdout)
        return json.loads(output.read_text(encoding="utf-8"))

    def test_malformed_xml_and_rels_fail_clean_gate_with_structured_errors(self) -> None:
        pptx = self.work / "malformed.pptx"
        output = self.work / "malformed-gate.json"
        write_pptx(
            pptx,
            slide_xml(plain_shape()),
            extra_parts={
                "ppt/unreferenced.xml": "<broken>",
                "ppt/slides/_rels/unreferenced.xml.rels": "<Relationships><broken></Relationships>",
            },
        )

        process = run_tool("gate", str(pptx), "--out", str(output))
        self.assertNotEqual(process.returncode, 0)
        report = json.loads(output.read_text(encoding="utf-8"))
        parse_errors = [
            error
            for error in report.get("errors", [])
            if isinstance(error, dict) and error.get("code") == "xml_parse_error"
        ]
        self.assertEqual(
            {error.get("part") for error in parse_errors},
            {"ppt/unreferenced.xml", "ppt/slides/_rels/unreferenced.xml.rels"},
        )
        self.assertTrue(all("line" in error and "column" in error for error in parse_errors))
        self.assertEqual(report["xml_validation"]["parse_error_count"], 2)
        self.assertFalse(report["technical_gate"]["passed"])

    def test_nested_group_objects_use_composed_geometry_and_are_diffed(self) -> None:
        before_pptx = self.work / "group-before.pptx"
        after_pptx = self.work / "group-after.pptx"
        write_pptx(before_pptx, slide_xml(nested_group(1_000_000, "Before")))
        write_pptx(after_pptx, slide_xml(nested_group(1_250_000, "After")))

        before = self.inspect(before_pptx, "group-before")
        after = self.inspect(after_pptx, "group-after")
        self.assertEqual(before["report_schema_version"], "1.0")
        self.assertEqual(before["report_kind"], "pptx-inspect")
        self.assertEqual(len(before["artifact_sha256"]), 64)
        self.assertEqual(len(before["package_sha256"]), 64)
        before_object = next(
            item for item in before["slides"][0]["objects"]
            if item.get("object_name") == "Grouped Label"
        )
        after_object = next(
            item for item in after["slides"][0]["objects"]
            if item.get("object_name") == "Grouped Label"
        )

        self.assertEqual(before_object["group_path"], ["group:id:2", "group:id:3"])
        self.assertEqual(
            before_object["box_emu"],
            {"x": 1_600_000, "y": 800_000, "cx": 800_000, "cy": 400_000},
        )
        self.assertEqual(after_object["box_emu"]["x"], 1_850_000)

        comparison = self.compare(before, after, "group")
        self.assertNotIn("passed", comparison)
        self.assertTrue(comparison["technical_regression_passed"])
        self.assertFalse(comparison["scope_verified"])
        modified = comparison["semantic_changes"]["changed_slides"][0]["objects_modified"]
        grouped_change = next(item for item in modified if item["object_key"] == "shape:id:4")
        self.assertTrue(
            {"box_emu", "text", "composed_parent_transform", "group_transform_sha256"}
            .issubset(grouped_change["changed_fields"])
        )

    def test_transition_timing_and_root_state_mutations_are_diffed(self) -> None:
        before_pptx = self.work / "state-before.pptx"
        after_pptx = self.work / "state-after.pptx"
        write_pptx(
            before_pptx,
            slide_xml(
                plain_shape(),
                root_attribute='showMasterSp="1"',
                transition='<p:transition spd="fast"><p:fade/></p:transition>',
                timing='<p:timing><p:tnLst/></p:timing>',
            ),
            presentation=presentation_xml('autoCompressPictures="0"'),
        )
        write_pptx(
            after_pptx,
            slide_xml(
                plain_shape(),
                root_attribute='showMasterSp="0"',
                transition='<p:transition spd="slow"><p:push dir="l"/></p:transition>',
                timing='<p:timing><p:tnLst><p:par/></p:tnLst></p:timing>',
            ),
            presentation=presentation_xml('autoCompressPictures="1"'),
        )

        before = self.inspect(before_pptx, "state-before")
        after = self.inspect(after_pptx, "state-after")
        comparison = self.compare(before, after, "state")
        slide_change = comparison["semantic_changes"]["changed_slides"][0]

        self.assertTrue(slide_change["slide_state_changed"])
        self.assertTrue(
            {"canonical_xml_sha256", "root_attributes", "transition", "timing"}
            .issubset(slide_change["slide_state_changes"])
        )
        self.assertTrue(comparison["semantic_changes"]["presentation_state_changed"])
        self.assertTrue(
            {"canonical_xml_sha256", "root_attributes"}
            .issubset(comparison["semantic_changes"]["presentation_state_changes"])
        )

    def test_dangling_picture_embed_is_a_blocking_relationship_error(self) -> None:
        pptx = self.work / "dangling-embed.pptx"
        output = self.work / "dangling-embed-gate.json"
        write_pptx(
            pptx,
            slide_xml(picture_with_embed("rId42")),
            extra_parts={
                "ppt/slides/_rels/slide1.xml.rels": (
                    '<?xml version="1.0" encoding="UTF-8"?>'
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>'
                ),
            },
        )

        process = run_tool("gate", str(pptx), "--out", str(output))
        self.assertNotEqual(process.returncode, 0)
        report = json.loads(output.read_text(encoding="utf-8"))
        missing_references = [
            error
            for error in report.get("errors", [])
            if isinstance(error, dict) and error.get("code") == "missing_relationship_reference"
        ]
        self.assertEqual(len(missing_references), 1)
        self.assertEqual(
            missing_references[0],
            {
                "code": "missing_relationship_reference",
                "part": "ppt/slides/slide1.xml",
                "from": "ppt/slides/slide1.xml",
                "relationship_part": "ppt/slides/_rels/slide1.xml.rels",
                "relationship_id": "rId42",
                "rid": "rId42",
                "attribute": "embed",
                "element": "blip",
                "reason": "relationship_id_missing",
            },
        )
        self.assertEqual(
            report["relationship_reference_validation"],
            {"checked_reference_count": 2, "missing_reference_count": 1},
        )
        self.assertFalse(report["technical_gate"]["passed"])

    def test_missing_target_in_any_relationship_part_fails_clean_gate(self) -> None:
        pptx = self.work / "missing-layout-master.pptx"
        output = self.work / "missing-layout-master-gate.json"
        slide_relationships = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rIdLayout" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" '
            'Target="../slideLayouts/slideLayout1.xml"/>'
            '</Relationships>'
        )
        layout = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<p:sldLayout xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
            'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" type="blank">'
            '<p:cSld><p:spTree/></p:cSld>'
            '</p:sldLayout>'
        )
        layout_relationships = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rIdMaster" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" '
            'Target="../slideMasters/missing.xml"/>'
            '<Relationship Id="rIdExternal" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
            'Target="https://example.com" TargetMode="External"/>'
            '</Relationships>'
        )
        write_pptx(
            pptx,
            slide_xml(plain_shape()),
            extra_parts={
                "ppt/slides/_rels/slide1.xml.rels": slide_relationships,
                "ppt/slideLayouts/slideLayout1.xml": layout,
                "ppt/slideLayouts/_rels/slideLayout1.xml.rels": layout_relationships,
            },
        )

        process = run_tool("gate", str(pptx), "--out", str(output))
        self.assertNotEqual(process.returncode, 0)
        report = json.loads(output.read_text(encoding="utf-8"))
        missing_targets = [
            error
            for error in report.get("errors", [])
            if isinstance(error, dict) and error.get("code") == "missing_relationship_target"
        ]
        self.assertEqual(
            missing_targets,
            [
                {
                    "code": "missing_relationship_target",
                    "part": "ppt/slideLayouts/_rels/slideLayout1.xml.rels",
                    "from": "ppt/slideLayouts/slideLayout1.xml",
                    "rid": "rIdMaster",
                    "target": "../slideMasters/missing.xml",
                    "resolved_target": "ppt/slideMasters/missing.xml",
                }
            ],
        )
        self.assertEqual(
            report["relationship_target_validation"],
            {"checked_relationship_count": 3, "missing_target_count": 1},
        )
        self.assertFalse(report["technical_gate"]["passed"])

    def test_compare_rejects_empty_and_incomplete_inspect_reports(self) -> None:
        empty_before = self.work / "empty-before.json"
        empty_after = self.work / "empty-after.json"
        empty_output = self.work / "empty-compare.json"
        empty_before.write_text("{}\n", encoding="utf-8")
        empty_after.write_text("{}\n", encoding="utf-8")

        empty_process = run_tool(
            "compare",
            str(empty_before),
            str(empty_after),
            "--out",
            str(empty_output),
        )
        self.assertNotEqual(empty_process.returncode, 0)
        empty_report = json.loads(empty_output.read_text(encoding="utf-8"))
        self.assertFalse(empty_report["checked"])
        self.assertFalse(empty_report["technical_regression_passed"])
        self.assertFalse(empty_report["scope_verified"])
        self.assertTrue(empty_report["validation_errors"])

        pptx = self.work / "complete.pptx"
        write_pptx(pptx, slide_xml(plain_shape()))
        complete = self.inspect(pptx, "complete")
        incomplete = json.loads(json.dumps(complete))
        incomplete["slides"][0]["objects"][0].pop("semantic_sha256")
        complete_path = self.work / "complete-report.json"
        incomplete_path = self.work / "incomplete-report.json"
        incomplete_output = self.work / "incomplete-compare.json"
        complete_path.write_text(json.dumps(complete), encoding="utf-8")
        incomplete_path.write_text(json.dumps(incomplete), encoding="utf-8")

        incomplete_process = run_tool(
            "compare",
            str(complete_path),
            str(incomplete_path),
            "--out",
            str(incomplete_output),
        )
        self.assertNotEqual(incomplete_process.returncode, 0)
        incomplete_report = json.loads(incomplete_output.read_text(encoding="utf-8"))
        self.assertFalse(incomplete_report["checked"])
        self.assertTrue(
            any(
                error.get("code") == "semantic_snapshot_unavailable"
                for error in incomplete_report.get("validation_errors", [])
            )
        )


if __name__ == "__main__":
    unittest.main()
