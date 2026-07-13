#!/usr/bin/env python3
"""Render a PPTX to per-slide PNGs and an HTML contact sheet."""

from __future__ import annotations

import argparse
import base64
import html
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence


DEFAULT_DPI = 144
COMMAND_TIMEOUT_SECONDS = 180
MANIFEST_NAME = "render-manifest.json"
RECOVERY_INFO_NAME = "recovery.json"


class RenderError(RuntimeError):
    """A user-actionable rendering failure."""


@dataclass(frozen=True)
class Tool:
    name: str
    path: str


@dataclass(frozen=True)
class RenderedSlide:
    page: int
    path: Path
    width: int
    height: int


def executable(names: Sequence[str], candidates: Sequence[Path] = ()) -> Optional[Tool]:
    for name in names:
        path = shutil.which(name)
        if path:
            return Tool(name=name, path=str(Path(path).resolve()))
    for candidate in candidates:
        expanded = candidate.expanduser()
        if expanded.is_file() and os.access(expanded, os.X_OK):
            return Tool(name=expanded.name, path=str(expanded.resolve()))
    return None


def libreoffice_tool() -> Optional[Tool]:
    candidates = [
        Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"),
        Path("~/Applications/LibreOffice.app/Contents/MacOS/soffice"),
        Path("/opt/libreoffice/program/soffice"),
        Path("/usr/lib/libreoffice/program/soffice"),
    ]
    if os.name == "nt":
        for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)"):
            root = os.environ.get(variable)
            if root:
                candidates.append(Path(root) / "LibreOffice" / "program" / "soffice.exe")
    return executable(("soffice", "libreoffice"), candidates)


def poppler_tool() -> Optional[Tool]:
    return executable(("pdftoppm",))


def command_detail(completed: subprocess.CompletedProcess[str]) -> str:
    output = (completed.stderr or completed.stdout or "").strip()
    if not output:
        return "The command produced no diagnostic output."
    lines = output.splitlines()
    compact = "\n".join(lines[-12:])
    return compact[-2000:]


def run_command(command: Sequence[str], purpose: str) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            list(command),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=COMMAND_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RenderError(f"{purpose} could not start because {command[0]!r} was not found.") from exc
    except subprocess.TimeoutExpired as exc:
        rendered = shlex.join(str(part) for part in command)
        raise RenderError(
            f"{purpose} timed out after {COMMAND_TIMEOUT_SECONDS} seconds. Command: {rendered}"
        ) from exc
    if completed.returncode != 0:
        rendered = shlex.join(str(part) for part in command)
        raise RenderError(
            f"{purpose} failed with exit code {completed.returncode}.\n"
            f"Command: {rendered}\n{command_detail(completed)}"
        )
    return completed


def parse_slides(value: Optional[str]) -> Optional[list[int]]:
    if value is None or value.strip().lower() == "all":
        return None
    pages: set[int] = set()
    for token in value.split(","):
        token = token.strip()
        if not token:
            raise argparse.ArgumentTypeError("--slides contains an empty item")
        if re.fullmatch(r"\d+", token):
            page = int(token)
            if page < 1:
                raise argparse.ArgumentTypeError("slide numbers start at 1")
            pages.add(page)
            continue
        match = re.fullmatch(r"(\d+)\s*-\s*(\d+)", token)
        if not match:
            raise argparse.ArgumentTypeError(
                f"invalid slide selector {token!r}; use values such as 1,3-5"
            )
        start, end = (int(part) for part in match.groups())
        if start < 1 or end < 1:
            raise argparse.ArgumentTypeError("slide numbers start at 1")
        if end < start:
            raise argparse.ArgumentTypeError(f"slide range {token!r} is descending")
        pages.update(range(start, end + 1))
    if not pages:
        raise argparse.ArgumentTypeError("--slides did not select any slides")
    return sorted(pages)


