#!/usr/bin/env python3
"""Judge a presentation eval with deterministic PPTX evidence and blind visual review."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evals.judges.common import anonymized_result, trace_summary  # noqa: E402
from evals.judges.model_judge_runtime import (  # noqa: E402
    ModelJudgeError,
    ModelJudgeOptions,
    is_transient_codex_failure,
    resolve_structured_output_mode,
    run_blind_model_judge,
)
from evals.runners.eval_lib import EvalConfigError, safe_child, sha256_file  # noqa: E402


REQUIRED_ENV = {
    "EVAL_ORACLE_FILE",
    "EVAL_RESULT_FILE",
    "EVAL_PAYLOAD_DIR",
    "EVAL_OUTPUT_DIR",
    "EVAL_JUDGE_RESULT_FILE",
}
OPTIONAL_PATH_ENV = {
    "EVAL_JUDGE_EVIDENCE_DIR",
    "EVAL_JUDGE_TRACE_DIR",
}


class JudgeError(RuntimeError):
    """Raised when the presentation judge cannot produce valid evidence."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise JudgeError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise JudgeError(f"{path} must contain an object")
    return value


def environment() -> dict[str, Path]:
    missing = sorted(name for name in REQUIRED_ENV if not os.environ.get(name))
    if missing:
        raise JudgeError(f"missing judge environment variables: {', '.join(missing)}")
    values = {name: Path(os.environ[name]).resolve() for name in REQUIRED_ENV}
    for name in OPTIONAL_PATH_ENV:
        if os.environ.get(name):
            values[name] = Path(os.environ[name]).resolve()
    return values


def run_command(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)


def is_renderer_infrastructure_failure(stderr: str) -> bool:
    normalized = stderr.lower()
    markers = (
        "library load denied by system policy",
        "code signature",
        "command not found",
        "libreoffice executable not found",
        "no such file or directory",
    )
    return any(marker in normalized for marker in markers)


def find_pptx(output_dir: Path, result: dict[str, Any]) -> list[Path]:
    declared: list[Path] = []
    for artifact in result.get("artifacts", []):
        if not isinstance(artifact, dict):
            continue
        relative = artifact.get("path")
        if not isinstance(relative, str) or not relative.lower().endswith(".pptx"):
            continue
        candidate = (output_dir / relative).resolve()
        try:
            candidate.relative_to(output_dir)
        except ValueError:
            continue
        if candidate.is_file():
            declared.append(candidate)
    if declared:
        return sorted(set(declared))
    return sorted(path for path in output_dir.rglob("*.pptx") if path.is_file())


def deterministic_evidence(pptx: Path, evidence_dir: Path) -> dict[str, Any]:
    inspect_path = evidence_dir / "pptx-inspect.json"
    gate_path = evidence_dir / "pptx-gate.json"
    render_dir = evidence_dir / "render"
    inspect = run_command(
        [
            sys.executable,
            str(ROOT / "presentation" / "scripts" / "pptx_tool.py"),
            "inspect",
            str(pptx),
            "--out",
            str(inspect_path),
        ],
        cwd=ROOT,
    )
    gate = run_command(
        [
            sys.executable,
            str(ROOT / "presentation" / "scripts" / "pptx_tool.py"),
            "gate",
            str(pptx),
            "--out",
            str(gate_path),
        ],
        cwd=ROOT,
    )
    render_command = [
        sys.executable,
        str(ROOT / "presentation" / "scripts" / "render_slides.py"),
        str(pptx),
        "--out-dir",
        str(render_dir),
        "--dpi",
        "120",
    ]
    render_attempts = 0
    while True:
        render_attempts += 1
        render = run_command(render_command, cwd=ROOT)
        if render.returncode == 0:
            break
        if render_attempts >= 3 or not is_renderer_infrastructure_failure(render.stderr):
            break
        shutil.rmtree(render_dir, ignore_errors=True)
        time.sleep(float(render_attempts))
    inspect_report = load_json(inspect_path) if inspect_path.is_file() else {}
    gate_report = load_json(gate_path) if gate_path.is_file() else {}
    render_manifest = (
        load_json(render_dir / "render-manifest.json")
        if (render_dir / "render-manifest.json").is_file()
        else {}
    )
    return {
        "commands": {
            "inspect_exit": inspect.returncode,
            "inspect_stderr": inspect.stderr[-2000:],
            "gate_exit": gate.returncode,
            "gate_stderr": gate.stderr[-2000:],
            "render_exit": render.returncode,
            "render_stderr": render.stderr[-2000:],
            "render_attempts": render_attempts,
            "render_infrastructure_failure": is_renderer_infrastructure_failure(
                render.stderr
            ),
        },
        "inspect": inspect_report,
        "gate": gate_report,
        "render_manifest": render_manifest,
        "render_dir": render_dir,
    }


