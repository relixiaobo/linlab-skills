#!/usr/bin/env python3
"""Check video-studio runtime dependencies."""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
from typing import Any


REQUIRED_BINS = ["ffmpeg", "ffprobe", "python3"]
# `manim` (math overlay engine) and `latex` (MathTex/Tex) are optional: only the
# manim math-overlay path needs them. `latex` covers the typical TeX entry point.
OPTIONAL_BINS = ["node", "npm", "npx", "manim", "latex"]
OPTIONAL_PY = ["pydantic", "srt", "PIL", "cv2", "numpy", "manim"]


def version_for(binary: str) -> str | None:
    path = shutil.which(binary)
    if not path:
        return None
    version_args = {
        "python3": ["--version"],
        "node": ["--version"],
        "npm": ["--version"],
        "npx": ["--version"],
        "manim": ["--version"],
        "latex": ["--version"],
    }.get(binary, ["-version"])
    try:
        proc = subprocess.run(
            [binary, *version_args],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=5,
        )
        first = proc.stdout.splitlines()[0] if proc.stdout else ""
        return first.strip() or path
    except Exception:
        return path


def ffmpeg_filters() -> dict[str, bool]:
    if not shutil.which("ffmpeg"):
        return {"subtitles": False, "overlay": False}
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-filters"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    available: set[str] = set()
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 3 and "->" in parts[2]:
            available.add(parts[1])
    return {
        "subtitles": "subtitles" in available,
        "overlay": "overlay" in available,
    }


def check() -> dict[str, Any]:
    bins = {}
    for name in REQUIRED_BINS + OPTIONAL_BINS:
        bins[name] = {
            "path": shutil.which(name),
            "version": version_for(name),
            "required": name in REQUIRED_BINS,
        }

    py = {}
    for name in OPTIONAL_PY:
        py[name] = importlib.util.find_spec(name) is not None
    filters = ffmpeg_filters()

    errors = [
        f"missing required binary: {name}"
        for name, info in bins.items()
        if info["required"] and not info["path"]
    ]

    warnings = []
    for name in OPTIONAL_BINS:
        if not bins[name]["path"]:
            warnings.append(f"optional binary not found: {name}")
    for name, available in py.items():
        if not available:
            warnings.append(f"optional Python package not found: {name}")
    if bins["ffmpeg"]["path"] and not filters["subtitles"]:
        warnings.append("FFmpeg subtitles filter not found; SRT burn-in will use Pillow image overlay fallback")
    if bins["ffmpeg"]["path"] and not filters["overlay"]:
        warnings.append("FFmpeg overlay filter not found; subtitle image fallback and overlays will fail")

    return {
        "status": "pass" if not errors else "fail",
        "binaries": bins,
        "pythonPackages": py,
        "ffmpegFilters": filters,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="Print JSON only")
    args = parser.parse_args()

    result = check()
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"video-studio doctor: {result['status'].upper()}")
        for name, info in result["binaries"].items():
            mark = "✓" if info["path"] else "✗"
            req = "required" if info["required"] else "optional"
            print(f"  {mark} {name} ({req}) {info['path'] or ''}")
        print("  ffmpeg filters:")
        for name, available in result["ffmpegFilters"].items():
            mark = "✓" if available else "✗"
            print(f"    {mark} {name}")
        for warning in result["warnings"]:
            print(f"  warning: {warning}")
        for error in result["errors"]:
            print(f"  error: {error}")

    return 0 if result["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
