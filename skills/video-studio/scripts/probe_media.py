#!/usr/bin/env python3
"""Probe media with ffprobe and emit normalized JSON."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


def run_ffprobe(path: Path) -> dict[str, Any]:
    if not shutil.which("ffprobe"):
        raise RuntimeError("ffprobe not found on PATH")
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "ffprobe failed")
    return json.loads(proc.stdout)


def normalize(raw: dict[str, Any], path: Path) -> dict[str, Any]:
    streams = raw.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    subtitle = [s for s in streams if s.get("codec_type") == "subtitle"]
    fmt = raw.get("format", {})
    duration = fmt.get("duration")
    try:
        duration_s = float(duration) if duration is not None else None
    except ValueError:
        duration_s = None

    width = video.get("width") if video else None
    height = video.get("height") if video else None
    fps = None
    if video:
        rate = video.get("avg_frame_rate") or video.get("r_frame_rate")
        if rate and "/" in rate:
            num, den = rate.split("/", 1)
            try:
                fps = float(num) / float(den) if float(den) else None
            except ValueError:
                fps = None

    return {
        "path": str(path),
        "duration": duration_s,
        "format": fmt.get("format_name"),
        "bitrate": int(fmt["bit_rate"]) if fmt.get("bit_rate", "").isdigit() else None,
        "video": {
            "exists": video is not None,
            "codec": video.get("codec_name") if video else None,
            "width": width,
            "height": height,
            "fps": fps,
            "pixFmt": video.get("pix_fmt") if video else None,
        },
        "audio": {
            "exists": bool(audio),
            "streams": [
                {
                    "codec": s.get("codec_name"),
                    "channels": s.get("channels"),
                    "sampleRate": s.get("sample_rate"),
                }
                for s in audio
            ],
        },
        # Soft subtitle tracks only. Burned-in / on-screen design captions live
        # in the video pixels and CANNOT be detected here — check provenance or
        # sample frames before adding more captions (see SKILL.md "No double
        # captions").
        "subtitles": {
            "exists": bool(subtitle),
            "streams": [
                {
                    "codec": s.get("codec_name"),
                    "language": (s.get("tags") or {}).get("language"),
                }
                for s in subtitle
            ],
        },
        "raw": raw,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("media")
    parser.add_argument("--output", "-o")
    args = parser.parse_args()

    path = Path(args.media).expanduser().resolve()
    if not path.exists():
        raise SystemExit(f"media not found: {path}")

    result = normalize(run_ffprobe(path), path)
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