def persist_deterministic_evidence(evidence: dict[str, Any], destination: Path) -> None:
    remove_names = ("pptx-inspect.json", "pptx-gate.json", "commands.json", "render")
    destination.mkdir(parents=True, exist_ok=True)
    for name in remove_names:
        target = destination / name
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink(missing_ok=True)
    source_root = Path(evidence["render_dir"]).parent
    for name in ("pptx-inspect.json", "pptx-gate.json"):
        source = source_root / name
        if source.is_file():
            shutil.copy2(source, destination / name)
    render_dir = Path(evidence["render_dir"])
    if render_dir.is_dir():
        shutil.copytree(render_dir, destination / "render")
    (destination / "commands.json").write_text(
        json.dumps(evidence["commands"], indent=2) + "\n",
        encoding="utf-8",
    )


def build_asset_match_report(
    *,
    oracle: dict[str, Any],
    payload_dir: Path,
    inspect: dict[str, Any],
) -> dict[str, Any]:
    metadata = oracle.get("metadata", {})
    expectations = (
        metadata.get("presentation_asset_expectations")
        if isinstance(metadata, dict)
        else None
    )
    if not isinstance(expectations, dict):
        return {"configured": False, "required": [], "forbidden": []}

    picture_index: dict[str, list[dict[str, Any]]] = {}
    for slide in inspect.get("slides", []):
        if not isinstance(slide, dict):
            continue
        slide_index = slide.get("index")
        for picture in slide.get("pictures", []):
            if not isinstance(picture, dict):
                continue
            image = picture.get("image")
            sha = image.get("sha256") if isinstance(image, dict) else None
            if not isinstance(sha, str):
                continue
            picture_index.setdefault(sha, []).append(
                {
                    "slide": slide_index,
                    "order": picture.get("order"),
                    "target": picture.get("target"),
                    "crop": picture.get("crop"),
                    "visible_fraction": picture.get("visible_fraction"),
                    "metrics": picture.get("metrics"),
                }
            )

    def source_record(raw: Any, *, required: bool) -> dict[str, Any]:
        if isinstance(raw, str):
            item: dict[str, Any] = {"path": raw}
        elif isinstance(raw, dict):
            item = dict(raw)
        else:
            raise JudgeError("presentation asset expectation must be a path or object")
        relative = item.get("path")
        if not isinstance(relative, str) or not relative:
            raise JudgeError("presentation asset expectation path must be non-empty")
        try:
            source = safe_child(payload_dir, relative)
        except EvalConfigError as exc:
            raise JudgeError(str(exc)) from exc
        if not source.is_file() or source.is_symlink():
            raise JudgeError(f"expected source asset is missing: {relative}")
        sha = sha256_file(source)
        matches = picture_index.get(sha, [])
        return {
            **item,
            "required": required,
            "source_sha256": sha,
            "matched_uses": len(matches),
            "matches": matches,
        }

    required = [
        source_record(item, required=True)
        for item in expectations.get("required", [])
    ]
    forbidden = [
        source_record(item, required=False)
        for item in expectations.get("forbidden", [])
    ]
    return {"configured": True, "required": required, "forbidden": forbidden}


