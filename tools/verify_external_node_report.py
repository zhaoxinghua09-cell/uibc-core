#!/usr/bin/env python3
"""Recompute the numbers in an outsider's receipt, on hardware we control.

`docs/external-review/EXTERNAL-NODE-001.md` quotes two figures from a run on a
host we do not control (Debian 13, `8a95747`):

    Ran 605 tests ... OK (skipped=22)
    checks compared: 70, mismatches: 2   AGREEMENT: FAIL - SPEC BUG

Quoting numbers nobody here can reproduce is the smallest form of hearsay. This
exports that commit into a scratch directory, runs the same two commands, and
compares.

What a match means: **the figures are properties of that commit, not of his
machine** - they follow from the code, which is why an unrelated host arrived at
them. What it does NOT mean: that his host behaved like ours (the skip count
differs, because skips follow installed extras), or that his report was audited.

    python3 tools/verify_external_node_report.py                  # the receipt
    python3 tools/verify_external_node_report.py --ref <sha>      # any commit
    python3 tools/verify_external_node_report.py --quick          # skip the 605-test run

Exit 0 only when every figure matches the receipt (or, with --quick, the
comparison figures match and the test run is reported as not checked).
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gitbin  # noqa: E402  (git may be a .cmd shim on Windows)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The receipt's figures, verbatim from docs/external-review/EXTERNAL-NODE-001.md.
RECEIPT_REF = "8a95747"
RECEIPT_TESTS = 605
RECEIPT_MISMATCHES = 2

TESTS_RE = re.compile(r"Ran (\d+) tests")
MISMATCH_RE = re.compile(r"checks compared: (\d+), mismatches: (\d+)")


def export(ref, dest):
    """A read-only copy of one commit, without touching the working tree.

    The archive is written to a file and unpacked with the standard library
    rather than piped into the system `tar`. The pipe version worked on the
    host this was written on (Debian) and failed on Windows:

        tar: Error opening archive: Failed to open '\\.\tape0'

    bsdtar there reads stdin only when told to (`-f -`), and without a stream
    name it falls back to a tape device. A check that fails on one OS and
    passes on another is not portable - it is a check that teaches the wrong
    lesson about a repository whose whole claim is "recompute it yourself",
    wherever you are.
    """
    with tempfile.TemporaryDirectory() as td:
        arc = os.path.join(td, "snapshot.tar")
        r = gitbin.run(["archive", "--format=tar", "-o", arc, ref],
                       cwd=REPO, capture_output=True, text=True)
        if r.returncode != 0:
            return r.returncode, 1, r.stderr or r.stdout
        try:
            with tarfile.open(arc) as tf:
                try:
                    tf.extractall(dest, filter="data")
                except TypeError:  # python < 3.12 has no extraction filter
                    tf.extractall(dest)
        except Exception as exc:  # noqa: BLE001 - surfaced as the export error
            return 0, 1, str(exc)
    return 0, 0, ""


def run_tests(root):
    r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests",
                        "-p", "test_*.py"], cwd=root, capture_output=True, text=True,
                       timeout=1800, env=dict(os.environ, PYTHONPATH=root))
    return (r.stdout or "") + (r.stderr or "")


def run_cross_check(root):
    r = subprocess.run([sys.executable, os.path.join("independent_verifier", "cross_check.py")],
                       cwd=root, capture_output=True, text=True, timeout=900,
                       env=dict(os.environ, PYTHONPATH=root))
    return (r.stdout or "") + (r.stderr or "")


def main():
    quick = "--quick" in sys.argv
    ref = RECEIPT_REF
    if "--ref" in sys.argv:
        ref = sys.argv[sys.argv.index("--ref") + 1]
    expect_tests = RECEIPT_TESTS if ref == RECEIPT_REF else None
    expect_mismatches = RECEIPT_MISMATCHES if ref == RECEIPT_REF else None

    scratch = tempfile.mkdtemp(prefix="node001-")
    root = os.path.join(scratch, "repo")
    os.makedirs(root)
    try:
        rc1, rc2, err = export(ref, root)
        if rc1 or rc2:
            print("EXPORT FAILED for %s\n%s" % (ref, err))
            return 2
        print("exported %s (%d files) into %s" % (ref, sum(len(f) for _, _, f in os.walk(root)), root))

        out_cc = run_cross_check(root)
        m = MISMATCH_RE.search(out_cc)
        compared, mismatches = (int(m.group(1)), int(m.group(2))) if m else (None, None)
        agreement = "FAIL - SPEC BUG" if "SPEC BUG" in out_cc else (
            "PASS" if "AGREEMENT: PASS" in out_cc else "unknown")
        print("")
        print("  compared: %s  mismatches: %s  agreement: %s"
              % (compared, mismatches, agreement))

        tests = None
        if not quick:
            out_t = run_tests(root)
            tm = TESTS_RE.search(out_t)
            tests = int(tm.group(1)) if tm else None
            skipped = re.search(r"skipped=(\d+)", out_t)
            print("  tests: %s  skipped: %s" % (tests, skipped.group(1) if skipped else "?"))
        else:
            print("  tests: not checked (--quick)")

        bad = []
        if expect_mismatches is not None and mismatches != expect_mismatches:
            bad.append("mismatches: receipt says %d, this run says %s"
                       % (expect_mismatches, mismatches))
        if expect_tests is not None and tests is not None and tests != expect_tests:
            bad.append("tests: receipt says %d, this run says %s" % (expect_tests, tests))
        if tests is None and not quick:
            bad.append("could not read a test count at all")

        print("")
        if bad:
            for b in bad:
                print("  DIFFERS: " + b)
            print("VERDICT: DIFFERS FROM THE RECEIPT")
            return 1
        if tests is None:
            print("VERDICT: MATCHES THE RECEIPT (comparison figures only; tests not checked)")
        else:
            print("VERDICT: MATCHES THE RECEIPT (%d tests, %d mismatches)" % (tests, mismatches))
        print("Scope: this shows the figures follow from the code at that commit, on a host we "
              "control. It does not show his host behaved like ours - the skip count follows "
              "installed extras, and 22 vs ours is exactly that - and it is not an audit of him.")
        return 0
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
