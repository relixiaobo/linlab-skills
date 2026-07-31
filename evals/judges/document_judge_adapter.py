#!/usr/bin/env python3
"""Judge source-first documents with deterministic evidence and blind review."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evals.judges.common import anonymized_result, trace_summary  # noqa: E402
from evals.judges.model_judge_runtime import (  # noqa: E402
    ModelJudgeError,
    ModelJudgeOptions,
    run_blind_model_judge,
)
from evals.runners.eval_lib import EvalConfigError, safe_child  # noqa: E402


REQUIRED_ENV = {
    "EVAL_ORACLE_FILE",
    "EVAL_RESULT_FILE",
    "EVAL_PAYLOAD_DIR",
    "EVAL_OUTPUT_DIR",
    "EVAL_JUDGE_RESULT_FILE",
}
MARKDOWN_TOOL = ROOT / "skills" / "document" / "scripts" / "markdown_tool.mjs"


class DocumentJudgeError(RuntimeError):
    """Raised when document evidence cannot be produced safely."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DocumentJudgeError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise DocumentJudgeError(f"{path} must contain an object")
    return value


def environment() -> dict[str, Path]:
    missing = sorted(name for name in REQUIRED_ENV if not os.environ.get(name))
    if missing:
        raise DocumentJudgeError(
            f"missing judge environment variables: {', '.join(missing)}"
        )
    return {name: Path(os.environ[name]).resolve() for name in REQUIRED_ENV}


def judge_config() -> dict[str, Any]:
    try:
        value = json.loads(os.environ.get("EVAL_JUDGE_CONFIG", "{}"))
    except json.JSONDecodeError as exc:
        raise DocumentJudgeError(f"invalid EVAL_JUDGE_CONFIG: {exc}") from exc
    if not isinstance(value, dict):
        raise DocumentJudgeError("EVAL_JUDGE_CONFIG must contain an object")
    required = {"artifact", "structure", "concepts", "criterion_failure_tags"}
    missing = sorted(required - set(value))
    unknown = sorted(set(value) - required)
    if missing or unknown:
        raise DocumentJudgeError(
            f"document config mismatch; missing={missing}, unknown={unknown}"
        )
    return value


def require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise DocumentJudgeError(f"{label} must be a non-empty string")
    return value


def validate_string_list(value: Any, label: str) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or not item for item in value)
    ):
        raise DocumentJudgeError(f"{label} must be a non-empty string array")
    if len(value) != len(set(value)):
        raise DocumentJudgeError(f"{label} must not contain duplicates")
    return value


def validate_config(config: dict[str, Any], oracle: dict[str, Any]) -> None:
    outcome_ids = {item["id"] for item in oracle["expected"]["outcomes"]}
    allowed_tags = set(oracle.get("failure_taxonomy", []))

    artifact = config["artifact"]
    if not isinstance(artifact, dict) or set(artifact) != {"path", "criterion"}:
        raise DocumentJudgeError("artifact config has an invalid shape")
    require_string(artifact["path"], "artifact.path")
    artifact_criterion = require_string(
        artifact["criterion"], "artifact.criterion"
    )

    structure = config["structure"]
    if not isinstance(structure, dict) or set(structure) != {
        "criterion",
        "minimum_heading_count",
        "maximum_word_count",
    }:
        raise DocumentJudgeError("structure config has an invalid shape")
    structure_criterion = require_string(
        structure["criterion"], "structure.criterion"
    )
    for name in ("minimum_heading_count", "maximum_word_count"):
        value = structure[name]
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise DocumentJudgeError(f"structure.{name} must be positive")

    concepts = config["concepts"]
    if not isinstance(concepts, dict) or not concepts:
        raise DocumentJudgeError("concepts config must be a non-empty object")
    for criterion, requirements in concepts.items():
        require_string(criterion, "concept criterion")
        if not isinstance(requirements, list) or not requirements:
            raise DocumentJudgeError(
                f"concept requirements for {criterion} must be a non-empty array"
            )
        requirement_ids: list[str] = []
        for requirement in requirements:
            if not isinstance(requirement, dict) or set(requirement) != {
                "id",
                "term_groups",
            }:
                raise DocumentJudgeError(
                    f"concept requirement for {criterion} has an invalid shape"
                )
            requirement_id = require_string(
                requirement["id"], f"concept id for {criterion}"
            )
            requirement_ids.append(requirement_id)
            groups = requirement["term_groups"]
            if not isinstance(groups, list) or not groups:
                raise DocumentJudgeError(
                    f"term_groups for {criterion}.{requirement_id} must be non-empty"
                )
            for index, alternatives in enumerate(groups, start=1):
                validate_string_list(
                    alternatives,
                    f"terms for {criterion}.{requirement_id} group {index}",
                )
        if len(requirement_ids) != len(set(requirement_ids)):
            raise DocumentJudgeError(
                f"concept requirement ids for {criterion} must be unique"
            )

    tag_map = config["criterion_failure_tags"]
    if not isinstance(tag_map, dict):
        raise DocumentJudgeError("criterion_failure_tags must be an object")
    configured_criteria = {artifact_criterion, structure_criterion} | set(concepts)
    unknown_criteria = sorted(configured_criteria - outcome_ids)
    if unknown_criteria:
        raise DocumentJudgeError(
            f"config references unknown criteria: {unknown_criteria}"
        )
    if set(tag_map) != configured_criteria:
        raise DocumentJudgeError(
            "criterion_failure_tags must cover every configured criterion"
        )
    invalid_tags = sorted(
        repr(tag)
        for tag in tag_map.values()
        if not isinstance(tag, str) or tag not in allowed_tags
    )
    if invalid_tags:
        raise DocumentJudgeError(
            f"criterion_failure_tags contains unsupported tags: {invalid_tags}"
        )


