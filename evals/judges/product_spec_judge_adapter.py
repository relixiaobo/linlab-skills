#!/usr/bin/env python3
"""Judge product specs with deterministic readiness evidence and blind review."""

from __future__ import annotations

import argparse
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
SPEC_CHECK = ROOT / "shape-product-spec" / "scripts" / "spec_check.py"


class ProductSpecJudgeError(RuntimeError):
    """Raised when product-spec evidence cannot be produced safely."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProductSpecJudgeError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ProductSpecJudgeError(f"{path} must contain an object")
    return value


def environment() -> dict[str, Path]:
    missing = sorted(name for name in REQUIRED_ENV if not os.environ.get(name))
    if missing:
        raise ProductSpecJudgeError(
            f"missing judge environment variables: {', '.join(missing)}"
        )
    return {name: Path(os.environ[name]).resolve() for name in REQUIRED_ENV}


def judge_config() -> dict[str, Any]:
    try:
        value = json.loads(os.environ.get("EVAL_JUDGE_CONFIG", "{}"))
    except json.JSONDecodeError as exc:
        raise ProductSpecJudgeError(f"invalid EVAL_JUDGE_CONFIG: {exc}") from exc
    if not isinstance(value, dict):
        raise ProductSpecJudgeError("EVAL_JUDGE_CONFIG must contain an object")
    required = {"artifact", "structure", "concepts", "criterion_failure_tags"}
    missing = sorted(required - set(value))
    unknown = sorted(set(value) - required)
    if missing or unknown:
        raise ProductSpecJudgeError(
            f"product-spec config mismatch; missing={missing}, unknown={unknown}"
        )
    return value


def require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ProductSpecJudgeError(f"{label} must be a non-empty string")
    return value


def validate_string_list(value: Any, label: str) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or not item for item in value)
    ):
        raise ProductSpecJudgeError(f"{label} must be a non-empty string array")
    if len(value) != len(set(value)):
        raise ProductSpecJudgeError(f"{label} must not contain duplicates")
    return value


def validate_config(config: dict[str, Any], oracle: dict[str, Any]) -> None:
    outcome_ids = {item["id"] for item in oracle["expected"]["outcomes"]}
    allowed_tags = set(oracle.get("failure_taxonomy", []))

    artifact = config["artifact"]
    if not isinstance(artifact, dict) or set(artifact) != {"path", "criterion"}:
        raise ProductSpecJudgeError("artifact config has an invalid shape")
    require_string(artifact["path"], "artifact.path")
    artifact_criterion = require_string(artifact["criterion"], "artifact.criterion")

    structure = config["structure"]
    if not isinstance(structure, dict) or set(structure) != {
        "criterion",
        "stable_id_minimums",
        "acceptance_criteria_minimum",
    }:
        raise ProductSpecJudgeError("structure config has an invalid shape")
    structure_criterion = require_string(
        structure["criterion"], "structure.criterion"
    )
    minimums = structure["stable_id_minimums"]
    if not isinstance(minimums, dict) or not minimums:
        raise ProductSpecJudgeError(
            "structure.stable_id_minimums must be a non-empty object"
        )
    for kind, minimum in minimums.items():
        require_string(kind, "stable ID kind")
        if (
            not isinstance(minimum, int)
            or isinstance(minimum, bool)
            or minimum < 1
        ):
            raise ProductSpecJudgeError(
                f"stable ID minimum {kind} must be positive"
            )
    if (
        not isinstance(structure["acceptance_criteria_minimum"], int)
        or isinstance(structure["acceptance_criteria_minimum"], bool)
        or structure["acceptance_criteria_minimum"] < 1
    ):
        raise ProductSpecJudgeError(
            "structure.acceptance_criteria_minimum must be positive"
        )

    concepts = config["concepts"]
    if not isinstance(concepts, dict):
        raise ProductSpecJudgeError("concepts config must be an object")
    for criterion, requirements in concepts.items():
        require_string(criterion, "concept criterion")
        if not isinstance(requirements, list) or not requirements:
            raise ProductSpecJudgeError(
                f"concept requirements for {criterion} must be a non-empty array"
            )
        requirement_ids: list[str] = []
        for requirement in requirements:
            if not isinstance(requirement, dict) or set(requirement) != {
                "id",
                "term_groups",
            }:
                raise ProductSpecJudgeError(
                    f"concept requirement for {criterion} has an invalid shape"
                )
            requirement_id = require_string(
                requirement["id"], f"concept id for {criterion}"
            )
            requirement_ids.append(requirement_id)
            groups = requirement["term_groups"]
            if not isinstance(groups, list) or not groups:
                raise ProductSpecJudgeError(
                    f"term_groups for {criterion}.{requirement_id} must be non-empty"
                )
            for index, alternatives in enumerate(groups, start=1):
                validate_string_list(
                    alternatives,
                    f"terms for {criterion}.{requirement_id} group {index}",
                )
        if len(requirement_ids) != len(set(requirement_ids)):
            raise ProductSpecJudgeError(
                f"concept requirement ids for {criterion} must be unique"
            )

    tag_map = config["criterion_failure_tags"]
    if not isinstance(tag_map, dict):
        raise ProductSpecJudgeError("criterion_failure_tags must be an object")
    configured_criteria = (
        {artifact_criterion, structure_criterion} | set(concepts)
    )
    unknown_criteria = sorted(configured_criteria - outcome_ids)
    if unknown_criteria:
        raise ProductSpecJudgeError(
            f"config references unknown criteria: {unknown_criteria}"
        )
    if set(tag_map) != configured_criteria:
        raise ProductSpecJudgeError(
            "criterion_failure_tags must cover every configured criterion"
        )
    invalid_tags = sorted(
        repr(tag)
        for tag in tag_map.values()
        if not isinstance(tag, str) or tag not in allowed_tags
    )
    if invalid_tags:
        raise ProductSpecJudgeError(
            f"criterion_failure_tags contains unsupported tags: {invalid_tags}"
        )


def artifact_path(output_dir: Path, relative: str) -> Path:
    unresolved = output_dir / relative
    if unresolved.is_symlink():
        raise ProductSpecJudgeError(f"artifact must not be a symlink: {relative}")
    return safe_child(output_dir, relative)


def normalize_text(text: str) -> str:
    return re.sub(r"[\W_]+", " ", text.casefold()).strip()


def audit_concepts(
    concepts: dict[str, Any],
    text: str,
) -> dict[str, Any]:
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
                requirement["id"]
                for requirement in audited_requirements
                if not requirement["passed"]
            ],
        }
    return result


def audit_structure(config: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    structure = config["structure"]
    id_counts = (report.get("summary") or {}).get("stable_id_counts") or {}
    acceptance_count = (report.get("summary") or {}).get(
        "acceptance_criteria_count", 0
    )
    minimum_counts = structure["stable_id_minimums"]
    acceptance_minimum = structure["acceptance_criteria_minimum"]
    return {
        structure["criterion"]: {
            "stable_id_minimums": minimum_counts,
            "stable_id_actuals": {
                kind: id_counts.get(kind, 0) for kind in minimum_counts
            },
            "missing_stable_ids": [
                kind
                for kind, minimum in minimum_counts.items()
                if id_counts.get(kind, 0) < minimum
            ],
            "acceptance_criteria": {
                "minimum": acceptance_minimum,
                "actual": acceptance_count,
                "passed": acceptance_count >= acceptance_minimum,
            },
        }
    }


def run_spec_check(
    spec_path: Path,
    relative_path: str,
    evidence_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    report_path = evidence_dir / "spec-check.json"
    command = [
        sys.executable,
        str(SPEC_CHECK),
        "inspect",
        str(spec_path),
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
        raise ProductSpecJudgeError(f"cannot run spec_check.py: {exc}") from exc
    (evidence_dir / "spec-check.stdout.log").write_text(
        proc.stdout, encoding="utf-8"
    )
    (evidence_dir / "spec-check.stderr.log").write_text(
        proc.stderr, encoding="utf-8"
    )
    if proc.returncode not in {0, 1} or not report_path.is_file():
        tail = f"{proc.stderr}\n{proc.stdout}"[-2000:]
        raise ProductSpecJudgeError(
            f"spec_check.py failed with code {proc.returncode}: {tail}"
        )
    report = load_json(report_path)
    report["path"] = f"artifacts/{Path(relative_path).name}"
    if bool(report.get("ok")) != (proc.returncode == 0):
        raise ProductSpecJudgeError(
            "spec_check.py exit code disagrees with its report"
        )
    report_path.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )
    return report, {
        "exit_code": proc.returncode,
        "stdout_log": "spec-check.stdout.log",
        "stderr_log": "spec-check.stderr.log",
    }


def build_artifact_audit(
    config: dict[str, Any],
    result: dict[str, Any],
    spec_path: Path,
    report: dict[str, Any],
    spec_check_run: dict[str, Any],
) -> dict[str, Any]:
    artifact_config = config["artifact"]
    text = spec_path.read_text(encoding="utf-8", errors="replace")
    declared = {
        item.get("path")
        for item in result.get("artifacts", [])
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    concepts = audit_concepts(config["concepts"], text)
    structure = audit_structure(config, report)
    criterion_checks: dict[str, Any] = {}
    for criterion in config["criterion_failure_tags"]:
        concept = concepts.get(criterion, {"requirements": [], "missing": []})
        structural = structure.get(
            criterion,
            {
                "stable_id_minimums": {},
                "stable_id_actuals": {},
                "missing_stable_ids": [],
            },
        )
        acceptance = structural.get("acceptance_criteria")
        criterion_checks[criterion] = {
            "concepts": concept,
            "structure": structural,
            "passed": (
                not concept["missing"]
                and not structural["missing_stable_ids"]
                and (acceptance is None or acceptance["passed"])
            ),
        }
    size = spec_path.stat().st_size
    return {
        "artifact": {
            "path": artifact_config["path"],
            "exists": True,
            "declared": artifact_config["path"] in declared,
            "bytes": size,
        },
        "spec_check": {
            **spec_check_run,
            "ok": bool(report.get("ok")),
            "errors": (report.get("findings") or {}).get("errors", []),
            "warnings": (report.get("findings") or {}).get("warnings", []),
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
    return f"""Act as a blind product-spec evaluator. You do not know which
