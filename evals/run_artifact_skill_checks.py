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

    workspace = ROOT / "artifact-skills-workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    docx = workspace / "document-smoke.docx"
    pptx = workspace / "presentation-smoke.pptx"
    xlsx = workspace / "spreadsheet-smoke.xlsx"
    create_minimal_docx(docx)
    create_minimal_pptx(pptx)
    create_minimal_xlsx(xlsx)

    commands = [
        ["node", "document/scripts/markdown_tool.mjs", "inspect", "evals/artifact-skills/document/source/board_notes.md", "--out", "artifact-skills-workspace/document-md-report.json"],
        ["python3", "document/scripts/docx_tool.py", "inspect", str(docx), "--out", "artifact-skills-workspace/document-docx-report.json"],
        ["python3", "spreadsheet/scripts/table_tool.py", "inspect", "evals/artifact-skills/spreadsheet/source/messy_export.csv", "--out", "artifact-skills-workspace/spreadsheet-csv-report.json"],
        ["python3", "spreadsheet/scripts/workbook_tool.py", "inspect", str(xlsx), "--out", "artifact-skills-workspace/spreadsheet-xlsx-report.json"],
        ["python3", "pdf/scripts/pdf_tool.py", "inspect", "evals/artifact-skills/pdf/source/one_page.pdf", "--out", "artifact-skills-workspace/pdf-inspect-report.json"],
    ]
    html = workspace / "presentation-smoke.html"
    html.parent.mkdir(parents=True, exist_ok=True)
    html.write_text(
        "<!doctype html><html><body><section class='slide'><h1>Eval</h1></section></body></html>\n",
        encoding="utf-8",
    )
    commands.append(["node", "presentation/scripts/html_tool.mjs", "inspect", str(html), "--out", "artifact-skills-workspace/presentation-html-report.json"])
    commands.append(["python3", "presentation/scripts/pptx_tool.py", "inspect", str(pptx), "--out", "artifact-skills-workspace/presentation-pptx-report.json"])

    for cmd in commands:
        proc = run(cmd)
        if proc.returncode != 0:
            errors.append(f"command failed {' '.join(cmd)}: {proc.stderr.strip() or proc.stdout.strip()}")
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


def create_minimal_pptx(path: Path) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/ppt/slides/slide1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>
</Types>""")
        zf.writestr("ppt/presentation.xml", """<?xml version="1.0" encoding="UTF-8"?>
<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:sldIdLst><p:sldId id="256" r:id="rId1"/></p:sldIdLst>
</p:presentation>""")
        zf.writestr("ppt/_rels/presentation.xml.rels", """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/>
</Relationships>""")
        zf.writestr("ppt/slides/slide1.xml", """<?xml version="1.0" encoding="UTF-8"?>
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:cSld><p:spTree><p:sp><p:txBody><a:bodyPr/><a:p><a:r><a:t>Eval slide headline</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld>
</p:sld>""")


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
    out = ROOT / "artifact-skills-workspace" / "forward-test-prompts.json"
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
