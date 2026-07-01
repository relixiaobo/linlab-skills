#!/usr/bin/env python3
"""Validate video-studio render_manifest.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ALLOWED_ENGINES = {"ffmpeg", "remotion", "web-frames", "external"}
ALLOWED_FIT = {"cover", "contain", "stretch", "original"}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def validate(manifest: dict[str, Any], base: Path, allow_missing: bool) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    for key in ["version", "engine", "canvas", "sources", "clips", "output"]:
        if key not in manifest:
            errors.append(f"missing required key: {key}")

    engine = manifest.get("engine")
    if engine and engine not in ALLOWED_ENGINES:
        errors.append(f"invalid engine: {engine}")

    canvas = manifest.get("canvas", {})
    for key in ["width", "height", "fps"]:
        if key not in canvas:
            errors.append(f"canvas missing {key}")
        elif not isinstance(canvas[key], (int, float)) or canvas[key] <= 0:
            errors.append(f"canvas.{key} must be a positive number")

    source_ids = set()
    for i, source in enumerate(as_list(manifest.get("sources"))):
        sid = source.get("id")
        if not sid:
            errors.append(f"sources[{i}] missing id")
            continue
        if sid in source_ids:
            errors.append(f"duplicate source id: {sid}")
        source_ids.add(sid)
        path = source.get("path")
        if path and not allow_missing and not (base / path).exists():
            errors.append(f"source path not found: {path}")

    for i, clip in enumerate(as_list(manifest.get("clips"))):
        source = clip.get("source")
        if source not in source_ids:
            errors.append(f"clips[{i}] references unknown source: {source}")
        start = clip.get("start")
        end = clip.get("end")
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            errors.append(f"clips[{i}] start/end must be numeric")
        elif end <= start:
            errors.append(f"clips[{i}] end must be greater than start")
        fit = clip.get("fit", "cover")
        if fit not in ALLOWED_FIT:
            errors.append(f"clips[{i}] invalid fit: {fit}")

    subtitles = manifest.get("subtitles")
    if isinstance(subtitles, dict):
        if subtitles.get("path") and not allow_missing and not (base / subtitles["path"]).exists():
            warnings.append(f"subtitle path not found: {subtitles['path']}")
        if "sourceHasCaptions" in subtitles and not isinstance(subtitles["sourceHasCaptions"], bool):
            errors.append("subtitles.sourceHasCaptions must be a boolean")
        if subtitles.get("burnIn") and subtitles.get("sourceHasCaptions"):
            warnings.append(
                "subtitles.burnIn + sourceHasCaptions: burn-in will be SKIPPED to avoid double captions"
            )

    output = manifest.get("output", {})
    if not output.get("path"):
        errors.append("output.path is required")

    return {
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest")
    parser.add_argument("--base-dir", default=".")
    parser.add_argument("--allow-missing", action="store_true")
    parser.add_argument("--output", "-o")
    args = parser.parse_args()

    manifest_path = Path(args.manifest).expanduser().resolve()
    base = Path(args.base_dir).expanduser().resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    result = validate(manifest, base, args.allow_missing)
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0 if result["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