def judge_prompt(oracle: dict[str, Any]) -> str:
    outcomes = oracle["expected"]["outcomes"]
    rubric = "\n".join(
        f"- {item['id']} ({item['weight']:.2f}, critical={str(item['critical']).lower()}): "
        f"{item['description']}"
        for item in outcomes
    )
    criterion_ids = [item["id"] for item in outcomes]
    failure_tags = oracle.get("failure_taxonomy", [])
    return f"""Act as a blind presentation evaluator. You do not know which
experimental condition produced this deck. Review source/prompt.md,
source/input/, agent-result.json, agent-response.md, agent-trace-summary.json,
pptx-inspect.json, pptx-gate.json, asset-matches.json, every attached source
asset, and every attached slide render.

Score every criterion below from 0.0 to 1.0. Set passed=true only at 0.75 or
higher and only when no blocking failure applies. Use concrete slide numbers,
source facts, inspection fields, or trace commands as evidence. Do not reward
claims in the response unless the artifact or trace proves them. Inspect the
hardest slide, not only the cover. For image relevance, distinguish real
evidence, conceptual media, constructed visuals, and intentional text-only
resets; do not impose an image quota on an analytical deck. For image fit,
veto stretching, destructive crops, unreadable UI/text, or severe upscaling.

Rubric:
{rubric}

Return exactly one score for every criterion id. Return only a JSON object with
no Markdown or surrounding commentary. Its shape must be:
{{"scores":[{{"criterion_id":"...","value":0.0,"passed":false,
"rationale":"...","evidence":["..."]}}],"failure_tags":[],"summary":"..."}}
Allowed criterion ids: {json.dumps(criterion_ids)}
Allowed failure tags: {json.dumps(failure_tags)}
"""


def model_judge(
    *,
    args: argparse.Namespace,
    oracle: dict[str, Any],
    workspace: Path,
    image_paths: list[Path],
    trace_root: Path,
) -> dict[str, Any]:
    criterion_ids = [item["id"] for item in oracle["expected"]["outcomes"]]
    options = ModelJudgeOptions(
        codex_bin=args.codex_bin,
        model=args.model,
        reasoning_effort=args.reasoning_effort,
        timeout_seconds=args.timeout_seconds,
        max_attempts=args.max_attempts,
        retry_delay_seconds=args.retry_delay_seconds,
        structured_output=args.structured_output,
    )
    try:
        return run_blind_model_judge(
            options=options,
            prompt=judge_prompt(oracle),
            workspace=workspace,
            trace_root=trace_root,
            criterion_ids=criterion_ids,
            failure_tags=oracle.get("failure_taxonomy", []),
            image_paths=image_paths,
        )
    except ModelJudgeError as exc:
        raise JudgeError(str(exc)) from exc


