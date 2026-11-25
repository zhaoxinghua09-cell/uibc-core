#!/usr/bin/env python3
"""One command for an outsider to audit *our* page, not just theirs.

Every gate in this repository checks one artefact: the receipt is current, the
picture is a rendering of the receipt, the register's numbers match the receipt,
the index is a scan of the tree. None of them checks that all of them still hold
*together*, and none of them runs from a clean copy — a working tree that has been
edited over many sessions is exactly where staleness hides.

So this runs the lot in one pass, in a directory it did not create:

  1. our own corpus receipt is a fresh measurement  (measure_own_corpus --check)
  2. the coverage picture is a fresh rendering      (build_corpus_sweep_svg --check)
  3. the two-ruler picture is a fresh rendering     (build_same_ruler_svg --check)
  4. the reach ladder is a fresh rendering          (build_reach_ladder_svg --check)
  5. the ledger's own invariants hold               (build_upstream_ledger --selftest)
  6. every locked claim still equals its receipt    (audit_claims_receipts)
  7. the evidence index is a scan of this tree      (build_evidence_index --check)

    python3 tools/stranger_own_check.py            # audit this checkout
    python3 tools/stranger_own_check.py --fresh    # fetch main, audit a clean copy
    python3 tools/stranger_own_check.py --json
    python3 tools/stranger_own_check.py --selftest # no network, no checkout

Exit 0 only when every check passes. A failing line prints the first line of the
failing check's output, so "does not reproduce" arrives with a reason attached.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = "zhaoxinghua09-cell/uibc-core"

CHECKS = (
    ("own-corpus-receipt", ("tools/measure_own_corpus.py", "--check")),
    ("coverage-picture", ("tools/build_corpus_sweep_svg.py", "--check")),
    ("two-ruler-picture", ("tools/build_same_ruler_svg.py", "--check")),
    ("reach-ladder-picture", ("tools/build_reach_ladder_svg.py", "--check")),
    ("ledger-invariants", ("tools/build_upstream_ledger.py", "--selftest")),
    ("claims-vs-receipts", ("tools/audit_claims_receipts.py",)),
    ("evidence-index", ("tools/build_evidence_index.py", "--check")),
)


def run_checks(root, runner=None):
    """Run every check in `root`. runner(argv, cwd) -> (code, output)."""
    if runner is None:
        def runner(argv, cwd):
            env = dict(os.environ, PYTHONIOENCODING="utf-8")
            proc = subprocess.run([sys.executable] + list(argv), cwd=cwd,
                                  capture_output=True, text=True, env=env)
            return proc.returncode, (proc.stdout or "") + (proc.stderr or "")

    rows = []
    for name, argv in CHECKS:
        code, output = runner(argv, root)
        lines = [ln for ln in output.splitlines() if ln.strip()]
        rows.append({
            "check": name,
            "argv": " ".join(argv),
            "code": code,
            "status": "PASS" if code == 0 else "FAIL",
            "last_line": lines[-1] if lines else "",
        })
    failed = [r for r in rows if r["code"] != 0]
    return {"root": root, "checks": rows, "passed": len(rows) - len(failed),
            "failed": len(failed),
            "verdict": "SELF-CONSISTENT" if not failed else "NOT SELF-CONSISTENT"}


def fetch_main(workdir):
    """Download the current main tarball. Standard library only."""
    import tarfile
    import urllib.request

    url = "https://codeload.github.com/%s/tar.gz/refs/heads/main" % REPO
    path = os.path.join(workdir, "main.tar.gz")
    with urllib.request.urlopen(url, timeout=180) as resp:
        blob = resp.read()
    with open(path, "wb") as f:
        f.write(blob)
    with tarfile.open(path) as tar:
        try:
            tar.extractall(workdir, filter="data")
        except TypeError:
            tar.extractall(workdir)
    for name in sorted(os.listdir(workdir)):
        candidate = os.path.join(workdir, name)
        if os.path.isdir(candidate) and os.path.exists(
                os.path.join(candidate, "tools", "measure_own_corpus.py")):
            return candidate, len(blob)
    return None, len(blob)


def _selftest():
    ok, fails = 0, []

    def check(label, cond):
        nonlocal ok
        if cond:
            ok += 1
        else:
            fails.append(label)

    def all_pass(argv, cwd):
        return 0, "ok"

    def one_fails(argv, cwd):
        return (1, "stale: not a fresh build") if "build_reach_ladder" in " ".join(argv) else (0, "ok")

    r = run_checks("x", all_pass)
    check("all-pass is self-consistent", r["verdict"] == "SELF-CONSISTENT" and r["failed"] == 0)
    check("every check is reported", len(r["checks"]) == len(CHECKS))

    r = run_checks("x", one_fails)
    check("one failure changes the verdict", r["verdict"] == "NOT SELF-CONSISTENT")
    check("the failing check is named", [c["check"] for c in r["checks"] if c["status"] == "FAIL"]
          == ["reach-ladder-picture"])
    check("the failure line is carried", "stale" in
          [c["last_line"] for c in r["checks"] if c["status"] == "FAIL"][0])

    # No check may depend on a network or a corpus it does not fetch itself.
    for _name, argv in CHECKS:
        check("%s is a local tool" % _name, argv[0].startswith("tools/"))

    if fails:
        print("SELFTEST FAILED: %s" % "; ".join(fails))
        return 1
    print("SELFTEST OK: %d checks" % ok)
    return 0


def _print(report):
    print("%d checks against %s" % (len(report["checks"]), report["root"]))
    for c in report["checks"]:
        print("  %-22s %s" % (c["check"], c["status"]))
        if c["status"] == "FAIL":
            print("    %s" % c["last_line"])
    print("VERDICT: %s (%d passed, %d failed)"
          % (report["verdict"], report["passed"], report["failed"]))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fresh", action="store_true",
                   help="fetch main and audit a clean copy instead of this tree")
    p.add_argument("--json", action="store_true")
    p.add_argument("--selftest", action="store_true")
    args = p.parse_args(argv)
    if args.selftest:
        return _selftest()

    workdir = None
    try:
        if args.fresh:
            workdir = tempfile.mkdtemp(prefix="own-audit-")
            root, nbytes = fetch_main(workdir)
            if not root:
                print("VERDICT: could not unpack main")
                return 1
            report = run_checks(root)
            report["source"] = {"kind": "fetch", "tarball_bytes": nbytes}
        else:
            report = run_checks(HERE)
            report["source"] = {"kind": "checkout"}
        if args.json:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            _print(report)
        return 0 if report["failed"] == 0 else 1
    finally:
        if workdir:
            shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
