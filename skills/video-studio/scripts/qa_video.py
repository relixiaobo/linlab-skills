#!/usr/bin/env python3
"""ffprobe + keyframe QA gate for final video outputs.

Beyond metadata and keyframes, this enforces the delivery contract that a
narrative/social video must not ship empty:

- audio stream present (when expected) and NOT silent (volumedetect)
- captions authored/declared (when expected)
- background music mixed (when expected)

Expectations resolve with precedence: explicit CLI flag > manifest qa fields >
--profile > auto-default. A failed expectation makes QA exit non-zero so the
caller cannot silently deliver a video with no sound, subtitles, or music.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


# Per-profile requirements. None means "not enforced by the profile".
# Captions are opt-in: no profile requires them by default. Enforce captions
# only when the user asked for them, via qa.expectCaptions or --expect-captions.
PROFILES: dict[str, dict[str, bool | None]] = {
    "social": {"audio": True, "captions": None, "bgm": True},
    "narrative": {"audio": True, "captions": None, "bgm": None},
    "raw": {"audio": None, "captions": None, "bgm": None},
    "auto": {"audio": True, "captions": None, "bgm": None},
}


def ffprobe(path: Path) -> dict[str, Any]:
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
    if proc.returncode:
        raise RuntimeError(proc.stderr.strip() or "ffprobe failed")
    return json.loads(proc.stdout)


def load_speech_helpers():
    """Borrow silencedetect helpers from captions_from_script when available."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from captions_from_script import audio_duration, detect_speech_spans
        return detect_speech_spans, audio_duration
    except Exception:
        return None, None


def media_duration(path: Path) -> float | None:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        return float(proc.stdout.strip())
    except ValueError:
        return None


def measure_volume(video: Path) -> dict[str, float | None]:
    """Return {mean, max} dBFS for the first audio stream via volumedetect."""
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(video), "-map", "0:a:0", "-af", "volumedetect", "-f", "null", "-"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    out = proc.stderr
    result: dict[str, float | None] = {"mean": None, "max": None}
    mean = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?) dB", out)
    peak = re.search(r"max_volume:\s*(-?\d+(?:\.\d+)?) dB", out)
    if mean:
        result["mean"] = float(mean.group(1))
    if peak:
        result["max"] = float(peak.group(1))
    return result


def extract_frame(video: Path, t: float, output: Path) -> bool:
    proc = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{t:.3f}",
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(output),
        ],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return proc.returncode == 0 and output.exists()


def summarize(raw: dict[str, Any]) -> dict[str, Any]:
    streams = raw.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    fmt = raw.get("format", {})
    duration = None
    try:
        duration = float(fmt.get("duration")) if fmt.get("duration") else None
    except ValueError:
        pass
    fps = None
    if video:
        rate = video.get("avg_frame_rate") or video.get("r_frame_rate")
        if rate and "/" in rate:
            n, d = rate.split("/", 1)
            try:
                fps = float(n) / float(d) if float(d) else None
            except ValueError:
                pass
    return {
        "duration": duration,
        "video": {
            "exists": video is not None,
            "codec": video.get("codec_name") if video else None,
            "width": video.get("width") if video else None,
            "height": video.get("height") if video else None,
            "fps": fps,
        },
        "audio": {"exists": bool(audio), "streams": len(audio)},
    }


def tri_state(flag_on: bool, flag_off: bool, manifest_val: Any, profile_val: bool | None) -> bool:
    """Resolve a requirement: explicit flag > manifest > profile > False."""
    if flag_on:
        return True
    if flag_off:
        return False
    if isinstance(manifest_val, bool):
        return manifest_val
    if profile_val is not None:
        return profile_val
    return False


