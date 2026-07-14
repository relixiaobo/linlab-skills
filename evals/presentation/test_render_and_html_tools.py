#!/usr/bin/env python3
"""Focused regression tests for presentation render and HTML tooling."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
RENDER_TOOL = ROOT / "presentation" / "scripts" / "render_slides.py"
HTML_TOOL = ROOT / "presentation" / "scripts" / "html_tool.mjs"
HTML_TEMPLATE_ROOT = ROOT / "presentation" / "assets" / "templates" / "html-studio"
HTML_TEMPLATE = HTML_TEMPLATE_ROOT / "deck.html"


def load_render_tool():
    spec = importlib.util.spec_from_file_location("presentation_render_slides", RENDER_TOOL)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not import {RENDER_TOOL}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


render_slides = load_render_tool()


def write_render_bundle(
    directory: Path,
    *,
    pages: list[int],
    contact_format: str = "html",
    marker: str,
) -> dict[str, bytes]:
    directory.mkdir(parents=True, exist_ok=True)
    files: dict[str, bytes] = {}
    slides = []
    for page in pages:
        filename = f"slide-{page:03d}.png"
        content = f"{marker}:slide:{page}".encode()
        (directory / filename).write_bytes(content)
        files[filename] = content
        slides.append({"page": page, "file": filename, "width": 1, "height": 1})

    contact_file = f"contact-sheet.{contact_format}"
    contact_content = f"{marker}:contact".encode()
    (directory / contact_file).write_bytes(contact_content)
    files[contact_file] = contact_content
    manifest = {
        "schema_version": 1,
        "generator": "render_slides.py",
        "source": {"path": "fixture.pdf", "type": "pdf"},
        "request": {"slides": pages, "dpi": 72},
        "tools": {},
        "slides": slides,
        "contact_sheet": {
            "file": contact_file,
            "format": contact_format,
            "renderer": "test",
        },
        "warnings": [],
    }
    manifest_bytes = (json.dumps(manifest, indent=2) + "\n").encode()
    (directory / render_slides.MANIFEST_NAME).write_bytes(manifest_bytes)
    files[render_slides.MANIFEST_NAME] = manifest_bytes
    return files


def read_files(directory: Path, names: set[str]) -> dict[str, bytes]:
    return {name: (directory / name).read_bytes() for name in names}


def one_page_pdf() -> bytes:
    content = b"0.95 g 0 0 720 405 re f\n"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 720 405] /Contents 4 0 R >>",
        f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"endstream",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode())
        output.extend(body)
        output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(output)


class RenderPublishTests(unittest.TestCase):
    def test_real_pdf_render_publishes_complete_bundle(self) -> None:
        if render_slides.pdf_renderer_tool() is None:
            self.skipTest("pdftoppm or mutool is unavailable")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "one-page.pdf"
            output = root / "rendered"
            source.write_bytes(one_page_pdf())

            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                result = render_slides.main(
                    [str(source), "--out-dir", str(output), "--dpi", "72"]
                )

            self.assertEqual(result, 0)
            manifest = json.loads(
                (output / render_slides.MANIFEST_NAME).read_text(encoding="utf-8")
            )
            self.assertEqual([slide["page"] for slide in manifest["slides"]], [1])
            self.assertTrue((output / "slide-001.png").is_file())
            self.assertTrue((output / manifest["contact_sheet"]["file"]).is_file())

    def test_unowned_filename_collision_is_rejected_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            staging = root / "transaction" / "staged"
            output = root / "output"
            write_render_bundle(staging, pages=[1], marker="new")
            output.mkdir()
            sentinel = output / "slide-001.png"
            sentinel.write_bytes(b"user-owned")

            with self.assertRaisesRegex(render_slides.RenderError, "not owned"):
                render_slides.publish_staged_render(staging, output)

            self.assertEqual(sentinel.read_bytes(), b"user-owned")
            self.assertFalse((output / render_slides.MANIFEST_NAME).exists())

    def test_invalid_old_manifest_does_not_authorize_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            staging = root / "transaction" / "staged"
            output = root / "output"
            write_render_bundle(staging, pages=[1], marker="new")
            output.mkdir()
            sentinel = output / "slide-001.png"
            sentinel.write_bytes(b"user-owned")
            invalid_manifest = output / render_slides.MANIFEST_NAME
            invalid_manifest.write_text("{}\n", encoding="utf-8")

            with self.assertRaisesRegex(render_slides.RenderError, "not a valid"):
                render_slides.publish_staged_render(staging, output)

            self.assertEqual(sentinel.read_bytes(), b"user-owned")
            self.assertEqual(invalid_manifest.read_text(encoding="utf-8"), "{}\n")

    def test_success_replaces_only_files_claimed_by_old_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "output"
            staging = root / "transaction" / "staged"
            write_render_bundle(
                output,
                pages=[1, 2],
                contact_format="png",
                marker="old",
            )
            sentinel = output / "slide-999.png"
            sentinel.write_bytes(b"unrelated")
            new_files = write_render_bundle(staging, pages=[1], marker="new")

            render_slides.publish_staged_render(staging, output)

            self.assertEqual((output / "slide-001.png").read_bytes(), new_files["slide-001.png"])
            self.assertEqual(sentinel.read_bytes(), b"unrelated")
            self.assertFalse((output / "slide-002.png").exists())
            self.assertFalse((output / "contact-sheet.png").exists())
            self.assertTrue((output / "contact-sheet.html").is_file())

    def test_publish_error_rolls_back_complete_previous_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "output"
            staging = root / "transaction" / "staged"
            old_files = write_render_bundle(output, pages=[1], marker="old")
            write_render_bundle(staging, pages=[1], marker="new")
            real_replace = os.replace

            def fail_on_staged_slide(source, destination):
                source_path = Path(source)
                if source_path.parent == staging and source_path.name == "slide-001.png":
                    raise OSError("injected publish failure")
                return real_replace(source, destination)

            with mock.patch.object(render_slides.os, "replace", side_effect=fail_on_staged_slide):
                with self.assertRaisesRegex(render_slides.RenderError, "Publishing"):
                    render_slides.publish_staged_render(staging, output)

            self.assertEqual(read_files(output, set(old_files)), old_files)

    def test_keyboard_interrupt_rolls_back_complete_previous_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "output"
            staging = root / "transaction" / "staged"
            old_files = write_render_bundle(output, pages=[1], marker="old")
            write_render_bundle(staging, pages=[1], marker="new")
            real_replace = os.replace

            def interrupt_on_staged_slide(source, destination):
                source_path = Path(source)
                if source_path.parent == staging and source_path.name == "slide-001.png":
                    real_replace(source, destination)
                    raise KeyboardInterrupt("injected interrupt")
                return real_replace(source, destination)

            with mock.patch.object(
                render_slides.os,
                "replace",
                side_effect=interrupt_on_staged_slide,
            ):
                with self.assertRaises(KeyboardInterrupt):
                    render_slides.publish_staged_render(staging, output)

            self.assertEqual(read_files(output, set(old_files)), old_files)
            self.assertEqual(list(root.glob("output.render-recovery-*")), [])

    def test_restore_failure_persists_recovery_bundle_beside_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "output"
            staging = root / "transaction" / "staged"
            old_files = write_render_bundle(output, pages=[1], marker="old")
            write_render_bundle(staging, pages=[1], marker="new")
            backup_dir = staging.parent / "previous-render"
            real_replace = os.replace

            def fail_publish_and_one_restore(source, destination):
                source_path = Path(source)
                destination_path = Path(destination)
                if source_path.parent == staging and source_path.name == "slide-001.png":
                    raise OSError("injected publish failure")
                if (
                    source_path.parent == backup_dir
                    and source_path.name == "slide-001.png"
                    and destination_path.parent == output
                ):
                    raise OSError("injected restore failure")
                return real_replace(source, destination)

            with mock.patch.object(
                render_slides.os,
                "replace",
                side_effect=fail_publish_and_one_restore,
            ):
                with self.assertRaisesRegex(render_slides.RenderError, "Recovery bundle") as raised:
                    render_slides.publish_staged_render(staging, output)

            recovery_dirs = list(root.glob("output.render-recovery-*"))
            self.assertEqual(len(recovery_dirs), 1, str(raised.exception))
            recovery = recovery_dirs[0]
            shutil.rmtree(staging.parent)
            self.assertEqual((recovery / "slide-001.png").read_bytes(), old_files["slide-001.png"])
            recovery_info = json.loads(
                (recovery / render_slides.RECOVERY_INFO_NAME).read_text(encoding="utf-8")
            )
            self.assertIn("restore slide-001.png", " ".join(recovery_info["rollback_errors"]))
            self.assertIn(str(recovery), str(raised.exception))

    def test_render_failure_preserves_existing_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "output"
            old_files = write_render_bundle(output, pages=[1], marker="old")
            invalid_pdf = root / "invalid.pdf"
            invalid_pdf.write_bytes(b"not a PDF")

            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                result = render_slides.main(
                    [str(invalid_pdf), "--out-dir", str(output), "--dpi", "72"]
                )

            self.assertEqual(result, 2)
            self.assertEqual(read_files(output, set(old_files)), old_files)


class HtmlInspectorTests(unittest.TestCase):
    def inspect(self, html: str, expected_returncode: int = 0) -> dict:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "deck.html"
            report = root / "report.json"
            source.write_text(html, encoding="utf-8")
            completed = subprocess.run(
                ["node", str(HTML_TOOL), "inspect", str(source), "--out", str(report)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                completed.returncode,
                expected_returncode,
                completed.stderr or completed.stdout,
            )
            return json.loads(report.read_text(encoding="utf-8"))

    def test_wrapped_div_and_custom_slides_receive_per_slide_checks(self) -> None:
        report = self.inspect(
            """<!doctype html>
