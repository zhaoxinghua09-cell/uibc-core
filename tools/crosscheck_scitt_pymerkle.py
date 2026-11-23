#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Cross-check the SCITT RFC 9162 vector package against a third-party Merkle library.

The vector package scores roots and verdicts with our own verifier. That is enough
for internal consistency and nothing else: the same code that produced a number
also certifies it. This script hands the same case files to a library nobody here
wrote -- pymerkle in its RFC 6962 mode -- and asks it two questions only:

  * does it, from the case's leaf texts, build the same *true* root the case claims
    (`root_true`)?
  * does the root it builds equal the case's `reconstructed_root` exactly in the
    cases that claim VALID, and differ in the cases that claim INVALID?

What this is not: it is not an external human run, and it is not an end-to-end
check. pymerkle is handed leaf text and asked for tree roots; it never sees a proof
path, a signature or a receipt, so nothing here vouches for deployment. pymerkle
also leaves MTH({}) undefined (its empty tree has no root), so the empty-tree
constant is reported as *un corroborated by this library*, not as agreement.

    python3 tools/crosscheck_scitt_pymerkle.py
    python3 tools/crosscheck_scitt_pymerkle.py --out tools/out/crosscheck_pymerkle.json
    python3 tools/crosscheck_scitt_pymerkle.py --self-test
