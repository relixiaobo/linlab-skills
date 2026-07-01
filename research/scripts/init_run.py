#!/usr/bin/env python3
"""Create a .research run directory for artifact-backed research."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def slugify(value: str, max_len: int = 72) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    return (value or "research")[:max_len].strip("-") or "research"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_if_missing(path: Path, content: str) -> None:
    if not path.exists():
        path.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--domain", default="general")
    parser.add_argument("--depth", default="standard", choices=["quick", "standard", "deep"])
    parser.add_argument("--root", default=".research")
    parser.add_argument("--slug")
    args = parser.parse_args()

    root = Path(args.root)
    slug = args.slug or slugify(args.topic)
    run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{slug}"
    topic_dir = root / slug
    runs_dir = root / "runs"
    raw_dir = topic_dir / "raw"

    runs_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "run_id": run_id,
        "topic": args.topic,
        "domain": args.domain,
        "depth": args.depth,
        "created_at": now_iso(),
        "topic_dir": str(topic_dir),
    }

    write_if_missing(root / "INDEX.md", "# Research Index\n\n")
    write_if_missing(topic_dir / "route.txt", f"domain: {args.domain}\ndepth: {args.depth}\n")
    write_if_missing(topic_dir / "plan.md", f"# Research Plan\n\nTopic: {args.topic}\n\n")
    write_if_missing(topic_dir / "sources.jsonl", "")
    write_if_missing(topic_dir / "claims.jsonl", "")
    write_if_missing(topic_dir / "audit.md", f"# Audit\n\nRun: {run_id}\nCreated: {meta['created_at']}\n\n")
    write_if_missing(topic_dir / "report.md", f"# {args.topic}\n\n")

    (runs_dir / f"{run_id}.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    with (root / "INDEX.md").open("a", encoding="utf-8") as fh:
        fh.write(f"- {meta['created_at']} [{args.topic}]({slug}/report.md) - {args.domain}, {args.depth}\n")

    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
