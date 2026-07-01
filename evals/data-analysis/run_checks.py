#!/usr/bin/env python3
"""Deterministic regression gate for the skill's verification & output scripts.

This is the enforcement the rest of the skill lacks: the decision frameworks and
the Operating Rules are instructions to the model, but THESE are assertions a
machine checks. It synthesizes novel trap data (per evals/README.md — never famous
datasets) and asserts the scripts catch the traps, that the trust badge cannot be
shown without real verification, and that the renderers still produce output.

Run:  python3 evals/data-analysis/run_checks.py
Exit: 0 if every check passes, 1 if any fails. Checks needing an optional
dependency (vl-convert / great-tables / jinja2) SKIP rather than fail.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "data-analysis" / "scripts"
PY = sys.executable
results = {"pass": 0, "fail": 0, "skip": 0}


def run(args: list[str], stdin: str | None = None) -> tuple[int, str]:
    proc = subprocess.run([PY, *args], capture_output=True, text=True, input=stdin)
    return proc.returncode, proc.stdout + proc.stderr


def check(name: str, args: list[str], *, want_exit=None, want_in=None, want_not_in=None,
          outfile=None, file_in=None, file_not_in=None):
    code, out = run(args)
    if "is required:" in out or "ModuleNotFoundError" in out:
        print(f"  SKIP  {name}  (optional dependency missing)")
        results["skip"] += 1
        return
    problems = []
    if want_exit is not None and code != want_exit:
        problems.append(f"exit {code} != {want_exit}")
    for s in (want_in or []):
        if s not in out:
            problems.append(f"missing {s!r}")
    for s in (want_not_in or []):
        if s in out:
            problems.append(f"unexpected {s!r}")
    # Assertions against a produced artifact (e.g. report HTML), not stdout.
    if outfile is not None:
        content = Path(outfile).read_text(encoding="utf-8") if Path(outfile).exists() else ""
        for s in (file_in or []):
            if s not in content:
                problems.append(f"file missing {s!r}")
        for s in (file_not_in or []):
            if s in content:
                problems.append(f"file unexpectedly has {s!r}")
    if problems:
        print(f"  FAIL  {name}  — {'; '.join(problems)}")
        print(f"        output: {out.strip()[:300]}")
        results["fail"] += 1
    else:
        print(f"  pass  {name}")
        results["pass"] += 1


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="da_evals_"))
    tri = str(SCRIPTS / "triangulate.py")

    # --- synthetic trap data (novel schemas, traps injected on purpose) ---
    (tmp / "fanout.csv").write_text("order_id,line\n1,a\n1,b\n2,c\n")        # order_id repeats -> fan-out
    (tmp / "unique.csv").write_text("order_id,amt\n1,10\n2,20\n3,30\n")
    (tmp / "nullkey.csv").write_text("k,v\n1,10\n,20\n2,30\n")               # one NULL key
    (tmp / "tz.csv").write_text("d,v\n2024-01-01T00:00:00+08:00,1\n2024-12-15T00:00:00+08:00,2\n")
    (tmp / "amounts.csv").write_text("amt\n10\n20\n30\n40\n")               # sum 100, 4 rows

    print("triangulate — grain")
    check("grain flags fan-out", [tri, "grain", "--data", str(tmp/"fanout.csv"), "--key", "order_id"],
          want_exit=1, want_in=["[FLAG]"])
    check("grain passes unique key", [tri, "grain", "--data", str(tmp/"unique.csv"), "--key", "order_id"],
          want_exit=0, want_in=["[PASS]"])
    check("grain surfaces NULL keys", [tri, "grain", "--data", str(tmp/"nullkey.csv"), "--key", "k"],
          want_in=["NULL key"])

    print("triangulate — magnitude (regression: must catch a sign flip)")
    check("magnitude flags sign flip", [tri, "magnitude", "--value", "-100", "--expected", "100"],
          want_exit=1, want_in=["[FLAG]", "SIGN MISMATCH"])
    check("magnitude flags orders-off", [tri, "magnitude", "--value", "100000", "--expected", "100"],
          want_exit=1, want_in=["[FLAG]"])
    check("magnitude passes close", [tri, "magnitude", "--value", "110", "--expected", "100"],
          want_exit=0, want_in=["[PASS]"])

    print("triangulate — window (regression: must not crash on tz-aware dates)")
    check("window survives tz-aware dates", [tri, "window", "--data", str(tmp/"tz.csv"),
          "--date", "d", "--start", "2024-01-01", "--end", "2024-12-31"],
          want_not_in=["Traceback", "TypeError"])
    check("window flags out-of-range", [tri, "window", "--data", str(tmp/"tz.csv"),
          "--date", "d", "--start", "2024-02-01", "--end", "2024-03-01"],
          want_exit=1, want_in=["[FLAG]"])

    print("triangulate — reconcile / coverage / parts")
    check("reconcile passes right total", [tri, "reconcile", "--data", str(tmp/"amounts.csv"),
          "--column", "amt", "--agg", "sum", "--expected", "100"], want_exit=0, want_in=["[PASS]"])
    check("reconcile flags wrong total", [tri, "reconcile", "--data", str(tmp/"amounts.csv"),
          "--column", "amt", "--agg", "sum", "--expected", "999"], want_exit=1, want_in=["[FLAG]"])
    check("reconcile rows agg = row count", [tri, "reconcile", "--data", str(tmp/"amounts.csv"),
          "--agg", "rows", "--expected", "4"], want_exit=0, want_in=["[PASS]"])
    check("coverage flags missing population", [tri, "coverage", "--data", str(tmp/"unique.csv"),
          "--key", "order_id", "--universe", "100"], want_exit=1, want_in=["[FLAG]"])
    check("parts flags broken conservation", [tri, "parts", "--data", str(tmp/"amounts.csv"),
          "--part-col", "amt", "--whole", "50"], want_exit=1, want_in=["[FLAG]"])

    # --- trust badge cannot be shown without real verification ---
    print("build_report — trust badge integrity")
    build = str(SCRIPTS / "build_report.py")
    BADGE = "Every key number independently verified"
    (tmp / "unverified.json").write_text(
        '{"title":"X","findings":[{"claim":"Sales up","body":"eyeballed it"}]}')
    (tmp / "verified.json").write_text(
        '{"title":"X","findings":[{"claim":"Sales up","status":"verified",'
        '"verification":"DuckDB and pandas agree to the dollar; row counts reconcile"}]}')
    check("no badge when nothing verified",
          [build, "--context", str(tmp/"unverified.json"), "--out", str(tmp/"u.html")],
          want_exit=0, outfile=str(tmp/"u.html"), file_not_in=[BADGE])
    check("badge when all verified",
          [build, "--context", str(tmp/"verified.json"), "--out", str(tmp/"v.html")],
          want_exit=0, outfile=str(tmp/"v.html"), file_in=[BADGE])

    # --- ledger validation rejects empty fields ---
    print("validate_findings — rejects incomplete ledger")
    vf = str(SCRIPTS / "validate_findings.py")
    (tmp / "bad.tsv").write_text(
        "id\tclaim\tcomputation\tevidence\tverification\tcaveat\tstatus\n"
        "F1\tclaim here\t\t\t\t\tverified\n")
    check("validate_findings fails on empty fields", [vf, str(tmp/"bad.tsv")],
          want_exit=1, want_in=["FAILED"])

    # --- renderer smoke tests (SKIP if optional deps absent) ---
    print("renderers — smoke")
    (tmp / "series.csv").write_text("d,rev\n2024-01-01,10\n2024-02-01,20\n")
    check("render_chart produces SVG", [str(SCRIPTS/"render_chart.py"), "--template", "time-trend",
          "--data", str(tmp/"series.csv"), "--map", "x=d,y=rev", "--out", str(tmp/"c.svg")],
          want_exit=0, want_in=["Wrote"])
    (tmp / "tbl.csv").write_text("metric,lift\nA,0.04\nB,-0.02\n")
    (tmp / "tbl.spec.json").write_text('{"rowname":"metric","sign_color":["lift"]}')
    check("render_table produces HTML", [str(SCRIPTS/"render_table.py"), "--data", str(tmp/"tbl.csv"),
          "--spec", str(tmp/"tbl.spec.json"), "--out", str(tmp/"t.html")],
          want_exit=0, want_in=["Wrote"])

    print(f"\n{results['pass']} passed, {results['fail']} failed, {results['skip']} skipped")
    sys.exit(1 if results["fail"] else 0)


if __name__ == "__main__":
    main()
