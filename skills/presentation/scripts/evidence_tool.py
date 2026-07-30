#!/usr/bin/env python3
"""Validate a presentation evidence ledger and its HTML bindings."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable


ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")
SOURCE_TYPES = {
    "official",
    "regulatory",
    "company",
    "academic",
    "user-provided",
    "industry",
    "media",
    "other",
}
SOURCE_STATUSES = {"core", "candidate", "rejected"}
CLAIM_KINDS = {"fact", "plan", "estimate", "interpretation", "definition"}
CLAIM_STATUSES = {"verified", "provisional", "disputed", "rejected"}
BOUND_VALUE_RE = re.compile(
    r"(?:"
    r"\b(?:19|20)\d{2}\b|"
    r"[$€£¥]\s*\d[\d,.]*|"
    r"\d[\d,.]*\s*(?:"
    r"%|bps?|pp|x|"
    r"k|mn|mm|bn|tn|million|billion|trillion|"
    r"bbls?|boe|boepd|mboe|mmboe|bcf|tcf|mmscfd|mtpa|"
    r"mw|gw|kwh|mwh|gwh|"
    r"km|cm|mm|m|ft|kg|t|tons?|tonnes?|"
    r"days?|months?|years?|hours?|minutes?|seconds?|pages?|people|users?|customers?|"
    r"亿|万|口|页|年|月|天|小时|分钟|秒|公里|千米|米|吨|人|家|个"
    r")(?!\w)"
    r")",
    re.IGNORECASE,
)


def split_ids(value: str | None) -> list[str]:
    if not value:
        return []
    return [item for item in re.split(r"[\s,]+", value.strip()) if item]


class BindingParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.claim_ids: set[str] = set()
        self.source_ids: set[str] = set()
        self.asset_ids: set[str] = set()
        self.slides: list[dict[str, Any]] = []
        self.stack: list[dict[str, Any]] = []
        self._slide_counter = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        classes = set(values.get("class", "").split())
        parent_slide = self.stack[-1]["slide"] if self.stack else None
        is_slide = "slide" in classes or "data-slide" in values
        slide = parent_slide
        if is_slide:
            self._slide_counter += 1
            slide = {
                "index": self._slide_counter,
                "id": values.get("id") or values.get("data-slide") or str(self._slide_counter),
                "claim_ids": set(),
                "text": [],
            }
            self.slides.append(slide)

        ignored = bool(classes & {"speaker-notes", "deck-controls", "slide-no"})
        if self.stack and self.stack[-1]["ignored"]:
            ignored = True
        if tag in {"script", "style"}:
            ignored = True

        claim_ids = split_ids(values.get("data-claim-id"))
        source_ids = split_ids(values.get("data-source-id"))
        asset_ids = split_ids(values.get("data-asset-id"))
        self.claim_ids.update(claim_ids)
        self.source_ids.update(source_ids)
        self.asset_ids.update(asset_ids)
        if slide is not None:
            slide["claim_ids"].update(claim_ids)

        self.stack.append({"tag": tag, "slide": slide, "ignored": ignored})

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]["tag"] == tag:
                del self.stack[index:]
                return

    def handle_data(self, data: str) -> None:
        if not self.stack or self.stack[-1]["ignored"]:
            return
        slide = self.stack[-1]["slide"]
        if slide is not None and data.strip():
            slide["text"].append(data.strip())


def parse_date(value: Any, subject: str, errors: list[str]) -> date | None:
    if not isinstance(value, str):
        errors.append(f"{subject}: expected ISO date string")
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        errors.append(f"{subject}: invalid ISO date {value!r}")
        return None


def require_string(item: dict[str, Any], field: str, subject: str, errors: list[str]) -> str:
    value = item.get(field)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{subject}: missing non-empty {field}")
        return ""
    return value


def indexed_items(
    items: Any, name: str, errors: list[str]
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    if not isinstance(items, list):
        errors.append(f"ledger.{name}: expected array")
        return [], {}
    normalized: list[dict[str, Any]] = []
    index: dict[str, dict[str, Any]] = {}
    for position, item in enumerate(items):
        subject = f"ledger.{name}[{position}]"
        if not isinstance(item, dict):
            errors.append(f"{subject}: expected object")
            continue
        item_id = require_string(item, "id", subject, errors)
        if item_id and not ID_RE.fullmatch(item_id):
            errors.append(f"{subject}.id: invalid id {item_id!r}")
        if item_id in index:
            errors.append(f"{subject}.id: duplicate id {item_id!r}")
        elif item_id:
            index[item_id] = item
        normalized.append(item)
    return normalized, index


def check_refs(
    values: Any,
    target: dict[str, Any],
    subject: str,
    errors: list[str],
    *,
    required: bool = False,
) -> list[str]:
    if not isinstance(values, list):
        errors.append(f"{subject}: expected array")
        return []
    refs = [value for value in values if isinstance(value, str)]
    if len(refs) != len(values):
        errors.append(f"{subject}: every reference must be a string")
    if required and not refs:
        errors.append(f"{subject}: at least one reference is required")
    for value in refs:
        if value not in target:
            errors.append(f"{subject}: unknown reference {value!r}")
    return refs


def validate_ledger(ledger_path: Path, html_path: Path | None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [f"cannot read ledger: {exc}"], "warnings": []}
    if not isinstance(ledger, dict):
        return {"ok": False, "errors": ["ledger root must be an object"], "warnings": []}

    if ledger.get("schemaVersion") != "1.0":
        errors.append("ledger.schemaVersion must be '1.0'")
    cutoff = parse_date(ledger.get("cutoffDate"), "ledger.cutoffDate", errors)

    sources, source_index = indexed_items(ledger.get("sources"), "sources", errors)
    claims, claim_index = indexed_items(ledger.get("claims"), "claims", errors)
    definitions, definition_index = indexed_items(
        ledger.get("definitions", []), "definitions", errors
    )
    assets, asset_index = indexed_items(ledger.get("assets"), "assets", errors)

    for position, source in enumerate(sources):
        subject = f"ledger.sources[{position}]"
        for field in ("title", "publisher", "type", "status", "accessedAt", "authority"):
            require_string(source, field, subject, errors)
        if source.get("type") not in SOURCE_TYPES:
            errors.append(f"{subject}.type: unsupported value {source.get('type')!r}")
        if source.get("status") not in SOURCE_STATUSES:
            errors.append(f"{subject}.status: unsupported value {source.get('status')!r}")
        if not source.get("url") and not source.get("localRef"):
            errors.append(f"{subject}: url or localRef is required")
        published = None
        if "publishedAt" in source:
            published = parse_date(source["publishedAt"], f"{subject}.publishedAt", errors)
        if cutoff and published and published > cutoff:
            if source.get("cutoffUse") != "retrospective":
                errors.append(
                    f"{subject}.publishedAt {published.isoformat()} exceeds cutoff "
                    f"{cutoff.isoformat()}; mark cutoffUse as 'retrospective' only when the "
                    "source is used to verify pre-cutoff state"
                )
            else:
                warnings.append(
                    f"{subject}: post-cutoff source is explicitly limited to retrospective use"
                )
        parse_date(source.get("accessedAt"), f"{subject}.accessedAt", errors)
        local_ref = source.get("localRef")
        if isinstance(local_ref, str) and not (ledger_path.parent / local_ref).exists():
            warnings.append(f"{subject}.localRef does not exist: {local_ref}")

    for position, definition in enumerate(definitions):
        subject = f"ledger.definitions[{position}]"
        require_string(definition, "label", subject, errors)
        require_string(definition, "definition", subject, errors)

    for position, claim in enumerate(claims):
        subject = f"ledger.claims[{position}]"
        require_string(claim, "statement", subject, errors)
        kind = require_string(claim, "kind", subject, errors)
        status = require_string(claim, "status", subject, errors)
        if kind not in CLAIM_KINDS:
            errors.append(f"{subject}.kind: unsupported value {kind!r}")
        if status not in CLAIM_STATUSES:
            errors.append(f"{subject}.status: unsupported value {status!r}")
        refs = check_refs(
            claim.get("sourceRefs"), source_index, f"{subject}.sourceRefs", errors, required=True
        )
        check_refs(
            claim.get("definitionRefs", []),
            definition_index,
            f"{subject}.definitionRefs",
            errors,
        )
        conflicts = check_refs(
            claim.get("conflictsWith", []), claim_index, f"{subject}.conflictsWith", errors
        )
        claim_id = claim.get("id")
        if claim_id and claim_id in conflicts:
            errors.append(f"{subject}.conflictsWith: claim cannot conflict with itself")
        relevant = None
        if "relevantAt" in claim:
            relevant = parse_date(claim["relevantAt"], f"{subject}.relevantAt", errors)
        if cutoff and relevant and relevant > cutoff:
            errors.append(
                f"{subject}.relevantAt {relevant.isoformat()} exceeds cutoff {cutoff.isoformat()}"
            )
        if status == "verified":
            for source_ref in refs:
                if source_index.get(source_ref, {}).get("status") == "rejected":
                    errors.append(f"{subject}: verified claim uses rejected source {source_ref!r}")
            if refs and all(source_index.get(ref, {}).get("status") == "candidate" for ref in refs):
                warnings.append(f"{subject}: verified claim is supported only by candidate sources")
        if kind in {"fact", "plan", "estimate"} and not claim.get("value"):
            warnings.append(f"{subject}: quantitative or factual claim has no structured value")

    for position, asset in enumerate(assets):
        subject = f"ledger.assets[{position}]"
        for field in ("type", "localFile", "factualRole", "rights"):
            require_string(asset, field, subject, errors)
        source_ref = require_string(asset, "sourceRef", subject, errors)
        if source_ref and source_ref not in source_index:
            errors.append(f"{subject}.sourceRef: unknown reference {source_ref!r}")
        elif source_ref and source_index[source_ref].get("status") == "rejected":
            errors.append(f"{subject}.sourceRef: asset uses rejected source {source_ref!r}")
        local_file = asset.get("localFile")
        if isinstance(local_file, str) and not (ledger_path.parent / local_file).exists():
            errors.append(f"{subject}.localFile does not exist: {local_file}")

    bindings: dict[str, Any] = {
        "html": str(html_path) if html_path else None,
        "claimRefs": [],
        "sourceRefs": [],
        "assetRefs": [],
        "unboundNumericSlides": [],
    }
    if html_path:
        try:
            parser = BindingParser()
            parser.feed(html_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError) as exc:
            errors.append(f"cannot read HTML bindings: {exc}")
        else:
            bindings["claimRefs"] = sorted(parser.claim_ids)
            bindings["sourceRefs"] = sorted(parser.source_ids)
            bindings["assetRefs"] = sorted(parser.asset_ids)
            for claim_id in parser.claim_ids:
                if claim_id not in claim_index:
                    errors.append(f"HTML references unknown claim {claim_id!r}")
                elif claim_index[claim_id].get("status") == "rejected":
                    errors.append(f"HTML references rejected claim {claim_id!r}")
            for source_id in parser.source_ids:
                if source_id not in source_index:
                    errors.append(f"HTML references unknown source {source_id!r}")
                elif source_index[source_id].get("status") == "rejected":
                    errors.append(f"HTML references rejected source {source_id!r}")
            for asset_id in parser.asset_ids:
                if asset_id not in asset_index:
                    errors.append(f"HTML references unknown asset {asset_id!r}")
            for slide in parser.slides:
                text = " ".join(slide["text"])
                if BOUND_VALUE_RE.search(text) and not slide["claim_ids"]:
                    bindings["unboundNumericSlides"].append(slide["id"])
            if bindings["unboundNumericSlides"]:
                warnings.append(
                    "slides contain metric-like values without data-claim-id bindings: "
                    + ", ".join(bindings["unboundNumericSlides"])
                )

            slide_ids = {slide["id"] for slide in parser.slides}
            for position, claim in enumerate(claims):
                used_by = claim.get("usedBy", [])
                if not isinstance(used_by, list) or not all(
                    isinstance(value, str) for value in used_by
                ):
                    errors.append(f"ledger.claims[{position}].usedBy: expected array of strings")
                    continue
                for slide_id in used_by:
                    if slide_id not in slide_ids:
                        errors.append(
                            f"ledger.claims[{position}].usedBy references unknown slide {slide_id!r}"
                        )
                    elif claim.get("id") not in next(
                        slide["claim_ids"] for slide in parser.slides if slide["id"] == slide_id
                    ):
                        warnings.append(
                            f"ledger.claims[{position}].usedBy lists {slide_id!r} but HTML lacks the binding"
                        )

    for claim_id, claim in claim_index.items():
        for other_id in claim.get("conflictsWith", []):
            other = claim_index.get(other_id)
            if other and claim_id not in other.get("conflictsWith", []):
                warnings.append(
                    f"claim conflict is not symmetric: {claim_id!r} -> {other_id!r}"
                )

    used_claims = set(bindings["claimRefs"])
    unused_verified = sorted(
        claim_id
        for claim_id, claim in claim_index.items()
        if claim.get("status") == "verified" and claim_id not in used_claims
    )
    if html_path and unused_verified:
        warnings.append("verified claims are not bound in HTML: " + ", ".join(unused_verified))

    return {
        "schemaVersion": "1.0",
        "ledger": str(ledger_path),
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "counts": {
            "sources": len(source_index),
            "claims": len(claim_index),
            "definitions": len(definition_index),
            "assets": len(asset_index),
            "boundClaims": len(bindings["claimRefs"]),
        },
        "bindings": bindings,
    }


def write_report(report: dict[str, Any], output: str) -> None:
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if output == "-":
        sys.stdout.write(payload)
    else:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["check"])
    parser.add_argument("ledger")
    parser.add_argument("--html")
    parser.add_argument("--out", default="-")
    args = parser.parse_args(list(argv) if argv is not None else None)
    report = validate_ledger(
        Path(args.ledger).resolve(), Path(args.html).resolve() if args.html else None
    )
    write_report(report, args.out)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
