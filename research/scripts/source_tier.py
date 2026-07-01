#!/usr/bin/env python3
"""Classify a URL into the research skill's broad evidence tiers."""

from __future__ import annotations

import argparse
import json
from urllib.parse import urlparse


S_DOMAINS = (
    ".gov", ".mil", "sec.gov", "nih.gov", "ncbi.nlm.nih.gov", "clinicaltrials.gov",
    "nist.gov", "fda.gov", "uspto.gov", "wipo.int", "epo.org", "ietf.org",
    "w3.org", "iso.org", "iec.ch", "openai.com", "docs.openai.com",
)

A_DOMAINS = (
    "nature.com", "science.org", "cell.com", "nejm.org", "thelancet.com",
    "acm.org", "ieee.org", "springer.com", "wiley.com", "arxiv.org",
    "semanticscholar.org", "crossref.org", "doi.org", "reuters.com",
    "apnews.com", "bloomberg.com", "ft.com", "wsj.com",
)

C_DOMAINS = (
    "twitter.com", "x.com", "reddit.com", "news.ycombinator.com",
    "facebook.com", "tiktok.com", "threads.net",
)


def classify(url: str) -> dict:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]

    tier = "B"
    reason = "ordinary secondary or unknown source"

    if any(host == d or host.endswith(d) for d in S_DOMAINS):
        tier = "S"
        reason = "official, regulatory, standards, or primary-source domain"
    elif any(host == d or host.endswith(d) for d in A_DOMAINS):
        tier = "A"
        reason = "authoritative academic, technical, or major news domain"
    elif any(host == d or host.endswith(d) for d in C_DOMAINS):
        tier = "C"
        reason = "social/community source; use as lead or sentiment signal"

    return {"url": url, "host": host, "tier": tier, "reason": reason}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("urls", nargs="+")
    args = parser.parse_args()
    rows = [classify(url) for url in args.urls]
    print(json.dumps(rows if len(rows) > 1 else rows[0], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
