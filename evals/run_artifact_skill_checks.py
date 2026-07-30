#!/usr/bin/env python3
"""Static and smoke checks for artifact skill eval definitions."""

from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "evals" / "artifact-skills" / "suite.json"


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def check_eval_file(path: Path) -> list[str]:
    errors: list[str] = []
    data = load_json(path)
    if not data.get("skill_name"):
        errors.append(f"{path}: missing skill_name")
    if not isinstance(data.get("evals"), list) or not data["evals"]:
        errors.append(f"{path}: missing evals")
        return errors
    seen = set()
    for item in data["evals"]:
        eval_id = item.get("id")
        if not eval_id:
            errors.append(f"{path}: eval missing id")
        elif eval_id in seen:
            errors.append(f"{path}: duplicate id {eval_id}")
        seen.add(eval_id)
        for key in ["name", "prompt", "expected_skill", "assertions"]:
            if key not in item:
                errors.append(f"{path}:{eval_id}: missing {key}")
        if not isinstance(item.get("assertions"), list) or not item.get("assertions"):
            errors.append(f"{path}:{eval_id}: assertions must be non-empty")
        if "$" not in item.get("prompt", "") and "should-not" not in item.get("name", ""):
            errors.append(f"{path}:{eval_id}: prompt should invoke a skill or be a negative boundary case")
        for rel in item.get("files", []):
            target = ROOT / rel
            if not target.exists():
                errors.append(f"{path}:{eval_id}: missing file {rel}")
    return errors


def ensure_fixtures() -> list[str]:
    errors: list[str] = []
    pdf_gen = run(["python3", "evals/artifact-skills/pdf/make_sample_pdfs.py"])
    if pdf_gen.returncode != 0:
        errors.append(f"pdf sample generation failed: {pdf_gen.stderr.strip()}")
    return errors