def convert_pptx_to_pdf(source: Path, work_dir: Path) -> tuple[Path, Tool]:
    tool = libreoffice_tool()
    if tool is None:
        raise RenderError(
            "PPTX rendering requires LibreOffice, but neither `soffice` nor `libreoffice` "
            "was found. Install LibreOffice and put its executable on PATH. On macOS, the "
            "standard /Applications/LibreOffice.app location is also detected automatically."
        )

    output_dir = work_dir / "pdf"
    profile_dir = work_dir / "libreoffice-profile"
    output_dir.mkdir(parents=True, exist_ok=True)
    profile_dir.mkdir(parents=True, exist_ok=True)
    command = [
        tool.path,
        f"-env:UserInstallation={profile_dir.resolve().as_uri()}",
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        str(output_dir),
        str(source),
    ]
    completed = run_command(command, "LibreOffice PPTX-to-PDF conversion")
    expected = output_dir / f"{source.stem}.pdf"
    if expected.is_file():
        return expected, tool
    candidates = sorted(output_dir.glob("*.pdf"))
    if len(candidates) == 1:
        return candidates[0], tool
    detail = command_detail(completed)
    raise RenderError(
        "LibreOffice exited successfully but did not create the expected PDF "
        f"{expected.name!r}.\n{detail}"
    )


def numbered_pngs(directory: Path, prefix: str) -> list[tuple[int, Path]]:
    pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)\.png$", re.IGNORECASE)
    found = []
    for path in directory.glob(f"{prefix}-*.png"):
        match = pattern.match(path.name)
        if match:
            found.append((int(match.group(1)), path))
    return sorted(found, key=lambda item: item[0])


def render_with_pdftoppm(
    tool: Tool, pdf: Path, work_dir: Path, pages: Optional[list[int]], dpi: int
) -> list[tuple[int, Path]]:
    output_dir = work_dir / "png"
    output_dir.mkdir(parents=True, exist_ok=True)
    if pages is None:
        prefix = output_dir / "page"
        run_command(
            [tool.path, "-png", "-r", str(dpi), str(pdf), str(prefix)],
            "Poppler PDF rendering",
        )
        rendered = numbered_pngs(output_dir, "page")
        if not rendered:
            raise RenderError(
                "`pdftoppm` exited successfully but produced no PNG pages. "
                "The PDF may be empty or unreadable."
            )
        return rendered

    rendered = []
    for page in pages:
        prefix = output_dir / f"selected-{page:06d}"
        try:
            run_command(
                [
                    tool.path,
                    "-png",
                    "-r",
                    str(dpi),
                    "-f",
                    str(page),
                    "-l",
                    str(page),
                    "-singlefile",
                    str(pdf),
                    str(prefix),
                ],
                f"Poppler rendering of requested slide {page}",
            )
        except RenderError as exc:
            raise RenderError(
                f"Requested slide {page} could not be rendered. Check that the PDF contains "
                f"that page.\n{exc}"
            ) from exc
        output = prefix.with_suffix(".png")
        if not output.is_file():
            raise RenderError(
                f"`pdftoppm` did not produce an image for requested slide {page}. "
                "Check that the PDF contains that page."
            )
        rendered.append((page, output))
    return rendered


def render_pdf_intermediate(
    pdf: Path, work_dir: Path, pages: Optional[list[int]], dpi: int
) -> tuple[list[tuple[int, Path]], Tool]:
    tool = poppler_tool()
    if tool is None:
        raise RenderError(
            "PPTX visual rendering requires Poppler's `pdftoppm`, but it was not found "
            "on PATH. Install Poppler and retry."
        )
    return render_with_pdftoppm(tool, pdf, work_dir, pages, dpi), tool


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) < 24 or not header.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RenderError(f"The renderer produced a non-PNG or truncated file: {path}")
    width = int.from_bytes(header[16:20], "big")
    height = int.from_bytes(header[20:24], "big")
    if width < 1 or height < 1:
        raise RenderError(f"The renderer produced a PNG with invalid dimensions: {path}")
    return width, height


def copy_rendered_pages(rendered: list[tuple[int, Path]], output_dir: Path) -> list[RenderedSlide]:
    output_dir.mkdir(parents=True, exist_ok=True)
    slides = []
    for page, source in rendered:
        destination = output_dir / f"slide-{page:03d}.png"
        shutil.copyfile(source, destination)
        width, height = png_size(destination)
        slides.append(RenderedSlide(page, destination, width, height))
    return slides