<html>
<head><style>.deck-stage { aspect-ratio: 16 / 9; }</style></head>
<body>
  <main class="deck-stage" data-deck>
    <div class="wrapper">
      <div class="slide" data-slide>
        <figure>Visual</figure>
        <ul><li>A</li><li>B</li><li>C</li><li>D</li><li>E</li></ul>
      </div>
    </div>
    <article data-slide data-layout="story-map">
      <svg aria-label="Map"></svg>
      <aside class="speaker-notes" hidden>Presenter notes for private use</aside>
    </article>
    <section class="slide" data-layout="statement">
      <p>Closing thought</p>
    </section>
  </main>
  <script>
    const ignored = '<div class="slide">not markup</div>';
    window.addEventListener('keydown', () => ignored);
  </script>
</body>
</html>
"""
        )

        self.assertEqual(report["slide_count"], 3)
        self.assertEqual(report["missing_layout_slides"], [1])
        self.assertEqual(report["bullet_dense_slides"], [1])
        self.assertEqual(report["notes_slides"], [2])
        self.assertEqual(report["unhidden_speaker_notes_slides"], [])
        self.assertEqual(report["visible_presenter_text_slides"], [])
        self.assertEqual(report["custom_layouts"], ["story-map"])
        self.assertEqual(report["visual_slide_count"], 3)

    def test_nested_slide_is_an_error_and_data_slide_prefix_is_not_a_slide(self) -> None:
        report = self.inspect(
            """<!doctype html>