def smoke_checks() -> list[str]:
    errors: list[str] = []

    workspace = ROOT / "work" / "artifact-skills"
    workspace.mkdir(parents=True, exist_ok=True)
    docx = workspace / "document-smoke.docx"
    pptx = workspace / "presentation-smoke.pptx"
    xlsx = workspace / "spreadsheet-smoke.xlsx"
    create_minimal_docx(docx)
    create_minimal_pptx(pptx)
    create_minimal_xlsx(xlsx)

    commands = [
        ["node", "skills/document/scripts/markdown_tool.mjs", "inspect", "evals/artifact-skills/document/source/board_notes.md", "--out", "work/artifact-skills/document-md-report.json"],
        ["python3", "skills/document/scripts/docx_tool.py", "inspect", str(docx), "--out", "work/artifact-skills/document-docx-report.json"],
        ["python3", "skills/spreadsheet/scripts/table_tool.py", "inspect", "evals/artifact-skills/spreadsheet/source/messy_export.csv", "--out", "work/artifact-skills/spreadsheet-csv-report.json"],
        ["python3", "skills/spreadsheet/scripts/workbook_tool.py", "inspect", str(xlsx), "--out", "work/artifact-skills/spreadsheet-xlsx-report.json"],
        ["python3", "skills/pdf/scripts/pdf_tool.py", "inspect", "evals/artifact-skills/pdf/source/one_page.pdf", "--out", "work/artifact-skills/pdf-inspect-report.json"],
    ]
    html = workspace / "presentation-smoke.html"
    html.parent.mkdir(parents=True, exist_ok=True)
    html.write_text(
        "<!doctype html><html><body><section class='slide'><h1>Eval</h1></section></body></html>\n",
        encoding="utf-8",
    )
    commands.append(["node", "skills/presentation/scripts/html_tool.mjs", "inspect", str(html), "--out", "work/artifact-skills/presentation-html-report.json"])
    commands.append(["python3", "skills/presentation/scripts/pptx_tool.py", "inspect", str(pptx), "--out", "work/artifact-skills/presentation-pptx-report.json"])
    render_dir = workspace / "presentation-render-smoke"
    commands.append([
        "python3",
        "skills/presentation/scripts/render_slides.py",
        "evals/artifact-skills/pdf/source/one_page.pdf",
        "--out-dir",
        str(render_dir),
        "--dpi",
        "72",
    ])

    for cmd in commands:
        proc = run(cmd)
        if proc.returncode != 0:
            errors.append(f"command failed {' '.join(cmd)}: {proc.stderr.strip() or proc.stdout.strip()}")

    render_manifest_path = render_dir / "render-manifest.json"
    try:
        render_manifest = load_json(render_manifest_path)
        rendered_slides = render_manifest.get("slides", [])
        contact_sheet = render_manifest.get("contact_sheet", {})
        contact_sheet_path = render_dir / str(contact_sheet.get("file", ""))
        if len(rendered_slides) != 1 or not (render_dir / "slide-001.png").is_file():
            errors.append("presentation renderer did not produce the expected slide PNG")
        if not contact_sheet_path.is_file():
            errors.append("presentation renderer did not produce the declared contact sheet")
    except (OSError, TypeError, json.JSONDecodeError) as exc:
        errors.append(f"presentation render smoke assertions failed: {exc}")

    pptx_report_path = workspace / "presentation-pptx-report.json"
    pptx_report: dict = {}
    try:
        pptx_report = load_json(pptx_report_path)
        slide = pptx_report["slides"][0]
        objects = slide["objects"]
        headline = next(obj for obj in objects if obj.get("object_name") == "Headline")
        table = next(obj for obj in objects if obj.get("object_name") == "Metrics Table")
        if headline.get("object_id") != 2 or headline.get("text_full") != "Eval slide headline":
            errors.append("presentation inspect did not preserve stable shape identity and full text")
        if headline.get("box") != {"x": 0.75, "y": 0.5, "w": 5.5, "h": 0.75}:
            errors.append("presentation inspect did not preserve the shape box")
        if headline.get("box_emu") != {"x": 685800, "y": 457200, "cx": 5029200, "cy": 685800}:
            errors.append("presentation inspect did not preserve the exact EMU shape box")
        if len(str(headline.get("non_text_sha256", ""))) != 64:
            errors.append("presentation inspect did not capture the non-text object property hash")
        if (table.get("table") or {}).get("values") != [["Metric", "Value"], ["Revenue", "42"]]:
            errors.append("presentation inspect did not preserve table cell values")
        if slide.get("notes_text") != "Speaker note for eval":
            errors.append("presentation inspect did not capture speaker notes text")
        if not any(
            rel.get("type_name") == "notesSlide" and rel.get("target_exists") is True
            for rel in slide.get("relationships", [])
        ):
            errors.append("presentation inspect did not capture resolved relationship targets")
    except (KeyError, IndexError, StopIteration, TypeError, OSError, json.JSONDecodeError) as exc:
        errors.append(f"presentation inspect accuracy assertions failed: {exc}")

    baseline_gate_path = workspace / "presentation-baseline-gate.json"
    baseline_gate = run([
        "python3",
        "skills/presentation/scripts/pptx_tool.py",
        "gate",
        str(pptx),
        "--baseline",
        str(pptx_report_path),
        "--out",
        str(baseline_gate_path),
    ])
    if baseline_gate.returncode != 0:
        errors.append(
            "presentation baseline gate failed unchanged deck: "
            + (baseline_gate.stderr.strip() or baseline_gate.stdout.strip())
        )
    else:
        baseline_gate_report = load_json(baseline_gate_path)
        if baseline_gate_report.get("technical_gate", {}).get("mode") != "baseline-no-new-regressions":
            errors.append("presentation baseline gate did not report baseline mode")
        if baseline_gate_report.get("absolute_technical_gate", {}).get("passed") is not False:
            errors.append("presentation baseline gate fixture did not retain its known absolute warning")

    clean_baseline_path = workspace / "presentation-clean-baseline.json"
    clean_baseline = dict(pptx_report)
    clean_baseline["tiny_text"] = []
    clean_baseline["warnings"] = [
        warning for warning in pptx_report.get("warnings", []) if warning != "tiny_text"
    ]
    clean_baseline_path.write_text(json.dumps(clean_baseline) + "\n", encoding="utf-8")
    new_regression_gate_path = workspace / "presentation-new-regression-gate.json"
    new_regression_gate = run([
        "python3",
        "skills/presentation/scripts/pptx_tool.py",
        "gate",
        str(pptx),
        "--baseline",
        str(clean_baseline_path),
        "--out",
        str(new_regression_gate_path),
    ])
    if new_regression_gate.returncode != 2:
        errors.append("presentation baseline gate did not fail a warning absent from the baseline")
    else:
        new_regression_report = load_json(new_regression_gate_path)
        if new_regression_report.get("technical_gate", {}).get("new_issue_counts", {}).get("tiny_text") != 1:
            errors.append("presentation baseline gate did not report the new warning fingerprint")

    before_issue_path = workspace / "presentation-before-issues.json"
    after_issue_path = workspace / "presentation-after-issues.json"
    same_issue_path = workspace / "presentation-same-issue.json"
    compare_path = workspace / "presentation-issue-compare.json"
    common_missing_relationship = [{
        "from": "ppt/slides/slide1.xml",
        "rid": "rId9",
        "target": "../media/missing.png",
    }]
    before_issue_report = json.loads(json.dumps(pptx_report))
    before_issue_report.update({
        "file": "before.pptx",
        "ok": False,
        "tiny_text": [{"slide": 1, "order": 2, "object_key": "shape:id:2"}],
        "errors": ["legacy_source_error"],
        "missing_relationship_targets": common_missing_relationship,
    })
    after_issue_report = json.loads(json.dumps(before_issue_report))
    after_issue_report.update({
        "file": "after.pptx",
        "tiny_text": [{"slide": 1, "order": 2, "object_key": "shape:id:9"}],
    })
    same_issue_report = json.loads(json.dumps(before_issue_report))
    same_issue_report.update({
        "file": "same-location.pptx",
        "tiny_text": [{
            "slide": 1,
            "order": 2,
            "object_key": "shape:id:2",
            "text": "edited target text",
        }],
    })
    before_issue_path.write_text(json.dumps(before_issue_report) + "\n", encoding="utf-8")
    after_issue_path.write_text(json.dumps(after_issue_report) + "\n", encoding="utf-8")
    same_issue_path.write_text(json.dumps(same_issue_report) + "\n", encoding="utf-8")
    compare = run([
        "python3",
        "skills/presentation/scripts/pptx_tool.py",
        "compare",
        str(before_issue_path),
        str(after_issue_path),
        "--out",
        str(compare_path),
    ])
    if compare.returncode != 2:
        errors.append("presentation compare did not fail a same-count issue replacement")
    else:
        compare_report = load_json(compare_path)
        if not compare_report.get("new_issue_fingerprints", {}).get("tiny_text"):
            errors.append("presentation compare did not report the replacement issue fingerprint")

    same_issue_compare = run([
        "python3",
        "skills/presentation/scripts/pptx_tool.py",
        "compare",
        str(before_issue_path),
        str(same_issue_path),
        "--out",
        str(workspace / "presentation-same-issue-compare.json"),
    ])
    if same_issue_compare.returncode != 0:
        errors.append("presentation compare treated edited evidence on the same issue as a new regression")

    semantic_after_pptx = workspace / "presentation-semantic-after.pptx"
    semantic_after_path = workspace / "presentation-semantic-after.json"
    create_minimal_pptx(semantic_after_pptx, headline="Edited slide headline")
    semantic_inspect = run([
        "python3",
        "skills/presentation/scripts/pptx_tool.py",
        "inspect",
        str(semantic_after_pptx),
        "--out",
        str(semantic_after_path),
    ])
    semantic_compare_path = workspace / "presentation-semantic-compare.json"
    if semantic_inspect.returncode != 0:
        errors.append(
            "presentation semantic after fixture inspection failed: "
            + (semantic_inspect.stderr.strip() or semantic_inspect.stdout.strip())
        )
    else:
        semantic_compare = run([
            "python3",
            "skills/presentation/scripts/pptx_tool.py",
            "compare",
            str(pptx_report_path),
            str(semantic_after_path),
            "--out",
            str(semantic_compare_path),
        ])
        if semantic_compare.returncode != 0:
            errors.append("presentation semantic diff incorrectly blocked a non-technical content change")
        else:
            semantic_report = load_json(semantic_compare_path).get("semantic_changes", {})
            modified = semantic_report.get("changed_slides", [{}])[0].get("objects_modified", [])
            changed_fields = modified[0].get("changed_fields", {}) if modified else {}
            if semantic_report.get("changed_slide_count") != 1 or "text" not in changed_fields:
                errors.append("presentation compare did not report the object text semantic change")
            if "non_text_sha256" in changed_fields:
                errors.append("presentation compare did not prove non-text object properties were preserved")
    return errors


