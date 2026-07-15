#!/usr/bin/env python3
"""Judge tabular-data analyses with deterministic truth and blind model review."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from decimal import Decimal, InvalidOperation
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
LEDGER_COLUMNS = [
    "id",
    "claim",
    "computation",
    "evidence",
    "verification",
    "caveat",
    "status",
]
LEDGER_STATUSES = {"verified", "refuted", "needs_followup"}
NUMBER_RE = re.compile(r"(?<![A-Za-z0-9_])[-+]?[$]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?")


class DataJudgeError(RuntimeError):
    """Raised when data-analysis evidence cannot be produced safely."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DataJudgeError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise DataJudgeError(f"{path} must contain an object")
    return value


def environment() -> dict[str, Path]:
    missing = sorted(name for name in REQUIRED_ENV if not os.environ.get(name))
    if missing:
        raise DataJudgeError(f"missing judge environment variables: {', '.join(missing)}")
    return {name: Path(os.environ[name]).resolve() for name in REQUIRED_ENV}


def judge_config() -> dict[str, Any]:
    try:
        value = json.loads(os.environ.get("EVAL_JUDGE_CONFIG", "{}"))
    except json.JSONDecodeError as exc:
        raise DataJudgeError(f"invalid EVAL_JUDGE_CONFIG: {exc}") from exc
    if not isinstance(value, dict):
        raise DataJudgeError("EVAL_JUDGE_CONFIG must contain an object")
    required = {"artifacts", "metric_contract", "join_contract"}
    missing = sorted(required - set(value))
    unknown = sorted(set(value) - required)
    if missing or unknown:
        raise DataJudgeError(
            f"data-analysis config mismatch; missing={missing}, unknown={unknown}"
        )
    return value


def read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fields = reader.fieldnames or []
            rows = [dict(row) for row in reader]
    except (OSError, csv.Error) as exc:
        raise DataJudgeError(f"cannot read CSV {path}: {exc}") from exc
    if not fields:
        raise DataJudgeError(f"CSV has no header: {path}")
    return fields, rows


def require_columns(fields: list[str], required: set[str], label: str) -> None:
    missing = sorted(required - set(fields))
    if missing:
        raise DataJudgeError(f"{label} is missing columns: {', '.join(missing)}")


def require_string_fields(value: dict[str, Any], fields: set[str], label: str) -> None:
    invalid = sorted(
        field
        for field in fields
        if not isinstance(value.get(field), str) or not value[field]
    )
    if invalid:
        raise DataJudgeError(f"{label} has invalid string fields: {', '.join(invalid)}")


def decimal_value(value: Any, label: str) -> Decimal:
    try:
        return Decimal(str(value).replace(",", "").replace("$", "").strip())
    except (InvalidOperation, AttributeError) as exc:
        raise DataJudgeError(f"{label} is not numeric: {value!r}") from exc


def filtered_rows(
    rows: list[dict[str, str]],
    filter_spec: dict[str, Any],
) -> list[dict[str, str]]:
    if set(filter_spec) != {"column", "equals"}:
        raise DataJudgeError("metric filter must contain only column and equals")
    column = filter_spec["column"]
    expected = str(filter_spec["equals"])
    return [row for row in rows if row.get(column) == expected]


def compute_metric(
    metric: dict[str, Any],
    rows: list[dict[str, str]],
) -> Decimal:
    required = {"id", "aggregation", "expected", "tolerance"}
    unknown = set(metric) - (required | {"column"})
    if required - set(metric) or unknown:
        raise DataJudgeError(f"invalid metric contract: {metric}")
    aggregation = metric["aggregation"]
    if aggregation == "count":
        if "column" in metric:
            raise DataJudgeError(f"count metric {metric['id']} must not declare column")
        return Decimal(len(rows))
    column = metric.get("column")
    if not isinstance(column, str) or not column:
        raise DataJudgeError(f"metric {metric['id']} requires a column")
    values = [decimal_value(row.get(column), f"{metric['id']}.{column}") for row in rows]
    if aggregation == "sum":
        return sum(values, Decimal(0))
    if aggregation == "mean":
        if not values:
            raise DataJudgeError(f"metric {metric['id']} cannot average an empty population")
        return sum(values, Decimal(0)) / Decimal(len(values))
    raise DataJudgeError(f"unsupported metric aggregation: {aggregation}")


