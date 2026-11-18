#!/usr/bin/env python3
"""Judge somebody else's AER-1 receipt with our own implementation.

This is the inbound half of interoperability. `tools/emit_aer1_receipts.py`
proves that their verifier accepts what we produce;
`tools/aer1_interop_demo.py` proves both implementations agree about
tamperings. What was still missing is the case a third party actually
needs: *somebody else's receipt arrives, and we must say what it is* —
with the full three-layer report Section 6 asks for, not just a
pass/fail.

Usage:

    python3 tools/aer1_verify_external.py --receipt path/to/receipt.json
    python3 tools/aer1_verify_external.py --dir  path/to/receipts/ --json
    python3 tools/aer1_verify_external.py --dir corpus/base/test-vectors/valid

Exit code 0 when every receipt judged matches the verdict it should
have: `--receipt` alone exits 0 if the file is valid, `--dir` exits 0
if the run completed and reported (use `--expect` to assert a label).

Why this exists as a separate tool rather than a flag on the verifier:
the file-level check is easy to skip. A caller reaching for
`json.load()` gets a dict in which a duplicated member has already been
silently collapsed to its last value, so a receipt that is invalid
because of a duplicate member name looks perfectly well-formed. That is
exactly how a one-line script of ours first mis-judged
`duplicate-member-name.json`. Any path that reads an untrusted receipt
must go through `first_duplicate_member` first, and this tool is the
place that guarantee lives.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import aer1_receipt_verifier as verifier  # noqa: E402


def judge(path):
    """Full report for one receipt file, including file-level checks."""
    with open(path, encoding="utf-8") as handle:
        text = handle.read()

    report = {"path": path, "file_checks": [], "structural": [],
              "binding": [], "reference_profile": [], "disinterested": [],
              "anchors": None, "id_verdict": None, "verdict": "REJECTED"}

    # Parse first: an unparsable file must be reported as such, and the
    # duplicate scan below can only run on text that parses at all.
    try:
        receipt = json.loads(text)
    except ValueError as exc:
        report["file_checks"].append("not valid JSON: %s" % exc)
        report["verdict"] = "REJECTED"
        return report

    duplicate = verifier.first_duplicate_member(text)
    if duplicate is not None:
        report["file_checks"].append("duplicate member name: %s" % duplicate)
        report["verdict"] = "REJECTED"
        return report

    if not isinstance(receipt, dict):
        report["file_checks"].append("receipt is not a JSON object")
        return report

    report["structural"] = verifier.core_check(receipt)
    try:
        report["binding"] = verifier.version_and_binding(receipt)[1]
    except Exception as exc:  # noqa: BLE001 - a malformed payload is a verdict
        report["binding"] = ["binding check raised: %s" % exc]
    try:
        report["reference_profile"] = verifier.reference_profile(receipt)
    except Exception as exc:  # noqa: BLE001
        report["reference_profile"] = ["reference profile raised: %s" % exc]
    try:
        report["disinterested"] = verifier.disinterested_tier(receipt)
    except Exception as exc:  # noqa: BLE001
        report["disinterested"] = ["disinterested tier raised: %s" % exc]

    try:
        report["anchors"] = verifier.anchor_report(receipt)
    except Exception as exc:  # noqa: BLE001
        report["anchors"] = {"error": str(exc)}
    try:
        report["id_verdict"] = verifier.id_verdict(receipt)
    except Exception as exc:  # noqa: BLE001
        report["id_verdict"] = "error: %s" % exc

    blocking = (report["file_checks"] or report["structural"] or
                report["binding"])
    report["verdict"] = "REJECTED" if blocking else "ACCEPTED"
    return report


def print_report(report):
    print("%s  ->  %s" % (os.path.basename(report["path"]), report["verdict"]))
    for group in ("file_checks", "structural", "binding",
                  "reference_profile", "disinterested"):
        for item in report[group]:
            print("    %-17s %s" % (group + ":", item))
    if isinstance(report.get("anchors"), dict) and "error" not in report["anchors"]:
        anchors = report["anchors"]
        print("    anchors:          present=%s evaluated=%s outcome=%s"
              % (anchors.get("present"), anchors.get("evaluated"),
                 anchors.get("outcome")))
    elif isinstance(report.get("anchors"), dict):
        print("    anchors:          %s" % report["anchors"].get("error"))
    if report.get("id_verdict"):
        print("    id_verdict:       %s" % report["id_verdict"])


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--receipt")
    group.add_argument("--dir")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--expect", choices=["ACCEPTED", "REJECTED"],
                        help="with --dir, assert every receipt gets this verdict")
    args = parser.parse_args()

    paths = ([args.receipt] if args.receipt else
             sorted(os.path.join(args.dir, name)
                    for name in os.listdir(args.dir) if name.endswith(".json")))
    if not paths:
        print("no receipts found")
        return 2

    reports = [judge(path) for path in paths]

    if args.json:
        print(json.dumps({"count": len(reports), "reports": reports}, indent=1))
    elif args.receipt:
        print_report(reports[0])
    else:
        accepted = sum(1 for r in reports if r["verdict"] == "ACCEPTED")
        print("%d receipts  %d accepted  %d rejected"
              % (len(reports), accepted, len(reports) - accepted))
        for report in reports:
            if report["verdict"] == "REJECTED":
                reason = (report["file_checks"] or report["structural"] or
                          report["binding"] or ["?"])[0]
                print("    %-32s %s" % (os.path.basename(report["path"]), reason))

    if args.receipt:
        return 0 if reports[0]["verdict"] == "ACCEPTED" else 1
    if args.expect:
        expected = args.expect
        wrong = [r for r in reports if r["verdict"] != expected]
        if wrong:
            print("expected %s for all, %d differ" % (expected, len(wrong)))
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
