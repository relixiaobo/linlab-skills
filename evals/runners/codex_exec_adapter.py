#!/usr/bin/env python3
"""Run one eval payload in an isolated, ephemeral Codex CLI session."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import Any, Iterable


REQUIRED_ENV = {
    "EVAL_RUN_MANIFEST",
    "EVAL_PROMPT_FILE",
    "EVAL_INPUT_DIR",
    "EVAL_SKILLS_DIR",
    "EVAL_OUTPUT_DIR",
    "EVAL_AGENT_RESULT_FILE",
}
TRACE_DIR_NAME = "trace"


class AdapterError(RuntimeError):
    """Raised when the Codex adapter cannot satisfy its execution protocol."""


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AdapterError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AdapterError(f"{path} must contain an object")
    return value


def ensure_environment() -> dict[str, str]:
    missing = sorted(name for name in REQUIRED_ENV if not os.environ.get(name))
    if missing:
        raise AdapterError(f"missing eval environment variables: {', '.join(missing)}")
    return {name: os.environ[name] for name in REQUIRED_ENV}


def copy_public_payload(
    *,
    prompt_path: Path,
    input_dir: Path,
    skills_dir: Path,
    workspace: Path,
    available_skills: list[dict[str, Any]],
) -> None:
    shutil.copy2(prompt_path, workspace / "prompt.md")
    shutil.copytree(input_dir, workspace / "input")
    copied_skills = workspace / "skills"
    copied_skills.mkdir()
    repo_skills = workspace / ".agents" / "skills"
    repo_skills.mkdir(parents=True)

    for skill in available_skills:
        name = skill.get("name")
        if not isinstance(name, str) or not name:
            raise AdapterError("agent manifest contains an invalid Skill name")
        source = skills_dir / name
        if not (source / "SKILL.md").is_file():
            raise AdapterError(f"materialized Skill is missing SKILL.md: {name}")
        destination = copied_skills / name
        shutil.copytree(source, destination)
        (repo_skills / name).symlink_to(destination, target_is_directory=True)


def seed_codex_home(destination: Path, source: Path) -> None:
    destination.mkdir(mode=0o700)
    auth = source / "auth.json"
    if not auth.is_file():
        raise AdapterError(f"Codex authentication file is missing: {auth}")
    (destination / "auth.json").symlink_to(auth)
    for name in ("models_cache.json", "installation_id", "version.json"):
        candidate = source / name
        if candidate.is_file():
            (destination / name).symlink_to(candidate)


def technical_prompt(user_prompt: str) -> str:
    return f"""You are completing a user task in an isolated workspace.

The exact user request is between the tags below and is also stored in
prompt.md. Carry it out using the files under input/.

<user_request>
{user_prompt.strip()}
</user_request>

Work autonomously and do not ask follow-up questions. You may use an available
repository Skill when it naturally applies; do not use one merely because it is
present. Place every final deliverable under deliverables/. Do not modify
prompt.md or input/. Before finishing, verify the deliverables in proportion to
their risk. In the final response, list delivered files and verification
performed. Do not discuss this wrapper or evaluation conditions.
"""


def build_codex_command(
    *,
    codex_bin: str,
    workspace: Path,
    response_path: Path,
    model: str,
    reasoning_effort: str,
    network_access: bool,
    user_prompt: str,
    provider_overrides: list[str] | None = None,
) -> list[str]:
    command = [
        codex_bin,
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
        "workspace-write",
        "--json",
        "--color",
        "never",
        "--model",
        model,
        "--cd",
        str(workspace),
        "--output-last-message",
        str(response_path),
        "--config",
        f'model_reasoning_effort="{reasoning_effort}"',
        "--config",
        'approval_policy="never"',
        "--config",
        f"sandbox_workspace_write.network_access={'true' if network_access else 'false'}",
        "--config",
        'shell_environment_policy.inherit="core"',
        "--config",
        'shell_environment_policy.include_only=["PATH","HOME","TMPDIR","LANG","LC_ALL"]',
    ]
    command.extend(provider_overrides or [])
    command.append(technical_prompt(user_prompt))
    return command


def toml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value)
    raise AdapterError(f"unsupported provider configuration value: {type(value).__name__}")


def provider_overrides(config_path: Path) -> tuple[str, list[str]]:
    if not config_path.is_file():
        return "openai", []
    try:
        config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise AdapterError(f"cannot read Codex provider configuration: {exc}") from exc
    provider_id = config.get("model_provider", "openai")
    if not isinstance(provider_id, str) or not provider_id:
        raise AdapterError("Codex model_provider must be a non-empty string")
    if provider_id == "openai":
        return provider_id, []
    providers = config.get("model_providers", {})
    provider = providers.get(provider_id) if isinstance(providers, dict) else None
    if not isinstance(provider, dict):
        raise AdapterError(f"active Codex provider is not defined: {provider_id}")

    safe_fields = {
        "name",
        "base_url",
        "wire_api",
        "requires_openai_auth",
        "request_max_retries",
        "stream_max_retries",
        "stream_idle_timeout_ms",
    }
    overrides = ["--config", f"model_provider={json.dumps(provider_id)}"]
    for key in sorted(safe_fields & set(provider)):
        overrides.extend(
            [
                "--config",
                f"model_providers.{provider_id}.{key}={toml_scalar(provider[key])}",
            ]
        )
    return provider_id, overrides


def parse_jsonl(text: str) -> list[dict[str, Any]]:
    events, diagnostics = parse_jsonl_best_effort(text)
    if diagnostics:
        first = diagnostics[0]
        if first["kind"] == "invalid-json":
            raise AdapterError(
                f"Codex JSONL line {first['line']} is invalid: {first['error']}"
            )
        raise AdapterError(f"Codex JSONL line {first['line']} must contain an object")
    return events


def parse_jsonl_best_effort(
    text: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Retain valid Codex events while recording malformed transport lines."""
    events: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            diagnostics.append(
                {
                    "line": line_number,
                    "kind": "invalid-json",
                    "error": str(exc),
                    "bytes": len(line.encode("utf-8")),
                }
            )
            continue
        if not isinstance(value, dict):
            diagnostics.append(
                {
                    "line": line_number,
                    "kind": "non-object",
                    "error": "JSONL event must contain an object",
                    "bytes": len(line.encode("utf-8")),
                }
            )
            continue
        events.append(value)
    return events, diagnostics