<html>
<head><style>.deck-stage { aspect-ratio: 16 / 9; }</style></head>
<body>
  <main class="deck-stage" data-deck>
    <div data-slide-index="99">Metadata only</div>
    <div class="wrapper">
      <section class="slide" data-layout="statement">
        <p>Outer page</p>
        <div class="wrapper">
          <article data-slide data-layout="statement"><p>Nested page</p></article>
        </div>
      </section>
    </div>
    <div data-slide data-layout="statement"><p>Second page</p></div>
  </main>
  <script>window.addEventListener('keydown', () => {});</script>
</body>
</html>
""",
            expected_returncode=1,
        )

        self.assertFalse(report["ok"])
        self.assertEqual(report["slide_count"], 2)
        self.assertEqual(report["deck_stage_count"], 1)
        self.assertIn("nested_slide_element_found", report["errors"])
        self.assertEqual(
            report["nested_slide_elements"],
            [{"element_index": 2, "tag": "article", "parent_element_index": 1}],
        )

    def test_speaker_notes_are_removed_from_audience_checks_but_legacy_notes_are_visible(self) -> None:
        report = self.inspect(
            """<!doctype html>
<html>
<head><style>.deck-stage { aspect-ratio: 16 / 9; }</style></head>
<body>
  <main class="deck-stage" data-deck>
    <section class="slide" data-layout="custom-composition">
      <p>Audience copy</p>
      <aside class="speaker-notes" hidden>
        <p>Presenter notes for private use</p>
        <figure>Private visual</figure>
        <ul><li>A</li><li>B</li><li>C</li><li>D</li><li>E</li></ul>
      </aside>
    </section>
    <section class="slide" data-layout="custom-composition">
      <p>Audience copy</p>
      <div class="notes">
        <p>Presenter notes legacy</p>
        <figure>Visible legacy visual</figure>
        <ul><li>A</li><li>B</li><li>C</li><li>D</li><li>E</li></ul>
      </div>
    </section>
  </main>
  <script>window.addEventListener('keydown', () => {});</script>
