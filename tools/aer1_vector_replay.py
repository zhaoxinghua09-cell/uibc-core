#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Replay AER-1 (draft-zambo-aer1) vectors with an implementation written here.

Why this exists
---------------
`tools/aer1_crosswalk.py` maps AER-1 *vector classes* to uibc checks at class
level, and says why: the two receipt schemas differ, so pushing their files
through our verifier would surface schema mismatches, not findings. That is a
true statement about a class-level comparison — and it leaves the corpus itself
unexecuted.

This tool executes it. The algorithms are implemented here, from the normative
text quoted in each vector file, and they do NOT import `uibc_core`. Two
consequences:

  * a PASS means "this implementation of the written rule reproduces the
    published expectation", not "our receipt format accepts their receipt";
  * where our in-repo Merkle uses RFC 6962 construction (odd node promoted),
    AER-1 Section 8.1 uses odd node *duplicated* — a different tree, so the
    same leaves give a different root. The code below implements theirs.

Covered families (each vector counted once, failure paths included):
  merkle        9   Section 8.1 leaf/node/odd-duplication, legacy construction
                    rejection, empty/single leaf, duplicate receipt_id
  unicode       5   Section 4: no Unicode normalisation; two MUST-mismatch pairs
  chain         7   Section 7 entry digest over decoded canonical_bytes, link,
                    genesis, closing entry
  chain-v07    28   -07 construction: digest binds prev/seq/job_id/close/id/tool/
                    provenance_class/output_hash; contiguous seq; one job_id;
                    boolean close only on the last entry; integer-valued floats
                    accepted; boolean seq rejected; ECMAScript-style escapes

Not covered here: anchor (8), commitment (8), id-binding (6), workflow-root (7).
That is 22 of 143 vectors, stated rather than glossed.

Usage
-----
    python tools/aer1_vector_replay.py --kit <corpus-dir>
    python tools/aer1_vector_replay.py --kit <corpus-dir> --json
