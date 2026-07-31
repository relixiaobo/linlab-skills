#!/usr/bin/env python3
"""Generate a simple mobile-readable cover image."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def extract_frame(video: Path, timestamp: str, output: Path) -> None:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found; provide --background instead")
    proc = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            timestamp,
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(output),
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "failed to extract frame")


def fit_cover(image: Image.Image, width: int, height: int) -> Image.Image:
    image = image.convert("RGB")
    scale = max(width / image.width, height / image.height)
    resized = image.resize((round(image.width * scale), round(image.height * scale)))
    left = (resized.width - width) // 2
    top = (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def find_font(font_path: str | None, size: int) -> ImageFont.ImageFont:
    if font_path:
        return ImageFont.truetype(font_path, size=size)
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    if not text:
        return []
    lines: list[str] = []
    current = ""
    for char in text:
        candidate = current + char
        bbox = draw.textbbox((0, 0), candidate, font=font, stroke_width=2)
        if bbox[2] - bbox[0] <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = char
    if current:
        lines.append(current)
    return lines


def draw_centered_text(
    image: Image.Image,
    title: str,
    subtitle: str | None,
    font_path: str | None,
    style: str,
) -> None:
    draw = ImageDraw.Draw(image)
    width, height = image.size
    title_font = find_font(font_path, max(48, width // 10))
    subtitle_font = find_font(font_path, max(28, width // 22))
    max_width = int(width * 0.82)
    title_lines = wrap_text(draw, title, title_font, max_width)[:3]
    subtitle_lines = wrap_text(draw, subtitle or "", subtitle_font, max_width)[:2]

    line_heights = []
    for line in title_lines:
        bbox = draw.textbbox((0, 0), line, font=title_font, stroke_width=4)
        line_heights.append(bbox[3] - bbox[1] + 14)
    for line in subtitle_lines:
        bbox = draw.textbbox((0, 0), line, font=subtitle_font, stroke_width=2)
        line_heights.append(bbox[3] - bbox[1] + 10)
    total = sum(line_heights) + (24 if subtitle_lines else 0)
    y = (height - total) // 2

    if style in {"frame", "image"}:
        overlay = Image.new("RGBA", image.size, (0, 0, 0, 115))
        image.paste(Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB"))

    for line in title_lines:
        bbox = draw.textbbox((0, 0), line, font=title_font, stroke_width=4)
        x = (width - (bbox[2] - bbox[0])) // 2
        draw.text((x, y), line, font=title_font, fill="white", stroke_width=4, stroke_fill="black")
        y += bbox[3] - bbox[1] + 14

    if subtitle_lines:
        y += 24
    for line in subtitle_lines:
        bbox = draw.textbbox((0, 0), line, font=subtitle_font, stroke_width=2)
        x = (width - (bbox[2] - bbox[0])) // 2
        draw.text((x, y), line, font=subtitle_font, fill=(255, 230, 80), stroke_width=2, stroke_fill="black")
        y += bbox[3] - bbox[1] + 10


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", required=True)
    parser.add_argument("--subtitle")
    parser.add_argument("--output", required=True)
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--background")
    parser.add_argument("--video")
    parser.add_argument("--timestamp", default="00:00:01")
    parser.add_argument("--font")
    parser.add_argument("--style", choices=["bold", "frame", "image"], default="bold")
    args = parser.parse_args()

    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    if args.background:
        base = fit_cover(Image.open(Path(args.background).expanduser()), args.width, args.height)
    elif args.video:
        with tempfile.TemporaryDirectory() as tmp:
            frame = Path(tmp) / "frame.png"
            extract_frame(Path(args.video).expanduser().resolve(), args.timestamp, frame)
            base = fit_cover(Image.open(frame), args.width, args.height)
    else:
        base = Image.new("RGB", (args.width, args.height), (16, 16, 16))

    if args.style == "bold":
        base = Image.new("RGB", (args.width, args.height), (16, 16, 16))

    draw_centered_text(base, args.title, args.subtitle, args.font, args.style)
    base.save(output)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
