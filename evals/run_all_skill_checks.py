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
    ("code-review", "skills/code-review"),
    ("data-analysis", "skills/data-analysis"),
    ("document", "skills/document"),
    ("feed-processing", "skills/feed-processing"),
    ("pdf", "skills/pdf"),
    ("presentation", "skills/presentation"),
    ("shape-product-spec", "skills/shape-product-spec"),
    ("spreadsheet", "skills/spreadsheet"),
    ("video-studio", "skills/video-studio"),
    ("archive/research", "archive/research"),
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
        for check_name, skill_path in SKILLS:
            checks.append(run(
                f"quick_validate:{check_name}",
                [sys.executable, str(QUICK_VALIDATE), skill_path],
            ))

    checks.extend([
        run("eval-platform-unit", [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests/unit",
            "-p",
            "test_*.py",
            "-v",
        ]),
        run("eval-suite-contract", [
            sys.executable,
            "evals/runners/evalctl.py",
            "validate",
            "--suite",
            "evals/suites/representative-ab.json",
        ]),
        run("eval-presentation-image-contract", [
            sys.executable,
            "evals/runners/evalctl.py",
            "validate",
            "--suite",
            "evals/suites/presentation-image-smoke.json",
        ]),
        run("eval-presentation-image-assets-contract", [
            sys.executable,
            "evals/runners/evalctl.py",
            "validate",
            "--suite",
            "evals/suites/presentation-image-assets-smoke.json",
        ]),
        run("code-review", [sys.executable, "evals/code-review/run_checks.py"]),
        run("artifact-skills", [sys.executable, "evals/run_artifact_skill_checks.py"]),
        run("presentation", [sys.executable, "tests/integration/presentation/run_checks.py"]),
        run("data-analysis", [python_for_data_analysis(), "tests/integration/data-analysis/run_checks.py"]),
        run("feed-processing", [sys.executable, "evals/feed-processing/run_checks.py"]),
        run("shape-product-spec", [sys.executable, "tests/integration/shape-product-spec/run_checks.py"]),
        run("video-studio", [sys.executable, "evals/video-studio/run_checks.py"]),
    ])

    python_files = [
        "evals/run_all_skill_checks.py",
        "evals/run_artifact_skill_checks.py",
        "evals/code-review/run_checks.py",
        "evals/data-analysis/run_checks.py",
        "evals/feed-processing/run_checks.py",
        "evals/presentation/run_checks.py",
        "evals/judges/common.py",
        "evals/judges/data_analysis_judge_adapter.py",
        "evals/judges/model_judge_runtime.py",
        "evals/judges/presentation_judge_adapter.py",
        "evals/judges/product_spec_judge_adapter.py",
        "evals/runners/codex_exec_adapter.py",
        "evals/runners/errors.py",
        "evals/runners/eval_lib.py",
        "evals/runners/evalctl.py",
        "evals/runners/schema_validation.py",
        "evals/shape-product-spec/run_checks.py",
        "evals/video-studio/run_checks.py",
        "tests/integration/data-analysis/run_checks.py",
        "tests/integration/shape-product-spec/run_checks.py",
        "tests/unit/eval_platform/test_codex_exec_adapter.py",
        "tests/unit/eval_platform/test_data_analysis_judge.py",
        "tests/unit/eval_platform/test_eval_runner.py",
        "tests/unit/eval_platform/test_presentation_judge.py",
        "tests/unit/eval_platform/test_product_spec_judge.py",
        "tests/fixtures/evals/fake_agent.py",
        "tests/fixtures/evals/fake_codex_judge.py",
        "tests/fixtures/evals/fake_judge.py",
        "tests/fixtures/evals/fake_mutating_judge.py",
        "tests/fixtures/evals/fake_secondary_judge.py",
        "skills/document/scripts/docx_tool.py",
        "skills/presentation/scripts/pptx_tool.py",
        "skills/presentation/scripts/evidence_tool.py",
        "skills/presentation/scripts/render_slides.py",
        "skills/pdf/scripts/pdf_tool.py",
        "skills/shape-product-spec/scripts/spec_check.py",
        "skills/spreadsheet/scripts/table_tool.py",
        "skills/spreadsheet/scripts/workbook_tool.py",
        "skills/video-studio/scripts/build_publish_package.py",
        "skills/video-studio/scripts/captions_from_script.py",
        "skills/video-studio/scripts/composite_overlay.py",
        "skills/video-studio/scripts/doctor.py",
        "skills/video-studio/scripts/make_cover.py",
        "skills/video-studio/scripts/probe_media.py",
        "skills/video-studio/scripts/qa_video.py",
        "skills/video-studio/scripts/render_ffmpeg.py",
        "skills/video-studio/scripts/render_frames_to_video.py",
        "skills/video-studio/scripts/render_manim.py",
        "skills/video-studio/scripts/scene_timing.py",
        "skills/video-studio/scripts/validate_manifest.py",
    ]
    python_files.extend(
        str(path.relative_to(ROOT))
        for path in sorted((ROOT / "tests" / "integration" / "presentation").glob("*.py"))
    )
    checks.append(run("python-compile", [sys.executable, "-m", "py_compile", *python_files]))

    node = shutil.which("node")
    if node:
        for script in [
            "skills/document/scripts/markdown_tool.mjs",
            "skills/presentation/scripts/html_tool.mjs",
            "skills/presentation/scripts/render_theme_previews.mjs",
            "skills/presentation/scripts/studio_tool.mjs",
            "tests/fixtures/evals/presentation-image-assets/render_assets.mjs",
            "skills/feed-processing/scripts/feed_diff.mjs",
            "skills/feed-processing/scripts/feed_discover.mjs",
            "skills/feed-processing/scripts/feed_fetch.mjs",
            "skills/feed-processing/scripts/feed_pack.mjs",
            "skills/feed-processing/scripts/feed_parse.mjs",
            "skills/feed-processing/scripts/feed_profile.mjs",
            "skills/feed-processing/scripts/feed_rules.mjs",
            "skills/feed-processing/scripts/feed_window.mjs",
            "skills/feed-processing/scripts/full_text_extract.mjs",
            "skills/feed-processing/scripts/lib/feed_common.mjs",
            "skills/feed-processing/scripts/opml_tool.mjs",
            "skills/feed-processing/scripts/source_list.mjs",
            "skills/feed-processing/scripts/validate_feed_pack.mjs",
            "skills/video-studio/scripts/capture_web_frames.mjs",
        ]:
            check_name = script.removeprefix("skills/")
            checks.append(run(f"node-check:{check_name}", [node, "--check", script]))
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
