#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Standalone re-check of docs/upstream-package/scitt-rfc9162.

Imports nothing from this project: the RFC 9162 fold is written here from the
text, so a disagreement means one of the two readings is wrong.

    python tools/check_scitt_vectors_standalone.py
    python tools/check_scitt_vectors_standalone.py --self-test

Checks, for every vector in manifest.json:
  * leaf digest == SHA-256(leaf_input_hex)
  * folding the recorded path with (tree_size, leaf_index) reproduces
    reconstructed_root
  * size 0: root_true == MTH({}) = SHA-256(), reconstructed_root empty, and no
    VALID verdict (RFC 9162 Section 2.1 and Section 2.1.1)
  * VALID* vectors: root_true == reconstructed_root
  * fail-* vectors: root_true != reconstructed_root
  * the ambiguity vector additionally folds to the same root at alt_tree_size
  * consistency vectors (kind=consistency): rebuilding both roots from old_root
    and the recorded consistency_path reproduces reconstructed_old_root /
    reconstructed_new_root, and VALID matches that rebuild
  * SHA256SUMS matches every listed file byte-for-byte

--self-test additionally proves these checks are not vacuous: seven deliberately
broken vectors (all-zero empty root, a filled-in size-0 fold result, a size-0
vector marked VALID, a leaf digest detached from its input, a consistency vector
with a zeroed old root, one with a proof node too many, and one with the two
sizes in the wrong order) are fed through the same code and must each be
caught. Exit 1 if any probe slips through.
Exit code 1 on any disagreement.
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.join(os.path.dirname(HERE), "docs", "upstream-package", "scitt-rfc9162")
SELF_TEST = "--self-test" in sys.argv
PASS_NOTE = []  # confirmations that are not findings (the ambiguity pair)
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


def _split(n):
    k = 1
    while k * 2 < n:
        k *= 2
    return k


def reconstruct_consistency(m, n, old_root, proof):
    """Rebuild (old_root, new_root) from the proof, or None.

    Written from the RFC 6962 Section 2.1.2 recursion, in the order the recursion
    appends nodes. A short proof, a long proof and a proof for the wrong size
    relation all fall out structurally instead of arithmetically.
    """
    if m < 1 or n < m:
        return None
    if m == n:
        return (old_root, old_root) if not proof else None
    p = list(proof)

    def walk(a, b, pos, seeded):
        if a == b:
            if seeded:
                return old_root, old_root, pos
            if pos >= len(p):
                return None
            return p[pos], p[pos], pos + 1
        k = _split(b)
        if a <= k:
            res = walk(a, k, pos, seeded)
            if res is None or res[2] >= len(p):
                return None
            return res[0], NODE(res[1], p[res[2]]), res[2] + 1
        res = walk(a - k, b - k, pos, False)
        if res is None or res[2] >= len(p):
            return None
        return NODE(p[res[2]], res[0]), NODE(p[res[2]], res[1]), res[2] + 1

    res = walk(m, n, 0, True)
    if res is None or res[2] != len(p):
        return None
    return res[0], res[1]


def check_one(cid, exp, fail):
    """Every rule this checker enforces, for one vector. Shared with --self-test."""
    if exp.get("kind") == "consistency":
        # RFC 6962 Section 2.1.2 defines SUBPROOF for 1 <= m <= n; the m = 0 case is
        # genuinely unspecified and is not carried as a vector (see manifest
        # underspecified_inputs), so this checker refuses it rather than guessing.
        rec = reconstruct_consistency(exp["old_size"], exp["new_size"],
                                      bytes.fromhex(exp["old_root"]),
                                      [bytes.fromhex(h) for h in exp["consistency_path"]])
        ro = rec[0].hex() if rec else ""
        rn = rec[1].hex() if rec else ""
        if (ro != exp["reconstructed_old_root"]) or (rn != exp["reconstructed_new_root"]):
            fail("%s: consistency reconstruction is not reproducible" % cid)
        if exp["result"].startswith("VALID") != (ro == exp["old_root"] and rn == exp["new_root"]):
            fail("%s: result %s contradicts the consistency fold" % (cid, exp["result"]))
        return
    leaf = LEAF(bytes.fromhex(exp["leaf_entry"]["leaf_input_hex"]))
    if leaf.hex() != exp["leaf_entry"]["digest_hex"]:
        fail("%s: leaf digest != SHA-256(leaf input)" % cid)
    path = [bytes.fromhex(h) for h in exp["inclusion_path"]]
    if exp["tree_size"] == 0:
        # RFC 9162 Section 2.1: MTH({}) = SHA-256(). Section 2.1.1 defines PATH
        # only for 0 <= m < n, so no leaf can sit in an empty tree: the root is
        # the empty-tree constant and the only correct verdict is a refusal.
        if exp["root_true"] != H(b"").hex():
            fail("%s: size 0 but root_true is not MTH({})" % cid)
        if exp["reconstructed_root"] != "":
            fail("%s: size 0 but a fold result is recorded" % cid)
        if exp["result"].startswith("VALID"):
            fail("%s: size 0 accepted a leaf" % cid)
        return
    rec = fold(leaf, exp["leaf_index"], exp["tree_size"], path)
    if rec.hex() != exp["reconstructed_root"]:
        fail("%s: fold does not reproduce reconstructed_root" % cid)
    valid_class = exp["result"].startswith("VALID")
    if valid_class != (rec.hex() == exp["root_true"]):
        fail("%s: result %s contradicts the root comparison" % (cid, exp["result"]))
    alt = exp.get("alt_tree_size")
    if alt is not None:
        alt_root = fold(leaf, exp["leaf_index"], alt, path)
        if alt_root.hex() != exp["root_true"]:
            fail("%s: declared ambiguity does not reproduce at size %s" % (cid, alt))
        else:
            PASS_NOTE.append("%s: ambiguity confirmed — size %s folds to the same root" % (cid, alt))