def manifest_owned_files(manifest_path: Path) -> Optional[set[str]]:
    """Return files owned by a structurally valid render manifest."""

    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("schema_version") != 1 or payload.get("generator") != "render_slides.py":
        return None

    slides = payload.get("slides")
    contact_sheet = payload.get("contact_sheet")
    if not isinstance(slides, list) or not slides or not isinstance(contact_sheet, dict):
        return None

    owned = {MANIFEST_NAME}
    pages: set[int] = set()
    for slide in slides:
        if not isinstance(slide, dict):
            return None
        page = slide.get("page")
        filename = slide.get("file")
        if not isinstance(page, int) or isinstance(page, bool) or page < 1 or page in pages:
            return None
        expected = f"slide-{page:03d}.png"
        if filename != expected or filename in owned:
            return None
        pages.add(page)
        owned.add(filename)

    contact_file = contact_sheet.get("file")
    contact_format = contact_sheet.get("format")
    expected_contact = {
        "png": "contact-sheet.png",
        "html": "contact-sheet.html",
    }.get(contact_format)
    if (
        expected_contact is None
        or not isinstance(contact_file, str)
        or contact_file != expected_contact
        or contact_file in owned
    ):
        return None
    owned.add(contact_file)
    return owned


def path_exists(path: Path) -> bool:
    """Treat broken symlinks as existing output collisions."""

    return path.exists() or path.is_symlink()


