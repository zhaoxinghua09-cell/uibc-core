#!/usr/bin/env python3
"""One-command conformance run for someone who did not clone this repository.

This file ships *inside* the conformance zip. It needs nothing from the
repository: stdlib only, and it calls whatever verifier you point it at.

    python run.py                          # reference verifier, if installed
    python run.py --verify "uibc verify {pkg}"
    python run.py --json                   # machine-readable

Exit code 0 only when every case behaved as the manifest requires.

What a pass means, and what it does not:
  - it means your verifier refused each broken package and named at least one
    check the manifest expects, and accepted the correct ones;
  - it does NOT mean the verifier is secure, independent or audited. The
    manifest is ours, the corpus is ours, and this runner is ours.
  - a receipt written here is only evidence that this command ran, on this
    machine, at this time, and produced this table. It is not a certification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "manifest.json")
CASES = os.path.join(HERE, "cases")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def verifier_version(command):
    """Version of the reference implementation, only when it is what was run.

    Probing `import uibc_core` regardless of the command would label someone
    else's verifier with our version number, which is the kind of receipt
    detail that turns into a false claim later.
    """
    if "uibc_core" not in command and "uibc " not in command:
        return "not the reference verifier (version not probed)"
    try:
        out = subprocess.run([sys.executable, "-c",
                              "import uibc_core;print(uibc_core.__version__)"],
                             capture_output=True, text=True, timeout=30)
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return "unknown"


def call_verifier(command, pkg):
    argv = command.replace("{pkg}", pkg).split()
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=180)
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"result": "FAIL" if proc.returncode else "PASS", "checks": [],
                "raw": proc.stdout[-400:]}
    checks = out.get("checks")
    if isinstance(checks, list) and checks and isinstance(checks[0], dict):
        return {"result": out.get("result"), "checks": checks}
    return {"result": out.get("result"), "checks": []}


def reported_failures(got):
    return {c.get("id") for c in got.get("checks", [])
            if str(c.get("result", "")).upper() == "FAIL"}


def judge(case, got):
    verdict = (got.get("result") or "").upper()
    if case.get("expect") == "accept":
        ok = verdict != "FAIL" and not reported_failures(got)
        return {"id": case["id"], "attack": case["attack"], "ok": ok,
                "verdict": verdict, "reported": [], "expected": [],
                "note": "" if ok else "refused a package that is correct"}
    reported = reported_failures(got)
    named = bool(reported & set(case["expected_checks"]))
    refused = verdict in ("FAIL", "INCONCLUSIVE")
    return {"id": case["id"], "attack": case["attack"],
            "ok": refused and named, "verdict": verdict,
            "reported": sorted(reported), "expected": case["expected_checks"],
            "note": ("" if refused and named else
                     "refused but did not name an expected check" if refused
                     else "did not refuse a package that is broken")}


def run_all(command):
    with open(MANIFEST, encoding="utf-8") as f:
        man = json.load(f)
    tmp = tempfile.mkdtemp(prefix="uibc-conf-")
    rows = []
    try:
        for case in man["cases"]:
            # manifest paths already start with "cases/", and are relative to the
            # archive root, not to cases/
            src = os.path.join(HERE, case["path"])
            pkg = os.path.join(tmp, case["id"])
            shutil.copytree(src, pkg)
            rows.append(judge(case, call_verifier(command, pkg)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", default=sys.executable + " -m uibc_core.cli verify {pkg}")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--receipt", default="receipt.json",
                    help="where to write the run receipt; '' to skip")
    ap.add_argument("--run-by", default="",
                    help="name to record as the person who ran this (leave blank if none)")
    a = ap.parse_args()

    if not os.path.isdir(CASES):
        sys.exit("error: cases/ not found next to this script; unzip the archive first")

    rows = run_all(a.verify)
    passed = sum(1 for r in rows if r["ok"])

    if not a.json:
        for r in rows:
            print("%-4s %-6s %s" % (r["id"], "ok" if r["ok"] else "FAIL",
                                    r["attack"][:44]
                                    + ("  " + r["note"] if r["note"] else "")))
        print("\nstrict %d/%d" % (passed, len(rows)))
        if passed != len(rows):
            print("\nIf every row failed at once, the verifier probably crashed or "
                  "printed no JSON. Install the reference one with:\n"
                  "    pip install uibc-core==0.4.1")

    if a.receipt:
        receipt = {
            "kind": "uibc-conformance-run-receipt",
            "notice": ("This records that a command ran on a machine and produced "
                       "this table. It is not a certification, and it is not an "
                       "independent audit: the corpus, the manifest and this runner "
                       "are all authored by the project."),
            "run_by": a.run_by or None,
            "when_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "command": a.verify,
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "verifier_version": verifier_version(a.verify),
            "manifest_sha256": sha256(MANIFEST) if os.path.isfile(MANIFEST) else None,
            "cases": len(rows), "passed": passed,
            "rows": rows,
        }
        with open(a.receipt, "w", encoding="utf-8", newline="\n") as f:
            json.dump(receipt, f, ensure_ascii=False, indent=2)
            f.write("\n")
        if not a.json:
            print("\nreceipt written to %s" % a.receipt)

    if a.json:
        print(json.dumps({"cases": len(rows), "passed": passed, "rows": rows},
                         ensure_ascii=False, indent=2))
    sys.exit(0 if passed == len(rows) else 1)


if __name__ == "__main__":
    main()