def create_minimal_docx(path: Path) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>""")
        zf.writestr("word/document.xml", """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Eval Document</w:t></w:r></w:p>
    <w:p><w:r><w:t>Source fidelity paragraph for validation.</w:t></w:r></w:p>
    <w:sectPr/>
  </w:body>
</w:document>""")


def create_minimal_pptx(path: Path, headline: str = "Eval slide headline") -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/ppt/slides/slide1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>
  <Override PartName="/ppt/notesSlides/notesSlide1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml"/>
</Types>""")
        zf.writestr("ppt/presentation.xml", """<?xml version="1.0" encoding="UTF-8"?>
<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:sldIdLst><p:sldId id="256" r:id="rId1"/></p:sldIdLst>
</p:presentation>""")
        zf.writestr("ppt/_rels/presentation.xml.rels", """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/>
</Relationships>""")
        zf.writestr("ppt/slides/slide1.xml", f"""<?xml version="1.0" encoding="UTF-8"?>
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:cSld><p:spTree>
    <p:sp>
      <p:nvSpPr><p:cNvPr id="2" name="Headline"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
      <p:spPr><a:xfrm><a:off x="685800" y="457200"/><a:ext cx="5029200" cy="685800"/></a:xfrm></p:spPr>
      <p:txBody><a:bodyPr/><a:p><a:r><a:rPr sz="700"/><a:t>{headline}</a:t></a:r></a:p></p:txBody>
    </p:sp>
    <p:graphicFrame>
      <p:nvGraphicFramePr><p:cNvPr id="3" name="Metrics Table"/><p:cNvGraphicFramePr/><p:nvPr/></p:nvGraphicFramePr>
      <p:xfrm><a:off x="685800" y="1600200"/><a:ext cx="5486400" cy="1828800"/></p:xfrm>
      <a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table"><a:tbl>
        <a:tblPr/><a:tblGrid><a:gridCol w="2743200"/><a:gridCol w="2743200"/></a:tblGrid>
        <a:tr h="914400">
          <a:tc><a:txBody><a:bodyPr/><a:p><a:r><a:t>Metric</a:t></a:r></a:p></a:txBody><a:tcPr/></a:tc>
          <a:tc><a:txBody><a:bodyPr/><a:p><a:r><a:t>Value</a:t></a:r></a:p></a:txBody><a:tcPr/></a:tc>
        </a:tr>
        <a:tr h="914400">
          <a:tc><a:txBody><a:bodyPr/><a:p><a:r><a:t>Revenue</a:t></a:r></a:p></a:txBody><a:tcPr/></a:tc>
          <a:tc><a:txBody><a:bodyPr/><a:p><a:r><a:t>42</a:t></a:r></a:p></a:txBody><a:tcPr/></a:tc>
        </a:tr>
      </a:tbl></a:graphicData></a:graphic>
    </p:graphicFrame>
  </p:spTree></p:cSld>
</p:sld>""")
        zf.writestr("ppt/slides/_rels/slide1.xml.rels", """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide" Target="../notesSlides/notesSlide1.xml"/>
</Relationships>""")
        zf.writestr("ppt/notesSlides/notesSlide1.xml", """<?xml version="1.0" encoding="UTF-8"?>
<p:notes xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:cSld><p:spTree><p:sp>
    <p:nvSpPr><p:cNvPr id="2" name="Notes Body"/><p:cNvSpPr/><p:nvPr><p:ph type="body"/></p:nvPr></p:nvSpPr>
    <p:txBody><a:bodyPr/><a:p><a:r><a:t>Speaker note for eval</a:t></a:r></a:p></p:txBody>
  </p:sp></p:spTree></p:cSld>
</p:notes>""")
        zf.writestr("ppt/notesSlides/_rels/notesSlide1.xml.rels", """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="../slides/slide1.xml"/>
</Relationships>""")