"""
import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CASE_DIR = os.path.join(ROOT, "docs", "upstream-package", "scitt-rfc9162", "v1")
CONTRACT = "uibc-scitt-crosscheck/1"
LIB = "pymerkle"

# The true tree is normally the declared one. One case declares a size *smaller*
# than the path assumes ("tree_size declared one smaller than the path assumes",
# proof length one short) and its root_true is the root of the path's tree, so the
# leaves it holds are those of the larger tree. Named explicitly rather than
# searched, so a mismatch cannot be papered over by brute force.
TRUE_SIZE_OVERRIDES = {"fail-wrong-tree-size": 8}

# Two cases hold leaves whose input is not their template text: one empty input, and
# one tree of (empty, single zero byte). Both are legitimate edge inputs, so they are
# written out explicitly. A *tampered* leaf (INVALID_LEAF_DIGEST) is deliberately
# absent: the true tree holds the untampered text, and the case's point is that the
# provided digest answers for something else.
LEAF_OVERRIDES = {
    "valid-empty-leaf": {0: b""},
    "valid-empty-leaf-tree2": {0: b"", 1: b"\x00"},
}


def _load_lib():
    try:
        from pymerkle import InmemoryTree  # noqa: F401
        import pymerkle
    except ImportError as e:
        sys.stderr.write(
            "pymerkle is not installed (%s).\n"
            "This is a third-party cross-check, not part of the package build:\n"
            "    python -m pip install 'pymerkle==6.0.0'\n" % e
        )
        raise SystemExit(2)
    return InmemoryTree, getattr(pymerkle, "__version__", "?")


def _read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _root_hex(tree):
    node = tree.root
    for attr in ("value", "digest", "data", "hash"):
        v = getattr(node, attr, None)
        if isinstance(v, (bytes, bytearray)):
            return bytes(v).hex()
    return None


def _leaves_for(case, name, flip_index=None):
    """Leaf bytes the true tree is supposed to hold for this case."""
    n = TRUE_SIZE_OVERRIDES.get(name, case["tree_size"])
    tpl = "scitt-rfc9162 test vectors v1 :: %s :: leaf %%d" % name
    leaves = [(tpl % i).encode() for i in range(n)]
    for i, value in LEAF_OVERRIDES.get(name, {}).items():
        leaves[i] = value
    if flip_index is not None:
        leaves[flip_index] = leaves[flip_index] + b"mutation"
    return leaves


def run(flip=None):
    InmemoryTree, version = _load_lib()
    rows = []
    total = agrees_true = verdict_agrees = 0
    undefined = []
    for name in sorted(os.listdir(CASE_DIR)):
        path = os.path.join(CASE_DIR, name, "expected.json")
        if not os.path.isfile(path):
            continue
        case = _read_json(path)
        if "inclusion_path" not in case:
            continue
        total += 1
        root_true = case.get("root_true") or ""
        folded = case.get("reconstructed_root", "")
        result = case.get("result", "")
        n = case["tree_size"]
        expected_valid = result.startswith("VALID")

        if n == 0:
            # pymerkle has no MTH({}) at all; the constant is not corroborated here.
            undefined.append(name)
            rows.append({"case": name, "tree_size": 0,
                         "library_root": None,
                         "root_true": root_true,
                         "note": "third party leaves MTH({}) undefined"})
            continue

        tree = InmemoryTree(algorithm="sha256", mode="rfc6962")
        for leaf in _leaves_for(case, name, flip):
            tree.append_entry(leaf)
        got = _root_hex(tree)

        true_ok = got == root_true
        agrees_true += 1 if true_ok else 0
        folds_to_true = got == folded
        verdict_ok = folds_to_true == expected_valid
        verdict_agrees += 1 if verdict_ok else 0
        rows.append({"case": name, "tree_size": n, "result": result,
                     "library_root": got, "root_true": root_true,
                     "reconstructed_root": folded,
                     "agrees_on_true_root": true_ok,
                     "agrees_on_verdict": verdict_ok})

    compared = total - len(undefined)
    report = {
        "contract_version": CONTRACT,
        "library": LIB,
        "library_version": version,
        "mode": "rfc6962",
        "cases_total": total,
        "cases_compared": compared,
        "agrees_on_true_root": agrees_true,
        "agrees_on_verdict": verdict_agrees,
        "empty_tree_undefined_by_library": undefined,
        "scope_note": ("leaf texts in, tree roots out; no proof path, no signature, "
                       "no receipt, no deployment claim"),
        "cases": rows,
    }
    ok = compared > 0 and agrees_true == compared and verdict_agrees == compared
    return ok, report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="write the JSON report here")
    ap.add_argument("--self-test", action="store_true",
                    help="mutate one leaf and require the check to notice")
    args = ap.parse_args()

    ok, report = run()
    print("THIRD-PARTY: %s %s (%s) -> true-root %d/%d, verdict %d/%d, undefined %d"
          % (report["library"], report["library_version"], report["mode"],
             report["agrees_on_true_root"], report["cases_compared"],
             report["agrees_on_verdict"], report["cases_compared"],
             len(report["empty_tree_undefined_by_library"])))
    if not ok:
        bad = [r["case"] for r in report["cases"]
               if r.get("agrees_on_true_root") is False or r.get("agrees_on_verdict") is False]
        print("  disagreements:", ", ".join(bad) or "(none listed)")

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(report, fh, indent=2, sort_keys=True)
            fh.write("\n")
        print("  wrote", args.out)

    if args.self_test:
        # A checker that cannot fail is not a check: mutate the leaf under test and
        # demand that the library root stops matching the case's true root.
        InmemoryTree, _ = _load_lib()
        names = [n for n in sorted(os.listdir(CASE_DIR))
                 if os.path.isfile(os.path.join(CASE_DIR, n, "expected.json"))]
        caught = 0
        probed = 0
        for name in names:
            case = _read_json(os.path.join(CASE_DIR, name, "expected.json"))
            if case.get("tree_size", 0) < 1:
                continue
            probed += 1
            tree = InmemoryTree(algorithm="sha256", mode="rfc6962")
            for leaf in _leaves_for(case, name, 0):
                tree.append_entry(leaf)
            if _root_hex(tree) != case["root_true"]:
                caught += 1
        print("  self-test: %d/%d mutated cases detected" % (caught, probed))
        if caught != probed:
            print("  SELF-TEST FAILED")
            return 1
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
