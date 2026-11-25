"""Put our own 63 vectors through the same arithmetic used against the competitor.

Why this exists
---------------
`docs/COMPETITOR-CORPUS-SWEEP.md` reports 69 of 171 upstream vectors replayable
without their code. That number only means something next to the same measurement
of ours: a corpus that grades itself generously and its neighbour strictly has
proved nothing. So this tool reads `docs/upstream-package/scitt-rfc9162/`, folds
every vector with the same two functions the competitor sweep imports from
`tools/verify_rekor_inclusion.py`, and prints the ratio.

Three checks per vector, kept apart on purpose:

  fold        the published root must be the one the numbers fold to (or must
              differ, when the vector publishes a refusal)
  leaf digest SHA-256(0x00 || leaf input) must equal the digest the file states
  publish     the file's own `reconstructed_root` must agree with our recomputation

A vector that folds to its root but whose leaf digest we cannot rebuild is not
called replayable: rebuilding the leaf is half the claim. Nothing here is mapped
to a pass by intent - an `INVALID_*` verdict is only consistent when the
arithmetic actually says no.

Usage
-----
  python tools/measure_own_corpus.py [--root <repo>] [--json] [--write] [--selftest]
"""

import argparse
import hashlib
import json
import os
import sys

EMPTY_ROOT = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.dirname(_HERE))
try:
    from tools.verify_rekor_inclusion import (_decomp_incl_proof, fold, leaf_hash,
                                              root_from_consistency_proof)
except ImportError:
    from verify_rekor_inclusion import (_decomp_incl_proof, fold, leaf_hash,
                                        root_from_consistency_proof)

PACKAGE = os.path.join("docs", "upstream-package", "scitt-rfc9162")
RECEIPT = os.path.join("docs", "upstream-package", "measurements", "own-corpus-replay.json")

# The verdict words this package uses, mapped to what a reader would call them.
# VALID_BUT_SIZE_UNAUTHENTICATED is counted as an accept and reported separately:
# the root authenticates the leaves, not the declared size.
ACCEPTS = ("VALID", "VALID_BUT_SIZE_UNAUTHENTICATED")


def _sha256_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _inclusion(v):
    """('match'|'mismatch'|'none', detail)."""
    size = v.get("tree_size")
    tsize_alt = v.get("alt_tree_size")
    index = v.get("leaf_index")
    root = (v.get("root_true") or "").lower()
    if size is None or index is None or not root:
        return "none", "no tree_size, leaf_index or root_true"
    if size == 0:
        # RFC 6962 Section 2.1 fixes MTH({}) = SHA-256(), and Section 2.1.1
        # defines a path only for 0 <= m < n, so nothing can sit in an empty tree.
        if root == EMPTY_ROOT:
            return "mismatch", "no leaf fits a tree of size 0, and the root is MTH({})"
        return "none", "size 0 without the empty-tree root: the file states no fixable root"
    if index < 0 or index >= size:
        return "mismatch", "leaf_index %d outside 0..%d-1" % (index, size - 1)
    digest = (v.get("leaf_entry") or {}).get("digest_hex")
    path = v.get("inclusion_path")
    if digest is None or path is None:
        return "none", "no leaf digest or no inclusion_path"
    inner, border = _decomp_incl_proof(index, size)
    if len(path) != inner + border:
        return "mismatch", "path carries %d hashes, size %d at index %d needs %d" % (
            len(path), size, index, inner + border)
    try:
        folded = fold(bytes.fromhex(digest), index, size,
                      [bytes.fromhex(p) for p in path])
    except (ValueError, TypeError) as e:
        return "none", "malformed numbers: %s" % e
    detail = "size %d index %d folds to %s.." % (size, index, folded.hex()[:8])
    if tsize_alt is not None:
        detail += "; the same path also folds at size %d, so the root does not " \
                  "authenticate the size" % tsize_alt
    if folded.hex() == root:
        return "match", detail
    return "mismatch", detail + ", not the published %s.." % root[:8]


def _consistency(v):
    """('match'|'mismatch'|'none', detail)."""
    old_size = v.get("old_size")
    new_size = v.get("new_size")
    old_root = (v.get("old_root") or "").lower()
    new_root = (v.get("new_root") or "").lower()
    if old_size is None or new_size is None or not old_root or not new_root:
        return "none", "no sizes or no roots"
    if new_size < old_size:
        return "mismatch", "new_size %d < old_size %d: no proof can exist" % (
            new_size, old_size)
    proof = v.get("consistency_path") or []
    try:
        computed = root_from_consistency_proof(
            old_size, new_size, [bytes.fromhex(p) for p in proof],
            bytes.fromhex(old_root))
    except (ValueError, TypeError) as e:
        return "mismatch", "the proof does not chain: %s" % e
    if computed.hex() == new_root:
        return "match", "%d->%d: root recomputed from the old root matches" % (
            old_size, new_size)
    return "mismatch", "recomputed %s.. != published %s.." % (
        computed.hex()[:8], new_root[:8])


