#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fold the package's inclusion paths with a second third-party implementation.

`tools/crosscheck_scitt_pymerkle.py` asks a library to *build trees* from leaf texts
and compares roots; it never reads a proof path, which is stated as a limit in
`docs/THIRD-PARTY-CROSSCHECK.md`. This script closes that half: it hands each case's
audit path to the merkle arithmetic vendored from Sigstore (`tools/third_party/
sigstore_merkle.py`, Apache-2.0, from sigstore 4.6.0, one import line changed --
see `tools/third_party/NOTICE.md`) and asks it to fold the path into a root.

Two things are checked per case, both arithmetic a stranger can recompute:

  * folding the case's declared leaf digest along the case's path, at the case's
    (index, tree_size), reproduces the case's `reconstructed_root`;
  * that root equals `root_true` exactly when the case claims VALID (including
    VALID_BUT_SIZE_UNAUTHENTICATED, where the declared size is not authenticated but
    the root is), and differs when the case claims INVALID.

What this is not: no leaf-text hashing (that is the pymerkle script's job), no
consistency SUBPROOF order, no signature, no receipt, no deployment claim. Sigstore's
file carries no consistency checker at all, so consistency proofs stay corroborated by
our verifier and the standalone checker only -- said here rather than glossed.

    python3 tools/crosscheck_scitt_sigstore.py
    python3 tools/crosscheck_scitt_sigstore.py --out tools/out/crosscheck_sigstore.json
    python3 tools/crosscheck_scitt_sigstore.py --self-test
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CASE_DIR = os.path.join(ROOT, "docs", "upstream-package", "scitt-rfc9162", "v1")
CONTRACT = "uibc-scitt-sigstore-crosscheck/1"
VENDOR = "sigstore 4.6.0 (tools/third_party/sigstore_merkle.py)"

sys.path.insert(0, os.path.join(HERE, "third_party"))
try:
    import sigstore_merkle as sm
except ImportError as exc:  # vendored file missing is a hard error, not a skip
    sys.stderr.write("vendored third-party file not importable: %s\n" % exc)
    raise SystemExit(2)


def _read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _root(case, path_override=None):
    """Fold the declared leaf digest along the case's path, using their arithmetic."""
    path = list(path_override if path_override is not None else case["inclusion_path"])
    index, size = int(case["leaf_index"]), int(case["tree_size"])
    seed = bytes.fromhex(case["leaf_entry"]["digest_hex"])
    inner, border = sm._decomp_inclusion_proof(index, size)
    if len(path) != inner + border:
        raise ValueError("path length %d does not split as %d+%d for index %d size %d"
                         % (len(path), inner, border, index, size))
    hashes = [bytes.fromhex(h) for h in path]
    seed = sm._chain_inner(seed, hashes[:inner], index)
    return sm._chain_border_right(seed, hashes[inner:]).hex()


def run(mutate=None):
    rows = []
    compared = fold_agrees = verdict_agrees = 0
    undefined = []
    refused = []
    mutated_attempted = mutated_detected = 0
    for name in sorted(os.listdir(CASE_DIR)):
        path = os.path.join(CASE_DIR, name, "expected.json")
        if not os.path.isfile(path):
            continue
        case = _read_json(path)
        if "inclusion_path" not in case:
            continue
        size = case["tree_size"]
        if size == 0:
            undefined.append(name)          # no path exists in an empty tree
            rows.append({"case": name, "tree_size": 0,
                         "note": "no audit path exists for tree_size=0"})
            continue
        compared += 1
        result = case.get("result", "")
        expected_valid = result.startswith("VALID")
        declared = case.get("reconstructed_root", "")
        true_root = case.get("root_true", "")

        if mutate is not None and case["inclusion_path"]:
            # flip one hex nibble of the first path node
            p = list(case["inclusion_path"])
            first = p[0]
            p[0] = ("1" if first[0] != "1" else "0") + first[1:]
            try:
                folded = _root(case, p)
            except ValueError as why:
                refused.append(name)
                rows.append({"case": name, "tree_size": size, "result": result,
                             "mutated": "refused: %s" % why})
                continue
            mutated_attempted += 1
            if folded != declared:
                mutated_detected += 1
            rows.append({"case": name, "tree_size": size, "result": result,
                         "mutated_root": folded, "reconstructed_root": declared})
            continue
        else:
            folded = None
            try:
                folded = _root(case)
            except ValueError as why:
                # The library refuses a path whose length cannot be split for this
                # (index, size) -- an honest refusal, recorded as such, not folded.
                refused.append(name)
                rows.append({"case": name, "tree_size": size, "result": result,
                             "refused": str(why), "expected_valid": expected_valid})
                if expected_valid:
                    verdict_agrees -= 1   # a VALID case the library cannot read is a failure
                continue

        fold_ok = folded == declared
        fold_agrees += 1 if fold_ok else 0
        verdict_ok = (folded == true_root) == expected_valid
        verdict_agrees += 1 if verdict_ok else 0
        rows.append({"case": name, "tree_size": size, "result": result,
                     "library_root": folded, "reconstructed_root": declared,
                     "root_true": true_root,
                     "agrees_on_fold": fold_ok, "agrees_on_verdict": verdict_ok})

    folded_cases = compared - len(refused)
    report = {
        "contract_version": CONTRACT,
        "third_party": VENDOR,
        "cases_total": compared + len(undefined),
        "cases_compared": compared,
        "cases_folded": folded_cases,
        "agrees_on_fold": fold_agrees,
        "agrees_on_verdict": verdict_agrees,
        "refused_by_library": refused,
        "empty_tree_has_no_path": undefined,
        "mutated_paths_attempted": mutated_attempted,
        "mutated_paths_detected": mutated_detected,
        "scope_note": ("declared leaf digest plus audit path in, root out; no leaf-text "
                       "hashing, no consistency order, no signature, no deployment claim"),
        "cases": rows,
    }
    ok = (folded_cases > 0 and fold_agrees == folded_cases
          and verdict_agrees == folded_cases)
    return ok, report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="write the JSON report here")
    ap.add_argument("--self-test", action="store_true",
                    help="flip one path nibble per case and require detection")
    args = ap.parse_args()

    ok, report = run()
    print("SIGSTORE: fold %d/%d, verdict %d/%d, no-path %d, refused-by-library %d"
          % (report["agrees_on_fold"], report["cases_folded"],
             report["agrees_on_verdict"], report["cases_folded"],
             len(report["empty_tree_has_no_path"]), len(report["refused_by_library"])))
    if not ok:
        bad = [r["case"] for r in report["cases"]
               if r.get("agrees_on_fold") is False or r.get("agrees_on_verdict") is False]
        print("  disagreements:", ", ".join(bad) or "(none listed)")
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(report, fh, indent=2, sort_keys=True)
            fh.write("\n")
        print("  wrote", args.out)

    if args.self_test:
        _, m_report = run(mutate=1)
        attempted = m_report["mutated_paths_attempted"]
        caught = m_report["mutated_paths_detected"]
        print("  self-test: %d/%d mutated paths detected" % (caught, attempted))
        if attempted == 0 or caught != attempted:
            print("  SELF-TEST FAILED")
            return 1
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
