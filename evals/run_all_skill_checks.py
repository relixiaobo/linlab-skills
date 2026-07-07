#!/usr/bin/env python3
"""Run all repository skill validation gates."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUICK_VALIDATE = Path.home() / ".codex" / "skills" / ".system" / "skill-creator" / "scripts" / "quick_validate.py"
SKILLS = [
    "code-review",
    "data-analysis",
    "document",
    "feed-processing",
    "pdf",
    "presentation",
    "shape-product-spec",
    "spreadsheet",
    "video-studio",
    "archive/research",
]


def run(name: str, cmd: list[str]) -> dict:
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)
    return {
        "name": name,
        "cmd": cmd,
        "exit": proc.returncode,
        "ok": proc.returncode == 0,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def python_for_data_analysis() -> str:
    venv_python = ROOT / ".venv" / "bin" / "python"
    return str(venv_python) if venv_python.exists() else sys.executable


def main() -> int:
    checks: list[dict] = []
    if not QUICK_VALIDATE.exists():
        checks.append({
            "name": "quick_validate",
            "cmd": [str(QUICK_VALIDATE)],
            "exit": 1,
            "ok": False,
            "stdout_tail": "",
            "stderr_tail": f"missing {QUICK_VALIDATE}",
        })
    else:
        for skill in SKILLS:
            checks.append(run(f"quick_validate:{skill}", [sys.executable, str(QUICK_VALIDATE), skill]))

    checks.extend([
        run("code-review", [sys.executable, "evals/code-review/run_checks.py"]),
        run("artifact-skills", [sys.executable, "evals/run_artifact_skill_checks.py"]),
        run("data-analysis", [python_for_data_analysis(), "evals/data-analysis/run_checks.py"]),
        run("feed-processing", [sys.executable, "evals/feed-processing/run_checks.py"]),
        run("shape-product-spec", [sys.executable, "evals/shape-product-spec/run_checks.py"]),
        run("video-studio", [sys.executable, "evals/video-studio/run_checks.py"]),
        run("python-compile", [
            sys.executable, "-m", "py_compile",
            "evals/run_all_skill_checks.py",
            "evals/run_artifact_skill_checks.py",
            "evals/code-review/run_checks.py",
            "evals/data-analysis/run_checks.py",
            "evals/feed-processing/run_checks.py",
            "evals/shape-product-spec/run_checks.py",
            "evals/video-studio/run_checks.py",
            "document/scripts/docx_tool.py",
            "presentation/scripts/pptx_tool.py",
            "pdf/scripts/pdf_tool.py",
            "shape-product-spec/scripts/spec_check.py",
            "spreadsheet/scripts/table_tool.py",
            "spreadsheet/scripts/workbook_tool.py",
            "video-studio/scripts/build_publish_package.py",
            "video-studio/scripts/captions_from_script.py",
            "video-studio/scripts/composite_overlay.py",
            "video-studio/scripts/doctor.py",
            "video-studio/scripts/make_cover.py",
            "video-studio/scripts/probe_media.py",
            "video-studio/scripts/qa_video.py",
            "video-studio/scripts/render_ffmpeg.py",
            "video-studio/scripts/render_frames_to_video.py",
            "video-studio/scripts/render_manim.py",
            "video-studio/scripts/scene_timing.py",
            "video-studio/scripts/validate_manifest.py",
        ]),
    ])

    node = shutil.which("node")
    if node:
        for script in [
            "document/scripts/markdown_tool.mjs",
            "presentation/scripts/html_tool.mjs",
            "feed-processing/scripts/feed_diff.mjs",
            "feed-processing/scripts/feed_discover.mjs",
            "feed-processing/scripts/feed_fetch.mjs",
            "feed-processing/scripts/feed_pack.mjs",
            "feed-processing/scripts/feed_parse.mjs",
            "feed-processing/scripts/feed_profile.mjs",
            "feed-processing/scripts/feed_rules.mjs",
            "feed-processing/scripts/feed_window.mjs",
            "feed-processing/scripts/full_text_extract.mjs",
            "feed-processing/scripts/lib/feed_common.mjs",
            "feed-processing/scripts/opml_tool.mjs",
            "feed-processing/scripts/source_list.mjs",
            "feed-processing/scripts/validate_feed_pack.mjs",
            "video-studio/scripts/capture_web_frames.mjs",
        ]:
            checks.append(run(f"node-check:{script}", [node, "--check", script]))
    else:
        checks.append({
            "name": "node-check",
            "cmd": ["node", "--check"],
            "exit": 1,
            "ok": False,
            "stdout_tail": "",
            "stderr_tail": "node is required for .mjs script checks",
        })

    ok = all(item["ok"] for item in checks)
    report = {"ok": ok, "checks": checks}
    print(json.dumps(report, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
