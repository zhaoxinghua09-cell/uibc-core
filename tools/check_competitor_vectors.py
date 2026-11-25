#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Judge a third party's *negative* vectors without using that third party's code.

Why this exists: `probityai/agent-evidence-vectors` ships three vectors that declare
`tree_size: 0` (or `old_size: 0`) **and** carry a Merkle root that is not the RFC
6962 root of an empty tree. All three publish the verdict `reject`, so a reader
cannot tell whether their verifier refused the *arithmetic* or merely refused
self-contradictory input. A test that can only pass by refusing to look at the
numbers is not testing the numbers - and the same published vector could not
distinguish an implementation that handles empty trees correctly from one that
rejects them by accident.

This tool answers one question per vector: **which code does the data itself force?**
It never reads their verifier and never trusts their `expect` block. The one constant
it does trust is the RFC's:

    MTH(D[0:0]) = SHA-256(b"") = e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
    (RFC 6962, section 2.1, empty tree hash)

So "size 0" beside any other root is the vector contradicting itself. Per vector the
report gives `declared_code` (what they publish), `forced_code` (what the data forces)
and `agrees`.

Well-formed twins live in `v0.38.0-counter/`: same shapes, correct constants, and a
reject that is forced by a structural rule instead of by a broken number. Judge them
together or the comparison says nothing.

Usage:
    python tools/check_competitor_vectors.py --dir docs/upstream-package/competitor-defects/v0.38.0
    python tools/check_competitor_vectors.py --dir ... --json
    python tools/check_competitor_vectors.py --self-test
"""
import argparse
import hashlib
import json
import os
import sys

EMPTY_ROOT = hashlib.sha256(b"").hexdigest()
SHA_PREFIX = "sha-256:"


def _finding(code, detail):
    return {"code": code, "detail": detail}


def _root_constant(value, size, field):
    value = value or ""
    if value.startswith(SHA_PREFIX):
        value = value[len(SHA_PREFIX):]
    if size == 0 and value.lower() != EMPTY_ROOT:
        return _finding("root-contradicts-size-zero",
                        "%s is %s but a 0-leaf tree has root %s (RFC 6962 2.1)"
                        % (field, value[:16] + "…", EMPTY_ROOT[:16] + "…"))
    return None


def _int(v, name, out):
    value = v.get(name)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        out.append(_finding("schema", "%s is not a non-negative integer (%r)" % (name, value)))
        return None
    return value


def judge_inclusion(v):
    out = []
    tree_size = _int(v, "tree_size", out)
    index = _int(v, "index", out)
    if tree_size is not None and index is not None and index >= tree_size:
        out.append(_finding("not-included",
                            "index %d does not exist in a tree of %d leaves" % (index, tree_size)))
    f = _root_constant(v.get("root"), tree_size, "root")
    if f:
        out.append(f)
    return out


def judge_consistency(v):
    out = []
    old_size = _int(v, "old_size", out)
    new_size = _int(v, "new_size", out)
    if old_size is not None and new_size is not None and old_size > new_size:
        out.append(_finding("schema", "old_size %d exceeds new_size %d" % (old_size, new_size)))
    if old_size is not None and new_size is not None and old_size == new_size and v.get("proof"):
        out.append(_finding("schema", "equal sizes %d=%d require an empty proof, got %d nodes"
                            % (old_size, new_size, len(v.get("proof") or []))))
    for field, size in (("old_root", old_size), ("new_root", new_size)):
        f = _root_constant(v.get(field), size, field)
        if f:
            out.append(f)
    return out


def judge_token(v):
    out = []
    try:
        text = json.loads(v.get("text") or "{}")
    except ValueError:
        return [_finding("schema", "text is not JSON")]
    claims = text.get("poc_claims") or {}
    size = _int(claims, "tree_size", out)
    f = _root_constant(claims.get("merkle_root"), size, "poc_claims.merkle_root")
    if f:
        out.append(f)
    return out


JUDGES = {"inclusion": judge_inclusion, "consistency": judge_consistency, "token": judge_token}


def check(path):
    with open(path, encoding="utf-8") as f:
        v = json.load(f)
    kind = v.get("kind")
    if kind not in JUDGES:
        return {"file": os.path.basename(path), "id": v.get("id"), "kind": kind,
                "skipped": "unknown kind", "findings": [], "declared_code": [],
                "forced_code": [], "agrees": None}
    declared = sorted(set((v.get("expect") or {}).get("code") or []))
    findings = JUDGES[kind](v)
    forced = sorted({f["code"] for f in findings})
    return {"file": os.path.basename(path), "id": v.get("id"), "kind": kind,
            "declared_result": (v.get("expect") or {}).get("result"),
            "declared_code": declared, "forced_code": forced,
            "agrees": bool(forced) and declared == forced,
            "findings": findings}


def run(dirpath):
    files = sorted(f for f in os.listdir(dirpath) if f.endswith(".json"))
    return [check(os.path.join(dirpath, f)) for f in files]


def selftest():
    cases = []
    well_formed = {"kind": "inclusion", "tree_size": 0, "index": 0, "proof": [], "root": EMPTY_ROOT,
                   "expect": {"code": ["not-included"], "result": "reject"}}
    cases.append(("well-formed size 0 rejects for the leaf count",
                  [f["code"] for f in judge_inclusion(well_formed)] == ["not-included"]))
    broken = dict(well_formed, root="00" * 32)
    codes = [f["code"] for f in judge_inclusion(broken)]
    cases.append(("a non-empty-tree root beside size 0 is the contradiction",
                  "root-contradicts-size-zero" in codes and "not-included" in codes))
    tok = {"kind": "token",
           "text": json.dumps({"poc_claims": {"tree_size": 0, "merkle_root": SHA_PREFIX + "11" * 32}})}
    cases.append(("a token claiming size 0 with another root is the contradiction",
                  [f["code"] for f in judge_token(tok)] == ["root-contradicts-size-zero"]))
    cons = {"kind": "consistency", "old_size": 0, "new_size": 0,
            "old_root": EMPTY_ROOT, "new_root": EMPTY_ROOT, "proof": ["00" * 32]}
    cases.append(("equal sizes with a non-empty proof is a schema failure",
                  [f["code"] for f in judge_consistency(cons)] == ["schema"]))
    bad = [name for name, passed in cases if not passed]
    print("self-test: %d/%d" % (len(cases) - len(bad), len(cases)))
    for name in bad:
        print("  FAILED:", name, file=sys.stderr)
    return 0 if not bad else 1


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", action="append", help="directory of vectors; repeatable")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        return selftest()
    if not args.dir:
        ap.print_help()
        return 2
    if args.json:
        print(json.dumps({"empty_tree_root": EMPTY_ROOT,
                          "dirs": [{"dir": d, "vectors": run(d)} for d in args.dir]}, indent=2))
    agree = total = 0
    for d in args.dir:
        print("== %s" % d)
        for v in run(d):
            total += 1
            agree += 1 if v["agrees"] else 0
            print("%-34s %-11s declared=%-20s forced=%-34s agrees=%s"
                  % (v["file"], v["kind"], ",".join(v["declared_code"]) or "-",
                     ",".join(v["forced_code"]) or "-", v["agrees"]))
            for f in v["findings"]:
                print("    - %s: %s" % (f["code"], f["detail"]))
    print("VERDICT: %d/%d vectors where the data forces the published code" % (agree, total))
    return 0 if agree == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
