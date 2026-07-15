#!/usr/bin/env python3
"""Generate deterministic PPTX fixtures for presentation behavior evals."""

from __future__ import annotations

import base64
import html
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "evals" / "artifact-skills" / "presentation" / "source"

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
C_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAIAAAAlC+aJAAAACXBIWXMAAAsSAAALEgHS3X78"
    "AAAAM0lEQVR4nO3PQQ0AIBDAsAP/nuGNAvZoFSzZOjNnyNiBdwN3A3cDdwN3A3cDdwN3A3cD"
    "dwN3A3cDdwF0B8xkBfQAB4VAAAAAASUVORK5CYII="
)


class DeterministicZipFile(zipfile.ZipFile):
    def writestr(self, zinfo_or_arcname, data, compress_type=None, compresslevel=None):
        if isinstance(zinfo_or_arcname, str):
            info = zipfile.ZipInfo(zinfo_or_arcname, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            zinfo_or_arcname = info
        return super().writestr(zinfo_or_arcname, data, compress_type, compresslevel)


def esc(value: str) -> str:
    return html.escape(value, quote=True)


def shape(shape_id: int, name: str, text: str, x: int, y: int, cx: int, cy: int) -> str:
    return f"""
<p:sp>
  <p:nvSpPr><p:cNvPr id="{shape_id}" name="{esc(name)}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
  <p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>
  <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang="en-US" sz="2400"/><a:t>{esc(text)}</a:t></a:r><a:endParaRPr lang="en-US"/></a:p></p:txBody>
</p:sp>"""


def linked_shape(shape_id: int, text: str) -> str:
    return f"""
<p:sp>
  <p:nvSpPr><p:cNvPr id="{shape_id}" name="Evidence link"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
  <p:spPr><a:xfrm><a:off x="900000" y="4700000"/><a:ext cx="3500000" cy="500000"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>
  <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang="en-US" sz="1800"><a:hlinkClick r:id="rIdLink"/></a:rPr><a:t>{esc(text)}</a:t></a:r><a:endParaRPr lang="en-US"/></a:p></p:txBody>
</p:sp>"""


def picture(shape_id: int) -> str:
    return f"""
<p:pic>
  <p:nvPicPr><p:cNvPr id="{shape_id}" name="Official brand mark" descr="Official fixture brand asset"/><p:cNvPicPr/><p:nvPr/></p:nvPicPr>
  <p:blipFill><a:blip r:embed="rIdImage"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>
  <p:spPr><a:xfrm><a:off x="10200000" y="400000"/><a:ext cx="1300000" cy="650000"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>
</p:pic>"""


def chart_frame(shape_id: int) -> str:
    return f"""
<p:graphicFrame>
  <p:nvGraphicFramePr><p:cNvPr id="{shape_id}" name="Pipeline chart"/><p:cNvGraphicFramePr/><p:nvPr/></p:nvGraphicFramePr>
  <p:xfrm><a:off x="1200000" y="1900000"/><a:ext cx="9000000" cy="4300000"/></p:xfrm>
  <a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/chart"><c:chart r:id="rIdChart"/></a:graphicData></a:graphic>
</p:graphicFrame>"""


def grouped_objects() -> str:
    return """
<p:grpSp>
  <p:nvGrpSpPr><p:cNvPr id="20" name="Operating model group"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
  <p:grpSpPr><a:xfrm><a:off x="1200000" y="1800000"/><a:ext cx="9000000" cy="3600000"/><a:chOff x="0" y="0"/><a:chExt cx="9000000" cy="3600000"/></a:xfrm></p:grpSpPr>
  <p:sp><p:nvSpPr><p:cNvPr id="21" name="Signal input"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="2500000" cy="1200000"/></a:xfrm><a:prstGeom prst="roundRect"><a:avLst/></a:prstGeom></p:spPr><p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr sz="2200"/><a:t>Signal input</a:t></a:r></a:p></p:txBody></p:sp>
  <p:sp><p:nvSpPr><p:cNvPr id="22" name="Decision loop"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="3250000" y="1000000"/><a:ext cx="2500000" cy="1200000"/></a:xfrm><a:prstGeom prst="roundRect"><a:avLst/></a:prstGeom></p:spPr><p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr sz="2200"/><a:t>Decision loop</a:t></a:r></a:p></p:txBody></p:sp>
  <p:sp><p:nvSpPr><p:cNvPr id="23" name="Measured outcome"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="6500000" y="2200000"/><a:ext cx="2500000" cy="1200000"/></a:xfrm><a:prstGeom prst="roundRect"><a:avLst/></a:prstGeom></p:spPr><p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr sz="2200"/><a:t>Measured outcome</a:t></a:r></a:p></p:txBody></p:sp>
</p:grpSp>"""


def slide_xml(index: int, title: str, body: str, *, board_target: bool = False) -> str:
    objects = [
        shape(2, "Title", title, 700000, 500000, 10500000, 900000),
        shape(3, "Body", body, 900000, 1600000, 9800000, 3200000),
        picture(4),
    ]
    if index == 4:
        objects.append(chart_frame(10))
    if index == 5:
        objects.append(grouped_objects())
    if index == 8:
        objects.append(linked_shape(30, "Source: https://example.com/evidence"))
    if board_target:
        objects.append(shape(7, "Pipeline subtitle", "Q3 pipeline", 900000, 5400000, 4300000, 650000))

    transition = '<p:transition spd="fast"><p:fade/></p:transition>' if index == 7 else ""
    timing = '<p:timing><p:tnLst><p:par/></p:tnLst></p:timing>' if index == 7 else ""
    hidden = ' show="0"' if index == 6 else ""
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:p="{P_NS}" xmlns:a="{A_NS}" xmlns:r="{R_NS}" xmlns:c="{C_NS}"{hidden}>
  <p:cSld name="Fixture slide {index}"><p:spTree>
    <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
    <p:grpSpPr/>
    {''.join(objects)}
  </p:spTree></p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
  {transition}
  {timing}
</p:sld>"""


def chart_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<c:chartSpace xmlns:c="{C_NS}" xmlns:a="{A_NS}" xmlns:r="{R_NS}">
  <c:date1904 val="0"/><c:lang val="en-US"/>
  <c:chart><c:autoTitleDeleted val="1"/><c:plotArea><c:layout/>
    <c:barChart><c:barDir val="col"/><c:grouping val="clustered"/><c:ser>
      <c:idx val="0"/><c:order val="0"/><c:tx><c:v>Pipeline</c:v></c:tx>
      <c:cat><c:strLit><c:ptCount val="3"/><c:pt idx="0"><c:v>Q1</c:v></c:pt><c:pt idx="1"><c:v>Q2</c:v></c:pt><c:pt idx="2"><c:v>Q3</c:v></c:pt></c:strLit></c:cat>
      <c:val><c:numLit><c:formatCode>0</c:formatCode><c:ptCount val="3"/><c:pt idx="0"><c:v>42</c:v></c:pt><c:pt idx="1"><c:v>57</c:v></c:pt><c:pt idx="2"><c:v>68</c:v></c:pt></c:numLit></c:val>
    </c:ser><c:axId val="123456"/><c:axId val="654321"/></c:barChart>
    <c:catAx><c:axId val="123456"/><c:scaling><c:orientation val="minMax"/></c:scaling><c:axPos val="b"/><c:crossAx val="654321"/></c:catAx>
    <c:valAx><c:axId val="654321"/><c:scaling><c:orientation val="minMax"/></c:scaling><c:axPos val="l"/><c:crossAx val="123456"/></c:valAx>
  </c:plotArea><c:plotVisOnly val="1"/></c:chart>
</c:chartSpace>"""


def notes_xml(index: int, note: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:notes xmlns:p="{P_NS}" xmlns:a="{A_NS}" xmlns:r="{R_NS}">
  <p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>
    {shape(2, f'Notes {index}', note, 500000, 500000, 8000000, 3000000)}
  </p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:notes>"""


def relationships(entries: list[tuple[str, str, str, str | None]]) -> str:
    rows = []
    for rel_id, rel_type, target, mode in entries:
        target_mode = f' TargetMode="{mode}"' if mode else ""
        rows.append(
            f'<Relationship Id="{rel_id}" Type="{rel_type}" Target="{target}"{target_mode}/>'
        )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{REL_NS}">{"".join(rows)}</Relationships>'
    )


def content_types(slide_count: int) -> str:
    overrides = [
        ('/ppt/presentation.xml', 'application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml'),
        ('/ppt/slideMasters/slideMaster1.xml', 'application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml'),
        ('/ppt/slideLayouts/slideLayout1.xml', 'application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml'),
        ('/ppt/notesMasters/notesMaster1.xml', 'application/vnd.openxmlformats-officedocument.presentationml.notesMaster+xml'),
        ('/ppt/theme/theme1.xml', 'application/vnd.openxmlformats-officedocument.theme+xml'),
        ('/ppt/charts/chart1.xml', 'application/vnd.openxmlformats-officedocument.drawingml.chart+xml'),
        ('/docProps/core.xml', 'application/vnd.openxmlformats-package.core-properties+xml'),
        ('/docProps/app.xml', 'application/vnd.openxmlformats-officedocument.extended-properties+xml'),
        ('/docProps/custom.xml', 'application/vnd.openxmlformats-officedocument.custom-properties+xml'),
    ]
    for index in range(1, slide_count + 1):
        overrides.append((f'/ppt/slides/slide{index}.xml', 'application/vnd.openxmlformats-officedocument.presentationml.slide+xml'))
        overrides.append((f'/ppt/notesSlides/notesSlide{index}.xml', 'application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml'))
    rows = ''.join(f'<Override PartName="{part}" ContentType="{kind}"/>' for part, kind in overrides)
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>{rows}
</Types>"""


def presentation_xml(slide_count: int) -> str:
    slides = ''.join(
        f'<p:sldId id="{255 + index}" r:id="rId{index}"/>'
        for index in range(1, slide_count + 1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:p="{P_NS}" xmlns:a="{A_NS}" xmlns:r="{R_NS}" autoCompressPictures="0">
  <p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rIdMaster"/></p:sldMasterIdLst>
  <p:sldIdLst>{slides}</p:sldIdLst>
  <p:sldSz cx="12192000" cy="6858000" type="screen16x9"/><p:notesSz cx="6858000" cy="9144000"/>
</p:presentation>"""


def master_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:p="{P_NS}" xmlns:a="{A_NS}" xmlns:r="{R_NS}">
  <p:cSld name="Fixture Master"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/></p:spTree></p:cSld>
  <p:clrMap accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" bg1="lt1" bg2="lt2" folHlink="folHlink" hlink="hlink" tx1="dk1" tx2="dk2"/>
  <p:sldLayoutIdLst><p:sldLayoutId id="1" r:id="rIdLayout"/></p:sldLayoutIdLst><p:txStyles/>
</p:sldMaster>"""


def layout_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:p="{P_NS}" xmlns:a="{A_NS}" xmlns:r="{R_NS}" type="blank" preserve="1">
  <p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/></p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sldLayout>"""


def notes_master_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:notesMaster xmlns:p="{P_NS}" xmlns:a="{A_NS}" xmlns:r="{R_NS}">
  <p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/></p:spTree></p:cSld>
  <p:clrMap accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" bg1="lt1" bg2="lt2" folHlink="folHlink" hlink="hlink" tx1="dk1" tx2="dk2"/>
</p:notesMaster>"""


def theme_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="{A_NS}" name="Fixture Theme"><a:themeElements>
  <a:clrScheme name="Fixture"><a:dk1><a:srgbClr val="111111"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1><a:dk2><a:srgbClr val="24324A"/></a:dk2><a:lt2><a:srgbClr val="F3F5F7"/></a:lt2><a:accent1><a:srgbClr val="2A6FDB"/></a:accent1><a:accent2><a:srgbClr val="D14F3F"/></a:accent2><a:accent3><a:srgbClr val="2F8F6B"/></a:accent3><a:accent4><a:srgbClr val="8B62B2"/></a:accent4><a:accent5><a:srgbClr val="D19B2A"/></a:accent5><a:accent6><a:srgbClr val="4F768C"/></a:accent6><a:hlink><a:srgbClr val="0563C1"/></a:hlink><a:folHlink><a:srgbClr val="954F72"/></a:folHlink></a:clrScheme>
  <a:fontScheme name="Fixture"><a:majorFont><a:latin typeface="Aptos Display"/></a:majorFont><a:minorFont><a:latin typeface="Aptos"/></a:minorFont></a:fontScheme>
  <a:fmtScheme name="Fixture"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst><a:lnStyleLst><a:ln w="9525"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst><a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst><a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme>
</a:themeElements></a:theme>"""


def properties(title: str, slide_count: int) -> dict[str, str]:
    return {
        "docProps/core.xml": f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>{esc(title)}</dc:title><dc:creator>Linlab fixture generator</dc:creator></cp:coreProperties>''',
        "docProps/app.xml": f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>Fixture Generator</Application><Slides>{slide_count}</Slides></Properties>''',
        "docProps/custom.xml": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/custom-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><property fmtid="{D5CDD505-2E9C-101B-9397-08002B2CF9AE}" pid="2" name="PrecisionSentinel"><vt:lpwstr>preserve-me</vt:lpwstr></property></Properties>''',
    }


def write_fixture(path: Path, title: str, slide_count: int, kind: str) -> None:
    titles = [
        title,
        "The decision in one page",
        "What changed and what did not",
        "Pipeline evidence",
        "Operating model",
        "Hidden appendix sentinel",
        "Board decision",
        "Source and caveat",
        "Customer voice",
        "Next actions",
    ]
    while len(titles) < slide_count:
        titles.append(f"{kind.title()} workstream {len(titles) + 1}")

    bodies = [
        "Fixture deck with factual claims, notes, media, links, and package sentinels.",
        "Revenue is 42, retention is 68%, and the evidence window ends 2026-06-30.",
        "Preserve wording, numbers, chart values, citations, notes, and object identity when requested.",
        "Quarterly values are Q1 42, Q2 57, Q3 68. Caveat: values are illustrative fixture data.",
        "Signal input becomes a decision loop and then a measured outcome.",
        "This hidden slide is intentionally present and must not disappear silently.",
        "Approve the next operating cycle. The subtitle below is the precision-edit target.",
        "Citation: Example Evidence Register, accessed 2026-07-10.",
        'Customer quote: "The workflow became predictable without losing judgment."',
        "Owner: leadership team. Due date: 2026-08-15.",
    ]
    while len(bodies) < slide_count:
        bodies.append(f"Locked source content for slide {len(bodies) + 1}; metric {100 + len(bodies)}.")

    path.parent.mkdir(parents=True, exist_ok=True)
    with DeterministicZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types(slide_count))
        zf.writestr("_rels/.rels", relationships([
            ("rIdOffice", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument", "ppt/presentation.xml", None),
            ("rIdCore", "http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties", "docProps/core.xml", None),
            ("rIdApp", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties", "docProps/app.xml", None),
            ("rIdCustom", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/custom-properties", "docProps/custom.xml", None),
        ]))
        zf.writestr("ppt/presentation.xml", presentation_xml(slide_count))
        pres_rels = [
            (f"rId{index}", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide", f"slides/slide{index}.xml", None)
            for index in range(1, slide_count + 1)
        ]
        pres_rels.extend([
            ("rIdMaster", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster", "slideMasters/slideMaster1.xml", None),
            ("rIdNotesMaster", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesMaster", "notesMasters/notesMaster1.xml", None),
        ])
        zf.writestr("ppt/_rels/presentation.xml.rels", relationships(pres_rels))
        zf.writestr("ppt/slideMasters/slideMaster1.xml", master_xml())
        zf.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", relationships([
            ("rIdLayout", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout", "../slideLayouts/slideLayout1.xml", None),
            ("rIdTheme", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme", "../theme/theme1.xml", None),
        ]))
        zf.writestr("ppt/slideLayouts/slideLayout1.xml", layout_xml())
        zf.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", relationships([
            ("rIdMaster", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster", "../slideMasters/slideMaster1.xml", None),
        ]))
        zf.writestr("ppt/notesMasters/notesMaster1.xml", notes_master_xml())
        zf.writestr("ppt/notesMasters/_rels/notesMaster1.xml.rels", relationships([
            ("rIdTheme", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme", "../theme/theme1.xml", None),
        ]))
        zf.writestr("ppt/theme/theme1.xml", theme_xml())
        zf.writestr("ppt/charts/chart1.xml", chart_xml())
        zf.writestr("ppt/media/brand.png", PNG)

        for index in range(1, slide_count + 1):
            board_target = kind == "board" and index == 7
            zf.writestr(
                f"ppt/slides/slide{index}.xml",
                slide_xml(index, titles[index - 1], bodies[index - 1], board_target=board_target),
            )
            slide_rels = [
                ("rIdLayout", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout", "../slideLayouts/slideLayout1.xml", None),
                ("rIdImage", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image", "../media/brand.png", None),
                ("rIdNotes", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide", f"../notesSlides/notesSlide{index}.xml", None),
            ]
            if index == 4:
                slide_rels.append(("rIdChart", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart", "../charts/chart1.xml", None))
            if index == 8:
                slide_rels.append(("rIdLink", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", "https://example.com/evidence", "External"))
            zf.writestr(f"ppt/slides/_rels/slide{index}.xml.rels", relationships(slide_rels))

            note = f"Speaker note {index}: preserve this talk track. Transition to slide {index + 1 if index < slide_count else 1}."
            zf.writestr(f"ppt/notesSlides/notesSlide{index}.xml", notes_xml(index, note))
            zf.writestr(f"ppt/notesSlides/_rels/notesSlide{index}.xml.rels", relationships([
                ("rIdSlide", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide", f"../slides/slide{index}.xml", None),
                ("rIdNotesMaster", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesMaster", "../notesMasters/notesMaster1.xml", None),
            ]))

        for name, value in properties(title, slide_count).items():
            zf.writestr(name, value)


def main() -> None:
    write_fixture(OUTPUT / "annual_strategy_source.pptx", "Annual Strategy Source", 14, "strategy")
    write_fixture(OUTPUT / "sales_redesign_source.pptx", "Sales Redesign Source", 18, "sales")
    write_fixture(OUTPUT / "board_deck.pptx", "Board Deck", 10, "board")


if __name__ == "__main__":
    main()
