#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Standalone re-check of docs/upstream-package/scitt-rfc9162.

Imports nothing from this project: the RFC 9162 fold is written here from the
text, so a disagreement means one of the two readings is wrong.

    python tools/check_scitt_vectors_standalone.py

Checks, for every vector in manifest.json:
  * leaf digest == SHA-256(leaf_input_hex)
  * folding the recorded path with (tree_size, leaf_index) reproduces
    reconstructed_root
  * VALID* vectors: root_true == reconstructed_root
  * fail-* vectors: root_true != reconstructed_root
  * the ambiguity vector additionally folds to the same root at alt_tree_size
  * SHA256SUMS matches every listed file byte-for-byte
Exit code 1 on any disagreement.
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.join(os.path.dirname(HERE), "docs", "upstream-package", "scitt-rfc9162")
H = lambda b: hashlib.sha256(b).digest()
LEAF = lambda data: hashlib.sha256(b"\x00" + data).digest()  # RFC 9162 leaf hash
NODE = lambda l, r: hashlib.sha256(b"\x01" + l + r).digest()


def fold(leaf, index, size, path):
    """RFC 9162 Section 2.1.3.2 style inclusion verification, written out."""
    fn, sn, r = index, size - 1, leaf
    for p in path:
        if fn & 1 or fn == sn:
            r = NODE(p, r)
            while not fn & 1 and fn:
                fn >>= 1
                sn >>= 1
        else:
            r = NODE(r, p)
        fn >>= 1
        sn >>= 1
    return r


def main():
    with open(os.path.join(PKG, "manifest.json"), encoding="utf-8") as fh:
        manifest = json.load(fh)
    ok, msgs = True, []
    for v in manifest["vectors"]:
        with open(os.path.join(PKG, v["dir"], "expected.json"), encoding="utf-8") as fh:
            exp = json.load(fh)
        leaf = LEAF(bytes.fromhex(exp["leaf_entry"]["leaf_input_hex"]))
        if leaf.hex() != exp["leaf_entry"]["digest_hex"]:
            ok = False; msgs.append("%s: leaf digest != SHA-256(leaf input)" % v["id"])
        path = [bytes.fromhex(h) for h in exp["inclusion_path"]]
        if exp["tree_size"] == 0:
            # RFC 9162 Section 2.1: MTH({}) = SHA-256(). Section 2.1.1 defines PATH
            # only for 0 <= m < n, so no leaf can sit in an empty tree: the root is
            # the empty-tree constant and the only correct verdict is a refusal.
            if exp["root_true"] != H(b"").hex():
                ok = False; msgs.append("%s: size 0 but root_true is not MTH({})" % v["id"])
            if exp["reconstructed_root"] != "":
                ok = False; msgs.append("%s: size 0 but a fold result is recorded" % v["id"])
            if exp["result"].startswith("VALID"):
                ok = False; msgs.append("%s: size 0 accepted a leaf" % v["id"])
            continue
        rec = fold(leaf, exp["leaf_index"], exp["tree_size"], path)
        if rec.hex() != exp["reconstructed_root"]:
            ok = False; msgs.append("%s: fold does not reproduce reconstructed_root" % v["id"])
        valid_class = exp["result"].startswith("VALID")
        if valid_class != (rec.hex() == exp["root_true"]):
            ok = False; msgs.append("%s: result %s contradicts the root comparison" % (v["id"], exp["result"]))
        alt = exp.get("alt_tree_size")
        if alt is not None:
            alt_root = fold(leaf, exp["leaf_index"], alt, path)
            if alt_root.hex() != exp["root_true"]:
                ok = False; msgs.append("%s: declared ambiguity does not reproduce at size %s" % (v["id"], alt))
            else:
                msgs.append("%s: ambiguity confirmed — size %s folds to the same root" % (v["id"], alt))
    with open(os.path.join(PKG, "SHA256SUMS"), encoding="utf-8") as fh:
        for line in fh.read().splitlines():
            if not line.strip():
                continue
            digest, rel = line.split("  ", 1)
            with open(os.path.join(PKG, rel), "rb") as fh2:
                if hashlib.sha256(fh2.read()).hexdigest() != digest:
                    ok = False; msgs.append("checksum mismatch: %s" % rel)
    msgs.append("vectors: %d" % len(manifest["vectors"]))
    for m in msgs:
        print("  " + m)
    print("VERDICT: %s" % ("CONSISTENT" if ok else "DISCREPANCY"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

