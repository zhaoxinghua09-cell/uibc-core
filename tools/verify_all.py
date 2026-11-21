#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One command to re-run every published claim and print a structured verdict.

Why: our reproduction commands are scattered across conformance.md, REVIEW-LOG.md,
EXTERNAL-NODE-KIT.md and individual tool docstrings. A reviewer has to assemble
them by hand. This script is the single local entry point for "复跑即服务"; the
hosted/CI badge layer is a separate (authorization-gated) step.

It is deliberately honest:
  - each check records its own exit code and a short tail, never a bare PASS;
  - a check that SKIPs for a missing dependency is reported as SKIP, not PASS;
  - exit code of THIS script is 0 only if every check that could run passed.

Usage:
  python tools/verify_all.py                 # human-readable
  python tools/verify_all.py --json          # machine-readable
  python tools/verify_all.py --out PATH      # also write a JSON report
"""
import argparse
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable

CHECKS = [
    ("corpus-generator-stable", "published vectors match a fresh build",
     [PY, "tools/conformance_vectors.py", "--check"], "29-vectors"),
    ("corpus-foreign-checker", "a checker importing nothing from uibc_core reproduces every vector",
     [PY, "tools/conformance_check.py"], "29-vectors"),
    ("two-implementation-agreement", "independent verifier agrees with main verifier",
     [PY, "independent_verifier/cross_check.py"], "determinism"),
    # NOTE: never call fixtures/generate_fixtures.py here — it WRITES fixtures and
    # EXPECTED.md as a side effect (it is a generator, not a read-only gate).
    # This test imports its compare_matrix with synthetic observed data and is read-only.
    ("fixture-expectations", "verdict matrix gate logic is sound (read-only)",
     [PY, "-m", "pytest", "tests/test_fixture_expectations.py", "-q"], "verdicts"),
]


def run_one(name, desc, cmd, tag, timeout=300):
    t0 = time.perf_counter()
    try:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                           timeout=timeout)
        out = ((p.stdout or "") + "\n" + (p.stderr or "")).strip()
        tail = out.splitlines()[-6:]
        rc = p.returncode
        combined = out.lower()
        if rc != 0:
            status = "FAIL"
        elif "skip:" in combined and "0 skipped" not in combined and "skipped=0" not in combined:
            status = "SKIP"
        else:
            status = "PASS"
    except subprocess.TimeoutExpired:
        rc, status, tail = -1, "TIMEOUT", ["exceeded %ss" % timeout]
    return {
        "check": name, "tag": tag, "what": desc,
        "cmd": " ".join(cmd), "status": status, "rc": rc,
        "secs": round(time.perf_counter() - t0, 1), "tail": tail,
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    results = [run_one(*c) for c in CHECKS]
    runnable = [r for r in results if r["status"] != "SKIP"]
    ok = all(r["status"] == "PASS" for r in runnable)
    summary = {
        "when": time.strftime("%Y-%m-%d %H:%M:%S"),
        "python": sys.version.split()[0],
        "checks": len(results),
        "pass": sum(r["status"] == "PASS" for r in results),
        "skip": sum(r["status"] == "SKIP" for r in results),
        "fail": sum(r["status"] in ("FAIL", "TIMEOUT") for r in results),
        "all_runnable_pass": ok,
        "results": results,
    }

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print("reproduce-all  %s  python %s" % (summary["when"], summary["python"]))
        print("-" * 68)
        for r in results:
            print("[%-4s] %-30s %5.1fs  %s" %
                  (r["status"], r["check"], r["secs"], r["tag"]))
            for line in r["tail"]:
                print("        " + line)
        print("-" * 68)
        print("pass=%d skip=%d fail=%d  all_runnable_pass=%s" %
              (summary["pass"], summary["skip"], summary["fail"], ok))
        print("NOTE: SKIP means a dependency was missing; install `.[verify]` and re-run.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