Exit code 0 = every replayable vector reproduced its expectation.
"""

import argparse
import base64
import hashlib
import json
import os
import sys


def _sha_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ---------------------------------------------------------------- merkle (§8.1)

def _leaf(receipt_id: str) -> bytes:
    return hashlib.sha256(receipt_id.encode("utf-8")).digest()


def _node(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(left + right).digest()


def _merkle_root(leaves) -> str:
    if not leaves:
        return _sha_hex(b"")
    level = list(leaves)
    while len(level) > 1:
        if len(level) % 2:
            level = level + [level[-1]]          # odd node duplicated (§8.1)
        level = [_node(level[i], level[i + 1]) for i in range(0, len(level), 2)]
    return level[0].hex()


def replay_merkle(kit) -> list:
    rows = []
    d = json.load(open(os.path.join(kit, "merkle-vectors.json")))
    for v in d["vectors"]:
        if "receipt_ids" in v:
            leaves = [_leaf(r) for r in v["receipt_ids"]]
        else:                                     # legacy construction: preimage leaves
            leaves = [hashlib.sha256(x["preimage"].encode("utf-8")).digest()
                      for x in v["leaves"]]
        got = _merkle_root(leaves)
        ok = got == v["expected_root"]
        if ok and "must_not_equal" in v:
            ok = got != v["must_not_equal"]
        rows.append(("merkle", v["name"], ok, got, v["expected_root"]))
    return rows


# --------------------------------------------------------------- unicode (§4)

def replay_unicode(kit) -> list:
    rows = []
    d = json.load(open(os.path.join(kit, "unicode-vectors.json")))
    for v in d["vectors"]:
        raw = base64.b64decode(v["payload_base64"])
        hex_ok = raw.hex() == v["payload_utf8_hex"]
        sha_ok = _sha_hex(raw) == v["sha256"]
        judged = "match" if (hex_ok and sha_ok) else "mismatch"
        rows.append(("unicode", v["name"], judged == v["expected"], judged, v["expected"]))
    return rows


# ----------------------------------------------------------------- chain (§7)

def replay_chain(kit) -> list:
    rows = []
    d = json.load(open(os.path.join(kit, "chain-vectors.json")))
    for v in d["vectors"]:
        prev, verdict, _why = "0" * 64, "valid", None
        for i, e in enumerate(v["timeline"]):
            raw = base64.b64decode(e["canonical_bytes"])
            if e["prev_digest"] != prev:
                verdict, _why = "invalid", "entry%d link broken" % i
                break
            prev = _sha_hex(raw)
        if verdict == "valid" and v["timeline"][-1].get("close") is not True:
            verdict, _why = "invalid", "last entry lacks close=true"
        rows.append(("chain", v["name"], verdict == v["expected_verdict"],
                     verdict, v["expected_verdict"]))
    return rows


# -------------------------------------------------------------- chain-v07 §7

def _canon(obj) -> bytes:
    """AER-1 -07 canonical JSON: sorted keys, no whitespace, ECMAScript-style
    escapes (lowercase \\uXXXX for non-ASCII, short escapes for control
    characters), integer-valued floats written as integers."""
    def norm(v):
        if isinstance(v, bool):
            return v
        if isinstance(v, float) and v.is_integer():
            return int(v)
        if isinstance(v, dict):
            return {k: norm(x) for k, x in v.items()}
        if isinstance(v, list):
            return [norm(x) for x in v]
        return v
    return json.dumps(norm(obj), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("utf-8")


def _entry_digest(e) -> str:
    try:
        raw = base64.b64decode(e["canonical_bytes"], validate=True)
    except Exception:
        raise ValueError("canonical_bytes not valid base64")
    obj = {
        "prev_digest": e["prev_digest"],
        "seq": e["seq"],
        "job_id": e.get("job_id"),
        "close": e.get("close", False),
        "id": e["id"],
        "tool": e.get("tool"),
        "provenance_class": e.get("provenance_class"),
        "output_hash": _sha_hex(raw),
    }
    return _sha_hex(_canon(obj))


def _check_v07(v):
    tl = v["timeline"]
    if len({json.dumps([e.get("job_id")], ensure_ascii=False) for e in tl}) != 1:
        return "invalid", "multiple job_id"
    prev = "0" * 64
    for i, e in enumerate(tl):
        if "prev_digest" not in e:
            return "invalid", "entry%d missing prev_digest" % i
        if e["prev_digest"] != prev:
            return "invalid", "entry%d link broken" % i
        if "seq" not in e:
            return "invalid", "entry%d missing seq" % i
        s = e["seq"]
        if isinstance(s, bool):
            return "invalid", "entry%d seq is boolean" % i
        if not isinstance(s, (int, float)):
            return "invalid", "entry%d seq not numeric" % i
        if s != i + 1:
            return "invalid", "entry%d seq not contiguous" % i
        c = e.get("close", False)
        if not isinstance(c, bool):
            return "invalid", "entry%d close not boolean" % i
        if i == len(tl) - 1 and c is not True:
            return "invalid", "last entry not closed"
        if i != len(tl) - 1 and c is True:
            return "invalid", "entry%d closed early" % i
        try:
            prev = _entry_digest(e)
        except ValueError as ex:
            return "invalid", "entry%d %s" % (i, ex)
    return "valid", None


def replay_chain_v07(kit) -> list:
    rows = []
    d = json.load(open(os.path.join(kit, "chain-vectors-v07.json")))
    for v in d["vectors"]:
        got, _ = _check_v07(v)
        rows.append(("chain-v07", v["name"], got == v["expected_verdict"],
                     got, v["expected_verdict"]))
    return rows


FAMILIES = [
    ("merkle", replay_merkle),
    ("unicode", replay_unicode),
    ("chain", replay_chain),
    ("chain-v07", replay_chain_v07),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kit", required=True, help="corpus dir (contains base/*.json)")
    ap.add_argument("--json", action="store_true", help="machine-readable result")
    a = ap.parse_args()

    base = os.path.join(a.kit, "base") if os.path.isdir(os.path.join(a.kit, "base")) else a.kit
    rows, per = [], {}
    for name, fn in FAMILIES:
        try:
            fam = fn(base)
        except FileNotFoundError:
            print("skip family %s: vector file not found" % name)
            continue
        rows.extend(fam)
        per[name] = {"vectors": len(fam), "pass": sum(1 for r in fam if r[2])}

    for cls, vec, ok, got, exp in rows:
        if not ok:
            print("FAIL  %-12s %-40s got=%s exp=%s" % (cls, vec, got, exp))
    total = len(rows)
    passed = sum(1 for r in rows if r[2])
    summary = {"families": per, "vectors_replayed": total, "pass": passed,
               "all_pass": passed == total}
    if a.json:
        print(json.dumps(summary, indent=1, ensure_ascii=False))
    else:
        for name, s in per.items():
            print("%-12s %d/%d" % (name, s["pass"], s["vectors"]))
        print("\n%d/%d vectors reproduced (independent implementation, no uibc_core import)" % (passed, total))
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
