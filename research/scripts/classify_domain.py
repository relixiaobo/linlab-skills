#!/usr/bin/env python3
"""Deterministic first-pass classifier for the research skill."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List


DOMAIN_SIGNALS: Dict[str, List[str]] = {
    "literature": [
        "literature review", "systematic review", "meta-analysis", "paper", "papers",
        "doi", "pubmed", "arxiv", "semantic scholar", "citation", "citations",
        "related work", "research gap", "clinical trial", "study design",
        "recent papers", "last few years of papers",
    ],
    "entity-dossier": [
        "due diligence", "diligence", "background on", "prep me for", "meeting prep",
        "red flag", "red flags", "investment diligence", "acquisition diligence",
        "founder background", "company background", "person background", "org background",
    ],
    "pulse": [
        "what are people saying", "current conversation", "sentiment", "trend",
        "trending", "buzz", "reddit", "hacker news", "hn", "twitter", "x/twitter",
        "community feedback", "complaints", "pain points",
    ],
    "patent": [
        "patent", "prior art", "freedom to operate", "fto", "novelty",
        "claims", "uspto", "espacenet", "google patents", "lens.org",
        "infringement risk", "patent landscape", "patent search",
    ],
    "grants": [
        "grant", "grants", "funding opportunity", "nih", "r01", "r21",
        "study section", "program officer", "funder", "foundation funding",
        "grant application", "funding application",
    ],
    "codebase-docs": [
        "api docs", "official docs", "library", "framework", "sdk", "changelog",
        "release notes", "migration", "version", "package", "repo", "codebase",
        "upgrade guide", "source code",
    ],
    "standards-regulatory": [
        "regulation", "regulatory", "compliance", "law", "legal", "standard",
        "standards", "rfc", "iso", "iec", "nist", "w3c", "fda", "sec rule",
        "jurisdiction", "national standard", "industry standard", "policy",
        "certification",
    ],
}

DEPTH_SIGNALS = {
    "deep": [
        "deep", "comprehensive", "exhaustive", "formal report", "dossier", "due diligence",
        "in-depth", "thorough", "full report",
    ],
    "quick": ["quick", "briefly", "lookup", "what is", "who is", "look up"],
}

VERIFY_SIGNALS = [
    "verify", "fact check", "fact-check", "is this true", "claim", "rumor", "another ai said",
]
BATCH_SIGNALS = [
    "compare", "comparison", "list of", "all of", "each of", "table", "csv", "benchmark", "matrix",
    "batch",
]


@dataclass
class Match:
    domain: str
    score: int
    signals: List[str]


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def has_signal(text: str, signal: str) -> bool:
    pattern = r"(?<![a-z0-9])" + re.escape(signal.lower()) + r"(?![a-z0-9])"
    return re.search(pattern, text) is not None


def score_signals(text: str, signals: Iterable[str]) -> List[str]:
    return [signal for signal in signals if has_signal(text, signal)]


def classify(query: str) -> Dict[str, object]:
    text = normalize(query)
    matches: List[Match] = []
    for domain, signals in DOMAIN_SIGNALS.items():
        found = score_signals(text, signals)
        if found:
            matches.append(Match(domain=domain, score=len(found), signals=found))

    matches.sort(key=lambda item: (-item.score, item.domain))
    selected = matches[0].domain if matches else "general"

    depth = "standard"
    if score_signals(text, DEPTH_SIGNALS["deep"]):
        depth = "deep"
    elif score_signals(text, DEPTH_SIGNALS["quick"]):
        depth = "quick"

    return {
        "selected_domain": selected,
        "depth": depth,
        "batch": bool(score_signals(text, BATCH_SIGNALS)),
        "verification": bool(score_signals(text, VERIFY_SIGNALS)),
        "matches": [match.__dict__ for match in matches],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="+", help="Research request text")
    args = parser.parse_args()
    print(json.dumps(classify(" ".join(args.query)), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