def artifact_path(output_dir: Path, relative: str) -> Path:
    unresolved = output_dir / relative
    if unresolved.is_symlink():
        raise DocumentJudgeError(f"artifact must not be a symlink: {relative}")
    return safe_child(output_dir, relative)


def normalize_text(text: str) -> str:
    return re.sub(r"[\W_]+", " ", text.casefold()).strip()


def audit_concepts(concepts: dict[str, Any], text: str) -> dict[str, Any]:
    normalized = normalize_text(text)
    result: dict[str, Any] = {}
    for criterion, requirements in concepts.items():
        audited_requirements: list[dict[str, Any]] = []
        for requirement in requirements:
            audited_groups: list[dict[str, Any]] = []
            for alternatives in requirement["term_groups"]:
                matched = next(
                    (
                        term
                        for term in alternatives
                        if normalize_text(term) in normalized
                    ),
                    None,
                )
                audited_groups.append(
                    {
                        "alternatives": alternatives,
                        "matched": matched,
                        "passed": matched is not None,
                    }
                )
            audited_requirements.append(
                {
                    "id": requirement["id"],
                    "passed": all(group["passed"] for group in audited_groups),
                    "term_groups": audited_groups,
                }
            )
        result[criterion] = {
            "requirements": audited_requirements,
            "missing": [
                item["id"] for item in audited_requirements if not item["passed"]
            ],
        }
    return result


def run_markdown_check(
    document_path: Path,
    relative_path: str,
    evidence_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    report_path = evidence_dir / "markdown-inspect.json"
    node = shutil.which("node")
    if not node:
        raise DocumentJudgeError("node is required to inspect Markdown documents")
    command = [
        node,
        str(MARKDOWN_TOOL),
        "inspect",
        str(document_path),
        "--out",
        str(report_path),
    ]
    try:
        proc = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DocumentJudgeError(f"cannot run markdown_tool.mjs: {exc}") from exc
    (evidence_dir / "markdown-inspect.stdout.log").write_text(
        proc.stdout, encoding="utf-8"
    )
    (evidence_dir / "markdown-inspect.stderr.log").write_text(
        proc.stderr, encoding="utf-8"
    )
    if proc.returncode not in {0, 1} or not report_path.is_file():
        tail = f"{proc.stderr}\n{proc.stdout}"[-2000:]
        raise DocumentJudgeError(
            f"markdown_tool.mjs failed with code {proc.returncode}: {tail}"
        )
    report = load_json(report_path)
    report["file"] = f"artifacts/{Path(relative_path).name}"
    if bool(report.get("ok")) != (proc.returncode == 0):
        raise DocumentJudgeError(
            "markdown_tool.mjs exit code disagrees with its report"
        )
    report_path.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )
    return report, {
        "exit_code": proc.returncode,
        "stdout_log": "markdown-inspect.stdout.log",
        "stderr_log": "markdown-inspect.stderr.log",
    }


