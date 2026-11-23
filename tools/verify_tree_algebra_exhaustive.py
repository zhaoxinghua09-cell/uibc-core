#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Sweep the whole tree algebra, not the 55 shapes that were chosen.

The committed corpus is a hand-picked set: it proves that *these* shapes work.
This sweep answers the neighbouring question — whether every shape up to a bound
works — for both primitives:

  inclusion : every (size, index) with 1 <= size <= MAX, 0 <= index < size
  consistency: every (m, n) with 1 <= m <= n <= MAX

Generation comes from uibc_core (the shipped implementation). Verification comes
from tools/check_scitt_vectors_standalone.py, which imports nothing from
uibc_core, so a disagreement is a real disagreement between two readings rather
than a tautology.

    python tools/verify_tree_algebra_exhaustive.py --max-size 64
    python tools/verify_tree_algebra_exhaustive.py --max-size 64 --dump inst.json

`--dump` writes the instances for tools/verify_tree_algebra_exhaustive.mjs, so a
second language re-derives every one of them from the recorded bytes alone.
Exit 1 on any disagreement; the counts are printed either way.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from uibc_core import merkle  # noqa: E402
import tools.check_scitt_vectors_standalone as ind  # noqa: E402
from tools.build_scitt_vector_package import _consistency_proof  # noqa: E402


def leaves_for(size):
    return [merkle.leaf_hash(b"sweep leaf %d" % i) for i in range(size)]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-size", type=int, default=64)
    ap.add_argument("--dump", default=None, help="write instances for the node sweep")
    ap.add_argument("--receipt", default=None,
                    help="write a small receipt binding the instance counts to a digest of the dump")
    ap.add_argument("--self-test", action="store_true",
                    help="mutate one instance and require the sweep to catch it")
    a = ap.parse_args(argv)

    instances, bad = [], []
    inc_count = cons_count = 0

    for size in range(1, a.max_size + 1):
        leaves = leaves_for(size)
        root = merkle.root_hash(leaves)
        for index in range(size):
            path = list(merkle.audit_path(leaves, index))
            got = ind.fold(leaves[index], index, size, path)
            inc_count += 1
            if got != root:
                bad.append("inclusion size=%d index=%d" % (size, index))
            instances.append({
                "kind": "inclusion", "size": size, "index": index,
                "leaf_digest": leaves[index].hex(),
                "root": root.hex(), "path": [p.hex() for p in path],
            })

    for n in range(1, a.max_size + 1):
        leaves = leaves_for(n)
        new_root = merkle.root_hash(leaves)
        for m in range(1, n + 1):
            old_root = merkle.root_hash(leaves[:m])
            proof = [] if m == n else _consistency_proof(leaves[:n], m)
            rec = ind.reconstruct_consistency(m, n, old_root, list(proof))
            cons_count += 1
            if rec is None or rec[0] != old_root or rec[1] != new_root:
                bad.append("consistency m=%d n=%d" % (m, n))
            instances.append({
                "kind": "consistency", "m": m, "n": n,
                "old_root": old_root.hex(), "new_root": new_root.hex(),
                "proof": [p.hex() for p in proof],
            })

    print("inclusion instances  : %d (sizes 1..%d, every index)" % (inc_count, a.max_size))
    print("consistency instances: %d (every 1 <= m <= n <= %d)" % (cons_count, a.max_size))
    print("disagreements        : %d" % len(bad))
    for b in bad[:20]:
        print("  " + b)

    if a.dump:
        with open(a.dump, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(instances, fh)
        print("instances written    : %s" % a.dump)

    if a.receipt:
        # The sweep prints numbers; a number in a log is not evidence a stranger can
        # recompute. This binds the counts to the bytes that produced them: anyone can
        # re-run the sweep, dump, and compare, and nobody has to trust the log line.
        # The digest cannot be verified without the dump, and that is stated, because
        # a receipt that verifies itself proves nothing.
        digest = hashlib.sha256(open(a.dump, "rb").read()).hexdigest() if a.dump else None
        receipt = {
            "contract_version": "uibc-sweep-receipt/1",
            "max_size": a.max_size,
            "inclusion_instances": inc_count,
            "consistency_instances": cons_count,
            "disagreements": len(bad),
            "dump_bytes": os.path.getsize(a.dump) if a.dump else None,
            "dump_sha256": digest,
            "checked_by": "tools/check_sweep_receipt.py, which needs the dump to check anything",
            "note": "counts are this run's; the digest names the instance file they were counted "
                    "in. Re-running the sweep regenerates both, so a receipt is evidence that a "
                    "run happened and what shape it had, never that it was the only run.",
        }
        with open(a.receipt, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(receipt, fh, indent=2)
            fh.write("\n")
        print("receipt written      : %s" % a.receipt)

    if a.self_test:
        # A sweep that cannot fail its own mutation is a loop, not a check. Two
        # probes, one per primitive: a single path node zeroed, and a single proof
        # node zeroed, both well inside the swept range.
        caught = []
        probe_inc = dict(instances[0])
        if probe_inc["path"]:
            probe_inc["path"] = ["00" * 32] + probe_inc["path"][1:]
        else:
            # size 1 has an empty path; take a size-4 instance instead
            probe_inc = dict(next(i for i in instances
                                  if i["kind"] == "inclusion" and i["size"] == 4))
            probe_inc["path"] = ["00" * 32] + probe_inc["path"][1:]
        got = ind.fold(bytes.fromhex(probe_inc["leaf_digest"]), probe_inc["index"],
                       probe_inc["size"], [bytes.fromhex(h) for h in probe_inc["path"]])
        if got.hex() != probe_inc["root"]:
            caught.append("inclusion: zeroed path node no longer folds to the root")

        probe_cons = dict(next(i for i in instances
                               if i["kind"] == "consistency" and i["proof"]))
        probe_cons["proof"] = ["00" * 32] + probe_cons["proof"][1:]
        rec = ind.reconstruct_consistency(probe_cons["m"], probe_cons["n"],
                                          bytes.fromhex(probe_cons["old_root"]),
                                          [bytes.fromhex(h) for h in probe_cons["proof"]])
        if rec is None or rec[1].hex() != probe_cons["new_root"]:
            caught.append("consistency: zeroed proof node no longer rebuilds the new root")

        for c in caught:
            print("self-test caught: " + c)
        if len(caught) != 2:
            bad.append("self-test did not catch every probe")
            print("VERDICT: SELFTEST-FAILED")
            return 1

    print("VERDICT: %s" % ("SWEEP-AGREES" if not bad else "SWEEP-DISAGREES"))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
