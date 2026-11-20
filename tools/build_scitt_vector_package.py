#!/usr/bin/env python3
"""Build a SCITT-shaped test-vector package for the RFC 9162 SHA-256 tree layer.

Why this exists: the IETF SCITT WG `examples` repository already carries a
vector set (``test-vectors/scitt-cose``) contributed by another project, whose
README states the rule this package follows:

    A mismatch against your implementation is exactly the report the authors
    want - agreement on rejection is as load-bearing as agreement on
    acceptance.

This package covers **only the hash-tree and inclusion-path layer**. It
deliberately does not carry COSE_Sign1 statement or receipt bytes: this
repository has no COSE library installed, so it cannot generate signed bytes
honestly. The gap is declared in the package README rather than filled with
something unverifiable.

Shape copied from ``test-vectors/scitt-cose``: a ``v1/<case>/`` directory per
vector, each with ``expected.json``; a ``manifest.json`` inlining each expected
block; a ``SHA256SUMS``; and a ``.gitattributes`` that pins vector files as
non-normalized so the checksums reproduce on any platform.

Every vector is self-checking: from ``leaf_entry.leaf_input_hex``,
``leaf_index``, ``tree_size`` and ``inclusion_path`` a reader reconstructs a
root and compares it with ``root_true``. Positive vectors must match; negative
vectors must not.

Usage:
    python tools/build_scitt_vector_package.py           # build + verify
    python tools/build_scitt_vector_package.py --check   # verify only
"""

import argparse
import hashlib
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from uibc_core import merkle  # noqa: E402

OUT = os.path.join(REPO, "docs", "upstream-package", "scitt-rfc9162")


def _leaf_text(vector_id, i):
    return ("scitt-rfc9162 test vectors v1 :: %s :: leaf %d" % (vector_id, i)).encode()


def _leaves(vector_id, size):
    return [merkle.leaf_hash(_leaf_text(vector_id, i)) for i in range(size)]


def root_from_path(leaf, index, size, path):
    """RFC 9162 SHA-256 inclusion-path verification, returning the root.

    Written out rather than imported so a reader of the package can reproduce
    it in any language without our code.
    """
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


# id, tree_size, leaf_index, tamper, expected_result, description
CASES = [
    ("valid-tree8-index2", 8, 2, None, "VALID",
     "Happy path: tree_size=8, leaf_index=2; the reconstructed root equals root_true."),
    ("valid-tree4-index0", 4, 0, None, "VALID",
     "Happy path: tree_size=4, leaf_index=0 (left edge)."),
    ("fail-tampered-path", 8, 2, "path", "INVALID_INCLUSION_PATH",
     "The first sibling is replaced with 32 zero bytes; reconstructed root differs."),
    ("fail-wrong-tree-size", 8, 2, "size", "INVALID_TREE_SIZE",
     "tree_size declared one smaller than the path assumes; proof length is one short."),
    ("fail-wrong-leaf-index", 8, 2, "index", "INVALID_LEAF_INDEX",
     "The path belongs to a different leaf index of the same tree."),
]


def _expected(cid, size, index, tamper, result, desc):
    leaves = _leaves(cid, size)
    true_root = merkle.root_hash(leaves)
    proof = list(merkle.audit_path(leaves, index))
    stated_size = size
    if tamper == "path":
        proof[0] = b"\x00" * 32
    elif tamper == "size":
        stated_size = size - 1
        proof = proof[:-1]
    elif tamper == "index":
        proof = list(merkle.audit_path(leaves, (index + 1) % size))
    reconstructed = root_from_path(leaves[index], index, stated_size, proof)
    exp = {
        "description": desc,
        "leaf_entry": {
            "leaf_input_hex": _leaf_text(cid, index).hex(),
            "leaf_input_ascii": _leaf_text(cid, index).decode(),
            "digest_hex": leaves[index].hex(),
            "definition": "SHA-256 of the leaf input bytes, hex-encoded",
        },
        "leaf_index": index,
        "tree_size": stated_size,
        "inclusion_path": [h.hex() for h in proof],
        "root_true": true_root.hex(),
        "reconstructed_root": reconstructed.hex() if reconstructed else "",
        "result": result,
    }
    return exp


def _write_gitattributes(out):
    ga = os.path.join(out, ".gitattributes")
    with open(ga, "w", encoding="utf-8") as fh:
        fh.write("# Pin vector files as non-normalized so SHA256SUMS reproduces\n")
        fh.write("# byte-for-byte on any platform, including core.autocrlf=true.\n")
        fh.write("v1/** -text\nmanifest.json -text\nREADME.md -text\nSHA256SUMS -text\n")


