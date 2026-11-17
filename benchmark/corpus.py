#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Materialise the benchmark as a portable corpus, so another team's verifier
can be run against the same packages.

Why: `run.py` measures OUR verifier. A benchmark that can only be run by its
author is marketing. This script writes plain package directories plus a
manifest, and `adapter.py` shows the one-function contract any verifier needs to
honour to be compared case by case.

    python benchmark/corpus.py                  # build ./benchmark/corpus
    python benchmark/corpus.py --out D:/tmp/c   # build elsewhere

Corpus layout:

    corpus/manifest.json          every case: id, mutation, expected verdict per
                                  mode, tree digest, and which checks our
                                  implementation fired
    corpus/base/                  the untouched, correctly sealed package
    corpus/cases/M01/ ... M21/    one package directory per mutation

Nothing here is specific to uibc: the directories are ordinary files, and the
expectation matrix is written before results are read.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MB = os.path.join(ROOT, "tools", "out", "_mb")
RESULTS = os.path.join(ROOT, "tools", "out", "mutation_benchmark.json")
MODES = ["open", "pinned", "head-pinned"]


def tree_digest(path):
    """sha256 over (relative path, file sha256), sorted - a portable identity."""
    h = hashlib.sha256()
    for dirpath, _dirnames, filenames in os.walk(path):
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, path).replace("\\", "/")
            h.update(rel.encode("utf-8") + b"\0")
            with open(full, "rb") as f:
                h.update(hashlib.sha256(f.read()).digest())
    return "sha256:" + h.hexdigest()


def build(out, rerun=False):
    if rerun or not os.path.exists(RESULTS):
        print("building benchmark packages ...")
        rc = subprocess.call([sys.executable,
                              os.path.join(ROOT, "tools", "mutation_benchmark.py")],
                             cwd=ROOT)
        if rc != 0:
            print("benchmark build failed rc=%d" % rc)
            return 2

    exp = json.load(open(os.path.join(HERE, "expected.json"), encoding="utf-8"))
    by_id = {c["id"]: c for c in exp["cases"]}
    results = json.load(open(RESULTS, encoding="utf-8"))
    observed = {}
    for row in results["rows"]:
        mid = row["id"].split()[0]
        observed[mid] = {"mutation": row.get("mutation", ""), "modes": row["modes"]}

    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out)
    shutil.copytree(os.path.join(MB, "base"), os.path.join(out, "base"))

    cases = []
    skipped = []
    for mid in sorted(by_id):
        src = os.path.join(MB, "m_" + mid)
        if not os.path.isdir(src):
            skipped.append(mid)
            continue
        dst = os.path.join(out, "cases", mid)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copytree(src, dst)
        entry = {
            "id": mid,
            "mutation": by_id[mid]["mutation"],
            "should_reject": by_id[mid]["should_reject"],
            "documented_accept": [m for m in MODES
                                  if mid in exp["by_design_accept"].get(m, [])],
            "tree_digest": tree_digest(dst),
            "our_verdict": {m: observed.get(mid, {}).get("modes", {}).get(m, {})
                            .get("verdict") for m in MODES},
            "our_failed_checks": {m: observed.get(mid, {}).get("modes", {}).get(m, {})
                                  .get("failed_checks", []) for m in MODES},
        }
        cases.append(entry)

    doc = {
        "meta": {
            "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "base_digest": tree_digest(os.path.join(out, "base")),
            "spec_id": _spec_id(),
            "contract": "adapter.py: verify(package_dir, pubkey_b64, expect_head) "
                        "-> 'PASS' | 'FAIL' | 'INCONCLUSIVE'",
            "note": "verdicts are per package; a MODE is a property of how the "
                    "verifier is called, not of the package bytes",
        },
        "semantics": exp["semantics"],
        "by_design_accept": exp["by_design_accept"],
        "cases": cases,
    }
    with open(os.path.join(out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)

    print("corpus written: %s" % out)
    print("cases: %d%s" % (len(cases),
                           (" (not materialised: %s)" % ",".join(skipped)) if skipped else ""))
    print("base digest: %s" % doc["meta"]["base_digest"])
    return 0


def _spec_id():
    try:
        sys.path.insert(0, ROOT)
        import uibc_core
        return uibc_core.spec_id()
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "corpus"))
    ap.add_argument("--rerun", action="store_true")
    a = ap.parse_args()
    return build(a.out, a.rerun)


if __name__ == "__main__":
    sys.exit(main())
