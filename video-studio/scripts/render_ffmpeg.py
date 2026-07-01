#!/usr/bin/env python3
"""Render a v1 video-studio render_manifest.json with FFmpeg.

This renderer intentionally covers the stable default path:
- normalize each clip to the manifest canvas
- concatenate normalized clips
- optionally burn subtitles as the last visual layer
- optionally mix original audio, external voiceover, and BGM

More complex overlays should be rendered by Remotion or web-to-video first,
then referenced as normal video sources.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SUPPORTED_ENGINES = {"ffmpeg"}


class RenderError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def append_log(run_log: Path | None, stage: str, event: str, note: str = "") -> None:
    if not run_log:
        return
    run_log.parent.mkdir(parents=True, exist_ok=True)
    with run_log.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": utc_now(), "stage": stage, "event": event, "note": note}, ensure_ascii=False) + "\n")


def progress(enabled: bool, stage: str, **extra: Any) -> None:
    if enabled:
        payload = {"ts": utc_now(), "stage": stage, **extra}
        print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)


def require_bin(name: str) -> None:
    if not shutil.which(name):
        raise RenderError(f"{name} not found on PATH")


def rel_or_abs(base: Path, value: str | None) -> Path | None:
    if not value:
        return None
    p = Path(value).expanduser()
    return p if p.is_absolute() else base / p


def shell_join(cmd: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)


def concat_quote(path: Path) -> str:
    return str(path).replace("'", "'\\''")


def run_cmd(cmd: list[str], dry_run: bool, commands: list[dict[str, Any]], label: str) -> None:
    commands.append({"label": label, "argv": cmd, "shell": shell_join(cmd)})
    if dry_run:
        return
    proc = subprocess.run(cmd, check=False)
    if proc.returncode != 0:
        raise RenderError(f"{label} failed with exit code {proc.returncode}")


def ffprobe_json(path: Path) -> dict[str, Any]:
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
        raise RenderError(proc.stderr.strip() or f"ffprobe failed for {path}")
    return json.loads(proc.stdout)


def ffmpeg_filters() -> set[str]:
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-filters"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    filters: set[str] = set()
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 3 and "->" in parts[2]:
            filters.add(parts[1])
    return filters


def has_audio(path: Path, dry_run: bool) -> bool:
    if dry_run:
        return True
    raw = ffprobe_json(path)
    return any(stream.get("codec_type") == "audio" for stream in raw.get("streams", []))


def has_subtitle_stream(path: Path, dry_run: bool) -> bool:
    """True if the media carries a SOFT subtitle stream. Burned-in/on-screen
    captions live in the pixels and cannot be detected here."""
    if dry_run:
        return False
    try:
        raw = ffprobe_json(path)
    except RenderError:
        return False
    return any(stream.get("codec_type") == "subtitle" for stream in raw.get("streams", []))


def media_duration(path: Path, dry_run: bool) -> float | None:
    if dry_run:
        return None
    try:
        raw = ffprobe_json(path)
        value = raw.get("format", {}).get("duration")
        return float(value) if value is not None else None
    except (RenderError, ValueError, TypeError):
        return None


def canvas_filter(width: int, height: int, fps: float, fit: str, crop: str) -> str:
    crop_x = "(iw-ow)/2"
    crop_y = "(ih-oh)/2"
    if crop == "left":
        crop_x = "0"
    elif crop == "right":
        crop_x = "iw-ow"
    elif crop == "top":
        crop_y = "0"
    elif crop == "bottom":
        crop_y = "ih-oh"

    if fit == "cover":
        scale = f"scale={width}:{height}:force_original_aspect_ratio=increase"
        crop_filter = f"crop={width}:{height}:{crop_x}:{crop_y}"
        return f"fps={fps},{scale},{crop_filter},setsar=1,format=yuv420p"
    if fit == "contain":
        scale = f"scale={width}:{height}:force_original_aspect_ratio=decrease"
        pad = f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black"
        return f"fps={fps},{scale},{pad},setsar=1,format=yuv420p"
    if fit == "stretch":
        return f"fps={fps},scale={width}:{height},setsar=1,format=yuv420p"
    if fit == "original":
        return f"fps={fps},scale=trunc(iw/2)*2:trunc(ih/2)*2,setsar=1,format=yuv420p"
    raise RenderError(f"unsupported clip fit: {fit}")


def subtitle_filter(path: Path) -> str:
    # FFmpeg filter parser needs backslash escaping for a few characters.
    value = str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    return f"subtitles=filename='{value}'"


def find_font(configured: str | None = None) -> str | None:
    candidates = [
        configured,
        os.environ.get("DEFAULT_VIDEO_FONT"),
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).expanduser().exists():
            return str(Path(candidate).expanduser())
    return None


def text_size(draw: Any, text: str, font: Any, stroke_width: int = 0) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    return int(box[2] - box[0]), int(box[3] - box[1])


def wrap_caption_text(draw: Any, text: str, font: Any, max_width: int, stroke_width: int) -> list[str]:
    normalized = " ".join(text.replace("\n", " ").split())
    if not normalized:
        return []
    tokens = normalized.split(" ") if " " in normalized else list(normalized)
    lines: list[str] = []
    current = ""
    joiner = " " if " " in normalized else ""
    for token in tokens:
        candidate = token if not current else current + joiner + token
        width, _ = text_size(draw, candidate, font, stroke_width)
        if width <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = token
    if current:
        lines.append(current)
    return lines


def parse_srt(path: Path) -> list[dict[str, Any]]:
    try:
        import srt
    except Exception as exc:  # pragma: no cover - depends on environment
        raise RenderError("SRT subtitle fallback requires the Python package 'srt'") from exc

    subtitles = list(srt.parse(path.read_text(encoding="utf-8-sig")))
    entries: list[dict[str, Any]] = []
    for item in subtitles:
        start = item.start.total_seconds()
        end = item.end.total_seconds()
        if end <= start:
            continue
        entries.append({"start": start, "end": end, "text": item.content.strip()})
    return entries


def render_subtitle_images(
    subtitle_path: Path,
    canvas: dict[str, Any],
    subtitle_cfg: dict[str, Any],
    work_dir: Path,
    dry_run: bool,
) -> list[dict[str, Any]]:
    if subtitle_path.suffix.lower() != ".srt":
        raise RenderError("subtitle image fallback only supports .srt; install FFmpeg with subtitles/libass for ASS files")
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception as exc:  # pragma: no cover - depends on environment
        raise RenderError("subtitle image fallback requires Pillow") from exc

    width = int(canvas["width"])
    height = int(canvas["height"])
    font_size = int(subtitle_cfg.get("fontSize") or max(28, min(72, height * 0.045)))
    stroke_width = int(subtitle_cfg.get("strokeWidth") or max(2, font_size * 0.08))
    bottom_margin = int(subtitle_cfg.get("bottomMargin") or height * 0.115)
    horizontal_padding = int(subtitle_cfg.get("horizontalPadding") or width * 0.07)
    line_gap = int(font_size * 0.28)
    font_path = find_font(subtitle_cfg.get("font"))
    font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
    fill = tuple(subtitle_cfg.get("textColor", [255, 255, 255, 255]))
    stroke_fill = tuple(subtitle_cfg.get("strokeColor", [0, 0, 0, 220]))
    background = tuple(subtitle_cfg.get("backgroundColor", [0, 0, 0, 110]))

    out_dir = work_dir / "subtitle_images"
    if not dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    rendered: list[dict[str, Any]] = []
    for index, entry in enumerate(parse_srt(subtitle_path), start=1):
        image_path = out_dir / f"subtitle-{index:04d}.png"
        if not dry_run:
            image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            max_text_width = width - horizontal_padding * 2
            lines = wrap_caption_text(draw, entry["text"], font, max_text_width, stroke_width)
            if not lines:
                continue
            line_sizes = [text_size(draw, line, font, stroke_width) for line in lines]
            block_width = max(w for w, _ in line_sizes)
            block_height = sum(h for _, h in line_sizes) + line_gap * (len(lines) - 1)
            box_pad_x = int(font_size * 0.48)
            box_pad_y = int(font_size * 0.32)
            x = int((width - block_width) / 2)
            y = int(height - bottom_margin - block_height)
            box = [
                max(0, x - box_pad_x),
                max(0, y - box_pad_y),
                min(width, x + block_width + box_pad_x),
                min(height, y + block_height + box_pad_y),
            ]
            draw.rounded_rectangle(box, radius=int(font_size * 0.28), fill=background)
            cursor_y = y
            for line, (_, line_height) in zip(lines, line_sizes):
                line_width, _ = text_size(draw, line, font, stroke_width)
                draw.text(
                    ((width - line_width) / 2, cursor_y),
                    line,
                    font=font,
                    fill=fill,
                    stroke_width=stroke_width,
                    stroke_fill=stroke_fill,
                )
                cursor_y += line_height + line_gap
            image.save(image_path)
        rendered.append({"path": image_path, "start": entry["start"], "end": entry["end"]})
    return rendered


def clip_duration(clip: dict[str, Any]) -> float:
    return float(clip["end"]) - float(clip["start"])


def render_clip(
    manifest: dict[str, Any],
    source_path: Path,
    clip: dict[str, Any],
    out_path: Path,
    dry_run: bool,
    commands: list[dict[str, Any]],
) -> None:
    canvas = manifest["canvas"]
    output = manifest.get("output", {})
    audio_cfg = manifest.get("audio", {})
    keep_original_audio = bool(audio_cfg.get("keepOriginal", True))
    width = int(canvas["width"])
    height = int(canvas["height"])
    fps = float(canvas["fps"])
    start = float(clip["start"])
    duration = clip_duration(clip)
    fit = clip.get("fit", "cover")
    crop = clip.get("crop", "center")
    vf = canvas_filter(width, height, fps, fit, crop)
    preset = str(output.get("preset", "fast"))
    crf = str(output.get("crf", 20))

    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{start:.6f}",
        "-t",
        f"{duration:.6f}",
        "-i",
        str(source_path),
        "-vf",
        vf,
        "-map",
        "0:v:0",
    ]

    source_has_audio = keep_original_audio and has_audio(source_path, dry_run)
    if source_has_audio:
        fade_out_start = max(0.0, duration - 0.03)
        cmd += [
            "-map",
            "0:a:0",
            "-af",
            f"afade=t=in:st=0:d=0.03,afade=t=out:st={fade_out_start:.6f}:d=0.03,aresample=48000",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
        ]
    else:
        cmd += ["-an"]

    cmd += [
        "-c:v",
        "libx264",
        "-preset",
        preset,
        "-crf",
        crf,
        "-pix_fmt",
        "yuv420p",
        str(out_path),
    ]
    run_cmd(cmd, dry_run, commands, f"render clip {clip.get('id', out_path.stem)}")


def concat_clips(clips: list[Path], joined: Path, dry_run: bool, commands: list[dict[str, Any]]) -> None:
    concat_file = joined.parent / "concat.txt"
    concat_file.parent.mkdir(parents=True, exist_ok=True)
    concat_text = "".join(f"file '{concat_quote(path)}'\n" for path in clips)
    if not dry_run:
        concat_file.write_text(concat_text, encoding="utf-8")
    else:
        commands.append({"label": "write concat list", "path": str(concat_file), "content": concat_text})
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_file),
        "-c",
        "copy",
        str(joined),
    ]
    run_cmd(cmd, dry_run, commands, "concat normalized clips")


def add_looped_input(cmd: list[str], path: Path, loop: bool) -> None:
    if loop:
        cmd += ["-stream_loop", "-1"]
    cmd += ["-i", str(path)]


def final_mux(
    manifest: dict[str, Any],
    base: Path,
    work_dir: Path,
    joined: Path,
    output_path: Path,
    total_duration: float,
    dry_run: bool,
    commands: list[dict[str, Any]],
) -> float:
    output_cfg = manifest.get("output", {})
    audio_cfg = manifest.get("audio", {})
    subtitles = manifest.get("subtitles") if isinstance(manifest.get("subtitles"), dict) else None
    burn_requested = bool(subtitles and subtitles.get("burnIn"))
    # When the source already shows captions (a burned-in/design caption layer,
    # or a soft track), burning again produces duplicate, overlapping subtitles.
    # subtitles.sourceHasCaptions lets the caller declare that and skip the burn.
    if burn_requested and subtitles.get("sourceHasCaptions"):
        print(
            "warning: subtitles.sourceHasCaptions is set — the source already shows captions; "
            "skipping subtitle burn-in to avoid duplicate captions. Re-caption from a caption-free "
            "master (and remove sourceHasCaptions) if you really intend to re-burn.",
            file=sys.stderr,
        )
        burn_requested = False
    subtitle_path = rel_or_abs(base, subtitles.get("path")) if burn_requested else None
    voiceover = rel_or_abs(base, audio_cfg.get("voiceover")) if audio_cfg.get("voiceover") else None
    bgm = rel_or_abs(base, audio_cfg.get("bgm")) if audio_cfg.get("bgm") else None

    if not dry_run:
        for required_path, name in [(subtitle_path, "subtitles"), (voiceover, "voiceover"), (bgm, "bgm")]:
            if required_path and not required_path.exists():
                raise RenderError(f"{name} path not found: {required_path}")

    # Keep the visual timeline in sync with narration. By default the output is
    # the length of the video timeline (clips), which silently CUTS a longer
    # voiceover. timingDriver="voiceover" (or padVideoToAudio) makes the
    # voiceover the source of truth: extend the video to the narration length by
    # freezing the last frame, instead of chopping the narration.
    voice_duration = media_duration(voiceover, dry_run) if voiceover else None
    timing_driver = str(audio_cfg.get("timingDriver", "")).lower()
    pad_to_audio = bool(audio_cfg.get("padVideoToAudio")) or timing_driver == "voiceover"
    target_duration = total_duration
    video_pad = 0.0
    if voice_duration:
        if pad_to_audio and voice_duration > total_duration:
            target_duration = voice_duration
            video_pad = voice_duration - total_duration
        elif voice_duration > total_duration + 0.25:
            print(
                f"warning: voiceover ({voice_duration:.2f}s) is longer than the video timeline "
                f"({total_duration:.2f}s); narration will be CUT. Set audio.timingDriver='voiceover' "
                f"(or padVideoToAudio=true), or extend the clips to match.",
                file=sys.stderr,
            )
        elif total_duration > voice_duration + 0.5 and not bgm:
            print(
                f"warning: video timeline ({total_duration:.2f}s) runs {total_duration - voice_duration:.2f}s "
                f"past the voiceover with no BGM; the tail will be silent.",
                file=sys.stderr,
            )

    filters = ffmpeg_filters() if subtitle_path and shutil.which("ffmpeg") else set()
    use_native_subtitles = bool(subtitle_path and "subtitles" in filters)
    subtitle_images: list[dict[str, Any]] = []
    if subtitle_path and not use_native_subtitles:
        if not dry_run and "overlay" not in filters:
            raise RenderError("burned subtitles require FFmpeg subtitles filter or overlay filter")
        subtitle_images = render_subtitle_images(subtitle_path, manifest["canvas"], subtitles or {}, work_dir, dry_run)

    needs_video_encode = bool(subtitle_path) or video_pad > 0.0
    needs_audio_filter = bool(voiceover or bgm)
    joined_has_audio = has_audio(joined, dry_run)

    cmd = ["ffmpeg", "-y", "-i", str(joined)]
    input_index = 1
    subtitle_image_indices: list[tuple[int, dict[str, Any]]] = []
    for item in subtitle_images:
        cmd += ["-loop", "1", "-i", str(item["path"])]
        subtitle_image_indices.append((input_index, item))
        input_index += 1
    voice_index = None
    bgm_index = None
    if voiceover:
        add_looped_input(cmd, voiceover, loop=False)
        voice_index = input_index
        input_index += 1
    if bgm:
        add_looped_input(cmd, bgm, loop=True)
        bgm_index = input_index
        input_index += 1

    filter_parts: list[str] = []
    video_output_label: str | None = None
    # Freeze-extend the last frame so the video covers a longer narration.
    video_base = "[0:v]"
    if video_pad > 0.0:
        filter_parts.append(f"[0:v]tpad=stop_mode=clone:stop_duration={video_pad:.6f}[vbase]")
        video_base = "[vbase]"
        video_output_label = "[vbase]"
    if subtitle_path and use_native_subtitles:
        filter_parts.append(f"{video_base}{subtitle_filter(subtitle_path)}[vout]")
        video_output_label = "[vout]"
    elif subtitle_image_indices:
        current_label = video_base
        for overlay_index, (image_index, item) in enumerate(subtitle_image_indices, start=1):
            next_label = "[vout]" if overlay_index == len(subtitle_image_indices) else f"[vsub{overlay_index}]"
            filter_parts.append(
                f"{current_label}[{image_index}:v]overlay=0:0:enable='between(t,{float(item['start']):.3f},{float(item['end']):.3f})'{next_label}"
            )
            current_label = next_label
        video_output_label = "[vout]"

    audio_filter_parts: list[str] = []
    audio_labels: list[str] = []
    if needs_audio_filter:
        if joined_has_audio and audio_cfg.get("keepOriginal", True):
            audio_filter_parts.append(f"[0:a]volume={float(audio_cfg.get('originalVolume', 1.0)):.3f}[a0]")
            audio_labels.append("[a0]")
        if voice_index is not None:
            audio_filter_parts.append(f"[{voice_index}:a]volume={float(audio_cfg.get('voiceoverVolume', 1.0)):.3f}[a{voice_index}]")
            audio_labels.append(f"[a{voice_index}]")
        if bgm_index is not None:
            audio_filter_parts.append(f"[{bgm_index}:a]volume={float(audio_cfg.get('bgmVolume', 0.12)):.3f}[a{bgm_index}]")
            audio_labels.append(f"[a{bgm_index}]")
        if len(audio_labels) == 1:
            audio_filter_parts.append(f"{audio_labels[0]}atrim=0:{target_duration:.6f},asetpts=PTS-STARTPTS[aout]")
        else:
            audio_filter_parts.append(
                "".join(audio_labels)
                + f"amix=inputs={len(audio_labels)}:duration=longest:normalize=0,atrim=0:{target_duration:.6f},asetpts=PTS-STARTPTS[aout]"
            )
    filter_parts.extend(audio_filter_parts)
    if filter_parts:
        cmd += ["-filter_complex", ";".join(filter_parts)]

    if video_output_label:
        cmd += ["-map", video_output_label]
    else:
        cmd += ["-map", "0:v:0"]
    if needs_audio_filter:
        cmd += ["-map", "[aout]"]
    elif joined_has_audio:
        cmd += ["-map", "0:a?"]

    if needs_video_encode:
        cmd += [
            "-c:v",
            "libx264",
            "-preset",
            str(output_cfg.get("preset", "fast")),
            "-crf",
            str(output_cfg.get("crf", 20)),
            "-pix_fmt",
            "yuv420p",
        ]
    else:
        cmd += ["-c:v", "copy"]

    if needs_audio_filter or joined_has_audio:
        cmd += ["-c:a", "aac", "-b:a", str(output_cfg.get("audioBitrate", "128k"))]
    else:
        cmd += ["-an"]

    cmd += ["-t", f"{target_duration:.6f}", "-movflags", "+faststart", str(output_path)]
    run_cmd(cmd, dry_run, commands, "final mux")
    return target_duration


def render(manifest_path: Path, base: Path, work_dir: Path, dry_run: bool, run_log: Path | None, progress_json: bool) -> dict[str, Any]:
    if not dry_run:
        require_bin("ffmpeg")
        require_bin("ffprobe")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("engine") not in SUPPORTED_ENGINES:
        raise RenderError(f"render_ffmpeg only supports engine=ffmpeg, got {manifest.get('engine')}")
    if manifest.get("overlays"):
        print("warning: render_ffmpeg v1 ignores manifest.overlays; pre-render overlays as clips or use Remotion", file=sys.stderr)

    append_log(run_log, "render_ffmpeg", "start", str(manifest_path))
    progress(progress_json, "start", manifest=str(manifest_path))

    work_dir.mkdir(parents=True, exist_ok=True)
    output_path = rel_or_abs(base, manifest.get("output", {}).get("path"))
    if not output_path:
        raise RenderError("manifest output.path is required")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    source_map = {item["id"]: item for item in manifest.get("sources", [])}
    commands: list[dict[str, Any]] = []
    rendered_clips: list[Path] = []

    # Guard against double captions: if we are about to burn subtitles but a
    # clip source already carries a subtitle track, warn loudly. (Burned-in /
    # on-screen captions are invisible to ffprobe — those are covered by
    # subtitles.sourceHasCaptions and the SKILL.md "No double captions" rule.)
    subtitles_cfg = manifest.get("subtitles") if isinstance(manifest.get("subtitles"), dict) else None
    if subtitles_cfg and subtitles_cfg.get("burnIn") and not subtitles_cfg.get("sourceHasCaptions"):
        warned_sources: set[str] = set()
        for clip in manifest.get("clips", []):
            src = source_map.get(clip.get("source"))
            if not src:
                continue
            src_path = rel_or_abs(base, src.get("path"))
            if not src_path or str(src_path) in warned_sources:
                continue
            warned_sources.add(str(src_path))
            if not dry_run and src_path.exists() and has_subtitle_stream(src_path, dry_run):
                print(
                    f"warning: source '{src.get('id')}' already contains a subtitle track; burning "
                    f"subtitles will DUPLICATE captions. Set subtitles.sourceHasCaptions=true to skip "
                    f"the burn, or re-caption from a caption-free master.",
                    file=sys.stderr,
                )

    total_duration = 0.0
    for index, clip in enumerate(manifest.get("clips", []), start=1):
        source = source_map.get(clip.get("source"))
        if not source:
            raise RenderError(f"clip references unknown source: {clip.get('source')}")
        source_path = rel_or_abs(base, source.get("path"))
        if not source_path:
            raise RenderError(f"source {source.get('id')} missing path")
        if not dry_run and not source_path.exists():
            raise RenderError(f"source path not found: {source_path}")
        duration = clip_duration(clip)
        if duration <= 0:
            raise RenderError(f"clip {clip.get('id', index)} has non-positive duration")
        total_duration += duration
        out_path = work_dir / f"clip-{index:04d}-{clip.get('id', index)}.mp4"
        render_clip(manifest, source_path, clip, out_path, dry_run, commands)
        rendered_clips.append(out_path)
        progress(progress_json, "item", item=index, total=len(manifest.get("clips", [])), pct=math.floor(index / len(manifest.get("clips", [])) * 70))

    if not rendered_clips:
        raise RenderError("manifest clips is empty")

    joined = work_dir / "joined.mp4"
    concat_clips(rendered_clips, joined, dry_run, commands)
    progress(progress_json, "concat", pct=80)

    final_duration = final_mux(manifest, base, work_dir, joined, output_path, total_duration, dry_run, commands)
    total_duration = final_duration if final_duration else total_duration
    progress(progress_json, "complete", pct=100, output=str(output_path))
    append_log(run_log, "render_ffmpeg", "done", str(output_path))

    return {
        "status": "dry-run" if dry_run else "rendered",
        "manifest": str(manifest_path),
        "output": str(output_path),
        "workDir": str(work_dir),
        "duration": total_duration,
        "commands": commands,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest")
    parser.add_argument("--base-dir", default=None, help="Base dir for relative manifest paths; defaults to manifest parent")
    parser.add_argument("--work-dir", default=None)
    parser.add_argument("--run-log", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--progress-json", action="store_true")
    parser.add_argument("--plan-output", default=None, help="Write command plan JSON")
    args = parser.parse_args()

    manifest_path = Path(args.manifest).expanduser().resolve()
    base = Path(args.base_dir).expanduser().resolve() if args.base_dir else manifest_path.parent
    work_dir = Path(args.work_dir).expanduser().resolve() if args.work_dir else base / "work" / "render_ffmpeg"
    run_log = Path(args.run_log).expanduser().resolve() if args.run_log else base / "run-log.jsonl"

    try:
        result = render(manifest_path, base, work_dir, args.dry_run, run_log, args.progress_json)
    except Exception as exc:
        append_log(run_log, "render_ffmpeg", "fail", str(exc))
        print(f"render_ffmpeg failed: {exc}", file=sys.stderr)
        return 2

    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.plan_output:
        plan_path = Path(args.plan_output).expanduser().resolve()
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
