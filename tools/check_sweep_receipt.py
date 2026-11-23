#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check a sweep receipt against the instance file it names.

A sweep prints "32,896 instances, 0 disagreements". A line in a log is not
evidence a stranger can recompute, so `verify_tree_algebra_exhaustive.py --receipt`
writes a small file binding those counts to a digest of the dump. This is the check
for that file. It refuses a receipt whose counts disagree with the dump, whose
digest disagrees with the dump bytes, whose counts are impossible for its own
`max_size`, and one that merely repeats a number it was told.

What it cannot do is prove a sweep was run, or that it was run only once. It is
stated in the receipt itself; a checker that pretended otherwise would be the
attestation-that-asserts shape this repository exists to refuse.

    python3 tools/check_sweep_receipt.py receipt.json --dump instances.json
    python3 tools/check_sweep_receipt.py --self-test
"""
import argparse
import hashlib
import json
import os
import sys

CONTRACT = "uibc-sweep-receipt/1"


def expected_counts(max_size):
    inc = max_size * (max_size + 1) // 2
    cons = max_size * (max_size + 1) // 2
    return inc, cons


def check(receipt, dump_path=None):
    ok, msgs = True, []

    def bad(m):
        nonlocal ok
        ok = False
        msgs.append(m)

    if receipt.get("contract_version") != CONTRACT:
        bad("contract_version is %r, expected %r" % (receipt.get("contract_version"), CONTRACT))
    size = receipt.get("max_size")
    if not isinstance(size, int) or size < 1:
        bad("max_size is %r, not a positive integer" % (size,))
        return ok, msgs
    inc, cons = receipt.get("inclusion_instances"), receipt.get("consistency_instances")
    want_inc, want_cons = expected_counts(size)
    if inc != want_inc:
        bad("inclusion_instances is %r; a full sweep of sizes 1..%d has %d"
            % (inc, size, want_inc))
    if cons != want_cons:
        bad("consistency_instances is %r; every 1 <= m <= n <= %d is %d pairs"
            % (cons, size, want_cons))
    if not isinstance(receipt.get("disagreements"), int) or receipt["disagreements"] < 0:
        bad("disagreements is %r" % (receipt.get("disagreements"),))
    sha = receipt.get("dump_sha256")
    if not (isinstance(sha, str) and len(sha) == 64 and all(c in "0123456789abcdef" for c in sha)):
        bad("dump_sha256 is not 64 lowercase hex characters")
    nbytes = receipt.get("dump_bytes")
    if not isinstance(nbytes, int) or nbytes <= 0:
        bad("dump_bytes is %r; a receipt without the size of the file it names names nothing"
            % (nbytes,))

    if dump_path:
        if not os.path.isfile(dump_path):
            bad("dump not found: %s" % dump_path)
            return ok, msgs
        raw = open(dump_path, "rb").read()
        if len(raw) != nbytes:
            bad("dump is %d bytes, receipt says %r" % (len(raw), nbytes))
        if hashlib.sha256(raw).hexdigest() != sha:
            bad("dump digest does not match the receipt")
        instances = json.loads(raw)
        got_inc = sum(1 for i in instances if i.get("kind") == "inclusion")
        got_cons = sum(1 for i in instances if i.get("kind") == "consistency")
        if (got_inc, got_cons) != (inc, cons):
            bad("the dump holds %d inclusion and %d consistency instances; receipt says %r / %r"
                % (got_inc, got_cons, inc, cons))
    return ok, msgs


def self_test():
    receipt = {
        "contract_version": CONTRACT, "max_size": 4,
        "inclusion_instances": 10, "consistency_instances": 10,
        "disagreements": 0, "dump_bytes": 876, "dump_sha256": "0" * 64,
    }
    ok, msgs = check(receipt)
    if not ok:
        print("FAIL: a consistent receipt was refused: %s" % msgs[:2])
        return 1
    print("self-test: a consistent receipt passes")

    cases = []
    cases.append(("counts that are impossible for the stated max_size",
                  dict(receipt, inclusion_instances=11)))
    cases.append(("consistency count that is impossible for the stated max_size",
                  dict(receipt, consistency_instances=9)))
    cases.append(("a digest that is not a digest", dict(receipt, dump_sha256="nope")))
    cases.append(("no dump_bytes", dict(receipt, dump_bytes=None)))
    cases.append(("a negative disagreement count", dict(receipt, disagreements=-1)))
    cases.append(("an unknown contract", dict(receipt, contract_version="uibc-sweep-receipt/2")))
    cases.append(("a max_size that does not fit the recorded counts",
                  dict(receipt, max_size=5)))

    failures = 0
    for name, doc in cases:
        ok, msgs = check(doc)
        if ok:
            print("FAIL: not refused -- %s" % name)
            failures += 1
        else:
            print("self-test caught: %s — %s" % (name, msgs[0]))

    # and against real bytes
    import tempfile
    tmp = tempfile.mkdtemp(prefix="sweep-receipt-")
    try:
        path = os.path.join(tmp, "dump.json")
        body = (b'[{"kind":"inclusion"},{"kind":"consistency"}]')
        open(path, "wb").write(body)
        r = dict(receipt, dump_bytes=len(body), dump_sha256=hashlib.sha256(body).hexdigest(),
                 max_size=1, inclusion_instances=1, consistency_instances=1)
        ok, msgs = check(r, path)
        if ok:
            print("self-test: a receipt matching its dump passes")
        else:
            print("FAIL: a matching dump was refused: %s" % msgs[:2])
            failures += 1
        tampered = dict(r, dump_sha256="f" * 64)
        ok, msgs = check(tampered, path)
        if ok:
            print("FAIL: a digest that does not match the dump was accepted")
            failures += 1
        else:
            print("self-test caught: a digest that does not match the dump — %s" % msgs[0])
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    return 1 if failures else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("receipt", nargs="?")
    ap.add_argument("--dump", default=None)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return self_test()
    if not a.receipt:
        ap.error("give a receipt path, or --self-test")
    ok, msgs = check(json.load(open(a.receipt, encoding="utf-8")), a.dump)
    for m in msgs:
        print("- " + m)
    print("VERDICT: %s" % ("SWEEP-RECEIPT-CONSISTENT" if ok else "SWEEP-RECEIPT-REFUSED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