def nested_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from nested_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from nested_strings(child)


def selected_skills(
    events: list[dict[str, Any]],
    available_skills: list[dict[str, Any]],
    raw_trace: str = "",
) -> list[str]:
    searchable = ("\n".join(nested_strings(events)) + "\n" + raw_trace).replace("\\", "/")
    selected: list[str] = []
    for skill in available_skills:
        name = str(skill["name"])
        needles = (
            f"/.agents/skills/{name}/SKILL.md",
            f"/skills/{name}/SKILL.md",
            f".agents/skills/{name}/SKILL.md",
            f"skills/{name}/SKILL.md",
        )
        if any(needle in searchable for needle in needles):
            selected.append(name)
    return selected


def usage_from_events(events: list[dict[str, Any]]) -> dict[str, int | float | None]:
    usage: dict[str, Any] = {}
    for event in events:
        if event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
            usage = event["usage"]
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    if not isinstance(input_tokens, int) or input_tokens < 0:
        input_tokens = None
    if not isinstance(output_tokens, int) or output_tokens < 0:
        output_tokens = None
    total_tokens = (
        input_tokens + output_tokens
        if isinstance(input_tokens, int) and isinstance(output_tokens, int)
        else None
    )
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "estimated_cost_usd": None,
    }


def copy_deliverables(source: Path, output_dir: Path) -> None:
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise AdapterError(f"deliverables must not contain symlinks: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        destination = output_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)


def output_files(output_dir: Path) -> tuple[list[str], list[str]]:
    artifacts: list[str] = []
    traces: list[str] = []
    for path in sorted(output_dir.rglob("*")):
        if not path.is_file() or path.name == "agent-result.json":
            continue
        relative = path.relative_to(output_dir).as_posix()
        if relative == "response.md":
            continue
        if relative.startswith(f"{TRACE_DIR_NAME}/"):
            traces.append(relative)
        else:
            artifacts.append(relative)
    return artifacts, traces


def run_codex(args: argparse.Namespace) -> dict[str, Any]:
    env = ensure_environment()
    manifest = read_json(Path(env["EVAL_RUN_MANIFEST"]))
    available_skills = manifest.get("available_skills", [])
    if not isinstance(available_skills, list):
        raise AdapterError("agent manifest available_skills must be a list")
    executor_config = manifest.get("executor_config", {})
    if not isinstance(executor_config, dict):
        raise AdapterError("agent manifest executor_config must be an object")

    model = args.model or executor_config.get("model")
    if not isinstance(model, str) or not model:
        raise AdapterError("Codex model must be pinned with --model or executor_config.model")
    reasoning_effort = args.reasoning_effort or executor_config.get("reasoning_effort", "medium")
    if reasoning_effort not in {"low", "medium", "high", "xhigh", "max"}:
        raise AdapterError(f"unsupported reasoning effort: {reasoning_effort}")
    network_access = bool(executor_config.get("network_access", args.network_access))
    timeout_seconds = int(executor_config.get("adapter_timeout_seconds", args.timeout_seconds))

    output_dir = Path(env["EVAL_OUTPUT_DIR"]).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    original_codex_home = Path(
        os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))
    ).expanduser().resolve()
    provider_id, provider_args = provider_overrides(original_codex_home / "config.toml")

    with tempfile.TemporaryDirectory(prefix="linlab-eval-agent-") as temp:
        temp_root = Path(temp)
        workspace = temp_root / "workspace"
        workspace.mkdir()
        deliverables = workspace / "deliverables"
        deliverables.mkdir()
        copy_public_payload(
            prompt_path=Path(env["EVAL_PROMPT_FILE"]),
            input_dir=Path(env["EVAL_INPUT_DIR"]),
            skills_dir=Path(env["EVAL_SKILLS_DIR"]),
            workspace=workspace,
            available_skills=available_skills,
        )
        fake_home = temp_root / "home"
        fake_home.mkdir()
        codex_home = temp_root / "codex-home"
        seed_codex_home(codex_home, original_codex_home)
        response_path = deliverables / "response.md"
        command = build_codex_command(
            codex_bin=args.codex_bin,
            workspace=workspace,
            response_path=response_path,
            model=model,
            reasoning_effort=reasoning_effort,
            network_access=network_access,
            user_prompt=Path(env["EVAL_PROMPT_FILE"]).read_text(encoding="utf-8"),
            provider_overrides=provider_args,
        )
        child_env = dict(os.environ)
        child_env.update(
            {
                "HOME": str(fake_home),
                "CODEX_HOME": str(codex_home),
                "TMPDIR": str(temp_root / "tmp"),
            }
        )
        Path(child_env["TMPDIR"]).mkdir()
        for key in list(child_env):
            if key.startswith("EVAL_"):
                child_env.pop(key)

        try:
            proc = subprocess.run(
                command,
                cwd=workspace,
                env=child_env,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            stdout = proc.stdout
            stderr = proc.stderr
            exit_code = proc.returncode
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            exit_code = 124
            stderr += f"\nCodex adapter timed out after {timeout_seconds} seconds.\n"

        trace_dir = output_dir / TRACE_DIR_NAME
        trace_dir.mkdir(parents=True, exist_ok=True)
        (trace_dir / "codex-events.jsonl").write_text(stdout, encoding="utf-8")
        (trace_dir / "codex-stderr.log").write_text(stderr, encoding="utf-8")
        (trace_dir / "codex-command.json").write_text(
            json.dumps(
                {
                    "command": command[:-1] + ["<technical-prompt>"],
                    "model": model,
                    "reasoning_effort": reasoning_effort,
                    "network_access": network_access,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        copy_deliverables(deliverables, output_dir)

        events, parse_diagnostics = (
            parse_jsonl_best_effort(stdout) if stdout.strip() else ([], [])
        )
        if parse_diagnostics:
            (trace_dir / "parse-diagnostics.json").write_text(
                json.dumps(
                    {
                        "warning": "Malformed Codex JSONL lines were skipped; raw trace is preserved.",
                        "invalid_line_count": len(parse_diagnostics),
                        "lines": parse_diagnostics,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

    if stderr:
        print(stderr, file=sys.stderr, end="" if stderr.endswith("\n") else "\n")

    response_exists = (output_dir / "response.md").is_file()
    failure: str | None = None
    if exit_code != 0:
        failure = f"codex exec exited with code {exit_code}"
    elif not response_exists:
        failure = "codex exec did not produce response.md"

    selected = selected_skills(events, available_skills, stdout)
    artifacts, traces = output_files(output_dir)
    protocol = {
        "status": "failed" if failure else "completed",
        "response_path": "response.md" if response_exists else None,
        "artifacts": artifacts,
        "traces": traces,
        "route": {
            "primary_skill": selected[0] if selected else None,
            "selected_skills": selected,
        },
        "usage": usage_from_events(events),
        "model": {
            "name": model,
            "config": {
                "reasoning_effort": reasoning_effort,
                "network_access": network_access,
                "codex_cli": args.codex_bin,
                "model_provider": provider_id,
                "codex_exit_code": exit_code,
                "trace_parse_warning_count": len(parse_diagnostics),
                "trace_parse_warning_lines": [
                    item["line"] for item in parse_diagnostics
                ],
            },
        },
        "failure": failure,
    }
    Path(env["EVAL_AGENT_RESULT_FILE"]).write_text(
        json.dumps(protocol, indent=2) + "\n",
        encoding="utf-8",
    )
    if failure:
        raise AdapterError(failure)
    return protocol


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--model")
    parser.add_argument("--reasoning-effort")
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument(
        "--network-access",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        protocol = run_codex(args)
    except AdapterError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, "protocol": protocol}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
