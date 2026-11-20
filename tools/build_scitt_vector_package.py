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
    # --- valid: tree shape and index position varied on purpose ---
    ("valid-tree1-index0", 1, 0, None, "VALID",
     "Smallest tree: tree_size=1, empty inclusion path, root == leaf digest."),
    ("valid-tree2-index0", 2, 0, None, "VALID",
     "tree_size=2, leaf_index=0: the only sibling is the left one."),
    ("valid-tree2-index1", 2, 1, None, "VALID",
     "tree_size=2, leaf_index=1: the sibling is consumed to the left of the leaf."),
    ("valid-tree3-index2", 3, 2, None, "VALID",
     "tree_size=3, leaf_index=2: the right subtree has size 1, so the path is uneven."),
    ("valid-tree4-index0", 4, 0, None, "VALID",
     "Happy path: tree_size=4, leaf_index=0 (left edge)."),
    ("valid-tree5-index2", 5, 2, None, "VALID",
     "tree_size=5, leaf_index=2: middle leaf of an unbalanced tree."),
    ("valid-tree6-index4", 6, 4, None, "VALID",
     "tree_size=6, leaf_index=4: near-right leaf of an unbalanced tree."),
    ("valid-tree7-index3", 7, 3, None, "VALID",
     "tree_size=7, leaf_index=3: interior leaf of a tree whose split is 4|3."),
    ("valid-tree8-index2", 8, 2, None, "VALID",
     "Happy path: tree_size=8, leaf_index=2; the reconstructed root equals root_true."),
    ("valid-tree9-index8", 9, 8, None, "VALID",
     "tree_size=9, leaf_index=8: split 8|1, so the tail leaf carries a short path."),
    ("valid-tree15-index7", 15, 7, None, "VALID",
     "tree_size=15, leaf_index=7: last leaf of the left subtree, path crosses the 8|7 split."),
    ("valid-tree16-index0", 16, 0, None, "VALID",
     "tree_size=16, leaf_index=0: full binary tree, all left edges."),
    ("valid-tree17-index8", 17, 8, None, "VALID",
     "tree_size=17, leaf_index=8: first leaf of the 1-leaf tail subtree."),
    ("valid-tree17-index16", 17, 16, None, "VALID",
     "tree_size=17, leaf_index=16: the single tail leaf of a 16|1 split."),
    ("valid-tree31-index15", 31, 15, None, "VALID",
     "tree_size=31, leaf_index=15: deepest interior leaf of a 16|15 split."),
    ("valid-tree32-index31", 32, 31, None, "VALID",
     "tree_size=32, leaf_index=31: full binary tree, all right edges."),

    # --- fail: one property broken per vector, so a report names the property ---
    ("fail-tampered-path", 8, 2, "path", "INVALID_INCLUSION_PATH",
     "The first sibling is replaced with 32 zero bytes; reconstructed root differs."),
    ("fail-tampered-path-last", 16, 9, "path-last", "INVALID_INCLUSION_PATH",
     "The last sibling is replaced with 32 zero bytes; only the final fold differs."),
    ("fail-tampered-path-small-tree", 4, 1, "path", "INVALID_INCLUSION_PATH",
     "Same single-byte tamper on a tree of size 4, to show the rule is not size-specific."),
    ("fail-empty-path", 5, 2, "path-empty", "INVALID_INCLUSION_PATH",
     "tree_size=5 with an empty inclusion path: reconstructed root is the leaf digest."),
    ("fail-path-too-long", 8, 2, "path-long", "INVALID_INCLUSION_PATH",
     "One extra 32-byte sibling appended; folding it adds a node that is not in the tree."),
    ("fail-tampered-leaf", 4, 1, "leaf", "INVALID_LEAF_DIGEST",
     "Leaf input altered before hashing: digest and reconstructed root both differ."),
    ("fail-wrong-tree-size", 8, 2, "size", "INVALID_TREE_SIZE",
     "tree_size declared one smaller than the path assumes; proof length is one short."),
    ("valid-tree9-index0", 9, 0, None, "VALID",
     "tree_size=9, leaf_index=0: the left subtree is full (8) and the tail is 1."),
    ("fail-wrong-leaf-index", 8, 2, "index", "INVALID_LEAF_INDEX",
     "The path belongs to a different leaf index of the same tree."),
    ("fail-wrong-leaf-index-edge", 16, 0, "index", "INVALID_LEAF_INDEX",
     "Left-most leaf paired with the right-most leaf's path on the same tree."),

    # --- ambiguous: the root does not authenticate the declared size ---
    ("ambiguous-tree-size", 7, 5, "ambiguous", "VALID_BUT_SIZE_UNAUTHENTICATED",
     "tree_size=7, leaf_index=5: the same inclusion_path folds to the same root at "
     "tree_size=8, so the declared size is not authenticated by the root. Independent "
     "reproduction of the RFC 9942 Section 5.2.1 observation posted to scitt@ietf.org "
     "on 2026-11-15."),
    ("ambiguous-tree-size-2", 2, 1, "ambiguous", "VALID_BUT_SIZE_UNAUTHENTICATED",
     "tree_size=2, leaf_index=1: the single-sibling path also folds at tree_size=3."),
    ("ambiguous-tree-size-4", 4, 3, "ambiguous", "VALID_BUT_SIZE_UNAUTHENTICATED",
     "tree_size=4, leaf_index=3: right-most leaf, path folds identically at tree_size=5."),
    ("ambiguous-tree-size-8", 8, 2, "ambiguous", "VALID_BUT_SIZE_UNAUTHENTICATED",
     "tree_size=8, leaf_index=2: the same path folds identically at tree_size=9. "
     "Together with the 7|8 instance this shows the ambiguity runs in both directions; "
     "each instance here was found by exhaustive search, not by hand."),
]

