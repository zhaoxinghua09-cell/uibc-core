#!/usr/bin/env python3
"""Run the conformance suite against any verifier, ours or someone else's.

The suite is 29 packages, each of which started correct and then had exactly
one thing broken, with the checks that must be reported recorded in
`conformance/manifest.json`.

A verifier "passes" a case when it refuses it — verdict FAIL or INCONCLUSIVE —
and names at least one of the checks the manifest expects. The exact wording of
the reason is not testable across implementations and is not required.

Checking someone else's verifier is the whole point: point `--verify` at their
command and the failures it produces are findings about them, reproducible
without asking us anything.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for p in (_REPO, os.path.join(_REPO, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

CONF = os.path.join(_REPO, "conformance")


def our_verifier(pkg):
    from uibc_core.verify import verify
    r = verify(pkg)
    return {"result": r["result"],
            "checks": [{"id": c["id"], "result": c["result"]} for c in r["checks"]]}


def external(command):
    def run(pkg):
        argv = command.replace("{pkg}", pkg).split()
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=120)
        try:
            out = json.loads(proc.stdout)
        except json.JSONDecodeError:
            return {"result": "FAIL" if proc.returncode else "PASS",
                    "checks": [], "raw": proc.stdout[-400:]}
        checks = out.get("checks")
        if isinstance(checks, list) and checks and isinstance(checks[0], dict):
            return {"result": out.get("result"), "checks": checks}
        return {"result": out.get("result"), "checks": []}
    return run


def reported_failures(got):
    return {c.get("id") for c in got.get("checks", [])
            if str(c.get("result", "")).upper() == "FAIL"}


def judge(case, got):
    verdict = (got.get("result") or "").upper()
    if case.get("expect") == "accept":
        # The other half: a correct package must not be refused. Without these,
        # a verifier that refuses everything scores full marks.
        ok = verdict not in ("FAIL",) and not reported_failures(got)
        return {"id": case["id"], "attack": case["attack"], "ok": ok,
                "refused": verdict == "FAIL", "verdict": verdict,
                "reported": [], "expected": [],
                "note": "" if ok else "refused a package that is correct"}
    reported = reported_failures(got)
    named = bool(reported & set(case["expected_checks"]))
    refused = verdict in ("FAIL", "INCONCLUSIVE")
    return {"id": case["id"], "attack": case["attack"],
            "ok": refused and named,
            "refused": refused,
            "verdict": verdict, "reported": sorted(reported),
            "expected": case["expected_checks"],
            "note": ("" if refused and named else
                     "refused but did not name an expected check" if refused
                     else "did not refuse a package that is broken")}


def run_all(verify_one):
    with open(os.path.join(CONF, "manifest.json"), encoding="utf-8") as f:
        man = json.load(f)
    rows = []
    tmp = tempfile.mkdtemp(prefix="uibc-cc-run-")
    try:
        root = CONF
        if not os.path.isdir(os.path.join(CONF, "cases")):
            # Only the archive is in the repo; unpack once.
            with zipfile.ZipFile(os.path.join(CONF, "uibc-conformance-0.4.0.zip")) as z:
                z.extractall(tmp)
            root = tmp
        for case in man["cases"]:
            src = os.path.join(root, case["path"])
            pkg = os.path.join(tmp, case["id"])
            shutil.copytree(src, pkg)
            rows.append(judge(case, verify_one(pkg)))
        return {"cases": len(rows),
                "passed": sum(1 for r in rows if r["ok"]),
                "refused": sum(1 for r in rows if r["refused"]),
                "rows": rows, "ok": all(r["ok"] for r in rows)}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", default=None,
                    help="external verifier command; use {pkg} for the package path")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    res = run_all(external(a.verify) if a.verify else our_verifier)
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        for r in res["rows"]:
            print("%-4s %-6s %s" % (r["id"], "ok" if r["ok"] else "FAIL",
                                    r["attack"][:44] + ("  " + r["note"] if r["note"] else "")))
        print("\nstrict %d/%d   refused %d/%d" % (res["passed"], res["cases"],
                                              res["refused"], res["cases"]))
    sys.exit(0 if res["ok"] else 1)