def build_source_truth(config: dict[str, Any], payload_dir: Path) -> dict[str, Any]:
    metric_contract = config["metric_contract"]
    required_metric_keys = {"source", "filter", "grain_key", "metrics"}
    if not isinstance(metric_contract, dict) or set(metric_contract) != required_metric_keys:
        raise DataJudgeError("metric_contract has an invalid shape")
    if not isinstance(metric_contract["metrics"], list) or not metric_contract["metrics"]:
        raise DataJudgeError("metric_contract.metrics must be a non-empty list")
    require_string_fields(metric_contract, {"source", "grain_key"}, "metric_contract")
    source_path = safe_child(payload_dir, metric_contract["source"])
    fields, rows = read_csv_rows(source_path)
    filter_spec = metric_contract["filter"]
    if not isinstance(filter_spec, dict):
        raise DataJudgeError("metric_contract.filter must be an object")
    if set(filter_spec) != {"column", "equals"}:
        raise DataJudgeError("metric filter must contain only column and equals")
    require_string_fields(filter_spec, {"column", "equals"}, "metric filter")
    required_columns = {metric_contract["grain_key"], filter_spec.get("column")}
    for metric in metric_contract["metrics"]:
        if isinstance(metric, dict) and metric.get("column"):
            required_columns.add(metric["column"])
    require_columns(fields, {str(item) for item in required_columns}, "metric source")
    selected = filtered_rows(rows, filter_spec)

    metric_results: list[dict[str, Any]] = []
    metric_ids: list[str] = []
    for metric in metric_contract["metrics"]:
        if not isinstance(metric, dict):
            raise DataJudgeError("metric_contract.metrics must contain objects")
        metric_id = metric.get("id")
        if not isinstance(metric_id, str) or not metric_id:
            raise DataJudgeError("metric contract id must be non-empty")
        metric_ids.append(metric_id)
        computed = compute_metric(metric, selected)
        expected = decimal_value(metric["expected"], f"metric {metric_id}.expected")
        tolerance = decimal_value(metric["tolerance"], f"metric {metric_id}.tolerance")
        metric_results.append(
            {
                "id": metric_id,
                "aggregation": metric["aggregation"],
                "column": metric.get("column"),
                "computed": format(computed, "f"),
                "expected": format(expected, "f"),
                "tolerance": format(tolerance, "f"),
                "contract_matches_source": abs(computed - expected) <= tolerance,
            }
        )
    if len(metric_ids) != len(set(metric_ids)):
        raise DataJudgeError("metric contract ids must be unique")

    join_contract = config["join_contract"]
    required_join_keys = {"left", "right", "left_key", "right_key", "left_measure"}
    if not isinstance(join_contract, dict) or set(join_contract) != required_join_keys:
        raise DataJudgeError("join_contract has an invalid shape")
    require_string_fields(join_contract, required_join_keys, "join_contract")
    left_path = safe_child(payload_dir, join_contract["left"])
    right_path = safe_child(payload_dir, join_contract["right"])
    left_fields, left_rows = read_csv_rows(left_path)
    right_fields, right_rows = read_csv_rows(right_path)
    require_columns(
        left_fields,
        {join_contract["left_key"], join_contract["left_measure"], filter_spec["column"]},
        "join left source",
    )
    require_columns(right_fields, {join_contract["right_key"]}, "join right source")
    left_counts = Counter(row[join_contract["left_key"]] for row in left_rows)
    right_counts = Counter(row[join_contract["right_key"]] for row in right_rows)
    inner_rows = sum(right_counts.get(key, 0) * count for key, count in left_counts.items())
    selected_left = filtered_rows(left_rows, filter_spec)
    correct_measure = sum(
        (decimal_value(row[join_contract["left_measure"]], "left measure") for row in selected_left),
        Decimal(0),
    )
    naive_join_measure = sum(
        (
            decimal_value(row[join_contract["left_measure"]], "left measure")
            * Decimal(right_counts.get(row[join_contract["left_key"]], 0))
            for row in selected_left
        ),
        Decimal(0),
    )
    join_ratio = Decimal(inner_rows) / Decimal(len(left_rows)) if left_rows else Decimal(0)
    return {
        "metric_source": {
            "path": metric_contract["source"],
            "rows": len(rows),
            "filtered_rows": len(selected),
            "filter": filter_spec,
            "grain_key": metric_contract["grain_key"],
            "grain_unique": len({row[metric_contract['grain_key']] for row in rows}) == len(rows),
        },
        "metrics": metric_results,
        "join": {
            "left": join_contract["left"],
            "right": join_contract["right"],
            "left_rows": len(left_rows),
            "right_rows": len(right_rows),
            "left_distinct_keys": len(left_counts),
            "right_distinct_keys": len(right_counts),
            "left_unique": all(count == 1 for count in left_counts.values()),
            "right_unique": all(count == 1 for count in right_counts.values()),
            "inner_rows": inner_rows,
            "join_to_left_row_ratio": format(join_ratio, "f"),
            "fanout_risk": inner_rows > len(left_rows),
            "max_right_fanout": max(right_counts.values(), default=0),
            "filtered_left_measure": format(correct_measure, "f"),
            "naive_joined_left_measure": format(naive_join_measure, "f"),
        },
    }


