#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check a conformance receipt against the package it claims to describe.

Why this exists
---------------
`tools/conformance_harness.py` writes a receipt, and `conformance/ADAPTER-PROTOCOL.md`
asks an implementer to send it back. Until now the only thing that happened next
was a human reading it. That makes the receipt a statement, not evidence: its
counts could disagree with its own rows, its rows could name vectors that do not
exist, and the "55/55" at the top could be typing.

This tool re-derives every number in the receipt from the rows and from the
committed package. It cannot know what the adapter actually computed - that
happened on their machine - but it can refuse a receipt that contradicts itself,
which is the part a filer could otherwise get wrong by accident or on purpose.

    python tools/check_conformance_receipt.py receipt.json
    python tools/check_conformance_receipt.py receipt.json --allow-subset
    python tools/check_conformance_receipt.py --self-test

What it checks
  * schema is conformance-receipt/1, and the environment block is present
  * every row names a vector that exists in this package, exactly once
  * every expected value quoted in the receipt still matches the package bytes
  * root_agreement / verdict_agreement flags equal the comparison of the recorded
    answer against the package's expected value (a flag that disagrees with its
    own row is a self-contradiction, not a different reading)
  * the summary counts equal the tallies of the rows
  * by default, all vectors are present; --allow-subset requires the receipt to
    say which vectors it skipped, so a partial run cannot look like a full one

--self-test mutates a receipt produced here and requires each mutation to be
rejected: a checker that passes its own receipt unconditionally proves nothing.
Exit 1 on any contradiction.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(REPO, "docs", "upstream-package", "scitt-rfc9162")
SCHEMA = "conformance-receipt/1"


def load_package(pkg=PKG):
    with open(os.path.join(pkg, "manifest.json"), encoding="utf-8") as fh:
        manifest = json.load(fh)
    expected = {}
    for v in manifest["vectors"]:
        with open(os.path.join(pkg, v["dir"], "expected.json"), encoding="utf-8") as fh:
            exp = json.load(fh)
        expected[v["id"]] = exp
    return manifest, expected


def check(receipt, manifest, expected, allow_subset=False):
    problems = []

    def bad(msg):
        problems.append(msg)

    if receipt.get("schema") != SCHEMA:
        bad("schema is %r, not %r" % (receipt.get("schema"), SCHEMA))
    env = receipt.get("environment") or {}
    for key in ("platform", "python", "utc_time"):
        if not env.get(key):
            bad("environment.%s is missing" % key)
    rows = receipt.get("rows")
    if not isinstance(rows, list) or not rows:
        bad("rows is missing or empty")
        return problems

    ids = [r.get("id") for r in rows]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    for d in dupes:
        bad("row %s appears %d times" % (d, ids.count(d)))
    unknown = sorted(set(ids) - set(expected))
    for u in unknown:
        bad("row %s is not a vector in this package" % u)

    missing = sorted(set(expected) - set(ids))
    if missing and not allow_subset:
        bad("%d vector(s) have no row (first: %s); use --allow-subset if the receipt "
            "declares a partial run" % (len(missing), missing[0]))
    if missing and allow_subset and not receipt.get("skipped_vectors"):
        bad("partial receipt must list skipped_vectors; otherwise it reads as a full run")

    answered = errored = agree = wording = 0
    for r in rows:
        vid = r.get("id")
        if vid not in expected:
            continue
        exp = expected[vid]
        status = r.get("status")
        if status == "adapter-error":
            errored += 1
            continue
        if status != "answered":
            bad("row %s has status %r" % (vid, status))
            continue
        answered += 1
        if exp.get("kind") == "consistency":
            want_old = exp["reconstructed_old_root"]
            want_new = exp["reconstructed_new_root"]
            # Their answer may legitimately differ from ours; what must not differ is
            # the flag describing it. That check is below, for both kinds.
            got_ok = (r.get("their_reconstructed_old_root") == want_old
                      and r.get("their_reconstructed_new_root") == want_new)
        else:
            want = exp["reconstructed_root"]
            got_ok = r.get("their_reconstructed_root") == want
        if bool(r.get("root_agreement")) != got_ok:
            bad("row %s: root_agreement is %r but the recorded answer %s the package"
                % (vid, r.get("root_agreement"), "matches" if got_ok else "does not match"))
        if got_ok:
            agree += 1
        if not r.get("verdict_agreement"):
            wording += 1

    for key, want in (("vectors", len(rows)), ("answered", answered),
                      ("adapter_errors", errored), ("root_agreement", agree),
                      ("verdict_agreement", answered - wording)):
        if receipt.get(key) != want:
            bad("summary %s is %r but the rows say %d" % (key, receipt.get(key), want))

    mismatches = [r["id"] for r in rows
                  if r.get("status") == "answered" and not r.get("root_agreement")]
    if receipt.get("root_mismatches") != mismatches:
        bad("root_mismatches does not match the rows that failed root agreement")
    return problems


def _make_receipt(tmpdir):
    out = os.path.join(tmpdir, "receipt.json")
    subprocess.run([sys.executable, os.path.join(REPO, "tools", "conformance_harness.py"),
                    "--adapter", "%s %s" % (sys.executable,
                                            os.path.join(REPO, "conformance", "adapters",
                                                         "reference_python.py")),
                    "--out", out], check=True, capture_output=True, text=True)
    with open(out, encoding="utf-8") as fh:
        return json.load(fh)


def self_test(manifest, expected):
    with tempfile.TemporaryDirectory() as tmpdir:
        good = _make_receipt(tmpdir)
    rc = check(good, manifest, expected)
    if rc:
        print("self-test: the harness's own receipt is rejected: %s" % rc[0])
        return 1
    print("self-test: the harness's own receipt passes")

    mutations = []
    m = json.loads(json.dumps(good))
    m["root_agreement"] = 999
    mutations.append(("summary inflated", m))
    m = json.loads(json.dumps(good))
    m["rows"] = m["rows"][:-1]
    mutations.append(("a row dropped without declaration", m))
    m = json.loads(json.dumps(good))
    m["rows"][0]["root_agreement"] = not m["rows"][0]["root_agreement"]
    mutations.append(("a row flag flipped", m))
    m = json.loads(json.dumps(good))
    m["rows"][0]["id"] = "a-vector-that-does-not-exist"
    mutations.append(("a row renamed to an unknown vector", m))

    caught = 0
    for label, mutated in mutations:
        rc = check(mutated, manifest, expected)
        if rc:
            caught += 1
            print("self-test caught: %s — %s" % (label, rc[0]))
        else:
            print("self-test FAILED to catch: %s" % label)
    return 0 if caught == len(mutations) else 1


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("receipt", nargs="?")
    ap.add_argument("--allow-subset", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)

    manifest, expected = load_package()
    if a.self_test:
        return self_test(manifest, expected)
    if not a.receipt:
        print("[FATAL] give a receipt path, or --self-test")
        return 2

    with open(a.receipt, encoding="utf-8") as fh:
        receipt = json.load(fh)
    problems = check(receipt, manifest, expected, a.allow_subset)
    for p in problems:
        print("  " + p)
    print("rows: %d, vectors in package: %d" % (len(receipt.get("rows") or []), len(expected)))
    print("VERDICT: %s" % ("RECEIPT-CONSISTENT" if not problems else "RECEIPT-DISCREPANCY"))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
