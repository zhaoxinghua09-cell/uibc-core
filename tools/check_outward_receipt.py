#!/usr/bin/env python3
"""Decide whether a receipt someone else published is usable as evidence.

`tools/conformance_bundle_run.py` writes `receipt.json`. A stranger runs it, gets
a table, and wants to publish the number. This tool answers one question before
that number is quoted anywhere: *does the file say what it claims to say?*

It is deliberately narrow. It cannot tell whether the run really happened — only
the person who ran it can attest to that, and they do so in the issue form. What
it can do is refuse receipts that are internally impossible: a version of
`unknown`, a count that does not match its own rows, a receipt whose runner never
named a verifier, a timestamp that is not a time.

Usage:
    python tools/check_outward_receipt.py receipt.json
    python tools/check_outward_receipt.py receipt.json --expect-manifest-sha256 <hex>

Exit 0 when acceptable, 1 when not, and it prints one line per reason.
"""
import argparse
import datetime
import json
import os
import re
import sys

KIND = "uibc-conformance-run-receipt"

REQUIRED = (
    "kind",
    "notice",
    "run_by",
    "when_utc",
    "command",
    "python",
    "platform",
    "verifier_version",
    "manifest_sha256",
    "cases",
    "passed",
    "rows",
)

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _iso_utc(value):
    try:
        datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
        return True
    except (TypeError, ValueError):
        return False


def check(receipt, expect_manifest_sha256=None, require_run_by=True):
    """Return a list of reasons this receipt cannot be quoted. Empty means acceptable."""
    reasons = []

    if not isinstance(receipt, dict):
        return ["the file is not a JSON object"]

    missing = [k for k in REQUIRED if k not in receipt]
    if missing:
        return ["missing keys: %s" % ", ".join(missing)]

    if receipt["kind"] != KIND:
        reasons.append("kind is %r, not %r" % (receipt["kind"], KIND))

    if not _iso_utc(receipt["when_utc"]):
        reasons.append("when_utc is not YYYY-MM-DDTHH:MM:SSZ: %r" % (receipt["when_utc"],))

    version = str(receipt["verifier_version"] or "")
    if not version or version == "unknown":
        reasons.append("verifier_version is %r; the run did not name which verifier judged it" % version)

    if not _HEX64.match(str(receipt["manifest_sha256"])):
        reasons.append("manifest_sha256 is not 64 lowercase hex characters")

    if expect_manifest_sha256 and str(receipt["manifest_sha256"]) != expect_manifest_sha256.lower():
        reasons.append(
            "manifest_sha256 is %s, the corpus you mean is %s"
            % (receipt["manifest_sha256"], expect_manifest_sha256.lower())
        )

    command = str(receipt["command"] or "")
    if not command:
        reasons.append("command is empty: no one can see what produced the table")
    elif not (".pyz" in command or "uibc_core" in command):
        reasons.append("command names neither the bundled verifier nor uibc_core: %r" % command)

    rows = receipt["rows"]
    if not isinstance(rows, list):
        reasons.append("rows is not a list")
        rows = []
    else:
        ids = [r.get("id") for r in rows if isinstance(r, dict)]
        if len(ids) != len(set(ids)):
            reasons.append("rows repeat an id: %s" % sorted({i for i in ids if ids.count(i) > 1}))
        bad = [r.get("id") for r in rows if not isinstance(r, dict) or "ok" not in r]
        if bad:
            reasons.append("rows without an ok field: %s" % bad)

    cases = receipt["cases"]
    passed = receipt["passed"]
    if not isinstance(cases, int) or not isinstance(passed, int):
        reasons.append("cases/passed are not integers")
    else:
        if cases != len(rows):
            reasons.append("cases is %d but rows has %d entries" % (cases, len(rows)))
        counted = sum(1 for r in rows if isinstance(r, dict) and r.get("ok") is True)
        if passed != counted:
            reasons.append("passed is %d but %d rows say ok" % (passed, counted))
        if passed > cases:
            reasons.append("passed (%d) exceeds cases (%d)" % (passed, cases))

    if require_run_by and not str(receipt["run_by"] or "").strip():
        reasons.append(
            "run_by is empty: a receipt with no named runner can be copied from anywhere, "
            "including from our own report"
        )

    return reasons


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("receipt", help="path to a receipt.json produced by run.py")
    ap.add_argument("--expect-manifest-sha256", default=None,
                    help="the corpus digest you intended to run")
    ap.add_argument("--allow-anonymous", action="store_true",
                    help="accept a receipt whose run_by is empty (it then cannot be a node report)")
    ap.add_argument("--json", action="store_true", help="print the reasons as JSON")
    args = ap.parse_args(argv)

    if not os.path.isfile(args.receipt):
        print("no such file: %s" % args.receipt)
        return 1

    receipt = load(args.receipt)
    reasons = check(receipt, args.expect_manifest_sha256, require_run_by=not args.allow_anonymous)

    if args.json:
        print(json.dumps({"acceptable": not reasons, "reasons": reasons}, indent=2))
    else:
        if reasons:
            print("NOT ACCEPTABLE — %d reason(s):" % len(reasons))
            for r in reasons:
                print("  - " + r)
        else:
            print(
                "ACCEPTABLE — %d/%d cases, verifier %s, corpus %s"
                % (receipt["passed"], receipt["cases"], receipt["verifier_version"],
                   receipt["manifest_sha256"][:12])
            )
    return 0 if not reasons else 1


if __name__ == "__main__":
    sys.exit(main())