def create_minimal_xlsx(path: Path) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>""")
        zf.writestr("xl/workbook.xml", """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Inputs" sheetId="1" r:id="rId1"/></sheets>
</workbook>""")
        zf.writestr("xl/_rels/workbook.xml.rels", """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>""")
        zf.writestr("xl/worksheets/sheet1.xml", """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <dimension ref="A1:B2"/>
  <sheetData>
    <row r="1"><c r="A1" t="inlineStr"><is><t>Metric</t></is></c><c r="B1" t="inlineStr"><is><t>Value</t></is></c></row>
    <row r="2"><c r="A2" t="inlineStr"><is><t>Revenue</t></is></c><c r="B2"><v>42</v></c></row>
  </sheetData>
</worksheet>""")


def write_forward_test_prompts(suite: dict) -> None:
    prompts = []
    for rel in suite.get("eval_files", []):
        data = load_json(ROOT / rel)
        for item in data.get("evals", []):
            prompts.append({
                "id": item["id"],
                "skill_path": data.get("skill_path"),
                "prompt": item["prompt"],
                "files": item.get("files", []),
            })
    out = ROOT / "work" / "artifact-skills" / "forward-test-prompts.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"prompts": prompts}, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    errors: list[str] = []
    suite = load_json(SUITE)
    errors.extend(ensure_fixtures())
    for rel in suite.get("eval_files", []):
        errors.extend(check_eval_file(ROOT / rel))
    errors.extend(smoke_checks())
    write_forward_test_prompts(suite)
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, indent=2))
        return 1
    print(json.dumps({"ok": True, "eval_files": suite.get("eval_files", [])}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
