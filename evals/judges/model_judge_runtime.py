"""Shared isolated Codex runtime for blind model-assisted Judge Adapters."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from evals.runners.codex_exec_adapter import (
    AdapterError,
    parse_jsonl_best_effort,
    provider_overrides,
    seed_codex_home,
    usage_from_events,
)


ROOT = Path(__file__).resolve().parents[2]
JUDGE_RESULT_SCHEMA = ROOT / "evals" / "schemas" / "eval-judge-result.schema.json"


class ModelJudgeError(RuntimeError):
    """Raised when the blind model judge cannot produce a result."""


@dataclass(frozen=True)
class ModelJudgeOptions:
    codex_bin: str
    model: str
    reasoning_effort: str
    timeout_seconds: int
    max_attempts: int
    retry_delay_seconds: float
    structured_output: str


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelJudgeError(f"cannot read model result {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ModelJudgeError(f"model result {path} must contain an object")
    return value


def judge_output_schema(
    criterion_ids: list[str],
    failure_tags: list[str],
) -> dict[str, Any]:
    canonical = json.loads(JUDGE_RESULT_SCHEMA.read_text(encoding="utf-8"))
    score = copy.deepcopy(canonical["$defs"]["score"])
    score["properties"]["criterion_id"] = {
        "type": "string",
        "enum": criterion_ids,
    }
    scores = copy.deepcopy(canonical["properties"]["scores"])
    scores.update(
        {
            "minItems": len(criterion_ids),
            "maxItems": len(criterion_ids),
            "items": score,
        }
    )
    failure_tag_schema = copy.deepcopy(canonical["properties"]["failure_tags"])
    failure_tag_schema["items"] = {"type": "string"}
    if failure_tags:
        failure_tag_schema["items"]["enum"] = failure_tags
    else:
        failure_tag_schema["maxItems"] = 0
    return {
        "type": "object",
        "additionalProperties": False,
        "required": copy.deepcopy(canonical["required"]),
        "properties": {
            "scores": scores,
            "failure_tags": failure_tag_schema,
            "summary": copy.deepcopy(canonical["properties"]["summary"]),
        },
    }


def write_judge_schema(
    path: Path,
    criterion_ids: list[str],
    failure_tags: list[str],
) -> None:
    path.write_text(
        json.dumps(judge_output_schema(criterion_ids, failure_tags), indent=2) + "\n",
        encoding="utf-8",
    )


def validate_model_judgment(
    value: dict[str, Any],
    criterion_ids: list[str],
    failure_tags: list[str],
) -> dict[str, Any]:
    scores = value.get("scores")
    if not isinstance(scores, list):
        raise ModelJudgeError("blind model result scores must be an array")
    if any(
        not isinstance(score, dict)
        or not isinstance(score.get("criterion_id"), str)
        for score in scores
    ):
        raise ModelJudgeError("blind model result contains an invalid criterion id")
    actual_ids = [score["criterion_id"] for score in scores]
    duplicate_ids = sorted(
        criterion_id
        for criterion_id in set(actual_ids)
        if actual_ids.count(criterion_id) > 1
    )
    if duplicate_ids:
        raise ModelJudgeError(
            f"blind model result scored criteria more than once: {duplicate_ids}"
        )
    if set(actual_ids) != set(criterion_ids):
        raise ModelJudgeError(
            "blind model result criterion mismatch: "
            f"expected {sorted(criterion_ids)}, got {sorted(actual_ids)}"
        )
    actual_tags = value.get("failure_tags")
    if not isinstance(actual_tags, list) or any(
        not isinstance(tag, str) for tag in actual_tags
    ):
        raise ModelJudgeError("blind model result failure_tags must be a string array")
    if len(actual_tags) != len(set(actual_tags)):
        raise ModelJudgeError("blind model result contains duplicate failure tags")
    unknown_tags = sorted(set(actual_tags) - set(failure_tags))
    if unknown_tags:
        raise ModelJudgeError(
            f"blind model result used unsupported failure tags: {unknown_tags}"
        )
    return value


def resolve_structured_output_mode(provider_id: str, requested: str) -> str:
    if requested not in {"auto", "schema", "prompt"}:
        raise ModelJudgeError(f"unsupported structured output mode: {requested}")
    if requested == "auto":
        return "schema" if provider_id == "openai" else "prompt"
    return requested


def is_transient_codex_failure(returncode: int, stdout: str, stderr: str) -> bool:
    if returncode == 0:
        return False
    combined = f"{stdout}\n{stderr}".lower()
    markers = (
        "429",
        "502 bad gateway",
        "503 service unavailable",
        "504 gateway timeout",
        "connection reset",
        "connection refused",
        "reconnecting",
        "rate limit",
        "stream disconnected",
        "temporarily unavailable",
        "timed out",
        "unexpected eof",
    )
    return returncode == 124 or any(marker in combined for marker in markers)


def next_attempt_number(trace_root: Path) -> int:
    numbers: list[int] = []
    if trace_root.is_dir():
        for path in trace_root.glob("attempt-*"):
            try:
                numbers.append(int(path.name.removeprefix("attempt-")))
            except ValueError:
                continue
    return max(numbers, default=0) + 1


def write_judge_attempt(
    *,
    trace_root: Path,
    attempt_number: int,
    stdout: str,
    stderr: str,
    returncode: int,
    transient: bool,
    options: ModelJudgeOptions,
    provider_id: str,
    structured_output_mode: str,
    duration_ms: int,
) -> dict[str, Any]:
    events, diagnostics = parse_jsonl_best_effort(stdout) if stdout.strip() else ([], [])
    usage = usage_from_events(events)
    attempt_dir = trace_root / f"attempt-{attempt_number:02d}"
    attempt_dir.mkdir(parents=True)
    metadata = {
        "attempt": attempt_number,
        "exit_code": returncode,
        "transient_failure": transient,
        "model": options.model,
        "reasoning_effort": options.reasoning_effort,
        "model_provider": provider_id,
        "structured_output_mode": structured_output_mode,
        "duration_ms": duration_ms,
        "usage": usage,
        "parse_diagnostics": diagnostics,
    }
    for directory in (attempt_dir, trace_root):
        (directory / "codex-events.jsonl").write_text(stdout, encoding="utf-8")
        (directory / "codex-stderr.log").write_text(stderr, encoding="utf-8")
        (directory / "usage.json").write_text(
            json.dumps(metadata, indent=2) + "\n",
            encoding="utf-8",
        )
    return metadata


def run_blind_model_judge(
    *,
    options: ModelJudgeOptions,
    prompt: str,
    workspace: Path,
    trace_root: Path,
    criterion_ids: list[str],
    failure_tags: list[str],
    image_paths: Iterable[Path] = (),
) -> dict[str, Any]:
    if options.max_attempts < 1:
        raise ModelJudgeError("max attempts must be at least 1")
    if options.retry_delay_seconds < 0:
        raise ModelJudgeError("retry delay must be non-negative")

    schema_path = workspace / "judge-output.schema.json"
    output_path = workspace / "judge-output.json"
    write_judge_schema(schema_path, criterion_ids, failure_tags)

    original_codex_home = Path(
        os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))
    ).expanduser().resolve()
    try:
        provider_id, provider_args = provider_overrides(
            original_codex_home / "config.toml"
        )
    except AdapterError as exc:
        raise ModelJudgeError(str(exc)) from exc
    structured_output_mode = resolve_structured_output_mode(
        provider_id,
        options.structured_output,
    )
    runtime_root = workspace.parent / "judge-runtime"
    runtime_root.mkdir()
    fake_home = runtime_root / "home"
    fake_home.mkdir()
    codex_home = runtime_root / "codex-home"
    try:
        seed_codex_home(codex_home, original_codex_home)
    except AdapterError as exc:
        raise ModelJudgeError(str(exc)) from exc
    tmp_dir = runtime_root / "tmp"
    tmp_dir.mkdir()

    command = [
        options.codex_bin,
        "exec",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--strict-config",
        "--skip-git-repo-check",
        "--disable",
        "plugins",
        "--disable",
        "multi_agent",
        "--sandbox",
        "read-only",
        "--json",
        "--color",
        "never",
        "--model",
        options.model,
        "--cd",
        str(workspace),
        "--output-last-message",
        str(output_path),
        "--config",
        f'model_reasoning_effort="{options.reasoning_effort}"',
        "--config",
        'approval_policy="never"',
        "--config",
        'shell_environment_policy.inherit="core"',
        "--config",
        'shell_environment_policy.include_only=["PATH","HOME","TMPDIR","LANG","LC_ALL"]',
    ]
    if structured_output_mode == "schema":
        output_index = command.index("--output-last-message")
        command[output_index:output_index] = ["--output-schema", str(schema_path)]
    for image_path in image_paths:
        command.extend(["--image", str(image_path)])
    command.extend(provider_args)
    command.append(prompt)

    child_env = dict(os.environ)
    child_env.update(
        {
            "HOME": str(fake_home),
            "CODEX_HOME": str(codex_home),
            "TMPDIR": str(tmp_dir),
        }
    )
    for key in list(child_env):
        if key.startswith("EVAL_"):
            child_env.pop(key)
    trace_root.mkdir(parents=True, exist_ok=True)
    attempt_number = next_attempt_number(trace_root)
    history: list[dict[str, Any]] = []
    for offset in range(options.max_attempts):
        output_path.unlink(missing_ok=True)
        attempt_started_wall = time.monotonic()
        try:
            proc = subprocess.run(
                command,
                cwd=workspace,
                env=child_env,
                capture_output=True,
                text=True,
                timeout=options.timeout_seconds,
                check=False,
            )
            stdout = proc.stdout
            stderr = proc.stderr
            returncode = proc.returncode
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            stderr += f"\nBlind model judge timed out after {options.timeout_seconds} seconds.\n"
            returncode = 124
        except OSError as exc:
            stdout = ""
            stderr = f"Cannot start blind model judge: {exc}\n"
            returncode = 127
        duration_ms = round((time.monotonic() - attempt_started_wall) * 1000)
        transient = is_transient_codex_failure(returncode, stdout, stderr)
        history.append(
            write_judge_attempt(
                trace_root=trace_root,
                attempt_number=attempt_number + offset,
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
                transient=transient,
                options=options,
                provider_id=provider_id,
                structured_output_mode=structured_output_mode,
                duration_ms=duration_ms,
            )
        )
        (trace_root / "attempts.json").write_text(
            json.dumps({"attempts": history}, indent=2) + "\n",
            encoding="utf-8",
        )
        if returncode == 0:
            return validate_model_judgment(
                load_json_object(output_path),
                criterion_ids,
                failure_tags,
            )
        if transient and offset + 1 < options.max_attempts:
            delay = min(options.retry_delay_seconds * (2**offset), 30.0)
            if delay > 0:
                time.sleep(delay)
            continue
        failure_tail = f"{stderr}\n{stdout}"[-2000:]
        raise ModelJudgeError(
            f"blind model judge exited with code {returncode} after {offset + 1} "
            f"attempt(s): {failure_tail}"
        )
    raise ModelJudgeError("blind model judge exhausted its retry loop")