def build_artifact_audit(
    config: dict[str, Any],
    result: dict[str, Any],
    document_path: Path,
    report: dict[str, Any],
    check_run: dict[str, Any],
) -> dict[str, Any]:
    artifact_config = config["artifact"]
    text = document_path.read_text(encoding="utf-8", errors="replace")
    declared = {
        item.get("path")
        for item in result.get("artifacts", [])
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    headings = report.get("headings")
    if not isinstance(headings, list):
        headings = []
    heading_count = report.get("heading_count", 0)
    word_count = report.get("word_count", 0)
    placeholders = report.get("placeholder_hits")
    if not isinstance(placeholders, list):
        placeholders = []
    structure_config = config["structure"]
    structure = {
        "minimum_heading_count": structure_config["minimum_heading_count"],
        "heading_count": heading_count,
        "heading_count_passed": (
            isinstance(heading_count, int)
            and heading_count >= structure_config["minimum_heading_count"]
        ),
        "first_heading_is_h1": bool(
            headings
            and isinstance(headings[0], dict)
            and headings[0].get("level") == 1
        ),
        "maximum_word_count": structure_config["maximum_word_count"],
        "word_count": word_count,
        "word_count_passed": (
            isinstance(word_count, int)
            and word_count <= structure_config["maximum_word_count"]
        ),
        "placeholder_hits": placeholders,
    }
    structure["hints_passed"] = bool(
        structure["heading_count_passed"]
        and structure["first_heading_is_h1"]
        and structure["word_count_passed"]
    )
    structure["placeholder_free"] = not placeholders
    concepts = audit_concepts(config["concepts"], text)
    criterion_checks: dict[str, Any] = {}
    for criterion in config["criterion_failure_tags"]:
        concept = concepts.get(criterion, {"requirements": [], "missing": []})
        structural = structure if criterion == structure_config["criterion"] else None
        criterion_checks[criterion] = {
            "concepts": concept,
            "structure": structural,
            "semantic_hints_passed": not concept["missing"],
            "structural_hints_passed": (
                structural is None or structural["hints_passed"]
            ),
        }
    return {
        "artifact": {
            "path": artifact_config["path"],
            "exists": True,
            "declared": artifact_config["path"] in declared,
            "bytes": document_path.stat().st_size,
            "sha256": hashlib.sha256(document_path.read_bytes()).hexdigest(),
        },
        "markdown_check": {
            **check_run,
            "ok": bool(report.get("ok")),
            "errors": report.get("errors", []),
            "warnings": report.get("warnings", []),
        },
        "criterion_checks": criterion_checks,
    }


def persist_evidence(
    evidence_dir: Path,
    artifact_audit: dict[str, Any],
    trace: dict[str, Any],
) -> None:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for name, value in (
        ("artifact-audit.json", artifact_audit),
        ("agent-trace-summary.json", trace),
    ):
        (evidence_dir / name).write_text(
            json.dumps(value, indent=2) + "\n",
            encoding="utf-8",
        )


def judge_prompt(oracle: dict[str, Any], artifact_relative: str) -> str:
    rubric = "\n".join(
        f"- {item['id']} ({item['weight']:.2f}, critical={str(item['critical']).lower()}): "
        f"{item['description']}"
        for item in oracle["expected"]["outcomes"]
    )
    criterion_ids = [item["id"] for item in oracle["expected"]["outcomes"]]
    failure_tags = oracle.get("failure_taxonomy", [])
    model_artifact = f"artifacts/{Path(artifact_relative).name}"
    return f"""Act as a blind document evaluator. You do not know which
experimental condition produced the work. Review source/prompt.md,
source/input/, agent-result.json, agent-response.md,
agent-trace-summary.json, {model_artifact}, markdown-inspect.json, and
artifact-audit.json.

Judge the memo as durable written communication for a board decision, not as a
template-compliance exercise. Check that the recommendation is prominent and
actionable; every number, estimate, risk, and unknown remains faithful to the
source; inferences are distinguished from facts; and the source map makes
substantive claims traceable. Evaluate whether predicted reader questions expose
real decision gaps rather than merely repeating headings. Confirm that Markdown
is a usable source of truth and that any Word handoff claim is accurate. Treat
artifact-audit.json term matches and misses as review hints, not proof that a
concept is present or absent. Use markdown-inspect.json only for structural
facts, then inspect the memo itself for semantic quality and contradictions.

Score every criterion from 0.0 to 1.0. Set passed=true only at 0.75 or higher
with no blocking failure. Ground every score in concrete source lines, memo
sections, claims, reader questions, or deterministic report fields.

Rubric:
{rubric}

Return exactly one score for every criterion id and only a JSON object shaped as:
{{"scores":[{{"criterion_id":"...","value":0.0,"passed":false,
"rationale":"...","evidence":["..."]}}],"failure_tags":[],"summary":"..."}}
Allowed criterion ids: {json.dumps(criterion_ids)}
Allowed failure tags: {json.dumps(failure_tags)}
"""


def path_spellings(path: Path) -> set[str]:
    spellings = {str(path), str(path.resolve())}
    for value in list(spellings):
        if value.startswith("/private/tmp/"):
            spellings.add(value.removeprefix("/private"))
        elif value.startswith("/tmp/"):
            spellings.add(f"/private{value}")
    return {value for value in spellings if value}


def blind_redactions(
    *,
    env: dict[str, Path],
    result: dict[str, Any],
    evidence_dir: Path,
) -> dict[str, str]:
    result_file = env["EVAL_RESULT_FILE"]
    run_dir = result_file.parent
    run_root = result_file.parents[3] if len(result_file.parents) > 3 else run_dir
    path_replacements = (
        (env["EVAL_PAYLOAD_DIR"], "source"),
        (env["EVAL_OUTPUT_DIR"], "agent-output"),
        (evidence_dir, "judge-evidence"),
        (run_dir, "run"),
        (run_root, "run-root"),
        (ROOT, "repository"),
    )
    redactions: dict[str, str] = {}
    for path, replacement in path_replacements:
        for spelling in path_spellings(path):
            redactions[spelling] = replacement
    condition_id = (result.get("condition") or {}).get("id")
    if isinstance(condition_id, str) and condition_id and condition_id != "baseline":
        redactions[condition_id] = "condition"
    return redactions


def sanitize_blind_value(value: Any, redactions: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {
            key: sanitize_blind_value(item, redactions)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize_blind_value(item, redactions) for item in value]
    if not isinstance(value, str):
        return value
    sanitized = value
    for sensitive, replacement in sorted(
        redactions.items(), key=lambda item: len(item[0]), reverse=True
    ):
        sanitized = sanitized.replace(sensitive, replacement)
    return sanitized


def assert_blind_workspace_clean(
    workspace: Path,
    *,
    forbidden_markers: set[str],
) -> None:
    encoded_markers = {
        marker: marker.encode("utf-8") for marker in sorted(forbidden_markers)
    }
    for path in sorted(workspace.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        content = path.read_bytes()
        for marker, encoded in encoded_markers.items():
            if encoded in content:
                relative = path.relative_to(workspace).as_posix()
                raise DocumentJudgeError(
                    f"blind-review input leaked experimental provenance in {relative}: "
                    f"{marker}"
                )


def prepare_model_workspace(
    *,
    workspace: Path,
    env: dict[str, Path],
    result: dict[str, Any],
    config: dict[str, Any],
    artifact_audit: dict[str, Any],
    markdown_report: dict[str, Any],
    trace: dict[str, Any],
    evidence_dir: Path,
) -> None:
    redactions = blind_redactions(
        env=env,
        result=result,
        evidence_dir=evidence_dir,
    )
    source_dir = workspace / "source"
    source_dir.mkdir()
    payload = env["EVAL_PAYLOAD_DIR"]
    shutil.copy2(payload / "prompt.md", source_dir / "prompt.md")
    shutil.copytree(payload / "input", source_dir / "input")
    (workspace / "agent-result.json").write_text(
        json.dumps(
            sanitize_blind_value(anonymized_result(result), redactions), indent=2
        )
        + "\n",
        encoding="utf-8",
    )
    response = env["EVAL_OUTPUT_DIR"] / "response.md"
    (workspace / "agent-response.md").write_text(
        sanitize_blind_value(
            response.read_text(encoding="utf-8", errors="replace")
            if response.is_file()
            else "",
            redactions,
        ),
        encoding="utf-8",
    )
    for name, value in (
        ("agent-trace-summary.json", trace),
        ("artifact-audit.json", artifact_audit),
        ("markdown-inspect.json", markdown_report),
    ):
        (workspace / name).write_text(
            json.dumps(sanitize_blind_value(value, redactions), indent=2) + "\n",
            encoding="utf-8",
        )
    artifact_dir = workspace / "artifacts"
    artifact_dir.mkdir()
    relative = config["artifact"]["path"]
    source = artifact_path(env["EVAL_OUTPUT_DIR"], relative)
    shutil.copy2(source, artifact_dir / Path(relative).name)
    assert_blind_workspace_clean(
        workspace,
        forbidden_markers=set(redactions),
    )


def score_index(judgment: dict[str, Any]) -> dict[str, dict[str, Any]]:
    scores = judgment.get("scores")
    if not isinstance(scores, list):
        raise DocumentJudgeError("model judgment has no scores list")
    indexed: dict[str, dict[str, Any]] = {}
    for score in scores:
        if not isinstance(score, dict) or not isinstance(
            score.get("criterion_id"), str
        ):
            raise DocumentJudgeError("model judgment contains an invalid score")
        indexed[score["criterion_id"]] = score
    return indexed


def cap_score(score: dict[str, Any], cap: float, rationale: str, evidence: str) -> None:
    value = score.get("value")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise DocumentJudgeError("model score value must be numeric")
    if float(value) > cap:
        score["value"] = cap
    score["passed"] = float(score["value"]) >= 0.75
    score["rationale"] = (
        f"{score.get('rationale', '')} Deterministic check: {rationale}".strip()
    )
    evidence_items = score.setdefault("evidence", [])
    if not isinstance(evidence_items, list):
        raise DocumentJudgeError("model score evidence must be a list")
    if evidence not in evidence_items:
        evidence_items.append(evidence)


def apply_deterministic_overrides(
    judgment: dict[str, Any],
    *,
    oracle: dict[str, Any],
    config: dict[str, Any],
    result: dict[str, Any],
    artifact_audit: dict[str, Any],
) -> dict[str, Any]:
    scores = score_index(judgment)
    expected_ids = [item["id"] for item in oracle["expected"]["outcomes"]]
    if set(scores) != set(expected_ids):
        raise DocumentJudgeError(
            f"model judgment criterion mismatch: expected {sorted(expected_ids)}, "
            f"got {sorted(scores)}"
        )
    failure_tags = set(judgment.get("failure_tags", []))

    acceptable = oracle["expected"]["route"]["acceptable_primary_skills"]
    route_ok = (result.get("route") or {}).get("primary_skill") in acceptable
    route = scores["correct-route"]
    route.update(
        {
            "value": 1.0 if route_ok else 0.0,
            "passed": route_ok,
            "rationale": (
                "Recorded primary Skill matches the expected document route."
                if route_ok
                else "Recorded primary Skill does not match the expected document route."
            ),
            "evidence": ["agent-result.json route"],
        }
    )
    if not route_ok:
        failure_tags.add("route-error")

    artifact = artifact_audit["artifact"]
    artifact_criterion = config["artifact"]["criterion"]
    if not artifact["declared"]:
        cap_score(
            scores[artifact_criterion],
            0.0,
            "the required board memo was not declared as an Agent artifact",
            "artifact-audit.json artifact.declared",
        )
        failure_tags.add("missing-artifact")
    if not artifact_audit["markdown_check"]["ok"]:
        errors = artifact_audit["markdown_check"]["errors"]
        cap_score(
            scores[artifact_criterion],
            0.25,
            "portable Markdown inspection failed: " + "; ".join(errors),
            "markdown-inspect.json errors",
        )
        failure_tags.add(config["criterion_failure_tags"][artifact_criterion])

    structure_criterion = config["structure"]["criterion"]
    structure = artifact_audit["criterion_checks"][structure_criterion]["structure"]
    if not structure["placeholder_free"]:
        cap_score(
            scores[structure_criterion],
            0.5,
            "final document contains placeholder text: "
            + ", ".join(structure["placeholder_hits"]),
            f"artifact-audit.json criterion_checks.{structure_criterion}.structure",
        )
        failure_tags.add(config["criterion_failure_tags"][structure_criterion])

    judgment["scores"] = [scores[criterion] for criterion in expected_ids]
    judgment["failure_tags"] = sorted(failure_tags)
    return judgment


def missing_artifact_result(
    oracle: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    acceptable = oracle["expected"]["route"]["acceptable_primary_skills"]
    route_ok = (result.get("route") or {}).get("primary_skill") in acceptable
    scores: list[dict[str, Any]] = []
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
                    else "The required board-memo artifact was not available."
                ),
                "evidence": [
                    "agent-result.json route"
                    if is_route
                    else "agent-result.json artifacts"
                ],
            }
        )
    tags = ["missing-artifact"]
    if not route_ok:
        tags.append("route-error")
    return {
        "scores": scores,
        "failure_tags": tags,
        "summary": "The required board-memo artifact was missing.",
    }


def missing_artifact_audit(
    config: dict[str, Any], result: dict[str, Any]
) -> dict[str, Any]:
    relative = config["artifact"]["path"]
    declared = {
        item.get("path")
        for item in result.get("artifacts", [])
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    return {
        "artifact": {
            "path": relative,
            "exists": False,
            "declared": relative in declared,
            "bytes": 0,
            "sha256": None,
        },
        "markdown_check": {
            "ran": False,
            "ok": False,
            "errors": ["artifact missing"],
            "warnings": [],
        },
        "criterion_checks": {},
    }


def run_judge(args: argparse.Namespace) -> dict[str, Any]:
    env = environment()
    oracle = load_json(env["EVAL_ORACLE_FILE"])
    config = judge_config()
    validate_config(config, oracle)
    result = load_json(env["EVAL_RESULT_FILE"])
    evidence_dir = Path(
        os.environ.get(
            "EVAL_JUDGE_EVIDENCE_DIR",
            str(env["EVAL_JUDGE_RESULT_FILE"].parent / "judge-evidence"),
        )
    ).resolve()
    trace_dir = Path(
        os.environ.get(
            "EVAL_JUDGE_TRACE_DIR",
            str(env["EVAL_JUDGE_RESULT_FILE"].parent / "judge-trace"),
        )
    ).resolve()
    trace = trace_summary(env["EVAL_OUTPUT_DIR"])
    relative = config["artifact"]["path"]
    document_path = artifact_path(env["EVAL_OUTPUT_DIR"], relative)
    if not document_path.is_file():
        artifact_audit = missing_artifact_audit(config, result)
        persist_evidence(evidence_dir, artifact_audit, trace)
        judgment = missing_artifact_result(oracle, result)
    else:
        markdown_report, check_run = run_markdown_check(
            document_path,
            relative,
            evidence_dir,
        )
        artifact_audit = build_artifact_audit(
            config,
            result,
            document_path,
            markdown_report,
            check_run,
        )
        persist_evidence(evidence_dir, artifact_audit, trace)
        with tempfile.TemporaryDirectory(prefix="linlab-document-judge-") as temp:
            temp_root = Path(temp)
            workspace = temp_root / "blind-review"
            workspace.mkdir()
            prepare_model_workspace(
                workspace=workspace,
                env=env,
                result=result,
                config=config,
                artifact_audit=artifact_audit,
                markdown_report=markdown_report,
                trace=trace,
                evidence_dir=evidence_dir,
            )
            options = ModelJudgeOptions(
                codex_bin=args.codex_bin,
                model=args.model,
                reasoning_effort=args.reasoning_effort,
                timeout_seconds=args.timeout_seconds,
                max_attempts=args.max_attempts,
                retry_delay_seconds=args.retry_delay_seconds,
                structured_output=args.structured_output,
            )
            judgment = run_blind_model_judge(
                options=options,
                prompt=judge_prompt(oracle, relative),
                workspace=workspace,
                trace_root=trace_dir,
                criterion_ids=[
                    item["id"] for item in oracle["expected"]["outcomes"]
                ],
                failure_tags=oracle.get("failure_taxonomy", []),
            )
        judgment = apply_deterministic_overrides(
            judgment,
            oracle=oracle,
            config=config,
            result=result,
            artifact_audit=artifact_audit,
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
    try:
        judgment = run_judge(args)
    except (
        DocumentJudgeError,
        EvalConfigError,
        ModelJudgeError,
        subprocess.TimeoutExpired,
    ) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, "judgment": judgment}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