experimental condition produced the work. Review source/prompt.md, source/input/,
agent-result.json, agent-response.md, agent-trace-summary.json,
{model_artifact}, spec-check.json, and artifact-audit.json.

Judge whether the spec is decision-ready and execution-ready, not whether it
imitates a template. Preserve source facts and unresolved policy; do not reward
invented certainty. Distinguish the clean-slate direction from the selected
constrained release and evaluate whether the tradeoff is coherent. Verify that
flows are reachable, permissions and states are explicit, non-goals prevent
overbuild, and acceptance criteria describe observable behavior rather than
implementation details. Treat artifact-audit.json term matches and misses as
semantic review hints, not as proof that a concept is present or absent. Use
spec-check.json for structural facts, then inspect the artifact itself for
semantic quality and contradictions.

Score every criterion from 0.0 to 1.0. Set passed=true only at 0.75 or higher
with no blocking failure. Ground every score in concrete source lines, stable
IDs, flow states, requirements, or deterministic report fields.

Rubric:
{rubric}

Return exactly one score for every criterion id and only a JSON object shaped as:
{{"scores":[{{"criterion_id":"...","value":0.0,"passed":false,
"rationale":"...","evidence":["..."]}}],"failure_tags":[],"summary":"..."}}
Allowed criterion ids: {json.dumps(criterion_ids)}
Allowed failure tags: {json.dumps(failure_tags)}
"""


def prepare_model_workspace(
    *,
    workspace: Path,
    env: dict[str, Path],
    result: dict[str, Any],
    config: dict[str, Any],
    artifact_audit: dict[str, Any],
    spec_report: dict[str, Any],
    trace: dict[str, Any],
) -> None:
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
        response.read_text(encoding="utf-8", errors="replace")
        if response.is_file()
        else "",
        encoding="utf-8",
    )
    for name, value in (
        ("agent-trace-summary.json", trace),
        ("artifact-audit.json", artifact_audit),
        ("spec-check.json", spec_report),
    ):
        (workspace / name).write_text(
            json.dumps(value, indent=2) + "\n",
            encoding="utf-8",
        )
    artifact_dir = workspace / "artifacts"
    artifact_dir.mkdir()
    source = artifact_path(env["EVAL_OUTPUT_DIR"], config["artifact"]["path"])
    shutil.copy2(source, artifact_dir / Path(config["artifact"]["path"]).name)


def score_index(judgment: dict[str, Any]) -> dict[str, dict[str, Any]]:
    scores = judgment.get("scores")
    if not isinstance(scores, list):
        raise ProductSpecJudgeError("model judgment has no scores list")
    indexed: dict[str, dict[str, Any]] = {}
    for score in scores:
        if not isinstance(score, dict) or not isinstance(score.get("criterion_id"), str):
            raise ProductSpecJudgeError("model judgment contains an invalid score")
        indexed[score["criterion_id"]] = score
    return indexed


def cap_score(score: dict[str, Any], cap: float, rationale: str, evidence: str) -> None:
    value = score.get("value")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ProductSpecJudgeError("model score value must be numeric")
    if float(value) > cap:
        score["value"] = cap
    score["passed"] = float(score["value"]) >= 0.75
    score["rationale"] = (
        f"{score.get('rationale', '')} Deterministic check: {rationale}".strip()
    )
    evidence_items = score.setdefault("evidence", [])
    if isinstance(evidence_items, list) and evidence not in evidence_items:
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
        raise ProductSpecJudgeError(
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
                "Recorded primary Skill matches the expected product-spec route."
                if route_ok
                else "Recorded primary Skill does not match the expected product-spec route."
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
            "the required product spec was not declared as an Agent artifact",
            "artifact-audit.json artifact.declared",
        )
        failure_tags.add("missing-artifact")
    if not artifact_audit["spec_check"]["ok"]:
        errors = artifact_audit["spec_check"]["errors"]
        cap_score(
            scores[artifact_criterion],
            0.25,
            "portable spec inspection failed: " + "; ".join(errors),
            "spec-check.json findings.errors",
        )
        failure_tags.add(config["criterion_failure_tags"][artifact_criterion])

    for criterion, check in artifact_audit["criterion_checks"].items():
        structure = check["structure"]
        missing_parts = [
            *(f"stable-id:{item}" for item in structure["missing_stable_ids"]),
        ]
        acceptance = structure.get("acceptance_criteria")
        if acceptance is not None and not acceptance["passed"]:
            missing_parts.append(
                "acceptance-criteria:"
                f"{acceptance['actual']}/{acceptance['minimum']}"
            )
        if not missing_parts:
            continue
        cap_score(
            scores[criterion],
            0.5,
            "required product-spec evidence is absent: " + ", ".join(missing_parts),
            f"artifact-audit.json criterion_checks.{criterion}",
        )
        failure_tags.add(config["criterion_failure_tags"][criterion])

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
                    else "The required product-spec artifact was not available."
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
        "summary": "The required product-spec artifact was missing.",
    }


def missing_artifact_audit(config: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
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
        },
        "spec_check": {"ran": False, "ok": False, "errors": ["artifact missing"]},
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
    spec_path = artifact_path(env["EVAL_OUTPUT_DIR"], relative)
    if not spec_path.is_file():
        artifact_audit = missing_artifact_audit(config, result)
        persist_evidence(evidence_dir, artifact_audit, trace)
        judgment = missing_artifact_result(oracle, result)
    else:
        spec_report, spec_check_run = run_spec_check(
            spec_path,
            relative,
            evidence_dir,
        )
        artifact_audit = build_artifact_audit(
            config,
            result,
            spec_path,
            spec_report,
            spec_check_run,
        )
        persist_evidence(evidence_dir, artifact_audit, trace)
        with tempfile.TemporaryDirectory(prefix="linlab-product-spec-judge-") as temp:
            temp_root = Path(temp)
            workspace = temp_root / "blind-review"
            workspace.mkdir()
            prepare_model_workspace(
                workspace=workspace,
                env=env,
                result=result,
                config=config,
                artifact_audit=artifact_audit,
                spec_report=spec_report,
                trace=trace,
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
                criterion_ids=[item["id"] for item in oracle["expected"]["outcomes"]],
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
        ProductSpecJudgeError,
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
