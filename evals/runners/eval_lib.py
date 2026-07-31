"""Shared loading, validation, hashing, and path-safety helpers for evals."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from evals.runners.errors import EvalConfigError
from evals.runners.schema_validation import validate_document


REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class CaseSpec:
    directory: Path
    prompt_path: Path
    input_dir: Path
    input_files: tuple[Path, ...]
    oracle_path: Path
    oracle: dict[str, Any]

    @property
    def id(self) -> str:
        return str(self.oracle["id"])

    @property
    def judge_adapter_id(self) -> str | None:
        evaluation = self.oracle.get("evaluation")
        if not isinstance(evaluation, dict):
            return None
        adapter = evaluation.get("adapter")
        return str(adapter) if adapter else None

    @property
    def judge_config(self) -> dict[str, Any]:
        evaluation = self.oracle.get("evaluation")
        if not isinstance(evaluation, dict):
            return {}
        config = evaluation.get("config", {})
        return dict(config) if isinstance(config, dict) else {}

    @property
    def intervention_activations(self) -> dict[str, dict[str, Any]]:
        return {
            str(item["behavior"]): dict(item)
            for item in self.oracle.get("intervention_activations", [])
        }


@dataclass(frozen=True)
class JudgeAdapterSpec:
    id: str
    kind: str
    protocol_version: str
    command: str
    jobs: tuple[str, ...]
    config: dict[str, Any]
    registry_path: Path
    registry_sha256: str


@dataclass(frozen=True)
class ConditionSpec:
    path: Path
    data: dict[str, Any]

    @property
    def id(self) -> str:
        return str(self.data["id"])

    @property
    def ablation_behaviors(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    str(ablation["behavior"])
                    for skill in self.data.get("skills", [])
                    for ablation in skill.get("ablations", [])
                }
            )
        )


@dataclass(frozen=True)
class SuiteRunSpec:
    case: CaseSpec
    conditions: tuple[ConditionSpec, ...]
    repetitions: int


@dataclass(frozen=True)
class SuiteSpec:
    path: Path
    data: dict[str, Any]
    runs: tuple[SuiteRunSpec, ...]
    repetitions_override: int | None = None

    @property
    def id(self) -> str:
        return str(self.data["id"])

    @property
    def judging_required(self) -> bool:
        return bool(self.data["judging"]["required"])


def load_document(path: Path) -> dict[str, Any]:
    """Load JSON or YAML without making PyYAML a core dependency.

    JSON is valid YAML 1.2, so checked-in oracle files use JSON-compatible YAML.
    Conventional YAML is also accepted when PyYAML is installed.
    """

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise EvalConfigError(f"cannot read {path}: {exc}") from exc

    try:
        value = json.loads(text)
    except json.JSONDecodeError as json_exc:
        if path.suffix.lower() == ".json":
            raise EvalConfigError(f"invalid JSON in {path}: {json_exc}") from json_exc
        try:
            import yaml  # type: ignore[import-not-found]
        except ModuleNotFoundError as exc:
            raise EvalConfigError(
                f"{path} is not JSON-compatible YAML; install PyYAML for general YAML syntax"
            ) from exc
        try:
            value = yaml.safe_load(text)
        except yaml.YAMLError as exc:  # type: ignore[attr-defined]
            raise EvalConfigError(f"invalid YAML in {path}: {exc}") from exc

    if not isinstance(value, dict):
        raise EvalConfigError(f"{path} must contain an object")
    return value


def repo_path(root: Path, relative: str, *, kind: str | None = None) -> Path:
    candidate = repo_relative_path(relative)
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise EvalConfigError(f"path escapes repository: {relative}") from exc
    if not resolved.exists():
        raise EvalConfigError(f"missing repository path: {relative}")
    if kind == "file" and not resolved.is_file():
        raise EvalConfigError(f"expected a file: {relative}")
    if kind == "dir" and not resolved.is_dir():
        raise EvalConfigError(f"expected a directory: {relative}")
    return resolved


def repo_relative_path(relative: Any) -> Path:
    if not isinstance(relative, str) or not relative:
        raise EvalConfigError("repository path must be a non-empty string")
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts or relative.startswith("-"):
        raise EvalConfigError(f"unsafe repository path: {relative}")
    return candidate


def resolve_git_revision(root: Path, revision: Any) -> str:
    if (
        not isinstance(revision, str)
        or not revision
        or revision.startswith("-")
        or any(character.isspace() for character in revision)
    ):
        raise EvalConfigError("Skill revision must be a non-empty Git revision without whitespace")
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", f"{revision}^{{commit}}"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    resolved = proc.stdout.strip()
    if proc.returncode != 0 or not re.fullmatch(r"[a-f0-9]{40}", resolved):
        raise EvalConfigError(f"cannot resolve Skill revision: {revision}")
    return resolved


def git_path_exists(root: Path, revision: str, relative: str) -> bool:
    path = repo_relative_path(relative).as_posix()
    proc = subprocess.run(
        ["git", "cat-file", "-e", f"{revision}:{path}"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0


def safe_child(root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if not relative or candidate.is_absolute() or ".." in candidate.parts:
        raise EvalConfigError(f"unsafe relative path: {relative}")
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise EvalConfigError(f"path escapes root: {relative}") from exc
    return resolved


def _unique(values: Iterable[Any], label: str) -> None:
    values = list(values)
    if len(values) != len(set(values)):
        raise EvalConfigError(f"{label} must not contain duplicates")


def load_judge_registry(
    path: Path,
    root: Path = REPO_ROOT,
) -> dict[str, JudgeAdapterSpec]:
    path = path.resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise EvalConfigError(f"judge registry escapes repository: {path}") from exc
    if not path.is_file() or path.is_symlink():
        raise EvalConfigError(f"judge registry must be a regular file: {path}")

    data = load_document(path)
    validate_document(data, "eval-judge-registry.schema.json", f"judge registry {path.name}")
    registry_sha = sha256_file(path)
    resolved: dict[str, JudgeAdapterSpec] = {}
    for adapter in data["adapters"]:
        adapter_id = adapter["id"]
        if adapter_id in resolved:
            raise EvalConfigError(f"judge registry contains duplicate adapter: {adapter_id}")
        resolved[adapter_id] = JudgeAdapterSpec(
            id=adapter_id,
            kind=adapter["kind"],
            protocol_version=adapter["protocol_version"],
            command=adapter["command"],
            jobs=tuple(adapter["jobs"]),
            config=dict(adapter.get("config", {})),
            registry_path=path,
            registry_sha256=registry_sha,
        )
    return resolved


def resolve_case_judge_adapter(
    case: CaseSpec,
    registry: dict[str, JudgeAdapterSpec],
) -> JudgeAdapterSpec | None:
    adapter_id = case.judge_adapter_id
    if adapter_id is None:
        return None
    adapter = registry.get(adapter_id)
    if adapter is None:
        raise EvalConfigError(
            f"case {case.id} references unknown judge adapter: {adapter_id}"
        )
    job = str(case.oracle["job"])
    if job not in adapter.jobs:
        raise EvalConfigError(
            f"judge adapter {adapter.id} does not support case job {job}"
        )
    return adapter


def validate_case(case_dir: Path, root: Path = REPO_ROOT) -> CaseSpec:
    case_dir = case_dir.resolve()
    try:
        case_dir.relative_to(root.resolve())
    except ValueError as exc:
        raise EvalConfigError(f"case directory escapes repository: {case_dir}") from exc
    if not case_dir.is_dir():
        raise EvalConfigError(f"missing case directory: {case_dir}")

    prompt_path = case_dir / "prompt.md"
    input_dir = case_dir / "input"
    oracle_path = case_dir / "oracle.yaml"
    for path, kind in ((prompt_path, "file"), (input_dir, "dir"), (oracle_path, "file")):
        if not path.exists() or (kind == "file" and not path.is_file()) or (kind == "dir" and not path.is_dir()):
            raise EvalConfigError(f"case {case_dir.name} is missing {path.name} ({kind})")

    prompt = prompt_path.read_text(encoding="utf-8").strip()
    if not prompt:
        raise EvalConfigError(f"{prompt_path} must not be empty")
    if re.search(r"\$[a-z][a-z0-9-]*", prompt):
        raise EvalConfigError(f"{prompt_path} must not force a Skill invocation")

    input_files = tuple(sorted(path for path in input_dir.rglob("*") if path.is_file()))
    if not input_files:
        raise EvalConfigError(f"{input_dir} must contain at least one Agent-visible input")
    for path in input_dir.rglob("*"):
        if path.is_symlink():
            raise EvalConfigError(f"case inputs must not contain symlinks: {path}")

    oracle = load_document(oracle_path)
    validate_document(oracle, "eval-case.schema.json", f"case {case_dir.name}")
    case_id = oracle["id"]
    if case_id != case_dir.name:
        raise EvalConfigError(f"case id {case_id} must match directory {case_dir.name}")
    expected = oracle["expected"]
    route = expected["route"]
    acceptable = route["acceptable_primary_skills"]
    forbidden = route.get("forbidden_primary_skills", [])
    overlap = set(acceptable) & set(forbidden)
    if overlap:
        raise EvalConfigError(f"route Skills cannot be both acceptable and forbidden: {sorted(overlap)}")

    outcomes = expected["outcomes"]
    outcome_ids: list[str] = []
    total_weight = 0.0
    for outcome in outcomes:
        outcome_ids.append(outcome["id"])
        total_weight += float(outcome["weight"])
    _unique(outcome_ids, "outcome ids")
    if abs(total_weight - 1.0) > 1e-9:
        raise EvalConfigError(f"case outcome weights must sum to 1.0, got {total_weight}")

    activation_behaviors: list[str] = []
    for activation in oracle.get("intervention_activations", []):
        behavior = str(activation["behavior"])
        activation_behaviors.append(behavior)
        for trigger_file in activation["trigger_files"]:
            relative = repo_relative_path(trigger_file)
            if not relative.parts or relative.parts[0] != "input":
                raise EvalConfigError(
                    f"case intervention {behavior} trigger must be Agent-visible under input/: "
                    f"{trigger_file}"
                )
            trigger = safe_child(case_dir, relative.as_posix())
            if not trigger.is_file() or trigger.is_symlink():
                raise EvalConfigError(
                    f"case intervention {behavior} trigger is not a regular input file: "
                    f"{trigger_file}"
                )
        unknown_outcomes = sorted(
            set(activation["observable_outcomes"]) - set(outcome_ids)
        )
        if unknown_outcomes:
            raise EvalConfigError(
                f"case intervention {behavior} references unknown outcomes: "
                f"{unknown_outcomes}"
            )
    _unique(activation_behaviors, "case intervention behavior ids")

    artifact_ids: list[str] = []
    for artifact in expected.get("artifacts", []):
        artifact_id = artifact["id"]
        artifact_ids.append(artifact_id)
        pattern = artifact["pattern"]
        if Path(pattern).is_absolute() or ".." in Path(pattern).parts:
            raise EvalConfigError(f"artifact expectation {artifact_id}.pattern is unsafe")
    _unique(artifact_ids, "artifact expectation ids")
    return CaseSpec(case_dir, prompt_path, input_dir, input_files, oracle_path, oracle)


def validate_condition(path: Path, root: Path = REPO_ROOT) -> ConditionSpec:
    data = load_document(path)
    validate_document(data, "eval-condition.schema.json", f"condition {path.name}")
    condition_id = data["id"]
    if path.stem != condition_id:
        raise EvalConfigError(f"condition id {condition_id} must match filename {path.stem}")
    kind = data["kind"]
    skills = data["skills"]

    names: list[str] = []
    ablation_count = 0
    for skill in skills:
        name = skill["name"]
        names.append(name)
        skill_path = repo_relative_path(skill["path"]).as_posix()
        revision = skill.get("revision")
        resolved_revision: str | None = None
        source: Path | None = None
        if revision is not None:
            resolved_revision = resolve_git_revision(root, revision)
            if not git_path_exists(root, resolved_revision, f"{skill_path}/SKILL.md"):
                raise EvalConfigError(
                    f"condition skill {name} is missing SKILL.md at revision {revision}"
                )
        else:
            source = repo_path(root, skill_path, kind="dir")
            if not (source / "SKILL.md").is_file():
                raise EvalConfigError(f"condition skill {name} is missing SKILL.md")
        ablations = skill.get("ablations", [])
        if kind == "skill-enabled" and ablations:
            raise EvalConfigError("skill-enabled conditions must not contain ablations")
        for ablation in ablations:
            ablation_path = repo_relative_path(ablation["path"]).as_posix()
            if resolved_revision:
                target_exists = git_path_exists(
                    root,
                    resolved_revision,
                    f"{skill_path}/{ablation_path}",
                )
                target_label = f"{resolved_revision}:{skill_path}/{ablation_path}"
            else:
                assert source is not None
                target = safe_child(source, ablation_path)
                target_exists = target.exists()
                target_label = str(target)
            if not target_exists:
                raise EvalConfigError(f"ablation target does not exist: {target_label}")
            if ablation["op"] == "replace":
                replacement = ablation.get("replacement")
                if not replacement:
                    raise EvalConfigError(f"replace ablation for {name} needs replacement")
                repo_path(root, replacement)
            ablation_count += 1
    _unique(names, f"condition {condition_id} skill names")
    if kind == "ablation" and ablation_count == 0:
        raise EvalConfigError("ablation conditions must declare at least one ablation")
    return ConditionSpec(path.resolve(), data)


def validate_suite(path: Path, root: Path = REPO_ROOT) -> SuiteSpec:
    data = load_document(path)
    validate_document(data, "eval-suite.schema.json", f"suite {path.name}")
    suite_id = data["id"]
    if path.stem != suite_id:
        raise EvalConfigError(f"suite id {suite_id} must match filename {path.stem}")
    default_repetitions = data["defaults"]["repetitions"]
    control_id = data["comparison"]["control_condition"]

    resolved_runs: list[SuiteRunSpec] = []
    seen_cases: set[str] = set()
    for item in data["runs"]:
        case_ref = item["case"]
        case_dir = repo_path(root, case_ref, kind="dir")
        if case_ref in seen_cases:
            raise EvalConfigError(f"suite contains duplicate case ref: {case_ref}")
        seen_cases.add(case_ref)
        case = validate_case(case_dir, root)

        condition_refs = item["conditions"]
        conditions = tuple(
            validate_condition(repo_path(root, ref, kind="file"), root) for ref in condition_refs
        )
        condition_ids = [condition.id for condition in conditions]
        _unique(condition_ids, f"suite run {case.id} condition ids")
        if control_id not in condition_ids:
            raise EvalConfigError(f"suite run {case.id} does not include control {control_id}")
        activated_behaviors = set(case.intervention_activations)
        for condition in conditions:
            missing_behaviors = sorted(
                set(condition.ablation_behaviors) - activated_behaviors
            )
            if missing_behaviors:
                raise EvalConfigError(
                    f"suite run {case.id} condition {condition.id} has unactivated "
                    f"ablation behaviors: {missing_behaviors}"
                )
        repetitions = item.get("repetitions", default_repetitions)
        resolved_runs.append(SuiteRunSpec(case, conditions, repetitions))
    return SuiteSpec(path.resolve(), data, tuple(resolved_runs))


def override_suite_repetitions(
    suite: SuiteSpec,
    repetitions: int | None,
) -> SuiteSpec:
    if repetitions is None:
        return suite
    if (
        not isinstance(repetitions, int)
        or isinstance(repetitions, bool)
        or not 1 <= repetitions <= 100
    ):
        raise EvalConfigError("repetitions override must be an integer from 1 to 100")
    runs = tuple(
        SuiteRunSpec(item.case, item.conditions, repetitions) for item in suite.runs
    )
    return SuiteSpec(suite.path, suite.data, runs, repetitions)


def validate_result(data: dict[str, Any]) -> None:
    validate_document(data, "eval-result.schema.json", "result")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_paths(paths: Iterable[Path], base: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted((path.resolve() for path in paths), key=lambda item: item.as_posix()):
        if path.is_symlink() or not path.is_file():
            raise EvalConfigError(f"cannot hash non-regular file: {path}")
        relative = path.relative_to(base.resolve()).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(sha256_file(path)))
    return digest.hexdigest()


def sha256_tree(root: Path) -> str:
    files = [path for path in root.rglob("*") if path.is_file()]
    return sha256_paths(files, root)


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()