def _leaf_digest_ok(v):
    """True/False/None: can the stated leaf digest be rebuilt from the stated input?"""
    entry = v.get("leaf_entry") or {}
    digest = (entry.get("digest_hex") or "").lower()
    text = entry.get("leaf_input_hex")
    if not digest or text is None:
        return None
    try:
        rebuilt = leaf_hash(bytes.fromhex(text)).hex()
    except (ValueError, TypeError):
        return None
    return rebuilt == digest


def _reconstructed_agrees(v, kind):
    """Does the file's own reconstructed_root equal the root our fold produced?"""
    if kind == "inclusion":
        stated = (v.get("reconstructed_root") or "").lower()
        size = v.get("tree_size")
        index = v.get("leaf_index")
        digest = (v.get("leaf_entry") or {}).get("digest_hex")
        path = v.get("inclusion_path")
        if not stated or size is None or index is None or digest is None \
                or path is None or size == 0:
            return None
        try:
            folded = fold(bytes.fromhex(digest), index, size,
                          [bytes.fromhex(p) for p in path])
        except (ValueError, TypeError):
            return None
        return folded.hex() == stated
    stated = (v.get("reconstructed_new_root") or "").lower()
    if not stated:
        return None
    old_size = v.get("old_size")
    new_size = v.get("new_size")
    old_root = (v.get("old_root") or "").lower()
    if old_size is None or new_size is None or not old_root:
        return None
    try:
        computed = root_from_consistency_proof(
            old_size, new_size,
            [bytes.fromhex(p) for p in (v.get("consistency_path") or [])],
            bytes.fromhex(old_root))
    except (ValueError, TypeError):
        return None
    return computed.hex() == stated


def classify(expected_word, arith):
    """What the published verdict rests on. Never guesses the vector's intent."""
    if arith == "none" or not expected_word:
        return "none"
    accept = expected_word in ACCEPTS
    if accept:
        return "consistent" if arith == "match" else "inconsistent"
    return "consistent" if arith == "mismatch" else "inconsistent"


def _entries(root):
    files = []
    base = os.path.join(root, PACKAGE)
    for dirpath, _dirs, names in os.walk(base):
        for name in sorted(names):
            if not name.endswith(".json"):
                continue
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            if rel == RECEIPT.replace(os.sep, "/"):
                # A receipt that digests itself can never be checked again.
                continue
            files.append({"path": rel, "bytes": os.path.getsize(path),
                          "sha256": _sha256_file(path)})
    # Sorted here, not left to os.walk: directory order differs between filesystems,
    # and an unsorted list makes the same corpus produce two different receipts on
    # Linux and Windows even when every digest in it agrees.
    return sorted(files, key=lambda e: e["path"])


