#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check docs/EXTERNAL-RUNS.json against the rules docs/RUNS.md states in prose.

Why this exists. `docs/RUNS.md` already says the right things: a row must carry
who ran it, a link that resolves, the archive digest, the figure exactly as
posted, and blind-or-directed in the runner's own words -- and that the two kinds
are never added together. All of that was prose. On 2026-11-22 a survey of a
neighbouring project's ledger found eight rows all labelled `independent`, of
which that project's own `evidence` field marked two as blind and six as
directed, posted by one implementer. Every one of those rows was individually
honest and the file was still misleading, because nothing in it could fail.

So the table becomes a file with a vocabulary, and this script is the thing that
refuses. It cannot check that a row is true. It can check that a row is
well-formed, that its kinds are closed, that a blind claim does not also record
reading our vectors, that figures are not normalised, and that the tallies at the
bottom equal the rows above them.

    python3 tools/check_external_runs.py                 # check the committed file
    python3 tools/check_external_runs.py --path X.json   # check something else
    python3 tools/check_external_runs.py --self-test      # prove it can fail
"""
import argparse
import json
import os
import re
import sys

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT = os.path.join(_REPO, "docs", "EXTERNAL-RUNS.json")

CONTRACT = "uibc-external-runs/1"

# Closed vocabularies. A new word is a change to this file, not a decision taken
# inside one row.
EVIDENCE = ("blind", "directed")
CODE = ("independent", "same code", "author")
REQUIRED = ("id", "runner", "where", "archive_sha256", "figure", "evidence", "code", "quote")

COUNT_KEYS = ("rows", "independent", "same_code", "author", "blind", "directed",
              "blind_independent")

HEX64 = re.compile(r"^[0-9a-f]{64}$")
FIGURE = re.compile(r"^\d+/\d+$")


def tally(runs):
    t = {k: 0 for k in COUNT_KEYS}
    t["rows"] = len(runs)
    for r in runs:
        code = r.get("code")
        if code == "independent":
            t["independent"] += 1
        elif code == "same code":
            t["same_code"] += 1
        elif code == "author":
            t["author"] += 1
        ev = r.get("evidence")
        if ev in EVIDENCE:
            t[ev] += 1
        if ev == "blind" and code == "independent":
            t["blind_independent"] += 1
    return t


def check_doc(doc):
    ok, msgs = True, []

    def bad(msg):
        nonlocal ok
        ok = False
        msgs.append(msg)

    if not isinstance(doc, dict):
        return False, ["the file is not a JSON object"]
    if doc.get("contract_version") != CONTRACT:
        bad("contract_version is %r, expected %r" % (doc.get("contract_version"), CONTRACT))
    runs = doc.get("runs")
    if not isinstance(runs, list):
        return False, ["runs is not a list"]

    seen = set()
    for i, r in enumerate(runs):
        tag = "row %d" % (i + 1)
        if not isinstance(r, dict):
            bad("%s is not an object" % tag)
            continue
        rid = r.get("id")
        if isinstance(rid, str) and rid.strip():
            tag = rid
            if rid in seen:
                bad("%s: duplicate id" % tag)
            seen.add(rid)
        else:
            bad("%s: no id" % tag)
        for k in REQUIRED:
            if k not in r:
                bad("%s: missing %r" % (tag, k))
        ev = r.get("evidence")
        if ev not in EVIDENCE:
            bad("%s: evidence %r is not in %s (a row saying 'independent' is not a "
                "kind, it is a conclusion)" % (tag, ev, list(EVIDENCE)))
        code = r.get("code")
        if code not in CODE:
            bad("%s: code %r is not in %s" % (tag, code, list(CODE)))
        where = r.get("where")
        if not (isinstance(where, str) and where.startswith(("http://", "https://"))):
            bad("%s: where must be a URL that resolves to the record itself" % tag)
        sha = r.get("archive_sha256")
        if not (isinstance(sha, str) and HEX64.match(sha)):
            bad("%s: archive_sha256 must be 64 lowercase hex characters" % tag)
        figure = r.get("figure")
        if figure != "no figure" and not (isinstance(figure, str) and FIGURE.match(figure)):
            bad("%s: figure %r is not verbatim n/n or 'no figure' -- percentages and "
                "fractions of a different corpus are normalisations, and RUNS.md forbids "
                "them" % (tag, figure))
        quote = r.get("quote")
        if not (isinstance(quote, str) and quote.strip()):
            bad("%s: quote is empty; a row must carry the runner's own words" % tag)
        if ev == "blind" and r.get("read_our_vectors") is True:
            bad("%s: called blind yet records having read our vectors" % tag)
        if r.get("read_our_vectors") is True and ev == "directed" and not r.get("note"):
            bad("%s: directed because our vectors were read, but no note says so" % tag)

    counts = doc.get("counts")
    if not isinstance(counts, dict):
        bad("counts is missing or not an object")
    else:
        want = tally(runs)
        for k in COUNT_KEYS:
            if k not in counts:
                bad("counts is missing %r" % k)
            elif counts[k] != want[k]:
                bad("counts[%s] is %r but the rows say %r" % (k, counts[k], want[k]))
        for k in counts:
            if k not in COUNT_KEYS:
                bad("counts carries %r, which is not a tally this file defines" % k)

    claimed = doc.get("headline")
    if claimed is not None:
        want = tally(runs)
        if claimed != want["blind_independent"]:
            bad("headline claims %r blind independent runs; the rows support %r"
                % (claimed, want["blind_independent"]))
    return ok, msgs


def check(path=DEFAULT):
    with open(path, encoding="utf-8") as fh:
        return check_doc(json.load(fh))


def _sample():
    row = {
        "id": "example-1",
        "runner": "@someone",
        "where": "https://example.invalid/run/1",
        "archive_sha256": "0" * 64,
        "figure": "63/63",
        "evidence": "directed",
        "code": "independent",
        "quote": "ran it after reading the changelog",
        "read_our_vectors": True,
        "note": "read the changelog before implementing",
    }
    doc = {"contract_version": CONTRACT, "runs": [row]}
    doc["counts"] = tally(doc["runs"])
    return doc


def self_test():
    """Eight mutations. Each must be refused, and the clean sample must pass."""
    import copy

    ok, msgs = check_doc(_sample())
    if not ok:
        print("FAIL: the clean sample was refused: %s" % msgs[:2])
        return 1
    print("self-test: a well-formed table passes")

    cases = []

    d = _sample(); d["runs"][0]["evidence"] = "independent"
    cases.append(("a row that calls itself 'independent' instead of blind or directed", d))

    d = _sample(); d["runs"][0]["blind"] = True
    d["runs"][0]["evidence"] = "blind"          # blind AND read our vectors
    cases.append(("a blind claim that also records reading our vectors", d))

    d = _sample(); d["runs"][0]["figure"] = "100%"
    cases.append(("a figure normalised into a percentage", d))

    d = _sample(); d["runs"][0]["archive_sha256"] = "abc"
    cases.append(("a digest that is not 64 hex characters", d))

    d = _sample(); d["counts"]["blind_independent"] = 1
    cases.append(("a tally that counts a directed run as blind", d))

    d = _sample(); d["runs"].append(copy.deepcopy(d["runs"][0]))
    d["counts"] = tally(d["runs"])
    cases.append(("the same run entered twice", d))

    d = _sample(); d["headline"] = 1
    cases.append(("a headline number the rows do not support", d))

    d = _sample(); d["runs"][0]["quote"] = "  "
    cases.append(("a row with no words from the runner", d))

    failures = 0
    for name, doc in cases:
        ok, msgs = check_doc(doc)
        if ok:
            print("FAIL: not refused -- %s" % name)
            failures += 1
        else:
            print("self-test caught: %s — %s" % (name, msgs[0]))
    return 1 if failures else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--path", default=DEFAULT)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return self_test()
    ok, msgs = check(a.path)
    for m in msgs:
        print("- " + m)
    print("rows: %d" % len(json.load(open(a.path, encoding="utf-8")).get("runs", [])))
    print("VERDICT: %s" % ("EXTERNAL-RUNS-CONSISTENT" if ok else "EXTERNAL-RUNS-REFUSED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
