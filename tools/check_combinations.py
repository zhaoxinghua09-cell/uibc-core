"""Two defects at once: does the verifier still see either of them?

Every check in this project is measured one mutation at a time. A package carrying
two defects is a different question, and the interesting failure mode is not
"both are caught" but "the two explain each other away": a second change that
supplies the consistency the first one broke, so the pair reads as coherent.

Method: a small family of single, independent mutations of the clean fixture; run
each alone (it must FAIL somewhere); then run every pair. Fourteen mutations are
91 pairs, a few seconds.

A pair that produces no FAIL is reported. Not every such pair is a hole - two
descriptive edits have nothing to catch - but every pair in which both halves
were caught alone and the combination is caught nowhere is a hole by definition.

Usage:  python3 tools/check_combinations.py [--json]
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from itertools import combinations

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BASE = os.path.join(REPO, "fixtures", "clean.uibc")
sys.path.insert(0, REPO)

from uibc_core.verify import verify  # noqa: E402


def _edit(pkg, rel, fn):
    path = os.path.join(pkg, rel)
    doc = json.load(open(path, encoding="utf-8"))
    fn(doc)
    json.dump(doc, open(path, "w", encoding="utf-8"), ensure_ascii=False)


def _flip_hex(text):
    return ("0" if text[0] != "0" else "1") + text[1:]


MUTATIONS = [
    ("m-ev0-agent", "event 0 names another agent",
     lambda p: _edit(p, "lifecycle.json",
                     lambda d: d["events"][0].__setitem__("agent_id", "fx-agent-002"))),
    ("m-ev0-type", "event 0 is not a REGISTER",
     lambda p: _edit(p, "lifecycle.json",
                     lambda d: d["events"][0].__setitem__("event_type", "ACTIVATE"))),
    ("m-ev2-prev", "the chain's tail cites nothing",
     lambda p: _edit(p, "lifecycle.json",
                     lambda d: d["events"][2].__setitem__("previous_event", None))),
    ("m-payload", "a hash-shaped claim that is not a hash",
     lambda p: _edit(p, "lifecycle.json",
                     lambda d: d["events"][0].__setitem__("payload_hash", "not-a-hash"))),
    ("m-root", "the evidence root is one byte off",
     lambda p: _edit(p, "manifest.json",
                     lambda d: d.__setitem__("evidence_root",
                                             _flip_hex(d["evidence_root"])))),
    ("m-count", "the declared count is wrong",
     lambda p: _edit(p, "manifest.json",
                     lambda d: d.__setitem__("evidence_count",
                                             d["evidence_count"] + 1))),
    ("m-agent", "the identity names another agent",
     lambda p: _edit(p, "identity.json",
                     lambda d: d.__setitem__("agent_id",
                                             d["agent_id"] + "-other"))),
    ("m-entry-hash", "one content hash is one byte off",
     lambda p: _edit(p, "evidence/index.json",
                     lambda d: d["entries"][0].__setitem__(
                         "content_hash", _flip_hex(d["entries"][0]["content_hash"])))),

    ("m-entry-path", "one entry points at a file that is not there",
     lambda p: _edit(p, "evidence/index.json",
                     lambda d: d["entries"][0].__setitem__("path", "files/nope.txt"))),
    ("m-entry-id", "two entries share one id",
     lambda p: _edit(p, "evidence/index.json",
                     lambda d: d["entries"][1].__setitem__(
                         "evidence_id", d["entries"][0]["evidence_id"]))),
    ("m-bom", "the manifest starts with a byte-order mark",
     lambda p: open(os.path.join(p, "manifest.json"), "wb").write(
         b"\xef\xbb\xbf" + open(os.path.join(p, "manifest.json"), "rb").read())),
    ("m-no-identity", "identity.json is missing",
     lambda p: os.remove(os.path.join(p, "identity.json"))),
    ("m-bad-time", "an event time is not a time",
     lambda p: _edit(p, "lifecycle.json",
                     lambda d: d["events"][1].__setitem__(
                         "timestamp", "2026-02-30T00:00:00Z"))),
    ("m-undeclared", "a note nobody declared, at the package root",
     lambda p: open(os.path.join(p, "notes.md"), "w").write("x")),
]


def _verdict(mutations):
    tmp = tempfile.mkdtemp()
    try:
        pkg = os.path.join(tmp, "pkg")
        shutil.copytree(BASE, pkg)
        for m in mutations:
            m[2](pkg)
        try:
            v = verify(pkg)
            return v.get("result"), sorted(c["id"] for c in v["checks"]
                                           if c["result"] == "FAIL")
        except Exception as e:  # noqa: BLE001
            return "raised", ["<raised %s>" % type(e).__name__]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def probe(triples=False):
    singles = []
    for m in MUTATIONS:
        verdict, fails = _verdict([m])
        singles.append({"id": m[0], "what": m[1], "verdict": verdict, "fails": fails})
    by_id = {s["id"]: s for s in singles}
    pairs = []
    for a, b in combinations(MUTATIONS, 2):
        verdict, fails = _verdict([a, b])
        pairs.append({"pair": [a[0], b[0]], "verdict": verdict, "fails": fails,
                      "both_caught_alone": bool(by_id[a[0]]["fails"]
                                                and by_id[b[0]]["fails"])})
    tri = []
    if triples:
        for a, b, c in combinations(MUTATIONS, 3):
            verdict, fails = _verdict([a, b, c])
            tri.append({"triple": [a[0], b[0], c[0]], "verdict": verdict,
                        "fails": fails,
                        "all_caught_alone": bool(by_id[a[0]]["fails"]
                                                 and by_id[b[0]]["fails"]
                                                 and by_id[c[0]]["fails"])})
    return singles, pairs, tri


def main():
    triples = "--triples" in sys.argv
    singles, pairs, tri = probe(triples=triples)
    if "--json" in sys.argv:
        json.dump({"singles": singles, "pairs": pairs, "triples": tri}, sys.stdout,
                  indent=2, ensure_ascii=False)
        print()
        return 0

    caught = sum(1 for s in singles if s["fails"])
    print("single mutations: %d, each caught alone: %d" % (len(singles), caught))
    for s in singles:
        print("  %-16s %-46s %s" % (s["id"], s["what"][:46],
                                   ",".join(s["fails"]) or "NOTHING"))
    print()
    silent = [p for p in pairs if not p["fails"]]
    cancelled = [p for p in silent if p["both_caught_alone"]]
    print("pairs: %d" % len(pairs))
    print("  caught something:  %d" % (len(pairs) - len(silent)))
    print("  caught nothing:    %d" % len(silent))
    print("  caught nothing although both halves were caught alone: %d"
          % len(cancelled))
    if silent:
        print("\n  pairs nothing caught:")
        for p in silent:
            print("    " + " + ".join(p["pair"])
                  + ("" if p["both_caught_alone"] else "   (one half not caught alone)"))
    if triples:
        tsilent = [t for t in tri if not t["fails"]]
        tcancel = [t for t in tsilent if t["all_caught_alone"]]
        print()
        print("triples: %d" % len(tri))
        print("  caught something:  %d" % (len(tri) - len(tsilent)))
        print("  caught nothing:    %d" % len(tsilent))
        print("  caught nothing although all three were caught alone: %d"
              % len(tcancel))
        for t in tsilent[:20]:
            print("    " + " + ".join(t["triple"]
                                     if isinstance(t["triple"], list) else t["triple"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