def main():
    with open(os.path.join(PKG, "manifest.json"), encoding="utf-8") as fh:
        manifest = json.load(fh)
    ok, msgs = True, []
    def fail(m):
        nonlocal ok
        ok = False
        msgs.append(m)

    for v in manifest["vectors"]:
        with open(os.path.join(PKG, v["dir"], "expected.json"), encoding="utf-8") as fh:
            exp = json.load(fh)
        check_one(v["id"], exp, fail)
    msgs.extend(PASS_NOTE)

    if SELF_TEST:
        # A checker that cannot fail its own mutations is decoration. Four
        # probes: the empty-tree constant, a size-0 fold result, a size-0
        # acceptance, and a leaf digest detached from its input.
        with open(os.path.join(PKG, "v1", "fail-empty-tree", "expected.json"),
                  encoding="utf-8") as fh:
            base = json.load(fh)
        valid_id = next(v for v in manifest["vectors"]
                        if v["expected_result"].startswith("VALID"))
        with open(os.path.join(PKG, valid_id["dir"], "expected.json"), encoding="utf-8") as fh:
            valid_base = json.load(fh)
        valid_tampered = dict(valid_base)
        valid_tampered["leaf_entry"] = dict(valid_base["leaf_entry"])
        valid_tampered["leaf_entry"]["digest_hex"] = "00" * 32
        probes = [
            ("empty root replaced by an all-zero digest", dict(base, root_true="00" * 32)),
            ("size-0 fold result filled in",
             dict(base, reconstructed_root=base["leaf_entry"]["digest_hex"])),
            ("size-0 vector marked VALID", dict(base, result="VALID")),
            ("leaf digest no longer matches its leaf input", valid_tampered),
        ]
        for label, tampered in probes:
            caught = []
            check_one("self-test", tampered, caught.append)
            if caught:
                msgs.append("self-test caught: %s — %s" % (label, caught[0]))
            else:
                ok = False
                msgs.append("self-test FAILED to catch: %s" % label)

        # The same discipline for the consistency half: three mutations on a
        # genuine vector, each of which a root-comparing-only checker would miss.
        cons_id = next(v for v in manifest["vectors"]
                       if v.get("kind") == "consistency"
                       and v["expected_result"] == "VALID"
                       and len(v["expected"]["consistency_path"]) >= 2)
        with open(os.path.join(PKG, cons_id["dir"], "expected.json"), encoding="utf-8") as fh:
            cons_base = json.load(fh)
        cons_probes = [
            ("consistency old_root replaced by zeros",
             dict(cons_base, old_root="00" * 32)),
            ("consistency proof one node too long",
             dict(cons_base, consistency_path=list(cons_base["consistency_path"]) + ["00" * 32])),
            ("consistency sizes put in the wrong order",
             dict(cons_base, old_size=cons_base["new_size"], new_size=cons_base["old_size"])),
        ]
        for label, tampered in cons_probes:
            caught = []
            check_one("self-test", tampered, caught.append)
            if caught:
                msgs.append("self-test caught: %s — %s" % (label, caught[0]))
            else:
                ok = False
                msgs.append("self-test FAILED to catch: %s" % label)
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