</body>
</html>
"""
        )

        self.assertEqual(report["notes_slides"], [1])
        self.assertEqual(report["unhidden_speaker_notes_slides"], [])
        self.assertEqual(report["text_only_slides"], [1])
        self.assertEqual(report["visual_slide_count"], 1)
        self.assertEqual(report["bullet_dense_slides"], [2])
        self.assertEqual(report["visible_presenter_text_slides"], [2])

    def test_speaker_notes_require_hidden_attribute_even_when_css_hides_them(self) -> None:
        body = """
<body>
  <main class="deck-stage" data-deck>
    <section class="slide" data-layout="statement">
      <p>Audience copy</p>
      <aside class="speaker-notes">Presenter notes</aside>
    </section>
  </main>
  <script>window.addEventListener('keydown', () => {});</script>
</body>
"""
        unhidden = self.inspect(
            "<!doctype html><html><head><style>.deck-stage { aspect-ratio: 16 / 9; }</style></head>"
            + body
            + "</html>",
            expected_returncode=1,
        )
        self.assertIn("speaker_notes_not_hidden", unhidden["errors"])
        self.assertEqual(unhidden["unhidden_speaker_notes_slides"], [1])

        hidden_by_css = self.inspect(
            "<!doctype html><html><head><style>"
            ".deck-stage { aspect-ratio: 16 / 9; } .speaker-notes { display: none; }"
            "</style></head>"
            + body
            + "</html>",
            expected_returncode=1,
        )
        self.assertIn("speaker_notes_not_hidden", hidden_by_css["errors"])
        self.assertEqual(hidden_by_css["unhidden_speaker_notes_slides"], [1])

        cascade_override = self.inspect(
            "<!doctype html><html><head><style>"
            ".deck-stage { aspect-ratio: 16 / 9; } "
            ".speaker-notes { display: none; } .speaker-notes { display: block; }"
            "</style></head>"
            + body
            + "</html>",
            expected_returncode=1,
        )
        self.assertIn("speaker_notes_not_hidden", cascade_override["errors"])
        self.assertEqual(cascade_override["unhidden_speaker_notes_slides"], [1])

    def test_non_16_9_fixed_stage_is_accepted(self) -> None:
        report = self.inspect(
            """<!doctype html>
<html>
<head><style>.deck-stage { width: 1200px; height: 900px; aspect-ratio: 4 / 3; }</style></head>
<body>
  <main class="deck-stage" data-deck>
    <section class="slide" data-layout="statement"><p>Four by three</p></section>
  </main>
  <script>window.addEventListener('keydown', () => {});</script>