def manifest_digest(entries):
    body = "".join("%s\t%s\n" % (e["path"], e["sha256"])
                   for e in sorted(entries, key=lambda e: e["path"]))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def run(root="."):
    base = os.path.join(root, PACKAGE)
    man = json.load(open(os.path.join(base, "manifest.json"), encoding="utf-8"))
    categories = {}
    for vec in man["vectors"]:
        path = os.path.join(base, vec["dir"], "expected.json")
        v = json.load(open(path, encoding="utf-8"))
        kind = vec.get("kind") or ("consistency" if "consistency_path" in v
                                   else "inclusion")
        if kind == "consistency":
            arith, detail = _consistency(v)
            leaf_ok = None
        else:
            arith, detail = _inclusion(v)
            leaf_ok = _leaf_digest_ok(v)
        agrees = _reconstructed_agrees(v, kind)
        word = vec.get("expected_result") or v.get("result")
        categories.setdefault(kind, {"vectors": []})["vectors"].append({
            "id": vec["id"],
            "dir": vec["dir"],
            "expected": word,
            "arith": arith,
            "detail": detail,
            "leaf_digest_rebuilt": leaf_ok,
            "own_reconstruction_agrees": agrees,
            "replay": classify(word, arith),
            "size_unauthenticated": word == "VALID_BUT_SIZE_UNAUTHENTICATED",
        })
    for kind, c in categories.items():
        rows = c["vectors"]
        n = {
            "vectors": len(rows),
            "replayable": sum(1 for r in rows if r["arith"] != "none"),
            "accept_published": sum(1 for r in rows if r["expected"] in ACCEPTS),
            "reject_published": sum(1 for r in rows if r["expected"] not in ACCEPTS),
            "consistent": sum(1 for r in rows if r["replay"] == "consistent"),
            "inconsistent": sum(1 for r in rows if r["replay"] == "inconsistent"),
            "none": sum(1 for r in rows if r["replay"] == "none"),
            "leaf_digest_rebuilt": sum(1 for r in rows if r["leaf_digest_rebuilt"]),
              "leaf_digest_stated": sum(
                  1 for r in rows if r["leaf_digest_rebuilt"] is not None),
            "own_reconstruction_agrees": sum(
                1 for r in rows if r["own_reconstruction_agrees"]),
            "own_reconstruction_stated": sum(
                1 for r in rows if r["own_reconstruction_agrees"] is not None),
            "size_unauthenticated": sum(1 for r in rows if r["size_unauthenticated"]),
        }
        c["counts"] = n
    entries = _entries(root)
    t = {"vectors": 0}
    for kind in categories:
        t["vectors"] += categories[kind]["counts"]["vectors"]
    for k in ("replayable", "accept_published", "reject_published", "consistent",
              "inconsistent", "none", "leaf_digest_rebuilt", "leaf_digest_stated", "size_unauthenticated",
              "own_reconstruction_agrees", "own_reconstruction_stated"):
        t[("n_" + k) if k in ("replayable", "accept_published", "reject_published") else k] = \
            sum(categories[kind]["counts"][k] for kind in categories)
    return {
        "corpus": PACKAGE.replace(os.sep, "/"),
        "version": man.get("version"),
        "rule": "tools/measure_own_corpus.py: same fold functions the competitor "
                "sweep imports from tools/verify_rekor_inclusion.py",
        "categories": categories,
        "totals": t,
        "manifest": {"files": entries, "count": len(entries)},
        "manifest_digest": manifest_digest(entries),
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".", help="repository root")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write", action="store_true",
                    help="write %s" % RECEIPT.replace(os.sep, "/"))
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the stored receipt no longer matches the corpus")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)

    if a.selftest:
        one = {"tree_size": 1, "leaf_index": 0, "inclusion_path": [],
               "root_true": leaf_hash(b"x").hex(),
               "leaf_entry": {"digest_hex": leaf_hash(b"x").hex(), "leaf_input_hex": "78"}}
        assert _inclusion(one)[0] == "match"
        assert _leaf_digest_ok(one) is True
        assert _inclusion(dict(one, root_true="00" * 32))[0] == "mismatch"
        # The size-0 rule needs the empty-tree constant, not another tree's root.
        assert _inclusion({"tree_size": 0, "leaf_index": 0, "root_true": EMPTY_ROOT})[0] == "mismatch"
        assert _inclusion({"tree_size": 0, "leaf_index": 0,
                           "root_true": "54" * 32})[0] == "none"
        # A path one hash short of what the size needs is a refusal.
        assert _inclusion(dict(one, tree_size=2))[0] == "mismatch"
        # The leaf digest check has to be able to say no.
        bad = dict(one, leaf_entry={"digest_hex": "00" * 32, "leaf_input_hex": "78"})
        assert _leaf_digest_ok(bad) is False
        assert _inclusion(bad)[0] == "mismatch"
        assert _consistency({"old_size": 3, "new_size": 2, "old_root": "00" * 32,
                             "new_root": "11" * 32, "consistency_path": []})[0] == "mismatch"
        # Classification is where a self-measurement can flatter itself.
        assert classify("VALID", "match") == "consistent"
        assert classify("VALID", "mismatch") == "inconsistent"
        assert classify("INVALID_TREE_SIZE", "mismatch") == "consistent"
        assert classify("INVALID_TREE_SIZE", "match") == "inconsistent"
        assert classify("VALID_BUT_SIZE_UNAUTHENTICATED", "match") == "consistent"
        assert classify("VALID", "none") == "none"
        print("selftest: 14/14")
        return 0

    result = run(a.root)
    if a.json:
        print(json.dumps(result, indent=2))
        return 0
    if a.write:
        out = os.path.join(a.root, RECEIPT)
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            json.dump(result, f, indent=2, sort_keys=True)
            f.write("\n")
        print("wrote %s" % RECEIPT.replace(os.sep, "/"))
        return 0
    if a.check:
        stored = json.load(open(os.path.join(a.root, RECEIPT), encoding="utf-8"))
        if json.dumps(stored, sort_keys=True) != json.dumps(result, sort_keys=True):
            print("receipt is stale: rerun with --write")
            return 1
        print("receipt matches the corpus")
        return 0

    print("corpus: %s" % result["corpus"])
    print("%-12s %7s %10s %8s %8s %8s %8s"
          % ("kind", "vectors", "replayable", "accept", "reject", "consist", "inconsist"))
    for kind, c in result["categories"].items():
        n = c["counts"]
        print("%-12s %7d %10d %8d %8d %8d %8d"
              % (kind, n["vectors"], n["replayable"], n["accept_published"],
                 n["reject_published"], n["consistent"], n["inconsistent"]))
    t = result["totals"]
    print("TOTAL %d vectors, replayable %d (%.0f%%), consistent %d, inconsistent %d, "
          "not replayable %d"
          % (t["vectors"], t["n_replayable"],
             100.0 * t["n_replayable"] / max(1, t["vectors"]),
             t["consistent"], t["inconsistent"], t["vectors"] - t["n_replayable"]))
    print("leaf digests rebuilt %d of %d vectors that state one; own "
          "reconstructed_root agrees %d of %d stated; %d vectors are "
          "VALID_BUT_SIZE_UNAUTHENTICATED"
          % (t["leaf_digest_rebuilt"], t["leaf_digest_stated"],
             t["own_reconstruction_agrees"], t["own_reconstruction_stated"],
             t["size_unauthenticated"]))
    print("manifest digest %s… (%d files)"
          % (result["manifest_digest"][:16], result["manifest"]["count"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())



