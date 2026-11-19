#!/usr/bin/env python3
"""Recompute another project's SCITT COSE vectors with our own tree code.

The IETF SCITT WG `examples` repository carries a vector set contributed by
`action-state-group/scitt-cose`. Each vector ships `expected.json` with
`leaf_entry`, `leaf_index`, `tree_size`, `inclusion_path` and
`reconstructed_root`. Those fields are pure hash-tree material: no COSE
library is needed to check whether a path folds to the stated root.

This tool does exactly that, using `uibc_core.merkle` only. It is the reverse
direction of `docs/external-review/EXTERNAL-NODE-001.md`: there an outsider
ran our code; here we run arithmetic over an outsider's committed bytes.

A disagreement is not a failure of theirs or of ours — it is a finding, and
the report this script prints says which numbers differ so a human can decide.

Usage:
    python tools/crosscheck_scitt_cose_vectors.py --dir /path/to/test-vectors/scitt-cose
"""

import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from uibc_core import merkle  # noqa: E402


def root_from_path(leaf, index, size, path):
    if size <= 0 or index >= size:
        return None
    fn, sn, r = index, size - 1, leaf
    for p in path:
        if fn % 2 == 1 or fn == sn:
            r = merkle.node_hash(p, r)
            while fn % 2 == 0 and fn != 0:
                fn >>= 1
                sn >>= 1
        else:
            r = merkle.node_hash(r, p)
        fn >>= 1
        sn >>= 1
    return r


def collect(dirpath):
    """Yield (id, expected-dict) for every expected.json under v1/."""
    v1 = os.path.join(dirpath, "v1")
    if not os.path.isdir(v1):
        raise SystemExit("no v1/ under %s" % dirpath)
    for name in sorted(os.listdir(v1)):
        p = os.path.join(v1, name, "expected.json")
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as fh:
                yield name, json.load(fh)


# What each vector class requires of the fold. A tampered path MUST fold away
# from the stated root; a valid one MUST fold onto it. The other negatives are
# informational here: their failures live in signature or VDS handling, which
# this tool does not model.
MUST_MATCH = {"VALID"}
MUST_DIFFER = {"INVALID_INCLUSION_PATH", "INVALID_TREE_SIZE", "INVALID_LEAF_INDEX"}


def check(dirpath):
    rows, mismatches = [], 0
    for vid, exp in collect(dirpath):
        # `leaf_entry` is the digest of the COSE_Sign1 bytes, i.e. the leaf
        # *input*; RFC 9162 leaf hash = SHA-256(0x00 || leaf_input).
        leaf = merkle.leaf_hash(bytes.fromhex(exp["leaf_entry"]))
        proof = [bytes.fromhex(h) for h in exp["inclusion_path"]]
        rec = root_from_path(leaf, exp["leaf_index"], exp["tree_size"], proof)
        rec_hex = rec.hex() if rec else ""
        stated = exp["reconstructed_root"]
        same = rec_hex == stated
        result = exp.get("result", "?")
        if result in MUST_MATCH:
            ok = same
        elif result in MUST_DIFFER:
            ok = not same
        else:
            ok = True  # not adjudicated here; reported for a human
        if not ok:
            mismatches += 1
        rows.append((vid, result, same, ok, rec_hex, stated))
    return rows, mismatches


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", required=True, help="path to test-vectors/scitt-cose")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    rows, mismatches = check(a.dir)
    if a.json:
        print(json.dumps({"vectors": len(rows), "mismatches": mismatches,
                          "rows": [{"id": r[0], "result": r[1], "fold_matches": r[2],
                                    "class_ok": r[3], "folded_root": r[4], "stated_root": r[5]}
                                   for r in rows]},
                         indent=2))
    else:
        for vid, result, same, ok, folded, stated in rows:
            verdict = ("fold==stated" if same else "fold differs") + ("" if ok else "  <-- VIOLATES ITS CLASS")
            print("%-28s %-24s %s" % (vid, result, verdict))
            if not ok:
                print("    folded: %s" % folded)
                print("    stated: %s" % stated)
        print("vectors: %d  mismatches: %d" % (len(rows), mismatches))
        print("VERDICT: %s" % ("THEIR PATHS FOLD TO THEIR STATED ROOTS"
                               if mismatches == 0 else "DISAGREEMENT - see rows above"))
    return 0 if mismatches == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