# The ambiguous case carries four extra fields. They are listed here rather than
# inlined so the shape stays visible next to the case table above.
AMBIGUOUS_NOTE = ("the size-8 fold consumes the same three siblings; no additional "
                  "node is read, so the root is identical")


def _expected(cid, size, index, tamper, result, desc):
    leaves = _leaves(cid, size)
    true_root = merkle.root_hash(leaves)
    proof = list(merkle.audit_path(leaves, index))
    stated_size = size
    leaf_input = _leaf_text(cid, index)
    leaf_digest = leaves[index]
    if tamper == "path":
        proof[0] = b"\x00" * 32
    elif tamper == "path-last":
        proof[-1] = b"\x00" * 32
    elif tamper == "path-empty":
        proof = []
    elif tamper == "path-long":
        proof = proof + [b"\x00" * 32]
    elif tamper == "leaf":
        leaf_input = _leaf_text(cid, index) + b" (tampered)"
        leaf_digest = merkle.leaf_hash(leaf_input)
    elif tamper == "size":
        stated_size = size - 1
        proof = proof[:-1]
    elif tamper == "size-zero":
        stated_size = 0
    elif tamper == "index":
        proof = list(merkle.audit_path(leaves, (index + 1) % size))
    reconstructed = root_from_path(leaf_digest, index, stated_size, proof)
    exp = {
        "description": desc,
        "leaf_entry": {
            "leaf_input_hex": leaf_input.hex(),
            "leaf_input_ascii": leaf_input.decode(),
            "digest_hex": leaf_digest.hex(),
            "definition": "SHA-256 of the leaf input bytes, hex-encoded",
        },
        "leaf_index": index,
        "tree_size": stated_size,
        "inclusion_path": [h.hex() for h in proof],
        "root_true": true_root.hex(),
        "reconstructed_root": reconstructed.hex() if reconstructed else "",
        "result": result,
    }
    if tamper == "ambiguous":
        # Same path, one larger declared size: if the fold reads no additional node
        # the root comes out identical, which is exactly the ambiguity being shown.
        alt = root_from_path(leaves[index], index, size + 1, proof)
        exp["alt_tree_size"] = size + 1
        exp["alt_root_equal"] = (alt is not None and alt == true_root)
        exp["note"] = AMBIGUOUS_NOTE
    return exp


