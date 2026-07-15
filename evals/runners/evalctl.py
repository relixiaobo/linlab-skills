#!/usr/bin/env python3
"""Validate, materialize, and execute paired Skill evaluation suites."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evals.runners.eval_lib import (  # noqa: E402
    FAILURE_TAGS,
    EvalConfigError,
    canonical_sha256,
    safe_child,
    sha256_file,
    sha256_paths,
    sha256_tree,
    validate_result,
    validate_suite,
)


IGNORED_COPY_NAMES = {".DS_Store", "__pycache__", "node_modules", ".git"}
AGENT_RESULT_NAME = "agent-result.json"
JUDGE_RESULT_NAME = "judge-result.json"
AGENT_PLACEHOLDERS = {
    "repo",
    "run",
    "payload",
    "prompt",
    "input",
    "skills",
    "output",
    "manifest",
    "agent_result",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def check_run_id(value: str) -> str:
    if not value or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for char in value):
        raise EvalConfigError("run id may contain only letters, digits, dot, underscore, and hyphen")
    if value in {".", ".."}:
        raise EvalConfigError("invalid run id")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def ignored_copy(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name in IGNORED_COPY_NAMES or name.endswith(".pyc")}


def copy_skill(source: Path, destination: Path, ablations: list[dict[str, Any]]) -> dict[str, Any]:
    for path in source.rglob("*"):
        if path.is_symlink():
            raise EvalConfigError(f"Skill source must not contain symlinks: {path}")
    shutil.copytree(source, destination, ignore=ignored_copy)
    source_sha = sha256_tree(destination)

    for ablation in ablations:
        target = safe_child(destination, str(ablation["path"]))
        if not target.exists():
            raise EvalConfigError(f"materialized ablation target is missing: {target}")
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        if ablation["op"] == "replace":
            replacement = (ROOT / str(ablation["replacement"])).resolve()
            target.parent.mkdir(parents=True, exist_ok=True)
            if replacement.is_dir():
                shutil.copytree(replacement, target, ignore=ignored_copy)
            else:
                shutil.copy2(replacement, target)

    return {
        "source_sha256": source_sha,
        "materialized_sha256": sha256_tree(destination),
    }


def git_provenance() -> tuple[str | None, bool]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    commit_value = commit.stdout.strip() if commit.returncode == 0 else None
    return commit_value or None, bool(status.stdout.strip())


def format_command(template: str, values: dict[str, str]) -> list[str]:
    try:
        rendered = template.format_map(values)
    except KeyError as exc:
        raise EvalConfigError(f"unknown command placeholder: {exc.args[0]}") from exc
    command = shlex.split(rendered)
    if not command:
        raise EvalConfigError("executor command must not be empty")
    return command


def run_process(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: int,
) -> tuple[int, str, str, str | None]:
    try:
        proc = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, proc.stdout, proc.stderr, None
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return 124, stdout, stderr, f"timed out after {timeout} seconds"
    except OSError as exc:
        return 127, "", "", str(exc)


def artifact_record(path: Path, output_dir: Path, kind: str) -> dict[str, Any]:
    path = path.resolve()
    try:
        relative = path.relative_to(output_dir.resolve()).as_posix()
    except ValueError as exc:
        raise EvalConfigError(f"agent artifact escapes output directory: {path}") from exc
    if not path.is_file() or path.is_symlink():
        raise EvalConfigError(f"agent artifact must be a regular file: {path}")
    return {
        "path": relative,
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "kind": kind,
    }


def load_agent_protocol(path: Path, output_dir: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvalConfigError(f"invalid or missing {AGENT_RESULT_NAME}: {exc}") from exc
    if not isinstance(data, dict):
        raise EvalConfigError(f"{AGENT_RESULT_NAME} must contain an object")
    if data.get("status", "completed") not in {"completed", "failed"}:
        raise EvalConfigError("agent protocol status must be completed or failed")

    route = data.get("route", {})
    if not isinstance(route, dict):
        raise EvalConfigError("agent protocol route must be an object")
    primary_skill = route.get("primary_skill")
    selected_skills = route.get("selected_skills", [])
    if primary_skill is not None and not isinstance(primary_skill, str):
        raise EvalConfigError("agent protocol primary_skill must be a string or null")
    if not isinstance(selected_skills, list) or not all(
        isinstance(skill, str) and skill for skill in selected_skills
    ):
        raise EvalConfigError("agent protocol selected_skills must be a list of strings")

    usage = data.get("usage", {})
    if not isinstance(usage, dict):
        raise EvalConfigError("agent protocol usage must be an object")
    normalized_usage: dict[str, int | float | None] = {}
    for key in ("input_tokens", "output_tokens", "total_tokens"):
        value = usage.get(key)
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
            raise EvalConfigError(f"agent protocol {key} must be a non-negative integer or null")
        normalized_usage[key] = value
    cost = usage.get("estimated_cost_usd")
    if cost is not None and (isinstance(cost, bool) or not isinstance(cost, (int, float)) or cost < 0):
        raise EvalConfigError("agent protocol estimated_cost_usd must be non-negative or null")
    normalized_usage["estimated_cost_usd"] = cost

    model = data.get("model", {})
    if not isinstance(model, dict):
        raise EvalConfigError("agent protocol model must be an object")
    model_name = model.get("name")
    if model_name is not None and not isinstance(model_name, str):
        raise EvalConfigError("agent protocol model.name must be a string or null")
    model_config = model.get("config", {})
    if not isinstance(model_config, dict):
        raise EvalConfigError("agent protocol model.config must be an object")

    records: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    response_path = data.get("response_path")
    if response_path:
        response = safe_child(output_dir, str(response_path))
        record = artifact_record(response, output_dir, "response")
        records.append(record)
        seen_paths.add(record["path"])
    for key, kind in (("artifacts", "artifact"), ("traces", "trace")):
        values = data.get(key, [])
        if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
            raise EvalConfigError(f"agent protocol {key} must be a list of paths")
        for relative in values:
            record = artifact_record(safe_child(output_dir, relative), output_dir, kind)
            if record["path"] not in seen_paths:
                records.append(record)
                seen_paths.add(record["path"])
    return {
        "status": data.get("status", "completed"),
        "route": {
            "primary_skill": primary_skill,
            "selected_skills": list(dict.fromkeys(selected_skills)),
        },
        "usage": normalized_usage,
        "model": model_name,
        "config": model_config,
        "artifacts": records,
        "failure": data.get("failure"),
    }


def load_judge_protocol(path: Path, oracle: dict[str, Any]) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvalConfigError(f"invalid or missing {JUDGE_RESULT_NAME}: {exc}") from exc
    if not isinstance(data, dict):
        raise EvalConfigError(f"{JUDGE_RESULT_NAME} must contain an object")

    outcomes = {item["id"]: item for item in oracle["expected"]["outcomes"]}
    raw_scores = data.get("scores")
    if not isinstance(raw_scores, list) or not raw_scores:
        raise EvalConfigError("judge protocol scores must be a non-empty list")
    scores: list[dict[str, Any]] = []
    seen: set[str] = set()
    weighted = 0.0
    for raw in raw_scores:
        if not isinstance(raw, dict):
            raise EvalConfigError("judge score must be an object")
        criterion_id = raw.get("criterion_id")
        if criterion_id not in outcomes:
            raise EvalConfigError(f"judge scored unknown criterion: {criterion_id}")
        if criterion_id in seen:
            raise EvalConfigError(f"judge scored criterion twice: {criterion_id}")
        seen.add(criterion_id)
        value = raw.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
            raise EvalConfigError(f"judge score {criterion_id} must be in [0, 1]")
        rationale = raw.get("rationale", "")
        evidence = raw.get("evidence", [])
        if not isinstance(rationale, str) or not isinstance(evidence, list) or not all(
            isinstance(item, str) for item in evidence
        ):
            raise EvalConfigError(f"judge score {criterion_id} has invalid rationale or evidence")
        weight = float(outcomes[criterion_id]["weight"])
        weighted += float(value) * weight
        scores.append(
            {
                "criterion_id": criterion_id,
                "value": float(value),
                "weight": weight,
                "passed": bool(raw.get("passed", value >= 0.5)),
                "rationale": rationale,
                "evidence": evidence,
            }
        )

    failure_tags = data.get("failure_tags", [])
    if not isinstance(failure_tags, list) or not all(isinstance(tag, str) for tag in failure_tags):
        raise EvalConfigError("judge failure_tags must be a list of strings")
    allowed_tags = set(oracle.get("failure_taxonomy", []))
    unknown_tags = set(failure_tags) - FAILURE_TAGS
    if unknown_tags:
        raise EvalConfigError(f"judge used unknown failure tags: {sorted(unknown_tags)}")
    case_unknown_tags = set(failure_tags) - allowed_tags
    if case_unknown_tags:
        raise EvalConfigError(
            f"judge used tags outside the case failure taxonomy: {sorted(case_unknown_tags)}"
        )
    complete = seen == set(outcomes)
    status = "completed" if complete else "partial"
    critical_failures = sorted(
        score["criterion_id"]
        for score in scores
        if outcomes[score["criterion_id"]]["critical"] and not score["passed"]
    )
    return {
        "status": status,
        "overall_score": weighted if complete else None,
        "passed": not critical_failures if complete else None,
        "critical_failures": critical_failures,
        "scores": scores,
        "failure_tags": list(dict.fromkeys(failure_tags)),
        "summary": str(data.get("summary", "")),
    }


def initial_result(
    *,
    run_id: str,
    suite_id: str,
    case_id: str,
    condition: dict[str, Any],
    repetition: int,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "run_id": run_id,
        "suite_id": suite_id,
        "case_id": case_id,
        "condition": condition,
        "repetition": repetition,
        "status": "materialized",
        "timestamps": {"started_at": None, "completed_at": None, "duration_ms": None},
        "executor": {
            "command": [],
            "exit_code": None,
            "model": None,
            "config": {},
            "stdout_path": None,
            "stderr_path": None,
        },
        "route": {"primary_skill": None, "selected_skills": []},
        "usage": {
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "estimated_cost_usd": None,
        },
        "artifacts": [],
        "judging": {
            "status": "pending",
            "overall_score": None,
            "passed": None,
            "critical_failures": [],
            "scores": [],
            "failure_tags": [],
            "summary": "",
        },
        "failure": None,
        "provenance": provenance,
    }


def materialize_one(
    *,
    suite_id: str,
    case: Any,
    condition: Any,
    repetition: int,
    run_id: str,
    run_dir: Path,
    repo_commit: str | None,
    repo_dirty: bool,
) -> tuple[dict[str, Any], dict[str, str]]:
    payload = run_dir / "payload"
    input_dir = payload / "input"
    skills_dir = payload / "skills"
    output_dir = run_dir / "output"
    payload.mkdir(parents=True)
    input_dir.mkdir()
    skills_dir.mkdir()
    output_dir.mkdir()
    shutil.copy2(case.prompt_path, payload / "prompt.md")
    for source in case.input_files:
        relative = source.relative_to(case.input_dir)
        destination = safe_child(input_dir, relative.as_posix())
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    materialized_skills: list[dict[str, Any]] = []
    adapter_skills: list[dict[str, str]] = []
    for skill in condition.data["skills"]:
        destination = skills_dir / skill["name"]
        hashes = copy_skill(
            (ROOT / skill["path"]).resolve(),
            destination,
            skill.get("ablations", []),
        )
        materialized_skills.append(
            {
                "name": skill["name"],
                **hashes,
                "ablations": skill.get("ablations", []),
            }
        )
        adapter_skills.append({"name": skill["name"], "path": str(destination)})

    manifest = {
        "schema_version": "1.0",
        "run_id": run_id,
        "case_id": case.id,
        "repetition": repetition,
        "prompt_path": str(payload / "prompt.md"),
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "available_skills": adapter_skills,
        "executor_config": condition.data.get("executor_config", {}),
    }
    manifest_path = run_dir / "agent-manifest.json"
    write_json(manifest_path, manifest)

    visible_paths = [payload / "prompt.md", *[path for path in input_dir.rglob("*") if path.is_file()]]
    case_sha = sha256_paths(visible_paths, payload)
    result = initial_result(
        run_id=run_id,
        suite_id=suite_id,
        case_id=case.id,
        condition={
            "id": condition.id,
            "kind": condition.data["kind"],
            "skills": materialized_skills,
        },
        repetition=repetition,
        provenance={
            "repo_commit": repo_commit,
            "repo_dirty": repo_dirty,
            "case_sha256": case_sha,
            "oracle_sha256": sha256_file(case.oracle_path),
            "condition_sha256": canonical_sha256(condition.data),
        },
    )
    values = {
        "repo": str(ROOT),
        "run": str(run_dir),
        "payload": str(payload),
        "prompt": str(payload / "prompt.md"),
        "input": str(input_dir),
        "skills": str(skills_dir),
        "output": str(output_dir),
        "manifest": str(manifest_path),
        "agent_result": str(output_dir / AGENT_RESULT_NAME),
        "result": str(run_dir / "result.json"),
        "oracle": str(case.oracle_path),
        "judge_result": str(run_dir / JUDGE_RESULT_NAME),
    }
    return result, values


def execute_one(
    *,
    result: dict[str, Any],
    values: dict[str, str],
    case: Any,
    agent_template: str,
    judge_template: str | None,
    timeout: int,
) -> dict[str, Any]:
    run_dir = Path(values["run"])
    payload = Path(values["payload"])
    output_dir = Path(values["output"])
    result_path = Path(values["result"])
    agent_values = {key: values[key] for key in AGENT_PLACEHOLDERS}
    agent_command = format_command(agent_template, agent_values)
    agent_env = {key: value for key, value in os.environ.items() if not key.startswith("EVAL_")}
    agent_env.update(
        {
            "EVAL_RUN_MANIFEST": values["manifest"],
            "EVAL_PROMPT_FILE": values["prompt"],
            "EVAL_INPUT_DIR": values["input"],
            "EVAL_SKILLS_DIR": values["skills"],
            "EVAL_OUTPUT_DIR": values["output"],
            "EVAL_AGENT_RESULT_FILE": values["agent_result"],
        }
    )

    started_wall = time.monotonic()
    result["timestamps"]["started_at"] = utc_now()
    exit_code, stdout, stderr, process_error = run_process(
        agent_command,
        cwd=payload,
        env=agent_env,
        timeout=timeout,
    )
    logs_dir = run_dir / "logs"
    logs_dir.mkdir()
    stdout_path = logs_dir / "executor.stdout.log"
    stderr_path = logs_dir / "executor.stderr.log"
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    result["executor"].update(
        {
            "command": agent_command,
            "exit_code": exit_code,
            "stdout_path": stdout_path.relative_to(run_dir).as_posix(),
            "stderr_path": stderr_path.relative_to(run_dir).as_posix(),
        }
    )

    if exit_code != 0:
        result["status"] = "failed"
        result["failure"] = {
            "stage": "executor",
            "category": "executor-error",
            "message": process_error or f"executor exited with code {exit_code}",
        }
    else:
        try:
            protocol = load_agent_protocol(Path(values["agent_result"]), output_dir)
            result["status"] = protocol["status"]
            result["route"] = protocol["route"]
            result["usage"] = protocol["usage"]
            result["artifacts"] = protocol["artifacts"]
            result["executor"]["model"] = protocol["model"]
            result["executor"]["config"] = protocol["config"]
            if protocol["status"] == "failed":
                result["failure"] = {
                    "stage": "executor",
                    "category": "executor-error",
                    "message": str(protocol.get("failure") or "agent reported failure"),
                }
        except EvalConfigError as exc:
            result["status"] = "failed"
            result["failure"] = {
                "stage": "protocol",
                "category": "protocol-error",
                "message": str(exc),
            }

    result["timestamps"]["completed_at"] = utc_now()
    result["timestamps"]["duration_ms"] = round((time.monotonic() - started_wall) * 1000)
    validate_result(result)
    write_json(result_path, result)

    if result["status"] == "completed" and judge_template:
        judge_command = format_command(judge_template, values)
        judge_env = {key: value for key, value in os.environ.items() if not key.startswith("EVAL_")}
        judge_env.update(
            {
                "EVAL_ORACLE_FILE": values["oracle"],
                "EVAL_RESULT_FILE": values["result"],
                "EVAL_PAYLOAD_DIR": values["payload"],
                "EVAL_OUTPUT_DIR": values["output"],
                "EVAL_JUDGE_RESULT_FILE": values["judge_result"],
            }
        )
        judge_exit, judge_stdout, judge_stderr, judge_error = run_process(
            judge_command,
            cwd=run_dir,
            env=judge_env,
            timeout=timeout,
        )
        (logs_dir / "judge.stdout.log").write_text(judge_stdout, encoding="utf-8")
        (logs_dir / "judge.stderr.log").write_text(judge_stderr, encoding="utf-8")
        if judge_exit != 0:
            result["status"] = "failed"
            result["judging"]["status"] = "failed"
            result["failure"] = {
                "stage": "judge",
                "category": "judge-error",
                "message": judge_error or f"judge exited with code {judge_exit}",
            }
        else:
            try:
                result["judging"] = load_judge_protocol(Path(values["judge_result"]), case.oracle)
            except EvalConfigError as exc:
                result["status"] = "failed"
                result["judging"]["status"] = "failed"
                result["failure"] = {
                    "stage": "judge",
                    "category": "protocol-error",
                    "message": str(exc),
                }
        validate_result(result)
        write_json(result_path, result)
    return result


def metric_value(result: dict[str, Any], metric: str) -> int | float | None:
    if metric == "score":
        return result["judging"]["overall_score"]
    if metric == "duration_ms":
        return result["timestamps"]["duration_ms"]
    return result["usage"].get(metric)


def build_summary(
    *,
    run_id: str,
    suite: Any,
    mode: str,
    results: list[tuple[Path, dict[str, Any]]],
    run_root: Path,
) -> dict[str, Any]:
    entries = [
        {
            "case_id": result["case_id"],
            "condition_id": result["condition"]["id"],
            "repetition": result["repetition"],
            "status": result["status"],
            "score": result["judging"]["overall_score"],
            "passed": result["judging"]["passed"],
            "result_path": path.relative_to(run_root).as_posix(),
        }
        for path, result in results
    ]
    index = {
        (result["case_id"], result["condition"]["id"], result["repetition"]): result
        for _, result in results
    }
    control_id = suite.data["comparison"]["control_condition"]
    comparisons: list[dict[str, Any]] = []
    for _, treatment in results:
        treatment_id = treatment["condition"]["id"]
        if treatment_id == control_id:
            continue
        key = (treatment["case_id"], control_id, treatment["repetition"])
        control = index.get(key)
        if not control:
            continue
        deltas: dict[str, int | float | None] = {}
        for metric in suite.data["comparison"]["metrics"]:
            control_value = metric_value(control, metric)
            treatment_value = metric_value(treatment, metric)
            deltas[metric] = (
                treatment_value - control_value
                if isinstance(control_value, (int, float)) and isinstance(treatment_value, (int, float))
                else None
            )
        comparisons.append(
            {
                "case_id": treatment["case_id"],
                "repetition": treatment["repetition"],
                "control_condition": control_id,
                "treatment_condition": treatment_id,
                "deltas": deltas,
            }
        )
    return {
        "schema_version": "1.0",
        "run_id": run_id,
        "suite_id": suite.id,
        "mode": mode,
        "result_count": len(results),
        "results": entries,
        "comparisons": comparisons,
    }


def validate_schema_documents() -> list[str]:
    schema_dir = ROOT / "evals" / "schemas"
    names: list[str] = []
    for path in sorted(schema_dir.glob("*.schema.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise EvalConfigError(f"invalid schema JSON in {path}: {exc}") from exc
        if value.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            raise EvalConfigError(f"{path} must declare JSON Schema draft 2020-12")
        names.append(path.name)
    if not names:
        raise EvalConfigError("no evaluation schemas found")
    return names


def command_validate(args: argparse.Namespace) -> int:
    suite_path = (ROOT / args.suite).resolve() if not Path(args.suite).is_absolute() else Path(args.suite)
    suite = validate_suite(suite_path, ROOT)
    schemas = validate_schema_documents()
    count = sum(len(run.conditions) * run.repetitions for run in suite.runs)
    print(
        json.dumps(
            {
                "ok": True,
                "suite": suite.id,
                "case_count": len(suite.runs),
                "planned_run_count": count,
                "schemas": schemas,
            },
            indent=2,
        )
    )
    return 0


def command_execute(args: argparse.Namespace, mode: str) -> int:
    suite_path = (ROOT / args.suite).resolve() if not Path(args.suite).is_absolute() else Path(args.suite)
    suite = validate_suite(suite_path, ROOT)
    run_id = check_run_id(args.run_id or default_run_id())
    results_root = Path(args.results_dir)
    if not results_root.is_absolute():
        results_root = ROOT / results_root
    run_root = results_root / run_id
    if run_root.exists():
        raise EvalConfigError(f"run directory already exists: {run_root}")
    run_root.mkdir(parents=True)
    repo_commit, repo_dirty = git_provenance()
    timeout = int(suite.data["defaults"]["timeout_seconds"])
    collected: list[tuple[Path, dict[str, Any]]] = []

    for suite_run in suite.runs:
        for condition in suite_run.conditions:
            for repetition in range(1, suite_run.repetitions + 1):
                run_dir = (
                    run_root
                    / suite_run.case.id
                    / condition.id
                    / f"rep-{repetition:02d}"
                )
                result, values = materialize_one(
                    suite_id=suite.id,
                    case=suite_run.case,
                    condition=condition,
                    repetition=repetition,
                    run_id=run_id,
                    run_dir=run_dir,
                    repo_commit=repo_commit,
                    repo_dirty=repo_dirty,
                )
                result_path = run_dir / "result.json"
                if mode == "run":
                    result = execute_one(
                        result=result,
                        values=values,
                        case=suite_run.case,
                        agent_template=args.agent_command,
                        judge_template=args.judge_command,
                        timeout=timeout,
                    )
                else:
                    validate_result(result)
                    write_json(result_path, result)
                collected.append((result_path, result))

    summary = build_summary(
        run_id=run_id,
        suite=suite,
        mode=mode,
        results=collected,
        run_root=run_root,
    )
    summary_path = run_root / "run-summary.json"
    write_json(summary_path, summary)
    print(json.dumps({"ok": True, "run_root": str(run_root), **summary}, indent=2))
    return 0 if all(result["status"] != "failed" for _, result in collected) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="validate schemas and a suite")
    validate_parser.add_argument("--suite", required=True, help="suite path, relative to repository root")

    for command in ("materialize", "run"):
        child = subparsers.add_parser(command, help=f"{command} a suite")
        child.add_argument("--suite", required=True, help="suite path, relative to repository root")
        child.add_argument("--results-dir", default="results", help="generated result root")
        child.add_argument("--run-id", help="stable run identifier")
        if command == "run":
            child.add_argument(
                "--agent-command",
                required=True,
                help="executor command template; see evals/README.md for placeholders",
            )
            child.add_argument(
                "--judge-command",
                help="optional post-run judge command template",
            )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            return command_validate(args)
        return command_execute(args, args.command)
    except EvalConfigError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