def extract_numbers(text: str) -> list[Decimal]:
    values: list[Decimal] = []
    for match in NUMBER_RE.finditer(text):
        try:
            values.append(decimal_value(match.group(0), "artifact number"))
        except DataJudgeError:
            continue
    return values


def audit_ledger(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        return {
            "exists": False,
            "valid": False,
            "fields": [],
            "rows": 0,
            "errors": ["findings.tsv is missing"],
            "warnings": [],
            "substantive_verification_rows": 0,
        }
    errors: list[str] = []
    warnings: list[str] = []
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            fields = reader.fieldnames or []
            rows = list(reader)
    except (OSError, csv.Error) as exc:
        return {
            "exists": True,
            "valid": False,
            "fields": [],
            "rows": 0,
            "errors": [str(exc)],
            "warnings": [],
            "substantive_verification_rows": 0,
        }
    missing = [field for field in LEDGER_COLUMNS if field not in fields]
    if missing:
        errors.append(f"missing columns: {', '.join(missing)}")
    if not rows:
        errors.append("ledger has no findings")
    substantive_verification_rows = 0
    for index, row in enumerate(rows, start=2):
        row_id = row.get("id") or f"line-{index}"
        for field in LEDGER_COLUMNS:
            if field in fields and not (row.get(field) or "").strip():
                errors.append(f"{row_id}: empty {field}")
        status = (row.get("status") or "").strip()
        if status and status not in LEDGER_STATUSES:
            errors.append(f"{row_id}: invalid status {status}")
        if status == "verified":
            evidence = (row.get("evidence") or "").strip()
            verification = (row.get("verification") or "").strip()
            if len(evidence) < 10:
                warnings.append(f"{row_id}: thin evidence")
            if len(verification) < 10:
                warnings.append(f"{row_id}: thin verification")
            if len(evidence) >= 10 and len(verification) >= 10:
                substantive_verification_rows += 1
    return {
        "exists": True,
        "valid": not errors,
        "fields": fields,
        "rows": len(rows),
        "errors": errors,
        "warnings": warnings,
        "substantive_verification_rows": substantive_verification_rows,
    }


def artifact_path(output_dir: Path, relative: str) -> Path:
    path = safe_child(output_dir, relative)
    if path.is_symlink():
        raise DataJudgeError(f"artifact must not be a symlink: {relative}")
    return path


def audit_artifacts(
    config: dict[str, Any],
    result: dict[str, Any],
    output_dir: Path,
    source_truth: dict[str, Any],
) -> dict[str, Any]:
    artifact_config = config["artifacts"]
    if not isinstance(artifact_config, dict) or set(artifact_config) != {"analysis", "findings"}:
        raise DataJudgeError("artifacts config must contain only analysis and findings")
    analysis_relative = artifact_config["analysis"]
    findings_relative = artifact_config["findings"]
    if not all(isinstance(item, str) and item for item in (analysis_relative, findings_relative)):
        raise DataJudgeError("artifact paths must be non-empty strings")
    analysis_path = artifact_path(output_dir, analysis_relative)
    findings_path = artifact_path(output_dir, findings_relative)
    response_path = artifact_path(output_dir, "response.md")
    analysis_text = (
        analysis_path.read_text(encoding="utf-8", errors="replace")
        if analysis_path.is_file()
        else ""
    )
    findings_text = (
        findings_path.read_text(encoding="utf-8", errors="replace")
        if findings_path.is_file()
        else ""
    )
    response_text = (
        response_path.read_text(encoding="utf-8", errors="replace")
        if response_path.is_file()
        else ""
    )
    combined = "\n".join((analysis_text, findings_text, response_text))
    normalized = combined.lower()
    numbers = extract_numbers(combined)
    metric_mentions: dict[str, bool] = {}
    for metric in source_truth["metrics"]:
        expected = decimal_value(metric["expected"], f"metric {metric['id']}.expected")
        tolerance = decimal_value(metric["tolerance"], f"metric {metric['id']}.tolerance")
        metric_mentions[metric["id"]] = any(abs(value - expected) <= tolerance for value in numbers)
    ledger = audit_ledger(findings_path)
    filter_spec = config["metric_contract"]["filter"]
    filter_column = str(filter_spec["column"]).lower()
    filter_value = str(filter_spec["equals"]).lower()
    grain_key = str(config["metric_contract"]["grain_key"]).lower()
    declared = {
        item.get("path")
        for item in result.get("artifacts", [])
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    return {
        "analysis": {
            "path": analysis_relative,
            "exists": analysis_path.is_file(),
            "declared": analysis_relative in declared,
            "bytes": analysis_path.stat().st_size if analysis_path.is_file() else 0,
        },
        "findings": {
            "path": findings_relative,
            "exists": findings_path.is_file(),
            "declared": findings_relative in declared,
            "bytes": findings_path.stat().st_size if findings_path.is_file() else 0,
            "ledger": ledger,
        },
        "metric_mentions": metric_mentions,
        "concepts": {
            "filter_scope": filter_value in normalized and filter_column in normalized,
            "grain": grain_key in normalized and any(
                token in normalized for token in ("grain", "one row per", "unique")
            ),
            "fanout": any(
                token in normalized
                for token in ("fan-out", "fanout", "one-to-many", "1:n", "double-count", "inflate")
            ),
            "independent_verification": any(
                token in normalized
                for token in (
                    "independent",
                    "cross-check",
                    "cross check",
                    "reconcile",
                    "second path",
                    "alternate aggregation",
                )
            )
            or ledger["substantive_verification_rows"] > 0,
        },
    }


def persist_evidence(
    evidence_dir: Path,
    source_truth: dict[str, Any],
    artifact_audit: dict[str, Any],
    trace: dict[str, Any],
) -> None:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for name, value in (
        ("source-truth.json", source_truth),
        ("artifact-audit.json", artifact_audit),
        ("agent-trace-summary.json", trace),
    ):
        (evidence_dir / name).write_text(
            json.dumps(value, indent=2) + "\n",
            encoding="utf-8",
        )


def judge_prompt(oracle: dict[str, Any]) -> str:
    rubric = "\n".join(
        f"- {item['id']} ({item['weight']:.2f}, critical={str(item['critical']).lower()}): "
        f"{item['description']}"
        for item in oracle["expected"]["outcomes"]
    )
    criterion_ids = [item["id"] for item in oracle["expected"]["outcomes"]]
    failure_tags = oracle.get("failure_taxonomy", [])
    return f"""Act as a blind data-analysis evaluator. You do not know which
experimental condition produced the work. Review source/prompt.md, source/input/,
agent-result.json, agent-response.md, agent-trace-summary.json, artifacts/,
source-truth.json, and artifact-audit.json.

Treat source-truth.json as evaluator-computed ground truth. Score every criterion
from 0.0 to 1.0 and set passed=true only at 0.75 or higher with no blocking
failure. Check the exact filter, population, grain, aggregation, and caveats.
Correct numbers alone do not prove fan-out control or independent verification;
require evidence in the analysis, findings ledger, or trace. Do not reward claims
that the artifacts and trace do not substantiate. Ground every score in concrete
file paths, ledger rows, source fields, or trace commands.

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
    source_truth: dict[str, Any],
    artifact_audit: dict[str, Any],
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
        response.read_text(encoding="utf-8", errors="replace") if response.is_file() else "",
        encoding="utf-8",
    )
    (workspace / "agent-trace-summary.json").write_text(
        json.dumps(trace, indent=2) + "\n",
        encoding="utf-8",
    )
    (workspace / "source-truth.json").write_text(
        json.dumps(source_truth, indent=2) + "\n",
        encoding="utf-8",
    )
    (workspace / "artifact-audit.json").write_text(
        json.dumps(artifact_audit, indent=2) + "\n",
        encoding="utf-8",
    )
    artifact_dir = workspace / "artifacts"
    artifact_dir.mkdir()
    for relative in config["artifacts"].values():
        source = artifact_path(env["EVAL_OUTPUT_DIR"], relative)
        if source.is_file():
            shutil.copy2(source, artifact_dir / Path(relative).name)


def score_index(judgment: dict[str, Any]) -> dict[str, dict[str, Any]]:
    scores = judgment.get("scores")
    if not isinstance(scores, list):
        raise DataJudgeError("model judgment has no scores list")
    return {
        score["criterion_id"]: score
        for score in scores
        if isinstance(score, dict) and isinstance(score.get("criterion_id"), str)
    }


def cap_score(score: dict[str, Any], cap: float, rationale: str, evidence: str) -> None:
    value = score.get("value")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise DataJudgeError("model score value must be numeric")
    if float(value) > cap:
        score["value"] = cap
    score["passed"] = float(score["value"]) >= 0.75
    score["rationale"] = f"{score.get('rationale', '')} Deterministic check: {rationale}".strip()
    evidence_items = score.setdefault("evidence", [])
    if isinstance(evidence_items, list) and evidence not in evidence_items:
        evidence_items.append(evidence)


def apply_deterministic_overrides(
    judgment: dict[str, Any],
    *,
    oracle: dict[str, Any],
    result: dict[str, Any],
    source_truth: dict[str, Any],
    artifact_audit: dict[str, Any],
) -> dict[str, Any]:
    scores = score_index(judgment)
    failure_tags = set(judgment.get("failure_tags", []))

    route = scores.get("correct-route")
    if route is not None:
        acceptable = oracle["expected"]["route"]["acceptable_primary_skills"]
        route_ok = (result.get("route") or {}).get("primary_skill") in acceptable
        route.update(
            {
                "value": 1.0 if route_ok else 0.0,
                "passed": route_ok,
                "rationale": (
                    "Recorded primary Skill matches the expected data-analysis route."
                    if route_ok
                    else "Recorded primary Skill does not match the expected data-analysis route."
                ),
                "evidence": ["agent-result.json route"],
            }
        )
        if not route_ok:
            failure_tags.add("route-error")

    if not all(metric["contract_matches_source"] for metric in source_truth["metrics"]):
        raise DataJudgeError("case metric contract does not match evaluator-computed source truth")

    metrics = scores.get("correct-metrics")
    missing_metrics = [
        metric_id
        for metric_id, present in artifact_audit["metric_mentions"].items()
        if not present
    ]
    missing_metric_evidence = list(missing_metrics)
    if not artifact_audit["concepts"]["filter_scope"]:
        missing_metric_evidence.append("filter-scope")
    if metrics is not None and missing_metric_evidence:
        cap_score(
            metrics,
            0.25,
            f"required metric evidence is absent: {', '.join(missing_metric_evidence)}",
            "artifact-audit.json metric_mentions and concepts.filter_scope",
        )
        failure_tags.add("factuality")

    fanout = scores.get("fanout-control")
    concepts = artifact_audit["concepts"]
    if fanout is not None and source_truth["join"]["fanout_risk"]:
        missing = [name for name in ("grain", "fanout") if not concepts[name]]
        if missing:
            cap_score(
                fanout,
                0.5,
                f"analysis does not substantiate {', '.join(missing)} control",
                "artifact-audit.json concepts",
            )
            failure_tags.add("process-compliance")

    verification = scores.get("independent-verification")
    if verification is not None and not concepts["independent_verification"]:
        cap_score(
            verification,
            0.5,
            "no independent verification or reconciliation evidence was found",
            "artifact-audit.json concepts.independent_verification",
        )
        failure_tags.add("verification")

    delivery = scores.get("auditable-delivery")
    required_artifacts = (
        artifact_audit["analysis"]["exists"]
        and artifact_audit["analysis"]["declared"]
        and artifact_audit["findings"]["exists"]
        and artifact_audit["findings"]["declared"]
    )
    if delivery is not None and not required_artifacts:
        cap_score(
            delivery,
            0.0,
            "analysis.md or findings.tsv is missing or undeclared",
            "artifact-audit.json",
        )
        failure_tags.add("missing-artifact")
    elif delivery is not None and not artifact_audit["findings"]["ledger"]["valid"]:
        cap_score(
            delivery,
            0.4,
            "findings.tsv violates the required audit-ledger contract",
            "artifact-audit.json findings.ledger",
        )
        failure_tags.add("process-compliance")

    judgment["failure_tags"] = sorted(failure_tags)
    return judgment


def missing_artifact_result(
    oracle: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
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
                    else "Required analysis artifacts were not available for review."
                ),
                "evidence": ["agent-result.json route" if is_route else "agent-result.json artifacts"],
            }
        )
    tags = ["missing-artifact"]
    if not route_ok:
        tags.append("route-error")
    return {
        "scores": scores,
        "failure_tags": tags,
        "summary": "Required data-analysis artifacts were missing.",
    }


def run_judge(args: argparse.Namespace) -> dict[str, Any]:
    env = environment()
    config = judge_config()
    oracle = load_json(env["EVAL_ORACLE_FILE"])
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
    source_truth = build_source_truth(config, env["EVAL_PAYLOAD_DIR"])
    if not all(metric["contract_matches_source"] for metric in source_truth["metrics"]):
        raise DataJudgeError("case metric contract does not match evaluator-computed source truth")
    artifact_audit = audit_artifacts(
        config,
        result,
        env["EVAL_OUTPUT_DIR"],
        source_truth,
    )
    trace = trace_summary(env["EVAL_OUTPUT_DIR"])
    persist_evidence(evidence_dir, source_truth, artifact_audit, trace)

    required_artifacts_exist = (
        artifact_audit["analysis"]["exists"]
        and artifact_audit["findings"]["exists"]
    )
    if not required_artifacts_exist:
        judgment = missing_artifact_result(oracle, result)
    else:
        with tempfile.TemporaryDirectory(prefix="linlab-data-analysis-judge-") as temp:
            temp_root = Path(temp)
            workspace = temp_root / "blind-review"
            workspace.mkdir()
            prepare_model_workspace(
                workspace=workspace,
                env=env,
                result=result,
                config=config,
                source_truth=source_truth,
                artifact_audit=artifact_audit,
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
                prompt=judge_prompt(oracle),
                workspace=workspace,
                trace_root=trace_dir,
                criterion_ids=[item["id"] for item in oracle["expected"]["outcomes"]],
                failure_tags=oracle.get("failure_taxonomy", []),
            )
        judgment = apply_deterministic_overrides(
            judgment,
            oracle=oracle,
            result=result,
            source_truth=source_truth,
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
    except (DataJudgeError, EvalConfigError, ModelJudgeError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, "judgment": judgment}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
