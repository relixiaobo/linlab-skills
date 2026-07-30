#!/usr/bin/env python3
"""Author burn-ready subtitles (SRT/ASS) from a KNOWN script.

This is not ASR. It turns a script that the caller already has (the narration
text, the storyboard lines, the on-screen copy) into a timed caption track, for
when the user has asked for subtitles. Captions are opt-in; do not add them
unrequested. Long lines are split at punctuation into short, sequential cues so
they read like normal subtitles instead of a two/three-line block.

Two ways to supply timing:

1. Timed lines (preferred, e.g. derived from a voiceover or storyboard):

   {"lines": [
     {"text": "First line", "start": 0.0, "end": 2.4},
     {"text": "Second line", "start": 2.4, "end": 5.1}
   ]}

2. Untimed text + a total duration -> evenly distributed:

   {"lines": ["First line", "Second line", "Third line"], "duration": 30}
   or  --text "First line. Second line. Third line." --duration 30

When a narration audio file exists, pass --voiceover to align cues to the REAL
speech timing (via ffmpeg silencedetect, still no ASR) and take the total
duration from the audio, so captions track what is actually being said instead
of drifting against an evenly-distributed guess.

Output is always SRT. Pass --ass-out to also emit a styled ASS track using the
bundled short-video-bold style header.

Examples:
  python3 captions_from_script.py --script script.json --srt-out media/assets/subtitles.srt
  python3 captions_from_script.py --text "Opening line. Second line. Closing line." --duration 18 \
      --srt-out media/assets/subtitles.srt --ass-out media/assets/subtitles.ass
  python3 captions_from_script.py --text "Opening line. Second line. Closing line." \
      --voiceover media/audio/voiceover.mp3 --srt-out media/assets/subtitles.srt
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path
from typing import Any


def display_len(text: str) -> int:
    """Approximate on-screen width in half-width units.

    CJK and other full/wide glyphs occupy ~2x a latin character, so measuring
    raw `len()` lets a "20-character" CJK line overflow to two or three wrapped
    rows. Counting wide glyphs as 2 keeps cues to roughly one readable line.
    """
    width = 0
    for ch in text:
        width += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return width


def hard_split(text: str, max_units: int) -> list[str]:
    """Split a separator-less run into <= max_units-wide chunks (display width)."""
    chunks: list[str] = []
    buffer = ""
    width = 0
    for ch in text:
        ch_w = 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
        if width + ch_w > max_units and buffer:
            chunks.append(buffer)
            buffer, width = ch, ch_w
        else:
            buffer += ch
            width += ch_w
    if buffer:
        chunks.append(buffer)
    return chunks or [text]


# Sentence terminators for CJK and latin text. CJK/full-width punctuation is
# written as \u escapes so this source stays ASCII-only while still segmenting
# CJK narration at runtime (ideographic stop, full-width ! ? ;, ellipsis).
# Latin sentences split on . ! ? ; that are followed by whitespace.
_SENTENCE_SPLIT = re.compile(r"(?<=[\u3002\uff01\uff1f\uff1b\u2026\n])|(?<=[.!?;])(?=\s)")


def audio_duration(path: Path) -> float:
    """Seconds of an audio/video file via ffprobe."""
    if not shutil.which("ffprobe"):
        raise SystemExit("ffprobe not found; required for --voiceover alignment")
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        return float(proc.stdout.strip())
    except ValueError as exc:
        raise SystemExit(f"could not read duration of {path}: {proc.stderr.strip()}") from exc


def detect_speech_spans(path: Path, total: float, noise_db: float, min_silence: float) -> list[tuple[float, float]]:
    """Return [(start, end)] speech spans using ffmpeg silencedetect (no ASR)."""
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg not found; required for --voiceover alignment")
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(path),
            "-af",
            f"silencedetect=noise={noise_db}dB:d={min_silence}",
            "-f",
            "null",
            "-",
        ],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    silences: list[tuple[float, float]] = []
    start: float | None = None
    for match in re.finditer(r"silence_(start|end):\s*(-?\d+(?:\.\d+)?)", proc.stderr):
        kind, value = match.group(1), float(match.group(2))
        if kind == "start":
            start = max(0.0, value)
        elif kind == "end" and start is not None:
            silences.append((start, value))
            start = None

    # Complement of silence within [0, total] = speech spans.
    spans: list[tuple[float, float]] = []
    cursor = 0.0
    for s_start, s_end in silences:
        if s_start - cursor > 0.05:
            spans.append((cursor, min(s_start, total)))
        cursor = max(cursor, s_end)
    if total - cursor > 0.05:
        spans.append((cursor, total))
    return spans or [(0.0, total)]


def _speechtime_to_real(spans: list[tuple[float, float]], target: float) -> float:
    """Map a position in cumulative speech-time to a real timestamp."""
    remaining = target
    for span_start, span_end in spans:
        length = span_end - span_start
        if remaining <= length:
            return span_start + remaining
        remaining -= length
    return spans[-1][1]


def align_to_speech(texts: list[str], spans: list[tuple[float, float]]) -> list[dict[str, Any]]:
    """Place cues at real speech timing, weighting by character length."""
    # Best case: one detected speech phrase per line -> snap 1:1.
    if len(spans) == len(texts):
        return [
            {"start": round(start, 3), "end": round(end, 3), "text": text}
            for text, (start, end) in zip(texts, spans)
        ]

    total_speech = sum(end - start for start, end in spans)
    weights = [max(1, display_len(t)) for t in texts]
    total_weight = sum(weights)
    entries: list[dict[str, Any]] = []
    cursor = 0.0
    for text, weight in zip(texts, weights):
        slice_len = total_speech * weight / total_weight
        start = _speechtime_to_real(spans, cursor)
        end = _speechtime_to_real(spans, min(total_speech, cursor + slice_len))
        if end <= start:
            end = min(spans[-1][1], start + 0.6)
        entries.append({"start": round(start, 3), "end": round(end, 3), "text": text})
        cursor += slice_len
    return entries


def split_text_into_lines(text: str, max_chars: int) -> list[str]:
    """Split raw script text into caption-sized lines."""
    raw = [seg.strip() for seg in _SENTENCE_SPLIT.split(text) if seg.strip()]
    if not raw:
        raw = [chunk.strip() for chunk in text.splitlines() if chunk.strip()]

    lines: list[str] = []
    for sentence in raw:
        if display_len(sentence) <= max_chars:
            lines.append(sentence)
            continue
        # Wrap an over-long sentence on commas/spaces, else hard-split.
        lines.extend(_wrap_long(sentence, max_chars))
    return lines


# Clause separators to wrap an over-long sentence on: CJK + latin commas,
# enumeration comma, semicolons, colons. Kept ATTACHED to the preceding text so
# a cue never starts with a dangling "\u3001" or "\uff0c".
_CLAUSE_ATOM = re.compile(r"[^\uff0c,\u3001\uff1b;\uff1a:\s]+[\uff0c,\u3001\uff1b;\uff1a:]*\s*")


_PUNCT_ONLY = re.compile(r"^[\uff0c,\u3001\uff1b;\uff1a:\u3002\uff01\uff1f!?\u2026\uff0e.]+$")


def _merge_tiny(parts: list[str], max_chars: int, min_units: int = 6) -> list[str]:
    """Fold an orphan fragment (a stray "\uff0c" or a 1-2 char tail) into a neighbour."""
    out: list[str] = []
    for part in parts:
        # Punctuation that got split off always rejoins the preceding line; a
        # short word fragment rejoins only if it still fits the budget.
        punct_only = bool(_PUNCT_ONLY.match(part))
        if out and (punct_only or (display_len(part) < min_units and display_len(out[-1]) + display_len(part) <= max_chars)):
            out[-1] = out[-1] + part
        else:
            out.append(part)
    if len(out) >= 2 and not _PUNCT_ONLY.match(out[0]) and display_len(out[0]) < min_units and display_len(out[0]) + display_len(out[1]) <= max_chars:
        out = [out[0] + out[1], *out[2:]]
    return out


def _wrap_long(sentence: str, max_chars: int) -> list[str]:
    atoms = [a for a in (m.group(0) for m in _CLAUSE_ATOM.finditer(sentence)) if a.strip()]
    if not atoms:
        atoms = [sentence]
    parts: list[str] = []
    buffer = ""
    for atom in atoms:
        if buffer.strip() and display_len((buffer + atom).strip()) > max_chars:
            parts.append(buffer.strip())
            buffer = atom
        else:
            buffer += atom
    if buffer.strip():
        parts.append(buffer.strip())
    # An atom with no internal separator can still exceed the budget: hard-split it.
    expanded: list[str] = []
    for part in parts:
        if display_len(part) <= max_chars:
            expanded.append(part)
        else:
            expanded.extend(hard_split(part, max_chars))
    return _merge_tiny(expanded, max_chars) or [sentence.strip()]


def _distribute(texts: list[str], win_start: float, win_end: float, gap: float) -> list[dict[str, Any]]:
    """Lay cues across [win_start, win_end], weighted by length, never overlapping."""
    weights = [max(1, display_len(t)) for t in texts]
    total_weight = sum(weights)
    window = max(0.0, win_end - win_start)
    cues: list[dict[str, Any]] = []
    cursor = win_start
    last = len(texts) - 1
    for index, (text, weight) in enumerate(zip(texts, weights)):
        seg_end = win_end if index == last else cursor + window * weight / total_weight
        cue_end = seg_end if index == last else seg_end - gap
        if cue_end <= cursor:
            cue_end = seg_end
        cues.append({"start": round(cursor, 3), "end": round(cue_end, 3), "text": text})
        cursor = seg_end
    return cues


def subdivide_cue(text: str, start: float, end: float, max_chars: int, gap: float) -> list[dict[str, Any]]:
    """Split one timed cue into short, sequential sub-cues.

    A timed line is often a whole sentence; shown as one cue it wraps to two or
    three lines at once, which does not read like normal subtitles. Split it at
    punctuation into one-phrase pieces and divide the cue's own time window
    between them (weighted by length), so captions appear one short line at a
    time instead of as a block.
    """
    pieces = split_text_into_lines(text, max_chars)
    if len(pieces) <= 1:
        return [{"start": round(start, 3), "end": round(end, 3), "text": text.strip()}]
    return _distribute(pieces, start, end, gap)


def build_entries(
    raw_lines: list[Any],
    duration: float | None,
    max_chars: int,
    gap: float,
) -> list[dict[str, Any]]:
    """Return [{start, end, text}] for SRT/ASS emission."""
    # Case 1: already-timed dict lines. Subdivide any long line so cues stay
    # short and one-line, like normal subtitles.
    if raw_lines and isinstance(raw_lines[0], dict):
        entries: list[dict[str, Any]] = []
        for item in raw_lines:
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            start = float(item["start"])
            end = float(item.get("end", start))
            if end <= start:
                continue
            entries.extend(subdivide_cue(text, start, end, max_chars, gap))
        if not entries:
            raise SystemExit("no timed lines with valid start/end found")
        return entries

    # Case 2: plain strings distributed across duration.
    texts = [str(line).strip() for line in raw_lines if str(line).strip()]
    if not texts:
        raise SystemExit("no caption text found")
    if not duration or duration <= 0:
        raise SystemExit("untimed lines require a positive --duration (or duration in the script JSON)")

    # Re-split any over-long string so cues stay readable.
    normalized: list[str] = []
    for text in texts:
        normalized.extend(split_text_into_lines(text, max_chars))

    # Lay cues across the duration, weighted by on-screen length, never overlapping.
    return _distribute(normalized, 0.0, duration, gap)


def fmt_srt_time(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def fmt_ass_time(seconds: float) -> str:
    cs = int(round(seconds * 100))
    h, cs = divmod(cs, 360_000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def to_srt(entries: list[dict[str, Any]]) -> str:
    blocks = []
    for i, entry in enumerate(entries, start=1):
        blocks.append(
            f"{i}\n{fmt_srt_time(entry['start'])} --> {fmt_srt_time(entry['end'])}\n{entry['text']}\n"
        )
    return "\n".join(blocks)


def to_ass(entries: list[dict[str, Any]], style_header: str | None) -> str:
    header = style_header or _DEFAULT_ASS_HEADER
    lines = [header.rstrip("\n"), ""]
    for entry in entries:
        text = entry["text"].replace("\n", "\\N")
        lines.append(
            f"Dialogue: 0,{fmt_ass_time(entry['start'])},{fmt_ass_time(entry['end'])},Default,,0,0,0,,{text}"
        )
    return "\n".join(lines) + "\n"


_DEFAULT_ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Noto Sans CJK SC,72,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,4,0,2,80,80,260,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"""