def build(out=OUT):
    os.makedirs(out, exist_ok=True)
    written, vectors = [], []
    for cid, size, index, tamper, result, desc in CASES:
        exp = _expected(cid, size, index, tamper, result, desc)
        d = os.path.join(out, "v1", cid)
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, "expected.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(exp, fh, indent=2, sort_keys=True)
            fh.write("\n")
        written.append(p)
        vectors.append({
            "id": cid, "dir": "v1/%s" % cid, "description": desc,
            "expected_result": result,
            "expected": {k: v for k, v in exp.items() if k != "description"},
        })

    manifest = {
        "version": "v1",
        "stability": "append-only",
        "scope_note": ("Covers the RFC 9162 SHA-256 hash-tree and inclusion-path layer "
                       "only. No COSE_Sign1 statement or receipt bytes are included; "
                       "see README 'What this set does not cover'."),
        "leaf_entry_definition": ("SHA-256 of the leaf input bytes, hex-encoded. Leaf "
                                  "inputs here are plain ASCII strings rather than "
                                  "COSE_Sign1 digests, so the tree algebra can be "
                                  "checked without a COSE library."),
        "tree_construction": ("leaves[i] = SHA-256(leaf_input_i); node_hash = "
                              "SHA-256(left||right); split = largest power of two below "
                              "the subtree size (RFC 9162); leaf_input_i = "
                              "'scitt-rfc9162 test vectors v1 :: <vector-id> :: leaf <i>'"),
        "reconstruction_rule": ("Fold the path over leaf_index with tree_size using RFC 9162 "
                                "SHA-256 verification; the result must equal root_true for "
                                "VALID vectors and must differ for the three fail-* vectors."),
        "vectors": vectors,
    }
    mp = os.path.join(out, "manifest.json")
    with open(mp, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
        fh.write("\n")
    written.append(mp)

    ga = os.path.join(out, ".gitattributes")
    with open(ga, "w", encoding="utf-8") as fh:
        fh.write("# Pin vector files as non-normalized so SHA256SUMS reproduces\n")
        fh.write("# byte-for-byte on any platform, including core.autocrlf=true.\n")
        fh.write("v1/** -text\nmanifest.json -text\nREADME.md -text\nSHA256SUMS -text\n")

    _write_gitattributes(out)
    sums = os.path.join(out, "SHA256SUMS")
    lines = []
    for p in written:
        rel = os.path.relpath(p, out).replace(os.sep, "/")
        with open(p, "rb") as fh:
            lines.append("%s  %s" % (hashlib.sha256(fh.read()).hexdigest(), rel))
    with open(sums, "w", encoding="utf-8") as fh:
        fh.write("\n".join(sorted(lines)) + "\n")
    return out, len(vectors)


def verify(out=OUT):
    ok, msgs = True, []
    with open(os.path.join(out, "manifest.json"), encoding="utf-8") as fh:
        manifest = json.load(fh)
    for v in manifest["vectors"]:
        with open(os.path.join(out, v["dir"], "expected.json"), encoding="utf-8") as fh:
            exp = json.load(fh)
        leaf = merkle.leaf_hash(bytes.fromhex(exp["leaf_entry"]["leaf_input_hex"]))
        if leaf.hex() != exp["leaf_entry"]["digest_hex"]:
            ok = False
            msgs.append("%s: leaf digest does not match leaf input" % v["id"])
        rec = root_from_path(leaf, exp["leaf_index"], exp["tree_size"],
                             [bytes.fromhex(h) for h in exp["inclusion_path"]])
        rec_hex = rec.hex() if rec else ""
        if rec_hex != exp["reconstructed_root"]:
            ok = False
            msgs.append("%s: recorded reconstructed_root is not reproducible" % v["id"])
        same = rec_hex == exp["root_true"]
        is_valid = exp["result"].startswith("VALID")
        if is_valid != same:
            ok = False
            msgs.append("%s: result %s but root comparison says %s"
                        % (v["id"], exp["result"], "equal" if same else "differ"))
    with open(os.path.join(out, "SHA256SUMS"), encoding="utf-8") as fh:
        for line in fh.read().splitlines():
            if not line.strip():
                continue
            digest, rel = line.split("  ", 1)
            with open(os.path.join(out, rel), "rb") as fh2:
                if hashlib.sha256(fh2.read()).hexdigest() != digest:
                    ok = False
                    msgs.append("checksum mismatch: %s" % rel)
    msgs.append("vectors: %d" % len(manifest["vectors"]))
    return ok, msgs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)
    if not a.check:
        out, n = build(a.out)
        print("built %d vectors into %s" % (n, out))
    ok, msgs = verify(a.out)
    for m in msgs:
        print("  " + m)
    print("VERDICT: %s" % ("CONSISTENT" if ok else "DISCREPANCY"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
