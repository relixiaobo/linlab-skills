#!/usr/bin/env python3
"""Deterministic offline smoke gate for the feed-processing skill scripts."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
SKILL = ROOT / "skills" / "feed-processing"
SCRIPTS = SKILL / "scripts"
ASSETS = SKILL / "assets" / "fixtures"
FIXTURES = ROOT / "tests" / "fixtures" / "feed-processing"
WORK = ROOT / "work" / "feed-processing" / "eval-smoke"
NODE = shutil.which("node")
results = {"pass": 0, "fail": 0}


def run(args: list[str], *, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    if not NODE:
        raise RuntimeError("node is required for feed-processing evals")
    return subprocess.run([NODE, *args], cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False)


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def check(name: str, ok: bool, detail: str = "") -> None:
    if ok:
        print(f"  pass  {name}")
        results["pass"] += 1
    else:
        print(f"  FAIL  {name}  {detail}")
        results["fail"] += 1


def require_run(name: str, args: list[str]) -> subprocess.CompletedProcess[str]:
    proc = run(args)
    check(name, proc.returncode == 0, (proc.stdout + proc.stderr).strip()[:500])
    return proc


class FeedFixtureHandler(BaseHTTPRequestHandler):
    active_requests = 0
    max_active_requests = 0
    counter_lock = threading.Lock()

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        if self.path.startswith("/large"):
            body = b"x" * 2048
            self.send_response(200)
            self.send_header("content-type", "application/rss+xml")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        with self.counter_lock:
            type(self).active_requests += 1
            type(self).max_active_requests = max(
                type(self).max_active_requests,
                type(self).active_requests,
            )
        try:
            time.sleep(0.1)
            body = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>Local Feed</title><link>http://127.0.0.1/</link><item><title>Local Item</title><link>http://127.0.0.1/item</link><guid>local-item</guid><pubDate>Tue, 07 Jul 2026 00:00:00 GMT</pubDate></item></channel></rss>"""
            self.send_response(200)
            self.send_header("content-type", "application/rss+xml")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        finally:
            with self.counter_lock:
                type(self).active_requests -= 1