def persist_recovery_bundle(
    backup_dir: Path,
    output_dir: Path,
    *,
    original_error: BaseException,
    rollback_errors: list[str],
) -> tuple[Optional[Path], Optional[str]]:
    """Move rollback evidence outside the temporary transaction directory."""

    metadata_error = None
    try:
        retained_files = sorted(path.name for path in backup_dir.iterdir())
    except BaseException as exc:
        retained_files = []
        metadata_error = f"could not list retained files: {exc}"
    recovery_metadata = {
        "schema_version": 1,
        "generator": "render_slides.py",
        "output_dir": str(output_dir),
        "retained_files": retained_files,
        "original_error": f"{type(original_error).__name__}: {original_error}",
        "rollback_errors": rollback_errors,
        "instructions": (
            "Files in this directory are the prior render outputs that could not be "
            "restored automatically. Inspect recovery.json, then move the required files "
            "back into output_dir before rendering again."
        ),
    }
    try:
        (backup_dir / RECOVERY_INFO_NAME).write_text(
            json.dumps(recovery_metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except BaseException as exc:
        write_error = f"could not write {RECOVERY_INFO_NAME}: {exc}"
        metadata_error = f"{metadata_error}; {write_error}" if metadata_error else write_error

    recovery_dir = output_dir.with_name(
        f"{output_dir.name}.render-recovery-{uuid.uuid4().hex[:12]}"
    )
    try:
        os.replace(backup_dir, recovery_dir)
        return recovery_dir, metadata_error
    except BaseException as move_exc:
        try:
            shutil.copytree(backup_dir, recovery_dir)
            detail = f"atomic recovery move failed and a copy was retained instead: {move_exc}"
            if metadata_error:
                detail = f"{metadata_error}; {detail}"
            return recovery_dir, detail
        except BaseException as copy_exc:
            detail = (
                f"could not persist rollback evidence beside the output directory: "
                f"move failed ({move_exc}); copy failed ({copy_exc})"
            )
            if metadata_error:
                detail = f"{metadata_error}; {detail}"
            return None, detail


def annotate_interrupted_publish(
    exc: BaseException,
    detail: str,
    recovery_dir: Optional[Path],
) -> None:
    """Attach recovery context while preserving interruption semantics."""

    if hasattr(exc, "add_note"):
        exc.add_note(detail)
    else:  # pragma: no cover - Python before 3.11.
        exc.args = (*exc.args, detail)
    if recovery_dir is not None:
        setattr(exc, "render_recovery_dir", str(recovery_dir))


def publish_staged_render(staging_dir: Path, output_dir: Path) -> Path:
    """Publish a complete staged render and leave unrelated files untouched.

    Every file is replaced atomically on the destination filesystem and the
    manifest is published last as the commit marker. Existing generated files
    are eligible for replacement or removal only when a valid prior manifest
    claims them. A best-effort rollback restores the prior bundle if publishing
    fails after it has started.
    """

    staged_manifest = staging_dir / MANIFEST_NAME
    new_owned = manifest_owned_files(staged_manifest)
    if new_owned is None:
        raise RenderError("The staged render manifest is missing or invalid; nothing was published.")
    missing_staged = sorted(name for name in new_owned if not (staging_dir / name).is_file())
    if missing_staged:
        raise RenderError(
            "The staged render is incomplete; missing: " + ", ".join(missing_staged)
        )

    existing_manifest = output_dir / MANIFEST_NAME
    old_owned: set[str] = set()
    if path_exists(existing_manifest):
        if not existing_manifest.is_file():
            raise RenderError(
                f"Refusing to replace {existing_manifest}: it is not a regular manifest file."
            )
        parsed = manifest_owned_files(existing_manifest)
        if parsed is None:
            raise RenderError(
                f"Refusing to replace outputs in {output_dir}: {MANIFEST_NAME} is not a "
                "valid render_slides.py manifest."
            )
        old_owned = parsed

    collisions = sorted(
        name
        for name in new_owned
        if path_exists(output_dir / name) and name not in old_owned
    )
    if collisions:
        raise RenderError(
            "Refusing to overwrite files not owned by a valid prior render manifest: "
            + ", ".join(collisions)
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    backup_dir = staging_dir.parent / "previous-render"
    backup_dir.mkdir()

    try:
        for name in sorted(old_owned):
            destination = output_dir / name
            if path_exists(destination):
                if not destination.is_file():
                    raise RenderError(
                        f"Refusing to replace managed output {destination}: it is not a regular file."
                    )
                os.replace(destination, backup_dir / name)

        publish_order = sorted(new_owned - {MANIFEST_NAME}) + [MANIFEST_NAME]
        for name in publish_order:
            os.replace(staging_dir / name, output_dir / name)
    except BaseException as exc:
        rollback_errors: list[str] = []
        for name in sorted(new_owned, reverse=True):
            staged = staging_dir / name
            destination = output_dir / name
            if path_exists(staged):
                continue
            try:
                if path_exists(destination):
                    destination.unlink()
            except BaseException as rollback_exc:
                rollback_errors.append(f"remove {name}: {rollback_exc}")
        for name in sorted(old_owned):
            backup = backup_dir / name
            try:
                if path_exists(backup):
                    os.replace(backup, output_dir / name)
            except BaseException as rollback_exc:
                rollback_errors.append(f"restore {name}: {rollback_exc}")

        detail = f"Publishing the staged render failed: {exc}"
        recovery_dir = None
        if rollback_errors:
            detail += "\nRollback also reported: " + "; ".join(rollback_errors)
            recovery_dir, recovery_error = persist_recovery_bundle(
                backup_dir,
                output_dir,
                original_error=exc,
                rollback_errors=rollback_errors,
            )
            if recovery_dir is not None:
                detail += f"\nRecovery bundle: {recovery_dir}"
            if recovery_error:
                detail += f"\nRecovery warning: {recovery_error}"

        if isinstance(exc, (KeyboardInterrupt, SystemExit, GeneratorExit)):
            annotate_interrupted_publish(exc, detail, recovery_dir)
            raise
        raise RenderError(detail) from exc

    return output_dir / MANIFEST_NAME


def html_contact_sheet(slides: list[RenderedSlide], destination: Path, source_name: str) -> dict[str, str]:
    figures = []
    for slide in slides:
        encoded = base64.b64encode(slide.path.read_bytes()).decode("ascii")
        figures.append(
            "<figure>"
            f'<img src="data:image/png;base64,{encoded}" '
            f'width="{slide.width}" height="{slide.height}" alt="Slide {slide.page}">'
            f"<figcaption>Slide {slide.page}</figcaption>"
            "</figure>"
        )
    title = html.escape(f"Contact sheet: {source_name}")
    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
html {{ color-scheme: light; font-family: system-ui, sans-serif; background: #e8eaed; }}
body {{ margin: 0; padding: 24px; }}
h1 {{ margin: 0 0 20px; font-size: 20px; font-weight: 650; }}
main {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 20px; }}
figure {{ margin: 0; min-width: 0; }}
img {{ display: block; width: 100%; height: auto; background: white; box-shadow: 0 1px 4px #0003; }}
figcaption {{ padding-top: 8px; color: #303134; font-size: 13px; }}
@media print {{ body {{ padding: 0; }} main {{ grid-template-columns: repeat(3, 1fr); }} }}
</style>
</head>
<body>
<h1>{title}</h1>
<main>{''.join(figures)}</main>
</body>
</html>
"""
    destination.write_text(document, encoding="utf-8")
    return {"file": destination.name, "format": "html", "renderer": "stdlib-data-uri"}


def create_contact_sheet(
    slides: list[RenderedSlide], output_dir: Path, source_name: str
) -> tuple[dict[str, str], list[str]]:
    html_destination = output_dir / "contact-sheet.html"
    return html_contact_sheet(slides, html_destination, source_name), []


def write_manifest(
    source: Path,
    output_dir: Path,
    requested_pages: Optional[list[int]],
    dpi: int,
    slides: list[RenderedSlide],
    pdf_tool: Tool,
    office_tool: Optional[Tool],
    contact_sheet: dict[str, str],
    warnings: list[str],
) -> Path:
    manifest = {
        "schema_version": 1,
        "generator": "render_slides.py",
        "source": {"path": str(source), "type": "pptx"},
        "request": {"slides": requested_pages if requested_pages is not None else "all", "dpi": dpi},
        "tools": {
            "pptx_to_pdf": (
                {"name": office_tool.name, "path": office_tool.path} if office_tool else None
            ),
            "pdf_to_png": {"name": pdf_tool.name, "path": pdf_tool.path},
            "contact_sheet": contact_sheet["renderer"],
        },
        "slides": [
            {
                "page": slide.page,
                "file": slide.path.name,
                "width": slide.width,
                "height": slide.height,
            }
            for slide in slides
        ],
        "contact_sheet": contact_sheet,
        "warnings": warnings,
    }
    destination = output_dir / MANIFEST_NAME
    destination.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return destination


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render a PPTX to per-slide PNGs, an HTML contact sheet, and a manifest."
    )
    parser.add_argument("input", type=Path, help="source .pptx file")
    parser.add_argument(
        "--out-dir",
        type=Path,
        help="output directory (default: <input-stem>-rendered beside the source)",
    )
    parser.add_argument(
        "--slides",
        metavar="SELECTOR",
        help="optional 1-based pages such as 1,3-5; omit or use 'all' for every page",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=DEFAULT_DPI,
        help=f"PNG resolution in dots per inch (default: {DEFAULT_DPI})",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    source = args.input.expanduser().resolve()
    if not source.is_file():
        parser.error(f"input file does not exist: {source}")
    if source.suffix.lower() != ".pptx":
        parser.error("input must have a .pptx extension")
    if args.dpi < 36 or args.dpi > 600:
        parser.error("--dpi must be between 36 and 600")
    try:
        requested_pages = parse_slides(args.slides)
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))

    output_dir = (
        args.out_dir.expanduser().resolve()
        if args.out_dir
        else source.with_name(f"{source.stem}-rendered")
    )
    try:
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix=f".{output_dir.name}.render-", dir=output_dir.parent
        ) as temporary:
            transaction_dir = Path(temporary)
            work_dir = transaction_dir / "work"
            staging_dir = transaction_dir / "staged"
            work_dir.mkdir()
            staging_dir.mkdir()
            pdf, office_tool = convert_pptx_to_pdf(source, work_dir)
            rendered, pdf_tool = render_pdf_intermediate(
                pdf, work_dir, requested_pages, args.dpi
            )
            slides = copy_rendered_pages(rendered, staging_dir)
            contact_sheet, warnings = create_contact_sheet(slides, staging_dir, source.name)
            write_manifest(
                source,
                staging_dir,
                requested_pages,
                args.dpi,
                slides,
                pdf_tool,
                office_tool,
                contact_sheet,
                warnings,
            )
            manifest = publish_staged_render(staging_dir, output_dir)
    except (OSError, RenderError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"Rendered {len(slides)} slide(s) to {output_dir}")
    print(f"Contact sheet: {output_dir / contact_sheet['file']}")
    print(f"Manifest: {manifest}")
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
