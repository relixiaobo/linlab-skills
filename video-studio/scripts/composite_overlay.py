#!/usr/bin/env python3
"""Composite a transparent overlay (e.g. a Manim math layer) over a background.

This is the second half of the manim *overlay* path: `render_manim.py` produces
an alpha `.mov`; this lays it over a background with FFmpeg's `overlay` filter,
honouring the overlay's alpha channel. The background may be:

  --background color:#0b1020      a solid colour canvas
  --background image:bg.png       a still image (looped to overlay length)
  --background video:bg.mp4       a video (e.g. a Remotion render)

The result is a normal opaque mp4 you can deliver directly or reference as a
`source` in render_manifest.json for the rest of the pipeline (captions, BGM, QA).

Overlay length drives the output length, so the math layer and background stay
in lockstep with the narration-bound timeline that produced the overlay.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def require_bin(name: str) -> None:
    if not shutil.which(name):
        raise SystemExit(f"{name} not found on PATH")


def probe_duration(path: Path) -> float:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    try:
        return float(proc.stdout.strip())
    except ValueError:
        return 0.0


def parse_background(spec: str) -> tuple[str, str]:
    if ":" not in spec:
        raise SystemExit("--background must be color:#RRGGBB | image:PATH | video:PATH")
    kind, _, value = spec.partition(":")
    kind = kind.strip().lower()
    if kind not in {"color", "image", "video"}:
        raise SystemExit(f"unknown background kind {kind!r}")
    return kind, value


def build_command(
    bg_kind: str,
    bg_value: str,
    overlay: Path,
    out_path: Path,
    width: int,
    height: int,
    fps: int,
    x: str,
    y: str,
    overlay_scale: float,
    opacity: float,
    duration: float,
) -> list[str]:
    cmd: list[str] = ["ffmpeg", "-y"]

    # Background input (input 0).
    if bg_kind == "color":
        cmd += ["-f", "lavfi", "-i", f"color=c={bg_value}:s={width}x{height}:r={fps}:d={duration:.3f}"]
    elif bg_kind == "image":
        cmd += ["-loop", "1", "-framerate", str(fps), "-t", f"{duration:.3f}", "-i", bg_value]
    else:  # video
        cmd += ["-i", bg_value]

    # Overlay input (input 1) — the alpha .mov.
    cmd += ["-i", str(overlay)]

    # Filter graph: normalise bg to canvas, optionally scale/fade the overlay, overlay.
    bg_chain = f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},fps={fps}[bg]"
    ov_filters = []
    if abs(overlay_scale - 1.0) > 1e-6:
        ov_filters.append(f"scale=iw*{overlay_scale}:ih*{overlay_scale}")
    if opacity < 1.0 - 1e-6:
        ov_filters.append(f"format=rgba,colorchannelmixer=aa={opacity}")
    ov_chain = "[1:v]" + (",".join(ov_filters) + "," if ov_filters else "") + "null[ov]"
    overlay_node = f"[bg][ov]overlay={x}:{y}:format=auto:shortest=1[vout]"
    filter_complex = f"{bg_chain};{ov_chain};{overlay_node}"

    cmd += [
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium",
        "-r", str(fps),
        str(out_path),
    ]
    return cmd


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--overlay", required=True, help="Transparent overlay (alpha .mov from render_manim.py)")
    ap.add_argument("--background", required=True, help="color:#RRGGBB | image:PATH | video:PATH")
    ap.add_argument("--out", required=True, help="Output mp4 path")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--x", default="(W-w)/2", help="Overlay x in ffmpeg overlay-expr (default centre)")
    ap.add_argument("--y", default="(H-h)/2", help="Overlay y in ffmpeg overlay-expr (default centre)")
    ap.add_argument("--overlay-scale", type=float, default=1.0)
    ap.add_argument("--opacity", type=float, default=1.0, help="Global overlay opacity 0..1")
    ap.add_argument("--sidecar", help="Optional overlay sidecar JSON to read fps/resolution from")
    args = ap.parse_args()

    require_bin("ffmpeg")
    require_bin("ffprobe")

    overlay = Path(args.overlay).expanduser().resolve()
    if not overlay.exists():
        raise SystemExit(f"overlay not found: {overlay}")

    if args.sidecar:
        meta = json.loads(Path(args.sidecar).expanduser().read_text(encoding="utf-8"))
        res = meta.get("resolution")
        if res:
            args.width, args.height = int(res[0]), int(res[1])
        if meta.get("fps"):
            args.fps = int(meta["fps"])

    bg_kind, bg_value = parse_background(args.background)
    duration = probe_duration(overlay)
    if duration <= 0:
        raise SystemExit(f"could not determine overlay duration for {overlay}")

    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = build_command(
        bg_kind, bg_value, overlay, out_path,
        args.width, args.height, args.fps,
        args.x, args.y, args.overlay_scale, args.opacity, duration,
    )
    proc = subprocess.run(cmd, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if proc.returncode != 0:
        print(json.dumps({"status": "error", "error": proc.stdout[-4000:]}, ensure_ascii=False))
        return 2

    print(json.dumps({
        "status": "ok",
        "output": str(out_path),
        "durationInSeconds": round(probe_duration(out_path), 3),
        "resolution": [args.width, args.height],
        "fps": args.fps,
        "background": {"kind": bg_kind, "value": bg_value},
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