def missing_artifact_result(oracle: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    acceptable = oracle["expected"]["route"]["acceptable_primary_skills"]
    route_ok = (result.get("route") or {}).get("primary_skill") in acceptable
    scores = []
    for outcome in oracle["expected"]["outcomes"]:
        is_route = outcome["id"] == "correct-route"
        value = 1.0 if is_route and route_ok else 0.0
        scores.append(
            {
                "criterion_id": outcome["id"],
                "value": value,
                "passed": value >= 0.75,
                "rationale": (
                    "The recorded primary Skill matches the expected route."
                    if value == 1.0
                    else "No PPTX was delivered, so this criterion cannot pass."
                ),
                "evidence": ["result.route"] if is_route else ["result.artifacts"],
            }
        )
    tags = ["missing-artifact"]
    if not route_ok:
        tags.append("route-error")
    return {
        "scores": scores,
        "failure_tags": tags,
        "summary": "No PPTX deliverable was available for deterministic or visual review.",
    }


def score_index(judgment: dict[str, Any]) -> dict[str, dict[str, Any]]:
    scores = judgment.get("scores", [])
    if not isinstance(scores, list):
        raise JudgeError("judge output scores must be a list")
    indexed: dict[str, dict[str, Any]] = {}
    for score in scores:
        if not isinstance(score, dict) or not isinstance(score.get("criterion_id"), str):
            raise JudgeError("judge output contains an invalid score")
        indexed[score["criterion_id"]] = score
    return indexed


def cap_score(score: dict[str, Any], cap: float, rationale: str, evidence: str) -> None:
    current = score.get("value")
    if not isinstance(current, (int, float)):
        raise JudgeError(f"judge score is not numeric: {score.get('criterion_id')}")
    if current > cap:
        score["value"] = cap
        score["passed"] = False
        score["rationale"] = f"{score.get('rationale', '')} Deterministic cap: {rationale}".strip()
        score.setdefault("evidence", []).append(evidence)


def apply_deterministic_overrides(
    judgment: dict[str, Any],
    *,
    oracle: dict[str, Any],
    result: dict[str, Any],
    inspect: dict[str, Any],
    commands: dict[str, Any],
    asset_matches: dict[str, Any] | None = None,
) -> dict[str, Any]:
    indexed = score_index(judgment)
    expected_ids = {item["id"] for item in oracle["expected"]["outcomes"]}
    if set(indexed) != expected_ids:
        raise JudgeError(
            f"judge output criterion mismatch: expected {sorted(expected_ids)}, got {sorted(indexed)}"
        )
    acceptable = oracle["expected"]["route"]["acceptable_primary_skills"]
    route_ok = (result.get("route") or {}).get("primary_skill") in acceptable
    route_score = indexed["correct-route"]
    route_score.update(
        {
            "value": 1.0 if route_ok else 0.0,
            "passed": route_ok,
            "rationale": "Deterministic comparison of the recorded primary Skill to the hidden route oracle.",
            "evidence": ["result.route.primary_skill"],
        }
    )

    failure_tags = set(judgment.get("failure_tags", []))
    if not route_ok:
        failure_tags.add("route-error")
    if commands.get("inspect_exit") != 0 or not inspect.get("ok", False):
        cap_score(
            indexed["editable-deliverable"],
            0.0,
            "PPTX inspection failed.",
            "pptx-inspect.json",
        )
        failure_tags.add("artifact-integrity")

    slide_count = len(inspect.get("slides", []))
    notes_count = int(inspect.get("notes_count", 0) or 0)
    if not 9 <= slide_count <= 11:
        cap_score(
            indexed["editable-deliverable"],
            0.5,
            f"Expected 9-11 slides but found {slide_count}.",
            "pptx-inspect.json:slides",
        )
    if notes_count < slide_count:
        cap_score(
            indexed["editable-deliverable"],
            0.6,
            f"Speaker notes cover {notes_count} of {slide_count} slides.",
            "pptx-inspect.json:notes_count",
        )

    distortions = inspect.get("image_aspect_distortions", [])
    severe_resolution = inspect.get("severe_image_resolution_warnings", [])
    missing_dimensions = inspect.get("missing_image_dimensions", [])
    if distortions:
        cap_score(
            indexed["image-fit"],
            0.0,
            f"Detected {len(distortions)} non-uniform image aspect distortion(s).",
            "pptx-inspect.json:image_aspect_distortions",
        )
        failure_tags.add("image-distortion")
    if severe_resolution:
        cap_score(
            indexed["image-fit"],
            0.25,
            f"Detected {len(severe_resolution)} severely undersized image(s).",
            "pptx-inspect.json:severe_image_resolution_warnings",
        )
        failure_tags.add("visual-quality")
    if missing_dimensions:
        cap_score(
            indexed["image-fit"],
            0.5,
            f"Could not verify dimensions for {len(missing_dimensions)} image(s).",
            "pptx-inspect.json:missing_image_dimensions",
        )
        failure_tags.add("verification")
    if asset_matches and asset_matches.get("configured"):
        required_assets = asset_matches.get("required", [])
        missing_assets = [
            item for item in required_assets if item.get("matched_uses", 0) == 0
        ]
        if missing_assets:
            cap = 0.25 if len(missing_assets) == len(required_assets) else 0.5
            cap_score(
                indexed["image-relevance"],
                cap,
                "Required source assets were not found as exact media in the PPTX: "
                + ", ".join(str(item.get("path")) for item in missing_assets),
                "asset-matches.json:required",
            )
            failure_tags.add("image-relevance")
        forbidden_assets = [
            item
            for item in asset_matches.get("forbidden", [])
            if item.get("matched_uses", 0) > 0
        ]
        if forbidden_assets:
            cap_score(
                indexed["image-relevance"],
                0.0,
                "Forbidden source assets were embedded in the PPTX: "
                + ", ".join(str(item.get("path")) for item in forbidden_assets),
                "asset-matches.json:forbidden",
            )
            failure_tags.add("image-relevance")
        cropped_matches: list[tuple[dict[str, Any], dict[str, Any], float]] = []
        for asset in required_assets:
            maximum = asset.get("max_cropped_fraction")
            if not isinstance(maximum, (int, float)):
                continue
            for match in asset.get("matches", []):
                visible = match.get("visible_fraction") or {}
                cropped = visible.get("cropped", 0.0)
                if isinstance(cropped, (int, float)) and cropped > float(maximum) + 1e-6:
                    cropped_matches.append((asset, match, float(cropped)))
        if cropped_matches:
            maximum_crop = max(item[2] for item in cropped_matches)
            cap_score(
                indexed["image-fit"],
                0.0 if maximum_crop > 0.05 else 0.5,
                f"Required contain assets were cropped; maximum cropped fraction was {maximum_crop:.3f}.",
                "asset-matches.json:required.matches",
            )
            failure_tags.add("image-distortion")
    if commands.get("render_exit") != 0:
        cap_score(
            indexed["rendered-verification"],
            0.0,
            "The judge could not render the delivered PPTX.",
            "judge-render-command",
        )
        failure_tags.add("artifact-integrity")

    judgment["scores"] = [indexed[item["id"]] for item in oracle["expected"]["outcomes"]]
    judgment["failure_tags"] = sorted(failure_tags)
    return judgment


def prepare_model_workspace(
    *,
    workspace: Path,
    env: dict[str, Path],
    result: dict[str, Any],
    evidence: dict[str, Any],
    asset_matches: dict[str, Any],
) -> list[Path]:
    source_dir = workspace / "source"
    source_dir.mkdir()
    payload = env["EVAL_PAYLOAD_DIR"]
    shutil.copy2(payload / "prompt.md", source_dir / "prompt.md")
    shutil.copytree(payload / "input", source_dir / "input")
    (workspace / "agent-result.json").write_text(
        json.dumps(anonymized_result(result), indent=2) + "\n",
        encoding="utf-8",
    )
    response = env["EVAL_OUTPUT_DIR"] / "response.md"
    (workspace / "agent-response.md").write_text(
        response.read_text(encoding="utf-8") if response.is_file() else "",
        encoding="utf-8",
    )
    (workspace / "agent-trace-summary.json").write_text(
        json.dumps(trace_summary(env["EVAL_OUTPUT_DIR"]), indent=2) + "\n",
        encoding="utf-8",
    )
    for name, value in (
        ("pptx-inspect.json", evidence["inspect"]),
        ("pptx-gate.json", evidence["gate"]),
        ("render-manifest.json", evidence["render_manifest"]),
        ("asset-matches.json", asset_matches),
    ):
        (workspace / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    render_dir = evidence["render_dir"]
    contact_sheets = sorted(render_dir.glob("contact-sheet.*"))
    slide_images = sorted(render_dir.glob("slide-*.png"))
    source_images = sorted(
        path
        for path in (source_dir / "input").rglob("*")
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    )
    return [*source_images, *contact_sheets, *slide_images]


def run_judge(args: argparse.Namespace) -> dict[str, Any]:
    env = environment()
    persistent_evidence_dir = env.get(
        "EVAL_JUDGE_EVIDENCE_DIR",
        env["EVAL_JUDGE_RESULT_FILE"].parent / "judge-evidence",
    )
    persistent_trace_dir = env.get(
        "EVAL_JUDGE_TRACE_DIR",
        env["EVAL_JUDGE_RESULT_FILE"].parent / "judge-trace",
    )
    oracle = load_json(env["EVAL_ORACLE_FILE"])
    result = load_json(env["EVAL_RESULT_FILE"])
    pptx_files = find_pptx(env["EVAL_OUTPUT_DIR"], result)
    if not pptx_files:
        judgment = missing_artifact_result(oracle, result)
        env["EVAL_JUDGE_RESULT_FILE"].write_text(
            json.dumps(judgment, indent=2) + "\n",
            encoding="utf-8",
        )
        return judgment

    with tempfile.TemporaryDirectory(prefix="linlab-presentation-judge-") as temp:
        temp_root = Path(temp)
        evidence_dir = temp_root / "evidence"
        evidence_dir.mkdir()
        anonymous_pptx = evidence_dir / "deck.pptx"
        shutil.copy2(pptx_files[0], anonymous_pptx)
        evidence = deterministic_evidence(anonymous_pptx, evidence_dir)
        asset_matches = build_asset_match_report(
            oracle=oracle,
            payload_dir=env["EVAL_PAYLOAD_DIR"],
            inspect=evidence["inspect"],
        )
        persist_deterministic_evidence(
            evidence,
            persistent_evidence_dir,
        )
        (persistent_evidence_dir / "asset-matches.json").write_text(
            json.dumps(asset_matches, indent=2) + "\n",
            encoding="utf-8",
        )
        if (
            evidence["commands"].get("render_exit") != 0
            and evidence["commands"].get("render_infrastructure_failure")
        ):
            raise JudgeError(
                "judge renderer infrastructure failure after "
                f"{evidence['commands'].get('render_attempts')} attempts: "
                f"{evidence['commands'].get('render_stderr', '')[-1000:]}"
            )
        model_workspace = temp_root / "blind-review"
        model_workspace.mkdir()
        images = prepare_model_workspace(
            workspace=model_workspace,
            env=env,
            result=result,
            evidence=evidence,
            asset_matches=asset_matches,
        )
        judgment = model_judge(
            args=args,
            oracle=oracle,
            workspace=model_workspace,
            image_paths=images,
            trace_root=persistent_trace_dir,
        )
        judgment = apply_deterministic_overrides(
            judgment,
            oracle=oracle,
            result=result,
            inspect=evidence["inspect"],
            commands=evidence["commands"],
            asset_matches=asset_matches,
        )
    env["EVAL_JUDGE_RESULT_FILE"].write_text(
        json.dumps(judgment, indent=2) + "\n",
        encoding="utf-8",
    )
    return judgment


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--model", default="gpt-5.6-sol")
    parser.add_argument("--reasoning-effort", default="medium")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--retry-delay-seconds", type=float, default=2.0)
    parser.add_argument(
        "--structured-output",
        choices=("auto", "schema", "prompt"),
        default="auto",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.max_attempts < 1:
        print(json.dumps({"ok": False, "error": "max attempts must be at least 1"}), file=sys.stderr)
        return 2
    if args.retry_delay_seconds < 0:
        print(json.dumps({"ok": False, "error": "retry delay must be non-negative"}), file=sys.stderr)
        return 2
    try:
        judgment = run_judge(args)
    except (JudgeError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, "judgment": judgment}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