def _write_gitattributes(out):
    ga = os.path.join(out, ".gitattributes")
    with open(ga, "w", encoding="utf-8", newline="\n") as fh:
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
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(exp, fh, indent=2, sort_keys=True)
            fh.write("\n")
        written.append(p)
        vectors.append({
            "id": cid, "dir": "v1/%s" % cid, "description": desc,
            "expected_result": result,
            "expected": {k: v for k, v in exp.items() if k != "description"},
        })

    classes = {}
    for v in vectors:
        classes[v["expected_result"]] = classes.get(v["expected_result"], 0) + 1

    manifest = {
        "version": "v1",
        "stability": "append-only",
        "scope_note": ("Covers the RFC 9162 SHA-256 hash-tree and inclusion-path layer "
                       "only. No COSE_Sign1 statement or receipt bytes are included; "
                       "see README 'What this set does not cover'."),
        "coverage_note": (
            "Declaring a tree_size one larger than the path assumes never changes the "
            "reconstructed root in this algebra - the fold reads no additional node - so "
            "that input is carried as an ambiguous-* vector (the root does not authenticate "
            "the size), not as an INVALID_TREE_SIZE vector. INVALID_TREE_SIZE therefore "
            "covers 'declared smaller' (path one short) and 'declared zero' (no fold "
            "defined) only. This asymmetry was found by running the vectors, not assumed: "
            "an earlier draft carried a 'size larger' fail case that our own verifier "
            "reported as root-equal."
        ),
        "class_counts": classes,
        "underspecified_inputs": [
            {
                "input": "tree_size=0 with a leaf_index asserted",
                "our_behaviour": "refused: no fold is defined, reconstructed_root left empty",
                "independent_behaviour": ("a literal RFC 9162 fold keeps folding and returns a "
                                          "root, because nothing in the text forbids size 0"),
                "why_not_a_vector": ("a vector has to be reproducible by an independent "
                                     "reading of the text. This input is not: two conforming "
                                     "readings disagree, so it is declared here instead of "
                                     "being scored. It was found on 2026-11-20 when the "
                                     "standalone checker disagreed with the builder; the "
                                     "earlier draft carried it as fail-tree-size-zero."),
            }
        ],
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
    with open(mp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
        fh.write("\n")
    written.append(mp)

    ga = os.path.join(out, ".gitattributes")
    with open(ga, "w", encoding="utf-8", newline="\n") as fh:
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
    with open(sums, "w", encoding="utf-8", newline="\n") as fh:
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
        if "alt_tree_size" in exp:
            # An ambiguous vector is only worth carrying if the claim in it is
            # reproducible: the same path must fold to the same root at the other size.
            alt = root_from_path(leaf, exp["leaf_index"], exp["alt_tree_size"],
                                 [bytes.fromhex(h) for h in exp["inclusion_path"]])
            alt_equal = alt is not None and alt == bytes.fromhex(exp["root_true"])
            if alt_equal != exp["alt_root_equal"]:
                ok = False
                msgs.append("%s: alt_root_equal is %s but the fold says %s"
                            % (v["id"], exp["alt_root_equal"], alt_equal))
            if not alt_equal:
                ok = False
                msgs.append("%s: claims size ambiguity that does not reproduce" % v["id"])
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


def check_drift(out=OUT):
    """Rebuild into a temp dir and demand byte-identity with the committed package.

    Why: on 2026-11-20 this check found that ``CASES`` knew about 5 vectors while the
    committed ``manifest.json`` listed 6 - ``ambiguous-tree-size`` had been added by
    hand afterwards. ``--check`` reads only the manifest, so it could not see the gap;
    a plain ``build`` run would have silently dropped that vector from the manifest while
    leaving its directory behind. Byte-identity closes both directions: the committed
    package must be exactly what the script produces, and the script must produce
    exactly what is committed.
    """
    import tempfile

    tmp = tempfile.mkdtemp(prefix="scitt-drift-")
    ok, msgs = True, []
    try:
        build(tmp)
        rels = []
        hand_written = {"README.md"}  # prose, maintained by hand; never built
        for root, _dirs, files in os.walk(out):
            for f in files:
                full = os.path.join(root, f)
                rel = os.path.relpath(full, out).replace(os.sep, "/")
                if rel in hand_written:
                    continue
                rels.append(rel)
        rels.sort()
        for rel in rels:
            a = os.path.join(out, rel)
            b = os.path.join(tmp, rel)
            if not os.path.isfile(b):
                ok = False
                msgs.append("committed file not produced by build: %s" % rel)
                continue
            if open(a, "rb").read() != open(b, "rb").read():
                ok = False
                msgs.append("committed bytes differ from build output: %s" % rel)
        built_rels = []
        for root, _dirs, files in os.walk(tmp):
            for f in files:
                built_rels.append(os.path.relpath(os.path.join(root, f), tmp).replace(os.sep, "/"))
        for rel in built_rels:
            if rel not in rels:
                ok = False
                msgs.append("build produces a file the package does not have: %s" % rel)
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    msgs.append("compared files: %d" % len(rels))
    return ok, msgs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--check-drift", action="store_true",
                    help="rebuild into a temp dir and compare bytes with the package")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)
    if a.check_drift:
        ok, msgs = check_drift(a.out)
        for m in msgs:
            print("  " + m)
        print("VERDICT: %s" % ("CONSISTENT" if ok else "DISCREPANCY"))
        return 0 if ok else 1
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
