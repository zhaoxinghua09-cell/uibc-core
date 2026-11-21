#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run ONE corpus against a SECOND verifier - the plug-in contract, demonstrated.

The corpus is verifier-agnostic: package directories plus an expectation matrix.
Any implementation that can answer "PASS / FAIL / INCONCLUSIVE" for a directory
can be compared case by case. Here the second implementation is
`independent_verifier/iverify.py` (separate code path, its own JCS and Ed25519),
used as a stand-in for a third party's verifier.

    python benchmark/corpus.py            # build the corpus first
    python benchmark/adapter.py

Honest limit: both implementations live in this repository and share an author.
This demonstrates the CONTRACT, not independence of judgement - a third party
still has to run it.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CORPUS = os.path.join(HERE, "corpus")
sys.path.insert(0, os.path.join(ROOT, "independent_verifier"))
sys.path.insert(0, ROOT)

MODES = ["open", "pinned", "head-pinned"]


def ours(package_dir, pubkey_b64=None, expect_head=None):
    from uibc_core.verify import verify
    pub = None
    if pubkey_b64:
        import base64
        pub = base64.b64decode(pubkey_b64)
    return verify(package_dir, pubkey=pub, expect_head=expect_head)["result"]


def theirs(package_dir, pubkey_b64=None, expect_head=None):
    """Second implementation. It takes no pinned key here, so in `pinned` mode it
    gets no input it cannot use - which is exactly the kind of limitation the
    comparison is meant to expose."""
    from iverify import independent_verify
    return independent_verify(package_dir)["result"]


def main():
    if not os.path.isdir(CORPUS):
        print("no corpus: run `python benchmark/corpus.py` first")
        return 2
    manifest = json.load(open(os.path.join(CORPUS, "manifest.json"), encoding="utf-8"))

    rows, disagree = [], []
    for case in manifest["cases"]:
        d = os.path.join(CORPUS, "cases", case["id"])
        a = ours(d)
        b = theirs(d)
        rows.append({"id": case["id"], "ours": a, "theirs": b,
                     "mutation": case["mutation"]})
        if a != b:
            disagree.append({"id": case["id"], "ours": a, "theirs": b,
                             "mutation": case["mutation"]})

    print("%-6s %-34s %-14s %-14s %s" % ("id", "mutation", "uibc_core", "independent", ""))
    for r in rows:
        print("%-6s %-34s %-14s %-14s %s"
              % (r["id"], r["mutation"][:34], r["ours"], r["theirs"],
                 "==" if r["theirs"] == r["ours"] else "!!"))
    agree = len(rows) - len(disagree)
    print("\n一致 %d/%d" % (agree, len(rows)))
    if disagree:
        print("分歧（这些才是值得讨论的）：")
        for d in disagree:
            print("  %s %s: ours=%s theirs=%s" % (d["id"], d["mutation"][:30],
                                                 d["ours"], d["theirs"]))

    out = os.path.join(HERE, "adapter_result.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"meta": {"what": "one corpus, two verifiers",
                            "contract": manifest["meta"]["contract"],
                            "boundary": "same repository, same author: demonstrates "
                                        "the contract, not independent judgement"},
                   "corpus_cases": len(rows), "agree": agree,
                   "rows": rows, "disagreements": disagree}, f,
                  ensure_ascii=False, indent=2)
    print("RESULT_JSON=" + out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
