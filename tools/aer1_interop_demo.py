#!/usr/bin/env python3
"""One command that lets an outsider judge the whole interop claim.

This is the executable form of docs/AER1-EMIT-RESULT.md. It does three
things in sequence and prints the verdicts of two independent
implementations side by side:

  1. render our evidence package as AER-1 0.4 receipts;
  2. hand those receipts to the publisher's runner, which must be
     supplied at run time and is never vendored into this repository;
  3. re-run a fixed set of eight tamperings against both implementations,
     so that a reader can see the verdicts are real and not a stub.

Usage:

    python3 tools/aer1_interop_demo.py --kit /path/to/aer1/kit
    python3 tools/aer1_interop_demo.py --kit ... --package fixtures/clean.uibc
    python3 tools/aer1_interop_demo.py --kit ... --json /tmp/demo.json

Exit code 0 means every check behaved as documented: our emissions were
accepted by both implementations, no tampering was accepted by either
implementation, and there was no cross-implementation divergence. The
one default-versus-strict divergence (a dropped metadata_hash) is
reported separately, because it reflects the text disagreeing with the
shipped corpus rather than one implementation being wrong.
"""

import argparse
import base64
import copy
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_PACKAGE = os.path.join(ROOT, "fixtures", "clean.uibc")
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


def load(name, path):
    if not os.path.exists(path):
        raise SystemExit("missing module: %s" % path)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verdicts(receipt, mine, theirs):
    fields, binding = mine.core_check(receipt), mine.version_and_binding(receipt)[1]
    ours = "PASS" if not (fields or binding) else "FAIL"
    if theirs is None:
        return ours, "n/a", "n/a"
    theirs_fields = theirs.check(receipt)
    theirs_binding = theirs.check_version_and_binding(receipt)[1]
    pub = "PASS" if not (theirs_fields or theirs_binding) else "FAIL"
    mine.STRICT_METADATA = True
    try:
        strict = "PASS" if not mine.core_check(receipt) else "FAIL"
    finally:
        mine.STRICT_METADATA = False
    return ours, pub, strict


def tamperings(base):
    """The fixed set of eight, in the order the document lists them."""
    cases = [("untouched", copy.deepcopy(base))]

    receipt = copy.deepcopy(base)
    raw = bytearray(base64.b64decode(receipt["canonical_bytes"], validate=True))
    raw[0] ^= 0x01
    receipt["canonical_bytes"] = base64.b64encode(bytes(raw)).decode("ascii")
    cases.append(("flip one payload byte", receipt))

    receipt = copy.deepcopy(base)
    receipt["output_hash"] = "sha256:" + "0" * 64
    cases.append(("wrong output_hash", receipt))

    receipt = copy.deepcopy(base)
    receipt["provenance_class"] = "EXECUTED BY US"
    cases.append(("relabel provenance", receipt))

    receipt = copy.deepcopy(base)
    receipt["created_at"] = "2026-02-30T09:00:00.000Z"
    cases.append(("impossible date", receipt))

    receipt = copy.deepcopy(base)
    receipt.pop("metadata_hash", None)
    cases.append(("drop metadata_hash", receipt))

    receipt = copy.deepcopy(base)
    encoded = base64.b64encode(
        base64.b64decode(receipt["canonical_bytes"], validate=True)).decode("ascii")
    body, pad = encoded.rstrip("="), encoded[len(encoded.rstrip("=")):]
    index = ALPHABET.index(body[-1])
    receipt["canonical_bytes"] = body[:-1] + ALPHABET[index ^ 1] + pad
    cases.append(("non-canonical base64 pad bit", receipt))

    receipt = copy.deepcopy(base)
    receipt["id"] = receipt["id"] + "\n"
    cases.append(("id with trailing newline", receipt))
    return cases


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--kit", required=True,
                        help="AER-1 corpus directory containing base/conformance.py")
    parser.add_argument("--package", default=DEFAULT_PACKAGE)
    parser.add_argument("--json", default=None)
    args = parser.parse_args()

    emit = load("emit_aer1_receipts", os.path.join(HERE, "emit_aer1_receipts.py"))
    mine = load("aer1_receipt_verifier", os.path.join(HERE, "aer1_receipt_verifier.py"))
    runner = os.path.join(args.kit, "base", "conformance.py")
    theirs = load("publisher_runner", runner)

    manifest, entries = emit.load_package(args.package)
    receipts = [emit.build_receipt(manifest, entry, i, args.package, args.package)
                for i, entry in enumerate(entries)]

    print("package : %s" % args.package)
    print("entries : %d   receipts: %d   schema: %s"
          % (len(entries), len(receipts), receipts[0]["receipt_schema_version"]))
    print("publisher runner: %s" % runner)
    print()

    emitted = []
    ok = True
    for receipt in receipts:
        ours, pub, _ = verdicts(receipt, mine, theirs)
        emitted.append({"id": receipt["id"], "ours": ours, "theirs": pub})
        ok = ok and ours == "PASS" and pub == "PASS"
    print("emit acceptance: %d/%d accepted by both"
          % (sum(1 for e in emitted if e["ours"] == e["theirs"] == "PASS"), len(emitted)))
    print()

    print("%-38s %-8s %-8s %-12s" % ("tampering", "ours", "theirs", "ours-strict"))
    rows = []
    for name, receipt in tamperings(receipts[0]):
        ours, pub, strict = verdicts(receipt, mine, theirs)
        rows.append({"case": name, "ours": ours, "theirs": pub, "ours_strict": strict})
        print("%-38s %-8s %-8s %-12s" % (name, ours, pub, strict))

    # Two different things get counted, and they are not the same kind of fact.
    # A cross-implementation divergence would mean one of us is wrong. A
    # default-versus-strict divergence only means the text and the shipped
    # corpus disagree, which is a property of the specification, not of a bug.
    cross = [r for r in rows if r["ours"] != r["theirs"]]
    modes = [r for r in rows if r["ours"] != r["ours_strict"]]

    for row in rows:
        if row["case"] != "untouched" and row["ours"] == "PASS":
            if row["case"] != "drop metadata_hash":
                ok = False
    ok = ok and not cross

    print()
    print("cross-implementation divergence: %s"
          % ("none" if not cross else ", ".join(
              "%s (%s vs %s)" % (d["case"], d["ours"], d["theirs"]) for d in cross)))
    print("default-vs-strict divergence   : %s"
          % ("none" if not modes else ", ".join(
              "%s (%s vs %s)" % (d["case"], d["ours"], d["ours_strict"]) for d in modes)))

    if args.json:
        payload = {
            "package": args.package,
            "entries": len(entries),
            "schema": receipts[0]["receipt_schema_version"],
            "emitted": emitted,
            "tamperings": rows,
            "cross_implementation_divergence": cross,
            "default_vs_strict_divergence": modes,
            "ok": ok,
        }
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        print("json: %s" % args.json)

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
