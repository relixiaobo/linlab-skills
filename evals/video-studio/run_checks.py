#!/usr/bin/env python3
"""End-to-end smoke gate for the video-studio skill scripts."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "video-studio"
MEDIA = ROOT / "evals" / "video-studio" / "media"
WORK = ROOT / "work" / "video-studio" / "eval-smoke"
PY = sys.executable


def run(cmd: list[str], *, cwd: Path = ROOT, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)


def require_ok(name: str, proc: subprocess.CompletedProcess[str], errors: list[str]) -> None:
    if proc.returncode != 0:
        output = (proc.stdout + proc.stderr).strip()
        errors.append(f"{name} failed with exit {proc.returncode}: {output[:1200]}")


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_manifest() -> Path:
    manifest = {
        "version": 1,
        "engine": "ffmpeg",
        "platform": "local",
        "canvas": {"width": 640, "height": 360, "fps": 30},
        "sources": [
            {"id": "main", "type": "video", "path": "../../../evals/video-studio/media/source_clip.mp4"}
        ],
        "clips": [
            {"id": "clip1", "source": "main", "start": 0.0, "end": 2.0, "fit": "contain", "crop": "center"}
        ],
        "audio": {"keepOriginal": True},
        "delivery": {"profile": "raw"},
        "output": {"path": "out/final.mp4", "codec": "h264", "crf": 28, "preset": "ultrafast", "audioBitrate": "96k"},
        "qa": {"expectedAudio": True, "expectCaptions": False, "expectBgm": False},
    }
    path = WORK / "render_manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> int:
    errors: list[str] = []
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        print(json.dumps({"ok": False, "errors": ["ffmpeg and ffprobe are required for video-studio smoke checks"]}, indent=2))
        return 1

    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)

    doctor = run([PY, str(SKILL / "scripts" / "doctor.py"), "--json"])
    require_ok("doctor", doctor, errors)
    if doctor.returncode == 0 and load_json_text(doctor.stdout).get("status") != "pass":
        errors.append("doctor status is not pass")

    probe_out = WORK / "source-probe.json"
    probe = run([PY, str(SKILL / "scripts" / "probe_media.py"), str(MEDIA / "source_clip.mp4"), "--output", str(probe_out)])
    require_ok("probe_media", probe, errors)
    if probe_out.exists():
        probe_data = load(probe_out)
        if not probe_data.get("video", {}).get("exists") or not probe_data.get("audio", {}).get("exists"):
            errors.append("source fixture must have video and audio streams")

    manifest = write_manifest()
    manifest_check = run([
        PY, str(SKILL / "scripts" / "validate_manifest.py"), str(manifest),
        "--base-dir", str(WORK), "--output", str(WORK / "manifest-check.json"),
    ])
    require_ok("validate_manifest", manifest_check, errors)

    render = run([
        PY, str(SKILL / "scripts" / "render_ffmpeg.py"), str(manifest),
        "--base-dir", str(WORK), "--work-dir", str(WORK / "work"),
        "--plan-output", str(WORK / "render-result.json"),
    ], timeout=240)
    require_ok("render_ffmpeg", render, errors)

    final = WORK / "out" / "final.mp4"
    qa = run([
        PY, str(SKILL / "scripts" / "qa_video.py"), str(final),
        "--manifest", str(manifest), "--base-dir", str(WORK),
        "--out-dir", str(WORK / "qa"), "--output", str(WORK / "qa.json"),
    ], timeout=180)
    require_ok("qa_video", qa, errors)
    if (WORK / "qa.json").exists():
        qa_data = load(WORK / "qa.json")
        meta = qa_data.get("metadata", {})
        if qa_data.get("status") != "pass":
            errors.append(f"qa status is {qa_data.get('status')}")
        if meta.get("video", {}).get("width") != 640 or meta.get("video", {}).get("height") != 360:
            errors.append("rendered video dimensions are not 640x360")
        duration = meta.get("duration")
        if not isinstance(duration, (int, float)) or not (1.6 <= duration <= 2.4):
            errors.append(f"rendered duration out of expected range: {duration}")
        if not meta.get("audio", {}).get("exists"):
            errors.append("rendered video is missing audio")

    cover = run([
        PY, str(SKILL / "scripts" / "make_cover.py"),
        "--title", "Eval Clip", "--subtitle", "Smoke test",
        "--video", str(final), "--timestamp", "00:00:01",
        "--output", str(WORK / "cover.png"),
    ])
    require_ok("make_cover", cover, errors)
    if not (WORK / "cover.png").exists():
        errors.append("cover image was not created")

    package = run([
        PY, str(SKILL / "scripts" / "build_publish_package.py"),
        "--platform", "local", "--video", str(final), "--cover", str(WORK / "cover.png"),
        "--title", "Eval Clip", "--qa", str(WORK / "qa.json"),
        "--output", str(WORK / "package.json"), "--strict",
    ])
    require_ok("build_publish_package", package, errors)
    if (WORK / "package.json").exists() and not load(WORK / "package.json").get("ready"):
        errors.append("publish package is not ready")

    result = {"ok": not errors, "workspace": str(WORK.relative_to(ROOT)), "errors": errors}
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1


def load_json_text(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


if __name__ == "__main__":
    sys.exit(main())
