#!/usr/bin/env python3
"""Bind scenes 1:1 to their narration so the on-screen scene matches the speech.

The desync "scene 1 is showing while scene 3 is being narrated" happens when
scene-change times are authored separately from narration times. This tool makes
them ONE timeline: each scene's duration is derived from its own narration, so
the picture for scene i is always on screen exactly while voiceover i plays.

Input (scenes.json):

  {
    "fps": 30,
    "scenes": [
      { "id": "s1", "visual": "chart-a", "narration": "First narration line", "audio": "media/audio/s1.mp3" },
      { "id": "s2", "visual": "chart-b", "narration": "Second narration line", "audio": "media/audio/s2.mp3" }
    ]
  }

Timing modes (auto-selected):

1. Per-scene audio (recommended): every scene has `audio`. Each scene's duration
   is that clip's real length; the clips are concatenated in order into one
   voiceover track -> alignment is exact by construction.
2. Single voiceover + segments: pass --voiceover and either give each scene an
   explicit `start`/`end`, or let silencedetect split the narration into
   len(scenes) speech spans (no ASR).
3. Explicit: every scene already has numeric `start`/`duration`.

Outputs (all optional except --storyboard-out):
  --storyboard-out   timeline with per-scene start/duration (seconds + frames)
  --voiceover-out    concatenated narration (per-scene-audio mode)
  --captions-out     SRT aligned to scene windows
  --props-out        ready-to-pass Remotion props {scenes, voiceover, durationInSeconds}
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from captions_from_script import (  # noqa: E402
    audio_duration,
    detect_speech_spans,
    fmt_srt_time,
    split_text_into_lines,
)


def rel_or_abs(base: Path, value: str) -> Path:
    p = Path(value).expanduser()
    return p if p.is_absolute() else base / p


def concat_audio(clips: list[Path], out_path: Path, work_dir: Path) -> float:
    """Concatenate per-scene narration clips into one track; return duration."""
    import shutil

    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg not found; required to concatenate per-scene audio")
    work_dir.mkdir(parents=True, exist_ok=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    concat_list = work_dir / "voiceover_concat.txt"
    body = "".join(f"file '{str(c).replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'\n" for c in clips)
    concat_list.write_text(body, encoding="utf-8")
    # Re-encode to a uniform format so heterogeneous inputs concat cleanly.
    proc = subprocess.run(
        [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
            "-ar", "48000", "-ac", "2", "-c:a", "libmp3lame", "-q:a", "2", str(out_path),
        ],
        check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise SystemExit(f"voiceover concat failed: {proc.stderr.strip()}")
    return audio_duration(out_path)


def build_timeline(
    scenes: list[dict[str, Any]],
    base: Path,
    voiceover: Path | None,
    work_dir: Path,
    voiceover_out: Path | None,
    noise_db: float,
    min_silence: float,
) -> tuple[list[dict[str, Any]], float, Path | None]:
    """Return (scenes_with_timing, total_duration, voiceover_path)."""
    has_audio = all(s.get("audio") for s in scenes)
    has_explicit = all(isinstance(s.get("start"), (int, float)) and isinstance(s.get("duration"), (int, float)) for s in scenes)

    timed: list[dict[str, Any]] = []
    voice_path = voiceover

    if has_audio:
        clips = [rel_or_abs(base, s["audio"]) for s in scenes]
        for clip in clips:
            if not clip.exists():
                raise SystemExit(f"scene audio not found: {clip}")
        durations = [audio_duration(c) for c in clips]
        cursor = 0.0
        for scene, dur in zip(scenes, durations):
            timed.append({**scene, "start": round(cursor, 3), "duration": round(dur, 3)})
            cursor += dur
        total = round(cursor, 3)
        if voiceover_out:
            voice_path = voiceover_out
            concat_audio(clips, voiceover_out, work_dir)
    elif has_explicit:
        total = 0.0
        for scene in scenes:
            start = float(scene["start"])
            dur = float(scene["duration"])
            timed.append({**scene, "start": round(start, 3), "duration": round(dur, 3)})
            total = max(total, start + dur)
        total = round(total, 3)
    elif voiceover:
        total = audio_duration(voiceover)
        # Prefer explicit per-scene start/end if every scene has them.
        if all(isinstance(s.get("start"), (int, float)) and isinstance(s.get("end"), (int, float)) for s in scenes):
            spans = [(float(s["start"]), float(s["end"])) for s in scenes]
        else:
            spans = detect_speech_spans(voiceover, total, noise_db, min_silence)
            if len(spans) != len(scenes):
                spans = _redistribute(spans, scenes, total)
        # Each scene appears when its narration starts and HOLDS through the
        # pause until the next scene begins, so the picture has no on-screen gap.
        starts = [s for s, _ in spans]
        for i, (scene, start) in enumerate(zip(scenes, starts)):
            end = starts[i + 1] if i + 1 < len(starts) else total
            timed.append({**scene, "start": round(start, 3), "duration": round(max(0.1, end - start), 3)})
        total = round(total, 3)
    else:
        raise SystemExit(
            "cannot derive scene timing: give every scene an `audio` clip, explicit start/duration, or pass --voiceover"
        )

    return timed, total, voice_path


def _redistribute(spans: list[tuple[float, float]], scenes: list[dict[str, Any]], total: float) -> list[tuple[float, float]]:
    """When detected speech spans != scene count, split total speech by narration length."""
    weights = [max(1, len(str(s.get("narration", "")))) for s in scenes]
    total_weight = sum(weights)
    speech_total = sum(e - s for s, e in spans) or total
    # Flatten speech time, then carve per-scene slices and map back to real time.
    cursor = 0.0
    out: list[tuple[float, float]] = []
    for weight in weights:
        slice_len = speech_total * weight / total_weight
        start = _speech_to_real(spans, cursor, total)
        end = _speech_to_real(spans, cursor + slice_len, total)
        out.append((start, max(start + 0.1, end)))
        cursor += slice_len
    return out


def _speech_to_real(spans: list[tuple[float, float]], target: float, total: float) -> float:
    remaining = target
    for s, e in spans:
        length = e - s
        if remaining <= length:
            return s + remaining
        remaining -= length
    return spans[-1][1] if spans else total


def scene_captions(timed: list[dict[str, Any]], max_chars: int) -> list[dict[str, Any]]:
    """One or more cues per scene, all inside the scene window."""
    cues: list[dict[str, Any]] = []
    for scene in timed:
        text = str(scene.get("narration", "")).strip()
        if not text:
            continue
        start = float(scene["start"])
        end = start + float(scene["duration"])
        lines = split_text_into_lines(text, max_chars)
        weights = [max(1, len(line)) for line in lines]
        total_weight = sum(weights)
        cursor = start
        for line, weight in zip(lines, weights):
            span = (end - start) * weight / total_weight
            cues.append({"start": round(cursor, 3), "end": round(min(end, cursor + span), 3), "text": line})
            cursor += span
    return cues


def write_srt(cues: list[dict[str, Any]], path: Path) -> None:
    blocks = []
    for i, c in enumerate(cues, start=1):
        blocks.append(f"{i}\n{fmt_srt_time(c['start'])} --> {fmt_srt_time(c['end'])}\n{c['text']}\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(blocks), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("scenes", help="scenes.json with {fps?, scenes:[...]}")
    parser.add_argument("--base-dir", default=".", help="Base dir for relative audio paths")
    parser.add_argument("--voiceover", help="Single narration track (mode 2)")
    parser.add_argument("--voiceover-out", help="Write concatenated narration here (per-scene-audio mode)")
    parser.add_argument("--storyboard-out", required=True)
    parser.add_argument("--captions-out")
    parser.add_argument("--props-out", help="Remotion props JSON")
    parser.add_argument("--max-chars", type=int, default=20)
    parser.add_argument("--noise-db", type=float, default=-35.0)
    parser.add_argument("--min-silence", type=float, default=0.32)
    parser.add_argument("--work-dir", default=None)
    args = parser.parse_args()

    base = Path(args.base_dir).expanduser().resolve()
    data = json.loads(Path(args.scenes).expanduser().read_text(encoding="utf-8"))
    scenes = data.get("scenes", [])
    if not scenes:
        raise SystemExit("scenes.json has no scenes")
    fps = int(data.get("fps", 30))
    work_dir = Path(args.work_dir).expanduser().resolve() if args.work_dir else base / "work" / "scene_timing"
    voiceover = Path(args.voiceover).expanduser().resolve() if args.voiceover else None
    voiceover_out = Path(args.voiceover_out).expanduser().resolve() if args.voiceover_out else None

    timed, total, voice_path = build_timeline(
        scenes, base, voiceover, work_dir, voiceover_out, args.noise_db, args.min_silence
    )

    for scene in timed:
        scene["startFrame"] = round(float(scene["start"]) * fps)
        scene["durationInFrames"] = max(1, round(float(scene["duration"]) * fps))

    storyboard = {"version": 1, "fps": fps, "durationInSeconds": total, "scenes": timed}
    out = Path(args.storyboard_out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(storyboard, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    cues = scene_captions(timed, args.max_chars)
    if args.captions_out:
        write_srt(cues, Path(args.captions_out).expanduser().resolve())

    if args.props_out:
        props = {
            "durationInSeconds": total,
            "voiceover": str(voice_path) if voice_path else "",
            "captions": cues,
            "scenes": [
                {
                    "id": s.get("id"),
                    "visual": s.get("visual"),
                    "title": s.get("title"),
                    "text": s.get("narration"),
                    "startFrame": s["startFrame"],
                    "durationInFrames": s["durationInFrames"],
                }
                for s in timed
            ],
        }
        Path(args.props_out).expanduser().resolve().write_text(
            json.dumps(props, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    result = {
        "status": "ok",
        "scenes": len(timed),
        "durationInSeconds": total,
        "voiceover": str(voice_path) if voice_path else None,
        "storyboard": str(out),
        "cues": len(cues),
        "timeline": [{"id": s.get("id"), "start": s["start"], "duration": s["duration"]} for s in timed],
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
