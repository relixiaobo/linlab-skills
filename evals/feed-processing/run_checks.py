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


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "feed-processing"
SCRIPTS = SKILL / "scripts"
ASSETS = SKILL / "assets" / "fixtures"
FIXTURES = ROOT / "evals" / "feed-processing" / "fixtures"
WORK = ROOT / "feed-processing-workspace" / "eval-smoke"
NODE = shutil.which("node")
results = {"pass": 0, "fail": 0}


def run(args: list[str], *, timeout: int = 60, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    if not NODE:
        raise RuntimeError("node is required for feed-processing evals")
    return subprocess.run(
        [NODE, *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        input=input_text,
    )


def run_timed(args: list[str], *, timeout: int = 60) -> tuple[subprocess.CompletedProcess[str], float]:
    start = time.monotonic()
    proc = run(args, timeout=timeout)
    return proc, time.monotonic() - start


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
    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        if self.path == "/portable/redirect.xml":
            self.send_response(302)
            self.send_header("location", "/portable/direct.xml")
            self.end_headers()
            return

        if self.path == "/portable/legacy-rss":
            self.send_response(302)
            self.send_header("location", "/portable/landing")
            self.end_headers()
            return

        if self.path == "/portable/empty-rss":
            self.send_response(302)
            self.send_header("location", "/portable/empty-landing")
            self.end_headers()
            return

        if self.path == "/portable/loop-a":
            self.send_response(302)
            self.send_header("location", "/portable/loop-b")
            self.end_headers()
            return

        if self.path == "/portable/loop-b":
            self.send_response(302)
            self.send_header("location", "/portable/loop-a")
            self.end_headers()
            return

        if self.path == "/portable/rate-limited":
            self.send_response(429)
            self.send_header("retry-after", "60")
            self.end_headers()
            return

        if self.path in {"/portable/landing", "/portable/empty-landing", "/portable/html-only"}:
            alternate = {
                "/portable/landing": '<link rel="alternate" type="application/rss+xml" href="/portable/recovered.xml">',
                "/portable/empty-landing": '<link rel="alternate" type="application/rss+xml" href="/portable/empty.xml">',
                "/portable/html-only": "",
            }[self.path]
            body = f"<!doctype html><html><head>{alternate}</head><body>Landing page</body></html>".encode()
            self.send_response(200)
            self.send_header("content-type", "text/html; charset=utf-8")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path in {"/portable/direct.xml", "/portable/recovered.xml"}:
            slug = "direct" if self.path.endswith("direct.xml") else "recovered"
            body = f"""<?xml version="1.0"?><rss version="2.0"><channel><title>{slug.title()} Feed</title><link>http://127.0.0.1/</link><item><title>{slug.title()} Item</title><link>http://127.0.0.1/{slug}</link><guid>{slug}-item</guid><pubDate>Tue, 07 Jul 2026 00:00:00 GMT</pubDate></item></channel></rss>""".encode()
            self.send_response(200)
            self.send_header("content-type", "application/rss+xml")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path == "/portable/empty.xml":
            body = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>Empty Feed</title><link>http://127.0.0.1/</link></channel></rss>"""
            self.send_response(200)
            self.send_header("content-type", "application/rss+xml")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path in {"/feed", "/rss", "/atom.xml", "/feed.xml", "/index.xml", "/rss.xml"}:
            self.send_response(404)
            self.end_headers()
            return

        if self.path.startswith("/large"):
            body = b"x" * 2048
            self.send_response(200)
            self.send_header("content-type", "application/rss+xml")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        time.sleep(0.1)
        body = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>Local Feed</title><link>http://127.0.0.1/</link><item><title>Local Item</title><link>http://127.0.0.1/item</link><guid>local-item</guid><pubDate>Tue, 07 Jul 2026 00:00:00 GMT</pubDate></item></channel></rss>"""
        self.send_response(200)
        self.send_header("content-type", "application/rss+xml")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class RedirectFixtureHandler(BaseHTTPRequestHandler):
    target = ""

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        self.send_response(302)
        self.send_header("location", f"{self.target}/portable/landing")
        self.end_headers()


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
    base_url = f"http://127.0.0.1:{server.server_port}"
    RedirectFixtureHandler.target = base_url
    redirect_server = ThreadingHTTPServer(("127.0.0.1", 0), RedirectFixtureHandler)
    redirect_thread = threading.Thread(target=redirect_server.serve_forever, daemon=True)
    redirect_thread.start()
    redirect_base_url = f"http://127.0.0.1:{redirect_server.server_port}"
    try:
        delayed_sources = WORK / "delayed-sources.json"
        delayed_sources.write_text(json.dumps({
            "sources": [
                {"sourceId": f"delayed-{index}", "feedUrl": f"{base_url}/feed-{index}.xml"}
                for index in range(16)
            ]
        }, indent=2), encoding="utf-8")
        delayed_out = WORK / "delayed-fetch.json"
        delayed_proc, elapsed = run_timed([
            str(SCRIPTS / "feed_fetch.mjs"),
            "--sources", str(delayed_sources),
            "--concurrency", "8",
            "--timeoutMs", "2000",
            "--out", str(delayed_out),
        ])
        check("feed_fetch fetches with bounded concurrency", delayed_proc.returncode == 0 and elapsed < 1.0, f"elapsed={elapsed:.2f}s {(delayed_proc.stdout + delayed_proc.stderr).strip()[:300]}")
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
        check("feed_fetch reports oversized_response without body", large["responses"][0]["error"]["code"] == "oversized_response" and "body" not in large["responses"][0])

        print("portable end-to-end processing")
        portable_request = {
            "schemaVersion": "1.0",
            "now": "2026-07-14T00:00:00Z",
            "limits": {
                "timeoutMs": 2000,
                "maxRedirects": 8,
                "maxCandidates": 8,
                "maxDiscoveryDepth": 2,
                "concurrency": 4,
            },
            "sources": [
                {"sourceId": "direct", "inputUrl": f"{base_url}/portable/direct.xml"},
                {"sourceId": "redirect", "inputUrl": f"{base_url}/portable/redirect.xml"},
                {"sourceId": "legacy", "inputUrl": f"{base_url}/portable/legacy-rss"},
                {"sourceId": "cross-origin", "inputUrl": f"{redirect_base_url}/old-feed"},
                {"sourceId": "empty", "inputUrl": f"{base_url}/portable/empty-rss"},
                {"sourceId": "html-only", "inputUrl": f"{base_url}/portable/html-only"},
                {"sourceId": "loop", "inputUrl": f"{base_url}/portable/loop-a"},
                {"sourceId": "rate", "inputUrl": f"{base_url}/portable/rate-limited"},
            ],
        }
        portable_request_path = WORK / "portable-request.json"
        portable_request_path.write_text(json.dumps(portable_request, indent=2), encoding="utf-8")
        portable_out = WORK / "portable-result.json"
        require_run("feed_process runs the portable workflow", [
            str(SCRIPTS / "feed_process.mjs"),
            "process",
            "--input", str(portable_request_path),
            "--out", str(portable_out),
        ])
        portable = load(portable_out)
        portable_sources = {source["sourceId"]: source for source in portable["sources"]}
        check("feed_process validates its result", portable["validation"]["ok"] is True, json.dumps(portable["validation"]))
        check(
            "feed_process reconciles terminal coverage",
            portable["coverage"]["requestedSources"] == 8
            and portable["coverage"]["parsedSources"] == 4
            and portable["coverage"]["emptySources"] == 1
            and portable["coverage"]["failedSources"] == 3
            and portable["coverage"]["parsedItems"] == 2,
            json.dumps(portable["coverage"]),
        )
        check(
            "feed_process follows direct feed redirects",
            portable_sources["redirect"]["status"] == "parsed"
            and portable_sources["redirect"]["redirected"] is True,
            json.dumps(portable_sources["redirect"]),
        )
        check(
            "feed_process recovers HTML discovery pages",
            portable_sources["legacy"]["status"] == "parsed"
            and portable_sources["legacy"]["recovered"] is True
            and portable_sources["legacy"]["resolvedFeedUrl"] == f"{base_url}/portable/recovered.xml",
            json.dumps(portable_sources["legacy"]),
        )
        check(
            "feed_process resolves relative candidates against a cross-origin final URL",
            portable_sources["cross-origin"]["status"] == "parsed"
            and portable_sources["cross-origin"]["resolvedFeedUrl"] == f"{base_url}/portable/recovered.xml",
            json.dumps(portable_sources["cross-origin"]),
        )
        check(
            "feed_process distinguishes empty feeds",
            portable_sources["empty"]["status"] == "empty"
            and any(warning["code"] == "no_items" for warning in portable_sources["empty"]["warnings"]),
            json.dumps(portable_sources["empty"]),
        )
        check(
            "feed_process deduplicates sources that resolve to the same feed",
            portable_sources["redirect"].get("duplicateOfSourceId") == "direct"
            and portable_sources["cross-origin"].get("duplicateOfSourceId") == "legacy"
            and sum(1 for warning in portable["warnings"] if warning["code"] == "duplicate_resolved_source") == 2,
        )
        check(
            "feed_process classifies bounded recovery failures",
            portable_sources["html-only"]["errors"][0]["code"] == "no_feed_discovered"
            and portable_sources["loop"]["errors"][0]["code"] == "redirect_loop"
            and portable_sources["rate"]["errors"][0]["code"] == "rate_limited",
        )
        check(
            "feed_process records machine-actionable errors",
            all(
                all(key in error for key in ["code", "stage", "retryable", "severity", "message", "nextAction"])
                for error in portable["errors"]
            ),
            json.dumps(portable["errors"]),
        )
        check(
            "feed_process keeps fetched bodies out of result attempts",
            all("body" not in attempt for source in portable["sources"] for attempt in source["attempts"]),
        )

        stdin_proc = run(
            [str(SCRIPTS / "feed_process.mjs"), "process", "--input", "-", "--no-common"],
            input_text=json.dumps({
                "now": "2026-07-14T00:00:00Z",
                "sources": [{"sourceId": "stdin", "inputUrl": f"{base_url}/portable/direct.xml"}],
            }),
        )
        stdin_result = json.loads(stdin_proc.stdout) if stdin_proc.returncode == 0 else {}
        check(
            "feed_process supports JSON stdin and stdout",
            stdin_proc.returncode == 0
            and stdin_result.get("coverage", {}).get("parsedSources") == 1,
            (stdin_proc.stdout + stdin_proc.stderr)[-500:],
        )

        local_payload_proc = run(
            [str(SCRIPTS / "feed_process.mjs"), "process", "--input", "-"],
            input_text=json.dumps({
                "now": "2026-07-14T00:00:00Z",
                "scope": {"mode": "newest_n", "count": 1},
                "sources": [{
                    "sourceId": "local-payload",
                    "inputUrl": "urn:fixture:rss2-basic",
                    "finalUrl": "https://example.com/rss.xml",
                    "contentType": "application/rss+xml",
                    "payload": (ASSETS / "rss2-basic.xml").read_text(encoding="utf-8"),
                }],
            }),
        )
        local_payload = json.loads(local_payload_proc.stdout) if local_payload_proc.returncode == 0 else {}
        check(
            "feed_process handles supplied payloads without network transport",
            local_payload_proc.returncode == 0
            and local_payload.get("coverage", {}).get("transportSucceeded") == 0
            and local_payload.get("coverage", {}).get("parsedSources") == 1
            and local_payload.get("sources", [{}])[0].get("attempts", [{}])[0].get("stage") == "input"
            and "payload" not in local_payload.get("sources", [{}])[0],
            (local_payload_proc.stdout + local_payload_proc.stderr)[-500:],
        )
        check(
            "feed_process applies the requested scope",
            local_payload.get("coverage", {}).get("parsedItems") == 2
            and local_payload.get("coverage", {}).get("selectedItems") == 1
            and local_payload.get("coverage", {}).get("skippedItems") == 1
            and len(local_payload.get("items", [])) == 1,
            json.dumps(local_payload.get("coverage", {})),
        )

        invalid_scope_proc = run(
            [str(SCRIPTS / "feed_process.mjs"), "process", "--input", "-"],
            input_text=json.dumps({
                "scope": {"mode": "newest_n", "count": -1},
                "sources": [{
                    "sourceId": "invalid-scope",
                    "inputUrl": "urn:fixture:rss2-basic",
                    "finalUrl": "https://example.com/rss.xml",
                    "contentType": "application/rss+xml",
                    "payload": (ASSETS / "rss2-basic.xml").read_text(encoding="utf-8"),
                }],
            }),
        )
        invalid_scope = json.loads(invalid_scope_proc.stdout) if invalid_scope_proc.stdout else {}
        check(
            "feed_process rejects invalid scope parameters",
            invalid_scope_proc.returncode == 1
            and invalid_scope.get("validation", {}).get("ok") is False
            and any("invalid_scope" in error for error in invalid_scope.get("validation", {}).get("errors", [])),
            (invalid_scope_proc.stdout + invalid_scope_proc.stderr)[-500:],
        )

        local_html_proc = run(
            [str(SCRIPTS / "feed_process.mjs"), "process", "--input", "-"],
            input_text=json.dumps({
                "sources": [{
                    "sourceId": "local-html",
                    "inputUrl": "urn:fixture:html",
                    "contentType": "text/html",
                    "payload": "<!doctype html><html><head></head><body>No feed</body></html>",
                }],
            }),
        )
        local_html = json.loads(local_html_proc.stdout) if local_html_proc.returncode == 0 else {}
        check(
            "feed_process bounds discovery for non-HTTP supplied HTML",
            local_html_proc.returncode == 0
            and local_html.get("sources", [{}])[0].get("status") == "failed"
            and local_html.get("errors", [{}])[0].get("code") == "no_feed_discovered"
            and any(warning["code"] == "common_paths_unavailable" for warning in local_html.get("warnings", [])),
            (local_html_proc.stdout + local_html_proc.stderr)[-500:],
        )

        source_list_proc = run(
            [str(SCRIPTS / "feed_process.mjs"), "process", "--input", "-"],
            input_text=f"{base_url}/portable/direct.xml\nnot-a-url\n",
        )
        source_list_result = json.loads(source_list_proc.stdout) if source_list_proc.returncode == 0 else {}
        check(
            "feed_process preserves source-list normalization warnings",
            source_list_proc.returncode == 0
            and source_list_result.get("coverage", {}).get("requestedSources") == 1
            and any(warning["code"] == "invalid_url" for warning in source_list_result.get("warnings", [])),
            (source_list_proc.stdout + source_list_proc.stderr)[-500:],
        )

        validate_proc = run(
            [str(SCRIPTS / "feed_process.mjs"), "validate", "--input", "-"],
            input_text=json.dumps(portable),
        )
        validate_result = json.loads(validate_proc.stdout) if validate_proc.returncode == 0 else {}
        check("feed_process validates through stdin", validate_result.get("ok") is True, validate_proc.stdout + validate_proc.stderr)

        capabilities_proc = run([str(SCRIPTS / "feed_process.mjs"), "capabilities"])
        capabilities = json.loads(capabilities_proc.stdout) if capabilities_proc.returncode == 0 else {}
        check(
            "feed_process declares a host-neutral JSON interface",
            capabilities.get("interface") == "json-stdio"
            and "host_sink" in capabilities.get("optionalCapabilities", []),
            capabilities_proc.stdout + capabilities_proc.stderr,
        )

        online_discover_out = WORK / "discover-cross-origin.json"
        require_run("feed_discover uses the final redirect URL as its base", [
            str(SCRIPTS / "feed_discover.mjs"),
            "--url", f"{redirect_base_url}/old-feed",
            "--out", str(online_discover_out),
        ])
        online_discover = load(online_discover_out)
        check(
            "feed_discover returns a candidate on the final origin",
            online_discover["pageUrl"] == f"{base_url}/portable/landing"
            and online_discover["candidates"][0]["url"] == f"{base_url}/portable/recovered.xml",
            json.dumps(online_discover),
        )

        portable_pack_out = WORK / "portable-pack.json"
        require_run("feed_pack accepts a portable processing result", [
            str(SCRIPTS / "feed_pack.mjs"),
            "--input", str(portable_out),
            "--out", str(portable_pack_out),
        ])
        portable_pack_validate = WORK / "portable-pack-validate.json"
        require_run("validate_feed_pack accepts portable source states", [
            str(SCRIPTS / "validate_feed_pack.mjs"),
            "--input", str(portable_pack_out),
            "--out", str(portable_pack_validate),
        ])
        portable_pack = load(portable_pack_out)
        check(
            "feed_pack preserves portable source coverage",
            len(portable_pack["sources"]) == 8
            and portable_pack["coverage"]["requestedSources"] == 8
            and portable_pack["coverage"]["failedSources"] == 3,
            json.dumps(portable_pack["coverage"]),
        )
    finally:
        redirect_server.shutdown()
        redirect_server.server_close()
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
    check(
        "feed_window preserves coverage",
        fetched_window["coverage"]["fetched"] == 1
        and fetched_window["coverage"]["erroredSources"] == 1
        and fetched_window["coverage"]["requestedSources"] == 2
        and fetched_window["coverage"]["failedSources"] == 1,
        json.dumps(fetched_window["coverage"]),
    )
    check("feed_window preserves errors", len(fetched_window["errors"]) == 1 and fetched_window["errors"][0]["sourceId"] == "fixture-dead-source")
    empty_rules = WORK / "empty-rules.json"
    empty_rules.write_text("{}", encoding="utf-8")
    fetched_rules_out = WORK / "fetched-rules.json"
    require_run("feed_rules preserves window errors", [str(SCRIPTS / "feed_rules.mjs"), "--input", str(fetched_window_out), "--rules", str(empty_rules), "--out", str(fetched_rules_out)])
    fetched_rules = load(fetched_rules_out)
    check(
        "feed_rules preserves coverage",
        fetched_rules["coverage"]["fetched"] == 1
        and fetched_rules["coverage"]["erroredSources"] == 1
        and fetched_rules["coverage"]["requestedSources"] == 2
        and fetched_rules["coverage"]["failedSources"] == 1,
        json.dumps(fetched_rules["coverage"]),
    )
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
    check(
        "full_text_extract preserves coverage",
        fetched_fulltext["coverage"]["fetched"] == 1
        and fetched_fulltext["coverage"]["erroredSources"] == 1
        and fetched_fulltext["coverage"]["requestedSources"] == 2
        and fetched_fulltext["coverage"]["failedSources"] == 1,
        json.dumps(fetched_fulltext["coverage"]),
    )
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