def load_manifest(path: Path | None, base: Path) -> dict[str, Any]:
    if not path:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    qa = data.get("qa", {}) if isinstance(data.get("qa"), dict) else {}
    audio = data.get("audio", {}) if isinstance(data.get("audio"), dict) else {}
    subs = data.get("subtitles", {}) if isinstance(data.get("subtitles"), dict) else {}
    delivery = data.get("delivery", {}) if isinstance(data.get("delivery"), dict) else {}
    sub_path = subs.get("path")
    bgm_path = audio.get("bgm")
    return {
        "profile": delivery.get("profile"),
        "expectAudio": qa.get("expectedAudio") if "expectedAudio" in qa else qa.get("expectAudio"),
        "expectCaptions": qa.get("expectCaptions"),
        "expectBgm": qa.get("expectBgm"),
        # A burned-in subtitle path counts as a declared caption source.
        "captionSource": str(base / sub_path) if sub_path and subs.get("burnIn", True) else None,
        "bgmDeclared": bool(bgm_path),
        "voiceoverPath": str(base / audio["voiceover"]) if audio.get("voiceover") else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("video")
    parser.add_argument("--out-dir", default="verify/qa")
    parser.add_argument("--frames", type=int, default=6)
    parser.add_argument("--expected-width", type=int)
    parser.add_argument("--expected-height", type=int)
    parser.add_argument("--manifest", help="render_manifest.json to derive expectations from")
    parser.add_argument("--base-dir", default=".", help="Base dir for manifest relative paths")
    parser.add_argument("--profile", choices=sorted(PROFILES), default="auto")
    # Audio
    parser.add_argument("--expected-audio", "--expect-audio", dest="expect_audio", action="store_true")
    parser.add_argument("--allow-silent", action="store_true", help="Do not require an audible audio track")
    parser.add_argument("--silence-db", type=float, default=-50.0, help="Peak dBFS below this counts as silent")
    # Captions
    parser.add_argument("--expect-captions", action="store_true")
    parser.add_argument("--no-captions", action="store_true")
    parser.add_argument("--captions", help="Caption source file (.srt/.ass) that was burned/declared")
    # BGM
    parser.add_argument("--expect-bgm", action="store_true")
    parser.add_argument("--no-bgm", action="store_true")
    parser.add_argument("--bgm-declared", action="store_true", help="Assert BGM was mixed (no manifest case)")
    # A/V sync
    parser.add_argument("--voiceover", help="Narration file to compare against output duration")
    parser.add_argument("--sync-tolerance", type=float, default=0.4, help="Allowed A/V duration delta, seconds")
    parser.add_argument("--storyboard", help="scene_timing.py storyboard.json to verify scene/narration alignment")
    parser.add_argument("--output", "-o")
    args = parser.parse_args()

    if not shutil.which("ffprobe"):
        raise SystemExit("ffprobe not found")
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg not found")

    video = Path(args.video).expanduser().resolve()
    base = Path(args.base_dir).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    frame_dir = out_dir / "frames"
    frame_dir.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest(Path(args.manifest).expanduser().resolve() if args.manifest else None, base)
    profile_name = manifest.get("profile") or args.profile
    profile = PROFILES.get(profile_name, PROFILES["auto"])

    expect_audio = tri_state(args.expect_audio, args.allow_silent, manifest.get("expectAudio"), profile["audio"])
    expect_captions = tri_state(args.expect_captions, args.no_captions, manifest.get("expectCaptions"), profile["captions"])
    expect_bgm = tri_state(args.expect_bgm, args.no_bgm, manifest.get("expectBgm"), profile["bgm"])

    caption_source = args.captions or manifest.get("captionSource")
    bgm_declared = args.bgm_declared or manifest.get("bgmDeclared", False)

    raw = ffprobe(video)
    meta = summarize(raw)
    errors: list[str] = []
    warnings: list[str] = []
    checks: list[dict[str, Any]] = []

    def record(name: str, status: str, detail: str) -> None:
        checks.append({"name": name, "status": status, "detail": detail})
        if status == "fail":
            errors.append(f"{name}: {detail}")
        elif status == "warn":
            warnings.append(f"{name}: {detail}")

    # --- Structural checks ---
    if not meta["video"]["exists"]:
        record("video-stream", "fail", "no video stream")
    if not meta["duration"] or meta["duration"] <= 0:
        record("duration", "fail", "invalid duration")
    if args.expected_width and meta["video"]["width"] != args.expected_width:
        record("width", "fail", f"{meta['video']['width']} != {args.expected_width}")
    if args.expected_height and meta["video"]["height"] != args.expected_height:
        record("height", "fail", f"{meta['video']['height']} != {args.expected_height}")

    # --- Audio presence + silence ---
    volume: dict[str, float | None] = {"mean": None, "max": None}
    if expect_audio:
        if not meta["audio"]["exists"]:
            record("audio-present", "fail", "expected an audio track but none found (silent video)")
        else:
            volume = measure_volume(video)
            peak = volume["max"]
            if peak is None:
                record("audio-audible", "warn", "could not measure volume; inspect audio manually")
            elif peak < args.silence_db:
                record(
                    "audio-audible",
                    "fail",
                    f"audio track is effectively silent (peak {peak:.1f} dBFS < {args.silence_db:.1f})",
                )
            else:
                record("audio-audible", "pass", f"peak {peak:.1f} dBFS, mean {volume['mean']} dBFS")
    elif meta["audio"]["exists"]:
        record("audio-present", "pass", "audio track present (not required by profile)")

    # --- Captions ---
    if expect_captions:
        if not caption_source:
            record("captions", "fail", "captions expected but no caption source declared (pass --captions or burn subtitles)")
        else:
            cap_path = Path(caption_source).expanduser()
            if cap_path.exists() and cap_path.stat().st_size > 0:
                record("captions", "warn", f"caption source present ({cap_path.name}); verify burn-in in extracted frames")
            else:
                record("captions", "fail", f"caption source missing or empty: {caption_source}")

    # --- BGM ---
    if expect_bgm:
        if bgm_declared:
            record("bgm", "warn", "BGM declared; confirm it is audible (and ducked under narration) in playback")
        else:
            record("bgm", "fail", "background music expected but none declared in manifest/inputs")

    # --- A/V sync: narration vs output duration ---
    voice_path = args.voiceover or manifest.get("voiceoverPath")
    if voice_path:
        vp = Path(voice_path).expanduser()
        out_dur = meta["duration"]
        if not vp.exists():
            record("av-sync", "warn", f"voiceover not found for sync check: {voice_path}")
        elif out_dur:
            vdur = media_duration(vp)
            if vdur:
                delta = vdur - out_dur  # positive => narration longer than video (cut)
                if delta > args.sync_tolerance:
                    record(
                        "av-sync",
                        "fail",
                        f"narration ({vdur:.2f}s) is {delta:.2f}s longer than the video ({out_dur:.2f}s) — it is cut off",
                    )
                elif -delta > max(args.sync_tolerance, 0.75):
                    record(
                        "av-sync",
                        "warn",
                        f"video ({out_dur:.2f}s) runs {-delta:.2f}s past the narration ({vdur:.2f}s); confirm the tail is intentional",
                    )
                else:
                    record("av-sync", "pass", f"video {out_dur:.2f}s ~= narration {vdur:.2f}s")

    # --- Scene/narration alignment ---
    scene_frames: list[str] = []
    if args.storyboard:
        sb_path = Path(args.storyboard).expanduser()
        if not sb_path.exists():
            record("scene-align", "warn", f"storyboard not found: {args.storyboard}")
        else:
            sb = json.loads(sb_path.read_text(encoding="utf-8"))
            scenes = sb.get("scenes", [])
            sb_total = sb.get("durationInSeconds")
            out_dur = meta["duration"] or 0
            if sb_total and out_dur and abs(sb_total - out_dur) > args.sync_tolerance:
                record(
                    "scene-timeline",
                    "fail",
                    f"output {out_dur:.2f}s does not match storyboard {sb_total:.2f}s — scenes will drift from narration",
                )
            elif scenes:
                record("scene-timeline", "pass", f"{len(scenes)} scenes over {out_dur:.2f}s match the storyboard")

            # Compare detected speech segments to scene count when narration exists.
            detect_spans, audio_dur = load_speech_helpers()
            if voice_path and detect_spans and audio_dur:
                vp = Path(voice_path).expanduser()
                if vp.exists():
                    vdur = audio_dur(vp) or out_dur
                    spans = detect_spans(vp, vdur, -35.0, 0.32)
                    if scenes and len(spans) != len(scenes):
                        record(
                            "scene-segments",
                            "warn",
                            f"detected {len(spans)} speech segments but {len(scenes)} scenes; verify each scene matches its line",
                        )
                    elif scenes:
                        max_delta = max(abs(float(s["start"]) - spans[i][0]) for i, s in enumerate(scenes))
                        if max_delta > max(args.sync_tolerance, 0.5):
                            record("scene-segments", "warn", f"scene starts drift up to {max_delta:.2f}s from speech")
                        else:
                            record("scene-segments", "pass", f"scene starts align with speech (<= {max_delta:.2f}s)")

            # One midpoint frame per scene for manual "right visual?" review.
            for scene in scenes:
                mid = float(scene.get("start", 0)) + float(scene.get("duration", 0)) / 2
                target = frame_dir / f"scene-{scene.get('id', 'x')}-{math.floor(mid * 1000):07d}ms.png"
                if extract_frame(video, mid, target):
                    scene_frames.append(str(target))

    # --- Keyframes ---
    frames: list[str] = []
    duration = meta["duration"] or 0
    if duration > 0:
        count = max(1, args.frames)
        times = [min(duration - 0.1, max(0, duration * (i + 1) / (count + 1))) for i in range(count)]
        for i, t in enumerate(times, start=1):
            target = frame_dir / f"frame-{i:03d}-{math.floor(t * 1000):07d}ms.png"
            if extract_frame(video, t, target):
                frames.append(str(target))
            else:
                record("keyframe", "warn", f"failed to extract frame at {t:.2f}s")

    status = "fail" if errors else ("warn" if warnings else "pass")
    result = {
        "status": status,
        "video": str(video),
        "profile": profile_name,
        "expectations": {"audio": expect_audio, "captions": expect_captions, "bgm": expect_bgm},
        "metadata": meta,
        "volume": volume,
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
        "frames": frames,
        "sceneFrames": scene_frames,
    }

    output = Path(args.output).expanduser().resolve() if args.output else out_dir / "qa.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
