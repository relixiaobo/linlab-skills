#!/usr/bin/env python3
"""Render a numbered PNG frame sequence into MP4 with FFmpeg."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", required=True, help="Input pattern, e.g. frames/%%06d.png")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--output", required=True)
    parser.add_argument("--audio")
    parser.add_argument("--crf", type=int, default=18)
    parser.add_argument("--preset", default="fast")
    args = parser.parse_args()

    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg not found")

    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",
        "-framerate",
        str(args.fps),
        "-i",
        args.frames,
    ]
    if args.audio:
        cmd += ["-i", args.audio]
    cmd += [
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        str(args.crf),
        "-preset",
        args.preset,
    ]
    if args.audio:
        cmd += ["-c:a", "aac", "-shortest"]
    cmd += [str(output)]

    proc = subprocess.run(cmd, check=False)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