def main() -> int:
    if not NODE:
        print(json.dumps({"ok": False, "errors": ["node is required for feed-processing evals"]}, indent=2))
        return 1
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)

    print("source list")
    source_out = WORK / "sources.json"
    require_run("source_list accepts plain URLs", [str(SCRIPTS / "source_list.mjs"), "--input", str(FIXTURES / "sources.txt"), "--out", str(source_out)])
    sources = load(source_out)
    check("source_list records valid sources", sources["coverage"]["sourceCount"] == 2)
    check("source_list warns on invalid URL", any(w["code"] == "invalid_url" for w in sources["warnings"]))
    require_run("source_list accepts CSV", [str(SCRIPTS / "source_list.mjs"), "--input", str(ASSETS / "sources.csv"), "--out", str(WORK / "sources-csv.json")])
    require_run("source_list accepts Markdown table", [str(SCRIPTS / "source_list.mjs"), "--input", str(ASSETS / "sources.md"), "--out", str(WORK / "sources-md.json")])
    require_run("source_list accepts OPML", [str(SCRIPTS / "source_list.mjs"), "--input", str(ASSETS / "sources.opml"), "--out", str(WORK / "sources-opml.json")])

    print("feed fetching")
    server = ThreadingHTTPServer(("127.0.0.1", 0), FeedFixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = f"http://127.0.0.1:{server.server_port}"
        delayed_sources = WORK / "delayed-sources.json"
        delayed_sources.write_text(json.dumps({
            "sources": [
                {"sourceId": f"delayed-{index}", "feedUrl": f"{base_url}/feed-{index}.xml"}
                for index in range(16)
            ]
        }, indent=2), encoding="utf-8")
        delayed_out = WORK / "delayed-fetch.json"
        with FeedFixtureHandler.counter_lock:
            FeedFixtureHandler.active_requests = 0
            FeedFixtureHandler.max_active_requests = 0
        delayed_proc = run([
            str(SCRIPTS / "feed_fetch.mjs"),
            "--sources", str(delayed_sources),
            "--concurrency", "8",
            "--timeoutMs", "2000",
            "--out", str(delayed_out),
        ])
        peak_concurrency = FeedFixtureHandler.max_active_requests
        check(
            "feed_fetch fetches with bounded concurrency",
            delayed_proc.returncode == 0 and 1 < peak_concurrency <= 8,
            f"peak={peak_concurrency} {(delayed_proc.stdout + delayed_proc.stderr).strip()[:300]}",
        )
        delayed = load(delayed_out)
        check("feed_fetch preserves concurrent coverage", delayed["coverage"]["requested"] == 16 and delayed["coverage"]["fetched"] == 16, json.dumps(delayed["coverage"]))

        large_out = WORK / "large-fetch.json"
        require_run("feed_fetch rejects oversized response", [
            str(SCRIPTS / "feed_fetch.mjs"),
            "--url", f"{base_url}/large",
            "--maxBytes", "128",
            "--out", str(large_out),
        ])
        large = load(large_out)
        check("feed_fetch reports response_too_large without body", large["responses"][0]["error"]["code"] == "response_too_large" and "body" not in large["responses"][0])
    finally:
        server.shutdown()
        server.server_close()

    print("feed discovery")
    discover_out = WORK / "discover.json"
    require_run("feed_discover finds alternate links", [str(SCRIPTS / "feed_discover.mjs"), "--html", str(FIXTURES / "page-with-feeds.html"), "--url", "https://example.com/page", "--out", str(discover_out)])
    discover = load(discover_out)
    check("feed_discover returns rss/atom/json", {c["type"] for c in discover["candidates"]} == {"rss", "atom", "jsonfeed"})
    nofeed_out = WORK / "discover-no-feed.json"
    require_run("feed_discover reports no alternate links", [str(SCRIPTS / "feed_discover.mjs"), "--html", str(FIXTURES / "page-no-feed.html"), "--url", "https://example.com/page", "--out", str(nofeed_out)])
    check("feed_discover suggests common paths", load(nofeed_out)["candidates"][0]["source"] == "common_path")

    print("feed parsing")
    parsed_out = WORK / "parsed.json"
    require_run("feed_parse handles RSS Atom JSON and malformed feed", [
        str(SCRIPTS / "feed_parse.mjs"),
        "--input", str(ASSETS / "rss2-basic.xml"),
        "--input", str(ASSETS / "atom-basic.xml"),
        "--input", str(ASSETS / "json-feed-basic.json"),
        "--input", str(ASSETS / "malformed-guid.xml"),
        "--out", str(parsed_out),
    ])
    parsed = load(parsed_out)
    check("feed_parse item count", parsed["coverage"]["parsedItems"] == 5, json.dumps(parsed["coverage"]))
    check("feed_parse surfaces missing date warning", any(w["code"] == "date_missing" for item in parsed["items"] for w in item["warnings"]))

    fetched_fixture = WORK / "fetched-fixture.json"
    fetched_fixture.write_text(json.dumps({
        "responses": [
            {
                "sourceId": "fixture-rss-source",
                "url": "https://example.com/rss.xml",
                "finalUrl": "https://example.com/rss.xml",
                "status": 200,
                "ok": True,
                "notModified": False,
                "body": (ASSETS / "rss2-basic.xml").read_text(encoding="utf-8"),
            },
            {
                "sourceId": "fixture-dead-source",
                "url": "https://example.com/dead.xml",
                "status": 404,
                "ok": False,
                "error": {"code": "http_error", "message": "HTTP 404"},
            },
        ],
        "coverage": {"requested": 2, "fetched": 1, "notModified": 0, "errored": 1},
    }, indent=2), encoding="utf-8")
    fetched_parse_out = WORK / "fetched-parse.json"
    require_run("feed_parse accepts feed_fetch output", [str(SCRIPTS / "feed_parse.mjs"), "--input", str(fetched_fixture), "--out", str(fetched_parse_out)])
    fetched_parse = load(fetched_parse_out)
    check("feed_parse preserves fetched response coverage", fetched_parse["coverage"]["requested"] == 2 and fetched_parse["coverage"]["fetched"] == 1 and fetched_parse["coverage"]["erroredSources"] == 1, json.dumps(fetched_parse["coverage"]))
    check("feed_parse preserves fetched source identity", all(item["sourceId"] == "fixture-rss-source" for item in fetched_parse["items"]))
    check("feed_parse records fetch errors", fetched_parse["errors"][0]["code"] == "http_error")

    print("windows and rules")
    window_out = WORK / "window.json"
    require_run("feed_window last 7 days", [str(SCRIPTS / "feed_window.mjs"), "--input", str(parsed_out), "--mode", "last_n_days", "--days", "7", "--now", "2026-07-07T12:00:00Z", "--out", str(window_out)])
    window = load(window_out)
    check("feed_window selects recent items", window["coverage"]["selectedItems"] == 3, json.dumps(window["coverage"]))
    check("feed_window reports ambiguous dates", any(s["reason"] == "date_ambiguous" for s in window["skipped"]))
    fetched_window_out = WORK / "fetched-window.json"
    require_run("feed_window preserves fetch/parse errors", [str(SCRIPTS / "feed_window.mjs"), "--input", str(fetched_parse_out), "--mode", "newest_n", "--count", "1", "--out", str(fetched_window_out)])
    fetched_window = load(fetched_window_out)
    check("feed_window preserves coverage", fetched_window["coverage"]["fetched"] == 1 and fetched_window["coverage"]["erroredSources"] == 1, json.dumps(fetched_window["coverage"]))
    check("feed_window preserves errors", len(fetched_window["errors"]) == 1 and fetched_window["errors"][0]["sourceId"] == "fixture-dead-source")
    empty_rules = WORK / "empty-rules.json"
    empty_rules.write_text("{}", encoding="utf-8")
    fetched_rules_out = WORK / "fetched-rules.json"
    require_run("feed_rules preserves window errors", [str(SCRIPTS / "feed_rules.mjs"), "--input", str(fetched_window_out), "--rules", str(empty_rules), "--out", str(fetched_rules_out)])
    fetched_rules = load(fetched_rules_out)
    check("feed_rules preserves coverage", fetched_rules["coverage"]["fetched"] == 1 and fetched_rules["coverage"]["erroredSources"] == 1, json.dumps(fetched_rules["coverage"]))
    check("feed_rules preserves errors", len(fetched_rules["errors"]) == 1 and fetched_rules["errors"][0]["sourceId"] == "fixture-dead-source")
    rules_out = WORK / "rules.json"
    require_run("feed_rules applies include/exclude", [str(SCRIPTS / "feed_rules.mjs"), "--input", str(window_out), "--rules", str(FIXTURES / "rules.json"), "--out", str(rules_out)])
    check("feed_rules keeps selected items", load(rules_out)["coverage"]["selectedItems"] >= 1)

    print("profile")
    profile_input = WORK / "profile-input.json"
    profile_input.write_text(json.dumps({
        "sources": [
            {"sourceId": "profile-a", "feedUrl": "https://example.com/a.xml", "title": "A"},
            {"sourceId": "profile-b", "feedUrl": "https://example.com/b.xml", "title": "B"},
            {"sourceId": "profile-empty", "feedUrl": "https://example.com/empty.xml", "title": "Empty"},
        ],
        "items": [
            {"sourceId": "profile-a", "title": "Same", "publishedAt": "2026-07-01T00:00:00.000Z", "url": "https://example.com/a/1", "summaryText": "short", "contentText": "short"},
            {"sourceId": "profile-a", "title": "Same", "publishedAt": "2026-07-01T00:00:00.000Z", "summaryText": "short", "contentText": "short"},
            {"sourceId": "profile-a", "title": "Newer", "updatedAt": "2026-07-03T00:00:00.000Z", "url": "https://example.com/a/3"},
            {"sourceId": "profile-b", "title": "Undated"},
        ],
    }, indent=2), encoding="utf-8")
    profile_out = WORK / "profile.json"
    require_run("feed_profile builds source profiles", [str(SCRIPTS / "feed_profile.mjs"), "--input", str(profile_input), "--out", str(profile_out)])
    profile = {row["sourceId"]: row for row in load(profile_out)["profile"]}
    check("feed_profile aggregates per-source stats", profile["profile-a"]["itemCount"] == 3 and profile["profile-empty"]["itemCount"] == 0)
    check("feed_profile tracks dates and duplicates", profile["profile-a"]["newestAt"] == "2026-07-03T00:00:00.000Z" and profile["profile-a"]["oldestAt"] == "2026-07-01T00:00:00.000Z" and profile["profile-a"]["duplicateTitleDateCount"] == 1)
    check("feed_profile tracks missing and truncation counts", profile["profile-a"]["missingUrlCount"] == 1 and profile["profile-a"]["truncationLikelyCount"] == 2 and profile["profile-b"]["missingDateCount"] == 1 and profile["profile-b"]["missingUrlCount"] == 1)

    print("diff")
    prior = WORK / "prior.json"
    current = WORK / "current.json"
    prior.write_text(json.dumps({"items": [parsed["items"][0], parsed["items"][1]]}, indent=2), encoding="utf-8")
    changed = dict(parsed["items"][0])
    changed["contentText"] = "Changed content"
    current.write_text(json.dumps({"items": [changed, parsed["items"][2], parsed["items"][2]]}, indent=2), encoding="utf-8")
    diff_out = WORK / "diff.json"
    require_run("feed_diff classifies item changes", [str(SCRIPTS / "feed_diff.mjs"), "--prior", str(prior), "--current", str(current), "--out", str(diff_out)])
    diff = load(diff_out)
    check("feed_diff changed/new/duplicate/stale", diff["coverage"]["changedItems"] == 1 and diff["coverage"]["newItems"] == 1 and diff["coverage"]["duplicateItems"] == 1 and diff["coverage"]["staleItems"] == 1, json.dumps(diff["coverage"]))

    print("full text and pack validation")
    summary_parse = WORK / "summary-parse.json"
    require_run("feed_parse summary fixture", [str(SCRIPTS / "feed_parse.mjs"), "--input", str(ASSETS / "rss2-summary.xml"), "--out", str(summary_parse)])
    summary = load(summary_parse)
    item_id = summary["items"][0]["itemId"]
    fulltext_out = WORK / "fulltext.json"
    require_run("full_text_extract records attempt ledger", [
        str(SCRIPTS / "full_text_extract.mjs"),
        "--input", str(summary_parse),
        "--article", f"{item_id}={ASSETS / 'article-static.html'}",
        "--out", str(fulltext_out),
    ])
    fulltext = load(fulltext_out)
    ft = fulltext["items"][0]["fullText"]
    check("full_text_extract selects static readability", ft["selectedStrategy"] == "static_readability" and len(ft["attempts"]) >= 2)
    fetched_fulltext_out = WORK / "fetched-fulltext.json"
    require_run("full_text_extract preserves upstream errors", [str(SCRIPTS / "full_text_extract.mjs"), "--input", str(fetched_rules_out), "--out", str(fetched_fulltext_out)])
    fetched_fulltext = load(fetched_fulltext_out)
    check("full_text_extract preserves coverage", fetched_fulltext["coverage"]["fetched"] == 1 and fetched_fulltext["coverage"]["erroredSources"] == 1, json.dumps(fetched_fulltext["coverage"]))
    check("full_text_extract preserves errors", len(fetched_fulltext["errors"]) == 1 and fetched_fulltext["errors"][0]["sourceId"] == "fixture-dead-source")
    pack_out = WORK / "feed-pack.json"
    require_run("feed_pack builds pack", [str(SCRIPTS / "feed_pack.mjs"), "--input", str(fulltext_out), "--out", str(pack_out)])
    validate_out = WORK / "validate.json"
    require_run("validate_feed_pack accepts valid pack", [str(SCRIPTS / "validate_feed_pack.mjs"), "--input", str(pack_out), "--out", str(validate_out)])
    check("validate_feed_pack ok", load(validate_out)["ok"] is True)
    fetched_pack_out = WORK / "fetched-pack.json"
    require_run("feed_pack preserves upstream errors", [str(SCRIPTS / "feed_pack.mjs"), "--input", str(fetched_fulltext_out), "--out", str(fetched_pack_out)])
    fetched_pack = load(fetched_pack_out)
    check("feed_pack keeps errored source coverage", fetched_pack["coverage"]["erroredSources"] == 1 and len(fetched_pack["errors"]) == 1, json.dumps(fetched_pack["coverage"]))
    fetched_validate_out = WORK / "fetched-validate.json"
    require_run("validate_feed_pack accepts pack with source errors", [str(SCRIPTS / "validate_feed_pack.mjs"), "--input", str(fetched_pack_out), "--out", str(fetched_validate_out)])

    bad_pack = load(pack_out)
    bad_pack["selectedItems"].append(bad_pack["selectedItems"][0])
    bad_path = WORK / "bad-pack.json"
    bad_path.write_text(json.dumps(bad_pack, indent=2), encoding="utf-8")
    bad = run([str(SCRIPTS / "validate_feed_pack.mjs"), "--input", str(bad_path), "--out", str(WORK / "bad-validate.json")])
    check("validate_feed_pack rejects duplicates", bad.returncode == 1)

    print(f"\n{results['pass']} passed, {results['fail']} failed")
    return 0 if results["fail"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
