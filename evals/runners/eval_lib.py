"""Shared loading, validation, hashing, and path-safety helpers for evals."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
EVIDENCE_SOURCES = {"response", "artifact", "trace", "route", "usage"}
FAILURE_TAGS = {
    "route-error",
    "task-understanding",
    "factuality",
    "missing-artifact",
    "artifact-integrity",
    "visual-quality",
    "image-relevance",
    "image-distortion",
    "process-compliance",
    "verification",
    "privacy",
    "efficiency",
    "executor-error",
    "judge-error",
    "protocol-error",
}


class EvalConfigError(ValueError):
    """Raised when an evaluation definition violates the repository contract."""


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

    @property
    def id(self) -> str:
        return str(self.data["id"])


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


def _require_slug(value: Any, label: str) -> str:
    if not isinstance(value, str) or not SLUG_RE.fullmatch(value):
        raise EvalConfigError(f"{label} must be a lowercase hyphenated slug")
    return value


def _require_list(value: Any, label: str, *, nonempty: bool = False) -> list[Any]:
    if not isinstance(value, list) or (nonempty and not value):
        suffix = " non-empty" if nonempty else ""
        raise EvalConfigError(f"{label} must be a{suffix} list")
    return value


def _unique(values: Iterable[Any], label: str) -> None:
    values = list(values)
    if len(values) != len(set(values)):
        raise EvalConfigError(f"{label} must not contain duplicates")


def _validate_schema_version(data: dict[str, Any], label: str) -> None:
    if data.get("schema_version") != "1.0":
        raise EvalConfigError(f"{label}.schema_version must be 1.0")


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
    _validate_schema_version(data, f"judge registry {path.name}")
    unknown_registry_fields = set(data) - {"schema_version", "adapters"}
    if unknown_registry_fields:
        raise EvalConfigError(
            f"judge registry contains unknown fields: {sorted(unknown_registry_fields)}"
        )
    adapters = _require_list(data.get("adapters"), "judge registry adapters", nonempty=True)
    registry_sha = sha256_file(path)
    resolved: dict[str, JudgeAdapterSpec] = {}
    for index, adapter in enumerate(adapters):
        if not isinstance(adapter, dict):
            raise EvalConfigError(f"judge adapter {index} must be an object")
        unknown_adapter_fields = set(adapter) - {
            "id",
            "kind",
            "protocol_version",
            "command",
            "jobs",
            "description",
            "config",
        }
        if unknown_adapter_fields:
            raise EvalConfigError(
                f"judge adapter {index} contains unknown fields: "
                f"{sorted(unknown_adapter_fields)}"
            )
        adapter_id = _require_slug(adapter.get("id"), f"judge adapter {index}.id")
        if adapter_id in resolved:
            raise EvalConfigError(f"judge registry contains duplicate adapter: {adapter_id}")
        kind = adapter.get("kind")
        if kind not in {"deterministic", "model", "hybrid"}:
            raise EvalConfigError(f"judge adapter {adapter_id}.kind is invalid")
        protocol_version = adapter.get("protocol_version")
        if protocol_version != "1.0":
            raise EvalConfigError(
                f"judge adapter {adapter_id}.protocol_version must be 1.0"
            )
        command = adapter.get("command")
        if not isinstance(command, str) or not command.strip():
            raise EvalConfigError(f"judge adapter {adapter_id}.command must be non-empty")
        jobs = _require_list(adapter.get("jobs"), f"judge adapter {adapter_id}.jobs", nonempty=True)
        for job in jobs:
            _require_slug(job, f"judge adapter {adapter_id} job")
        _unique(jobs, f"judge adapter {adapter_id}.jobs")
        config = adapter.get("config", {})
        if not isinstance(config, dict):
            raise EvalConfigError(f"judge adapter {adapter_id}.config must be an object")
        description = adapter.get("description")
        if description is not None and not isinstance(description, str):
            raise EvalConfigError(
                f"judge adapter {adapter_id}.description must be a string"
            )
        resolved[adapter_id] = JudgeAdapterSpec(
            id=adapter_id,
            kind=str(kind),
            protocol_version=str(protocol_version),
            command=command,
            jobs=tuple(str(job) for job in jobs),
            config=dict(config),
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
    _validate_schema_version(oracle, f"case {case_dir.name}")
    case_id = _require_slug(oracle.get("id"), "case.id")
    if case_id != case_dir.name:
        raise EvalConfigError(f"case id {case_id} must match directory {case_dir.name}")
    for key in ("title", "job"):
        if not isinstance(oracle.get(key), str) or not oracle[key]:
            raise EvalConfigError(f"case.{key} must be a non-empty string")
    _require_slug(oracle["job"], "case.job")
    if oracle.get("risk_level") not in {None, "low", "medium", "high"}:
        raise EvalConfigError("case.risk_level must be low, medium, or high")
    tags = _require_list(oracle.get("tags"), "case.tags")
    for tag in tags:
        _require_slug(tag, "case tag")
    _unique(tags, "case.tags")

    evaluation = oracle.get("evaluation")
    if evaluation is not None:
        if not isinstance(evaluation, dict):
            raise EvalConfigError("case.evaluation must be an object")
        unknown = set(evaluation) - {"adapter", "config"}
        if unknown:
            raise EvalConfigError(
                f"case.evaluation contains unknown fields: {sorted(unknown)}"
            )
        _require_slug(evaluation.get("adapter"), "case.evaluation.adapter")
        config = evaluation.get("config", {})
        if not isinstance(config, dict):
            raise EvalConfigError("case.evaluation.config must be an object")

    expected = oracle.get("expected")
    if not isinstance(expected, dict):
        raise EvalConfigError("case.expected must be an object")
    route = expected.get("route")
    if not isinstance(route, dict):
        raise EvalConfigError("case.expected.route must be an object")
    acceptable = _require_list(
        route.get("acceptable_primary_skills"),
        "case.expected.route.acceptable_primary_skills",
        nonempty=True,
    )
    if not all(isinstance(item, str) and item for item in acceptable):
        raise EvalConfigError("acceptable_primary_skills must contain non-empty strings")
    _unique(acceptable, "acceptable_primary_skills")
    forbidden = _require_list(
        route.get("forbidden_primary_skills", []),
        "case.expected.route.forbidden_primary_skills",
    )
    if not all(isinstance(item, str) and item for item in forbidden):
        raise EvalConfigError("forbidden_primary_skills must contain non-empty strings")
    _unique(forbidden, "forbidden_primary_skills")
    overlap = set(acceptable) & set(forbidden)
    if overlap:
        raise EvalConfigError(f"route Skills cannot be both acceptable and forbidden: {sorted(overlap)}")

    outcomes = _require_list(expected.get("outcomes"), "case.expected.outcomes", nonempty=True)
    outcome_ids: list[str] = []
    total_weight = 0.0
    for index, outcome in enumerate(outcomes):
        if not isinstance(outcome, dict):
            raise EvalConfigError(f"outcome {index} must be an object")
        outcome_id = _require_slug(outcome.get("id"), f"outcome {index}.id")
        outcome_ids.append(outcome_id)
        if not isinstance(outcome.get("description"), str) or not outcome["description"]:
            raise EvalConfigError(f"outcome {outcome_id}.description must be non-empty")
        weight = outcome.get("weight")
        if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not 0 < weight <= 1:
            raise EvalConfigError(f"outcome {outcome_id}.weight must be in (0, 1]")
        total_weight += float(weight)
        if not isinstance(outcome.get("critical"), bool):
            raise EvalConfigError(f"outcome {outcome_id}.critical must be boolean")
        evidence = _require_list(
            outcome.get("evidence_sources"),
            f"outcome {outcome_id}.evidence_sources",
            nonempty=True,
        )
        if not set(evidence).issubset(EVIDENCE_SOURCES):
            raise EvalConfigError(f"outcome {outcome_id} has an unknown evidence source")
        _unique(evidence, f"outcome {outcome_id}.evidence_sources")
    _unique(outcome_ids, "outcome ids")
    if abs(total_weight - 1.0) > 1e-9:
        raise EvalConfigError(f"case outcome weights must sum to 1.0, got {total_weight}")

    artifact_ids: list[str] = []
    for index, artifact in enumerate(
        _require_list(expected.get("artifacts", []), "case.expected.artifacts")
    ):
        if not isinstance(artifact, dict):
            raise EvalConfigError(f"artifact expectation {index} must be an object")
        artifact_id = _require_slug(artifact.get("id"), f"artifact expectation {index}.id")
        artifact_ids.append(artifact_id)
        pattern = artifact.get("pattern")
        if not isinstance(pattern, str) or not pattern or Path(pattern).is_absolute() or ".." in Path(pattern).parts:
            raise EvalConfigError(f"artifact expectation {artifact_id}.pattern is unsafe")
        if not isinstance(artifact.get("required"), bool):
            raise EvalConfigError(f"artifact expectation {artifact_id}.required must be boolean")
    _unique(artifact_ids, "artifact expectation ids")

    judges = _require_list(oracle.get("judges"), "case.judges", nonempty=True)
    judge_ids: list[str] = []
    judged_criteria: set[str] = set()
    for index, judge in enumerate(judges):
        if not isinstance(judge, dict):
            raise EvalConfigError(f"judge {index} must be an object")
        judge_id = _require_slug(judge.get("id"), f"judge {index}.id")
        judge_ids.append(judge_id)
        if judge.get("type") not in {"deterministic", "rubric", "model", "human"}:
            raise EvalConfigError(f"judge {judge_id}.type is invalid")
        criteria = _require_list(judge.get("criteria"), f"judge {judge_id}.criteria", nonempty=True)
        unknown = set(criteria) - set(outcome_ids)
        if unknown:
            raise EvalConfigError(f"judge {judge_id} references unknown criteria: {sorted(unknown)}")
        _unique(criteria, f"judge {judge_id}.criteria")
        judged_criteria.update(criteria)
    _unique(judge_ids, "judge ids")
    if judged_criteria != set(outcome_ids):
        missing = sorted(set(outcome_ids) - judged_criteria)
        raise EvalConfigError(f"case outcomes are not assigned to a judge: {missing}")

    taxonomy = _require_list(oracle.get("failure_taxonomy", []), "case.failure_taxonomy")
    unknown_tags = set(taxonomy) - FAILURE_TAGS
    if unknown_tags:
        raise EvalConfigError(f"case has unknown failure taxonomy tags: {sorted(unknown_tags)}")
    _unique(taxonomy, "case.failure_taxonomy")
    return CaseSpec(case_dir, prompt_path, input_dir, input_files, oracle_path, oracle)


def validate_condition(path: Path, root: Path = REPO_ROOT) -> ConditionSpec:
    data = load_document(path)
    _validate_schema_version(data, f"condition {path.name}")
    condition_id = _require_slug(data.get("id"), "condition.id")
    if path.stem != condition_id:
        raise EvalConfigError(f"condition id {condition_id} must match filename {path.stem}")
    if not isinstance(data.get("label"), str) or not data["label"]:
        raise EvalConfigError("condition.label must be a non-empty string")
    kind = data.get("kind")
    if kind not in {"baseline", "skill-enabled", "ablation"}:
        raise EvalConfigError(f"condition {condition_id}.kind is invalid")
    skills = _require_list(data.get("skills"), f"condition {condition_id}.skills")
    if kind == "baseline" and skills:
        raise EvalConfigError("baseline conditions must not expose Skills")
    if kind != "baseline" and not skills:
        raise EvalConfigError(f"{kind} conditions must expose at least one Skill")

    names: list[str] = []
    ablation_count = 0
    for index, skill in enumerate(skills):
        if not isinstance(skill, dict):
            raise EvalConfigError(f"condition skill {index} must be an object")
        name = _require_slug(skill.get("name"), f"condition skill {index}.name")
        names.append(name)
        skill_path = repo_relative_path(skill.get("path")).as_posix()
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
        ablations = _require_list(skill.get("ablations", []), f"skill {name}.ablations")
        if kind == "skill-enabled" and ablations:
            raise EvalConfigError("skill-enabled conditions must not contain ablations")
        for ablation in ablations:
            if not isinstance(ablation, dict) or ablation.get("op") not in {"remove", "replace"}:
                raise EvalConfigError(f"skill {name} has an invalid ablation")
            ablation_path = repo_relative_path(ablation.get("path", "")).as_posix()
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
    _validate_schema_version(data, f"suite {path.name}")
    suite_id = _require_slug(data.get("id"), "suite.id")
    if path.stem != suite_id:
        raise EvalConfigError(f"suite id {suite_id} must match filename {path.stem}")
    if not isinstance(data.get("title"), str) or not data["title"]:
        raise EvalConfigError("suite.title must be a non-empty string")
    defaults = data.get("defaults")
    if not isinstance(defaults, dict):
        raise EvalConfigError("suite.defaults must be an object")
    default_repetitions = defaults.get("repetitions")
    timeout = defaults.get("timeout_seconds")
    if not isinstance(default_repetitions, int) or not 1 <= default_repetitions <= 100:
        raise EvalConfigError("suite.defaults.repetitions must be in [1, 100]")
    if not isinstance(timeout, int) or not 1 <= timeout <= 86400:
        raise EvalConfigError("suite.defaults.timeout_seconds must be in [1, 86400]")

    comparison = data.get("comparison")
    if not isinstance(comparison, dict):
        raise EvalConfigError("suite.comparison must be an object")
    control_id = _require_slug(comparison.get("control_condition"), "suite control condition")
    metrics = _require_list(comparison.get("metrics"), "suite comparison metrics", nonempty=True)
    allowed_metrics = {"score", "input_tokens", "output_tokens", "total_tokens", "duration_ms"}
    if not set(metrics).issubset(allowed_metrics):
        raise EvalConfigError("suite comparison contains an unknown metric")
    _unique(metrics, "suite comparison metrics")

    run_items = _require_list(data.get("runs"), "suite.runs", nonempty=True)
    resolved_runs: list[SuiteRunSpec] = []
    seen_cases: set[str] = set()
    for index, item in enumerate(run_items):
        if not isinstance(item, dict):
            raise EvalConfigError(f"suite run {index} must be an object")
        case_ref = item.get("case")
        case_dir = repo_path(root, case_ref, kind="dir")
        if case_ref in seen_cases:
            raise EvalConfigError(f"suite contains duplicate case ref: {case_ref}")
        seen_cases.add(case_ref)
        case = validate_case(case_dir, root)

        condition_refs = _require_list(
            item.get("conditions"), f"suite run {case.id}.conditions", nonempty=True
        )
        if len(condition_refs) < 2:
            raise EvalConfigError(f"suite run {case.id} needs at least two conditions")
        _unique(condition_refs, f"suite run {case.id}.conditions")
        conditions = tuple(
            validate_condition(repo_path(root, ref, kind="file"), root) for ref in condition_refs
        )
        condition_ids = [condition.id for condition in conditions]
        _unique(condition_ids, f"suite run {case.id} condition ids")
        if control_id not in condition_ids:
            raise EvalConfigError(f"suite run {case.id} does not include control {control_id}")
        repetitions = item.get("repetitions", default_repetitions)
        if not isinstance(repetitions, int) or not 1 <= repetitions <= 100:
            raise EvalConfigError(f"suite run {case.id}.repetitions must be in [1, 100]")
        resolved_runs.append(SuiteRunSpec(case, conditions, repetitions))
    return SuiteSpec(path.resolve(), data, tuple(resolved_runs))


def validate_result(data: dict[str, Any]) -> None:
    required = {
        "schema_version",
        "run_id",
        "suite_id",
        "case_id",
        "condition",
        "repetition",
        "status",
        "timestamps",
        "executor",
        "route",
        "usage",
        "artifacts",
        "judging",
        "failure",
        "provenance",
    }
    missing = required - set(data)
    if missing:
        raise EvalConfigError(f"result is missing fields: {sorted(missing)}")
    _validate_schema_version(data, "result")
    _require_slug(data["suite_id"], "result.suite_id")
    _require_slug(data["case_id"], "result.case_id")
    if data["status"] not in {"materialized", "completed", "failed"}:
        raise EvalConfigError("result.status is invalid")
    condition = data["condition"]
    if not isinstance(condition, dict):
        raise EvalConfigError("result.condition must be an object")
    _require_slug(condition.get("id"), "result.condition.id")
    if condition.get("kind") not in {"baseline", "skill-enabled", "ablation"}:
        raise EvalConfigError("result.condition.kind is invalid")
    for skill in _require_list(condition.get("skills"), "result.condition.skills"):
        if not isinstance(skill, dict):
            raise EvalConfigError("result condition Skill must be an object")
        for key in ("source_sha256", "materialized_sha256"):
            if not SHA256_RE.fullmatch(str(skill.get(key, ""))):
                raise EvalConfigError(f"result skill {key} is invalid")
        resolved_revision = skill.get("resolved_revision")
        if resolved_revision is not None and not re.fullmatch(r"[a-f0-9]{40}", str(resolved_revision)):
            raise EvalConfigError("result skill resolved_revision is invalid")
    provenance = data["provenance"]
    if not isinstance(provenance, dict):
        raise EvalConfigError("result.provenance must be an object")
    for key in ("case_sha256", "oracle_sha256", "condition_sha256"):
        if not SHA256_RE.fullmatch(str(provenance.get(key, ""))):
            raise EvalConfigError(f"result.provenance.{key} is invalid")
    lineage = data.get("lineage")
    if lineage is not None:
        if not isinstance(lineage, dict):
            raise EvalConfigError("result.lineage must be an object")
        if not isinstance(lineage.get("source_run_id"), str) or not lineage["source_run_id"]:
            raise EvalConfigError("result.lineage.source_run_id is invalid")
        if not SHA256_RE.fullmatch(str(lineage.get("source_result_sha256", ""))):
            raise EvalConfigError("result.lineage.source_result_sha256 is invalid")
        if lineage.get("action") not in {"reused-executor-output", "reran-executor"}:
            raise EvalConfigError("result.lineage.action is invalid")
        if not isinstance(lineage.get("resumed_at"), str) or not lineage["resumed_at"]:
            raise EvalConfigError("result.lineage.resumed_at is invalid")
    judging = data["judging"]
    if not isinstance(judging, dict) or judging.get("status") not in {
        "pending",
        "partial",
        "completed",
        "failed",
    }:
        raise EvalConfigError("result.judging.status is invalid")
    score = judging.get("overall_score")
    if score is not None and (isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= score <= 1):
        raise EvalConfigError("result.judging.overall_score must be null or in [0, 1]")
    passed = judging.get("passed")
    if passed is not None and not isinstance(passed, bool):
        raise EvalConfigError("result.judging.passed must be boolean or null")
    critical_failures = judging.get("critical_failures")
    if not isinstance(critical_failures, list) or not all(
        isinstance(item, str) and SLUG_RE.fullmatch(item) for item in critical_failures
    ):
        raise EvalConfigError("result.judging.critical_failures must be a list of slugs")
    judge = data.get("judge")
    if judge is not None:
        if not isinstance(judge, dict):
            raise EvalConfigError("result.judge must be an object")
        adapter_id = judge.get("adapter_id")
        if adapter_id is not None:
            _require_slug(adapter_id, "result.judge.adapter_id")
        if judge.get("kind") not in {
            None,
            "deterministic",
            "model",
            "hybrid",
            "override",
        }:
            raise EvalConfigError("result.judge.kind is invalid")
        protocol_version = judge.get("protocol_version")
        if protocol_version not in {None, "1.0"}:
            raise EvalConfigError("result.judge.protocol_version is invalid")
        command = judge.get("command")
        if not isinstance(command, list) or not all(isinstance(item, str) for item in command):
            raise EvalConfigError("result.judge.command must be a list of strings")
        config = judge.get("config")
        if not isinstance(config, dict):
            raise EvalConfigError("result.judge.config must be an object")
        for key in ("registry_sha256", "evidence_manifest_sha256"):
            value = judge.get(key)
            if value is not None and not SHA256_RE.fullmatch(str(value)):
                raise EvalConfigError(f"result.judge.{key} is invalid")


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