</body>
</html>
"""
        )

        self.assertNotIn("missing_fixed_stage_hint", report["warnings"])

    def test_ratio_safe_image_contract_is_reported(self) -> None:
        report = self.inspect(
            """<!doctype html>
<html>
<head><style>
.deck-stage { aspect-ratio: 16 / 9; }
.media-frame { width: 640px; height: 360px; }
img[data-fit="cover"] { width: 100%; height: 100%; object-fit: cover; }
</style></head>
<body>
  <main class="deck-stage" data-deck data-asset-posture="mixed">
    <section class="slide" data-layout="hero-media">
      <figure class="media-frame">
        <img src="data:image/gif;base64,R0lGODlhAQABAAAAACw="
          alt="Relevant subject"
          data-asset-id="asset-subject"
          data-asset-role="subject"
          data-fit="cover"
          data-focal-point="50% 50%">
      </figure>
    </section>
  </main>
  <script>window.addEventListener('keydown', () => {});</script>
</body>
</html>
"""
        )

        self.assertEqual(report["asset_posture"], "mixed")
        self.assertEqual(report["image_count"], 1)
        self.assertEqual(report["media_bearing_slides"], [1])
        self.assertEqual(report["image_contract_issues"], [])

    def test_image_contract_and_required_media_are_blocking(self) -> None:
        missing_contract = self.inspect(
            """<!doctype html>
<html>
<head><style>.deck-stage { aspect-ratio: 16 / 9; }</style></head>
<body>
  <main class="deck-stage" data-deck data-asset-posture="visual">
    <section class="slide" data-layout="hero-media">
      <img src="data:image/gif;base64,R0lGODlhAQABAAAAACw=" alt="Subject">
    </section>
  </main>
  <script>window.addEventListener('keydown', () => {});</script>
</body>
</html>
""",
            expected_returncode=1,
        )
        self.assertIn("image_asset_contract_failed", missing_contract["errors"])
        self.assertEqual(
            missing_contract["image_contract_issues"][0]["issues"],
            ["missing_asset_id", "missing_asset_role", "missing_fit"],
        )

        missing_media = self.inspect(
            """<!doctype html>
<html>
<head><style>.deck-stage { aspect-ratio: 16 / 9; }</style></head>
<body>
  <main class="deck-stage" data-deck data-asset-posture="mixed">
    <section class="slide" data-layout="diagram"><svg aria-label="Diagram"></svg></section>
  </main>
  <script>window.addEventListener('keydown', () => {});</script>
</body>
</html>
""",
            expected_returncode=1,
        )
        self.assertIn("required_media_missing", missing_media["errors"])

    def test_studio_template_is_export_safe_and_inspectable(self) -> None:
        template = HTML_TEMPLATE.read_text(encoding="utf-8")
        for export_risk in (
            "linear-gradient",
            "::before",
            "::after",
            "border-left: solid",
            "border-right: solid",
        ):
            self.assertNotIn(export_risk, template)
        self.assertIn("export-mode", template)
        self.assertIn("window.__PRESENTATION_READY__", template)
        self.assertIn('data-asset-posture="analytical"', template)
        self.assertIn('class="speaker-notes" hidden', template)
        self.assertNotIn('class="notes"', template)
        self.assertEqual(template.count('class="slide"'), 5)

        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            shutil.copytree(HTML_TEMPLATE_ROOT, project, dirs_exist_ok=True)
            (project / "theme").mkdir()
            shutil.copy2(
                ROOT / "presentation" / "assets" / "themes" / "analytical-ledger" / "tokens.css",
                project / "theme" / "tokens.css",
            )
            result = subprocess.run(
                ["node", str(HTML_TOOL), "inspect", str(project / "deck.html")],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertTrue(report["ok"])
            self.assertEqual(report["layout_catalog_version"], "1.0")
            self.assertEqual(report["slide_count"], 5)
            self.assertEqual(report["warnings"], [])
            self.assertEqual(report["remote_dependency_references"], [])


if __name__ == "__main__":
    unittest.main()