def load_ass_header(style_path: str | None) -> str | None:
    if not style_path:
        # Default to the bundled style relative to this script.
        bundled = Path(__file__).resolve().parent.parent / "assets" / "ass-styles" / "short-video-bold.ass"
        style_path = str(bundled) if bundled.exists() else None
    if not style_path:
        return None
    text = Path(style_path).expanduser().read_text(encoding="utf-8")
    # Keep everything up to and including the [Events] Format line.
    marker = text.find("[Events]")
    if marker == -1:
        return text.rstrip("\n")
    tail = text[marker:]
    fmt_end = tail.find("\n", tail.find("Format:"))
    cutoff = marker + (fmt_end if fmt_end != -1 else len(tail))
    return text[:cutoff].rstrip("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--script", help="JSON with {lines:[...], duration?:number}")
    src.add_argument("--text", help="Raw script text to split into cues")
    parser.add_argument("--duration", type=float, help="Total seconds for untimed lines")
    parser.add_argument("--voiceover", help="Align cues to this narration audio via silencedetect (no ASR)")
    parser.add_argument("--noise-db", type=float, default=-35.0, help="silencedetect noise floor for --voiceover")
    parser.add_argument("--min-silence", type=float, default=0.32, help="Min silence seconds to split on for --voiceover")
    parser.add_argument(
        "--max-chars",
        type=int,
        default=24,
        help="Max on-screen width per caption line in half-width units (CJK/full-width counts as 2); "
        "~24 keeps a cue to one short line. Lower for narrow/vertical frames.",
    )
    parser.add_argument("--gap", type=float, default=0.12, help="Silent gap between cues, seconds")
    parser.add_argument("--srt-out", required=True, help="Output .srt path")
    parser.add_argument("--ass-out", help="Optional output .ass path (styled)")
    parser.add_argument("--ass-style", help="ASS style file to source the header from")
    args = parser.parse_args()

    duration = args.duration
    if args.script:
        data = json.loads(Path(args.script).expanduser().read_text(encoding="utf-8"))
        raw_lines = data.get("lines", [])
        if duration is None:
            duration = data.get("duration")
    else:
        raw_lines = split_text_into_lines(args.text, args.max_chars)

    aligned_to: str | None = None
    if args.voiceover and not (raw_lines and isinstance(raw_lines[0], dict)):
        # Align untimed lines to the real narration so caption timing tracks speech.
        voice = Path(args.voiceover).expanduser().resolve()
        if not voice.exists():
            raise SystemExit(f"voiceover not found: {voice}")
        total = audio_duration(voice)
        spans = detect_speech_spans(voice, total, args.noise_db, args.min_silence)
        texts: list[str] = []
        for line in raw_lines:
            texts.extend(split_text_into_lines(str(line), args.max_chars))
        entries = align_to_speech(texts, spans)
        duration = total
        aligned_to = str(voice)
    else:
        # Explicit timed lines win; otherwise even-distribute across --duration.
        entries = build_entries(raw_lines, duration, args.max_chars, args.gap)

    srt_path = Path(args.srt_out).expanduser().resolve()
    srt_path.parent.mkdir(parents=True, exist_ok=True)
    srt_path.write_text(to_srt(entries), encoding="utf-8")

    result: dict[str, Any] = {
        "status": "ok",
        "cues": len(entries),
        "srt": str(srt_path),
        "start": entries[0]["start"],
        "end": entries[-1]["end"],
        "duration": round(duration, 3) if duration else entries[-1]["end"],
        "alignedTo": aligned_to,
    }

    if args.ass_out:
        ass_path = Path(args.ass_out).expanduser().resolve()
        ass_path.parent.mkdir(parents=True, exist_ok=True)
        ass_path.write_text(to_ass(entries, load_ass_header(args.ass_style)), encoding="utf-8")
        result["ass"] = str(ass_path)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
