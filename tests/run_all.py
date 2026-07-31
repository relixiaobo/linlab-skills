#!/usr/bin/env python3
"""Run all repository skill validation gates."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from integration.skills.baseline_comparison import compare_baseline


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

# Phase 0 baseline ID -> current mandatory check ID.
# quick_validate:code-review              -> skill-packages:code-review
# quick_validate:data-analysis            -> skill-packages:data-analysis
# quick_validate:document                 -> skill-packages:document
# quick_validate:feed-processing          -> skill-packages:feed-processing
# quick_validate:pdf                      -> skill-packages:pdf
# quick_validate:presentation             -> skill-packages:presentation
# quick_validate:shape-product-spec       -> skill-packages:shape-product-spec
# quick_validate:spreadsheet              -> skill-packages:spreadsheet
# quick_validate:video-studio             -> skill-packages:video-studio
# quick_validate:archive/research         -> skill-packages:archive/research
# eval-suite-contract                     -> suite-contract:representative-ab.json
# eval-presentation-image-contract        -> suite-contract:presentation-image-smoke.json
# eval-presentation-image-assets-contract -> suite-contract:presentation-image-assets-smoke.json
BASELINE_ID_MAP = {
    **{
        f"quick_validate:{check_name}": f"skill-packages:{check_name}"
        for check_name, _ in SKILLS
    },
    "eval-suite-contract": "suite-contract:representative-ab.json",
    "eval-presentation-image-contract": "suite-contract:presentation-image-smoke.json",
    "eval-presentation-image-assets-contract": "suite-contract:presentation-image-assets-smoke.json",
}


def run(name: str, cmd: list[str]) -> dict:
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)
    return {
        "name": name,
        "cmd": cmd,
        "exit": proc.returncode,
        "status": "passed" if proc.returncode == 0 else "failed",
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def skipped(name: str, cmd: list[str], reason: str) -> dict:
    return {
        "name": name,
        "cmd": cmd,
        "exit": None,
        "status": "skipped",
        "stdout_tail": "",
        "stderr_tail": reason,
    }


def discovered_files(*roots: Path, suffix: str) -> list[str]:
    return sorted({
        str(path.relative_to(ROOT))
        for root in roots
        for path in root.rglob(f"*{suffix}")
        if "__pycache__" not in path.parts
    })


def main(baseline_path: Path | None = None) -> int:
    checks: list[dict] = []
    for check_name, skill_path in SKILLS:
        checks.append(run(
            f"skill-packages:{check_name}",
            [sys.executable, "tests/integration/skills/test_skill_packages.py", skill_path],
        ))

    if not QUICK_VALIDATE.exists():
        for check_name, skill_path in SKILLS:
            cmd = [sys.executable, str(QUICK_VALIDATE), skill_path]
            checks.append(skipped(
                f"external-quick-validate:{check_name}",
                cmd,
                f"optional validator not found: {QUICK_VALIDATE}",
            ))
    else:
        for check_name, skill_path in SKILLS:
            checks.append(run(
                f"external-quick-validate:{check_name}",
                [sys.executable, str(QUICK_VALIDATE), skill_path],
            ))

    checks.append(run("eval-platform-unit", [
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests/unit",
        "-p",
        "test_*.py",
        "-v",
    ]))

    for suite in sorted((ROOT / "evals" / "suites").glob("*.json")):
        suite_path = str(suite.relative_to(ROOT))
        checks.append(run(f"suite-contract:{suite.name}", [
            sys.executable,
            "evals/runners/evalctl.py",
            "validate",
            "--suite",
            suite_path,
        ]))

    checks.extend([
        run("code-review", [sys.executable, "tests/integration/code-review/run_checks.py"]),
        run("artifact-skills", [sys.executable, "tests/integration/artifact-skills/run_checks.py"]),
        run("presentation", [sys.executable, "tests/integration/presentation/run_checks.py"]),
        run("data-analysis", [sys.executable, "tests/integration/data-analysis/run_checks.py"]),
        run("feed-processing", [sys.executable, "tests/integration/feed-processing/run_checks.py"]),
        run("shape-product-spec", [sys.executable, "tests/integration/shape-product-spec/run_checks.py"]),
        run("video-studio", [sys.executable, "tests/integration/video-studio/run_checks.py"]),
    ])

    python_files = [
        "tests/run_all.py",
        "tests/integration/artifact-skills/run_checks.py",
        "tests/integration/code-review/run_checks.py",
        "tests/integration/feed-processing/run_checks.py",
        "evals/judges/common.py",
        "evals/judges/data_analysis_judge_adapter.py",
        "evals/judges/document_judge_adapter.py",
        "evals/judges/model_judge_runtime.py",
        "evals/judges/presentation_judge_adapter.py",
        "evals/judges/product_spec_judge_adapter.py",
        "evals/runners/codex_exec_adapter.py",
        "evals/runners/errors.py",
        "evals/runners/eval_lib.py",
        "evals/runners/evalctl.py",
        "evals/runners/schema_validation.py",
        "tests/integration/video-studio/run_checks.py",
        "tests/integration/data-analysis/run_checks.py",
        "tests/integration/shape-product-spec/run_checks.py",
        "tests/unit/eval_platform/test_codex_exec_adapter.py",
        "tests/unit/eval_platform/test_data_analysis_judge.py",
        "tests/unit/eval_platform/test_document_judge.py",
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
    python_files.extend(discovered_files(
        ROOT / "evals",
        ROOT / "tests",
        ROOT / "skills",
        ROOT / "archive" / "research",
        suffix=".py",
    ))
    checks.append(run("python-compile", [
        sys.executable,
        "-m",
        "py_compile",
        *sorted(set(python_files)),
    ]))

    node = shutil.which("node")
    if node:
        node_scripts = [
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
        ]
        node_scripts.extend(discovered_files(ROOT / "skills", ROOT / "tests", suffix=".mjs"))
        for script in sorted(set(node_scripts)):
            check_name = script.removeprefix("skills/")
            checks.append(run(f"node-check:{check_name}", [node, "--check", script]))
    else:
        checks.append({
            "name": "node-check",
            "cmd": ["node", "--check"],
            "exit": 1,
            "status": "failed",
            "stdout_tail": "",
            "stderr_tail": "node is required for .mjs script checks",
        })

    status = "failed" if any(item["status"] == "failed" for item in checks) else "passed"
    report = {"status": status, "checks": checks}
    if baseline_path is not None:
        comparison = compare_baseline(checks, baseline_path, BASELINE_ID_MAP, ROOT)
        report["baseline_comparison"] = comparison
        if comparison["status"] == "failed":
            report["status"] = "failed"
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.exit(main())
    if len(sys.argv) == 3 and sys.argv[1] == "--compare-baseline":
        candidate = Path(sys.argv[2])
        baseline = candidate if candidate.is_absolute() else ROOT / candidate
        sys.exit(main(baseline))
    print(f"Usage: {sys.argv[0]} [--compare-baseline BASELINE_JSON]", file=sys.stderr)
    sys.exit(2)
