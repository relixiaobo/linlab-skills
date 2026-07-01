#!/usr/bin/env python3
"""Build a social/video publish handoff package JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def resolve(path: str | None) -> str | None:
    if not path:
        return None
    return str(Path(path).expanduser().resolve())


def exists_or_blocking(path: str | None, label: str, blocking: list[str]) -> str | None:
    resolved = resolve(path)
    if resolved and not Path(resolved).exists():
        blocking.append(f"{label} not found: {resolved}")
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", required=True)
    parser.add_argument("--video", required=True)
    parser.add_argument("--cover")
    parser.add_argument("--title", required=True)
    parser.add_argument("--body", default="")
    parser.add_argument("--tags", default="")
    parser.add_argument("--srt")
    parser.add_argument("--vtt")
    parser.add_argument("--ass")
    parser.add_argument("--qa")
    parser.add_argument("--output", required=True)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    blocking: list[str] = []
    tags = [tag.strip().lstrip("#") for tag in args.tags.split(",") if tag.strip()]

    package: dict[str, Any] = {
        "version": 1,
        "platform": args.platform,
        "video": exists_or_blocking(args.video, "video", blocking),
        "cover": exists_or_blocking(args.cover, "cover", blocking),
        "subtitles": {
            "srt": exists_or_blocking(args.srt, "srt", blocking),
            "vtt": exists_or_blocking(args.vtt, "vtt", blocking),
            "ass": exists_or_blocking(args.ass, "ass", blocking),
        },
        "copy": {
            "title": args.title,
            "body": args.body,
            "tags": tags,
        },
        "qa": exists_or_blocking(args.qa, "qa", blocking),
        "ready": False,
        "blocking": blocking,
    }

    if not args.title.strip():
        package["blocking"].append("title is empty")
    package["ready"] = not package["blocking"]

    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(package, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(package, indent=2, ensure_ascii=False))
    return 2 if args.strict and package["blocking"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
