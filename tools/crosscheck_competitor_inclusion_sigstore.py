#!/usr/bin/env python3
"""Judge the competitor's inclusion vectors with arithmetic we did not write.

`sweep_competitor_corpus.py` reports 69 of 171 replayable. Every one of those is
replayed by *our* fold functions, which is exactly the critique our own standard
makes: the code that produces the number also certifies it. So this tool hands the
same inclusion bytes to the vendored Sigstore implementation
(`tools/third_party/sigstore_merkle.py`, upstream Rekor's Trillian-derived folding),
which shares no code path with ours, and asks one question per vector:

    fold the leaf up the published path -- does it land on the published root?

and then compares that answer with two independent statements: the verdict the
vector itself publishes, and the row our sweep receipt already recorded.

It does not touch consistency vectors (the vendored Sigstore code has no
consistency fold) or canonical vectors (no Merkle arithmetic at all). Those stay
counted as ours, and the report says so rather than averaging over them.

    python3 tools/crosscheck_competitor_inclusion_sigstore.py --dir <corpus>
    python3 tools/crosscheck_competitor_inclusion_sigstore.py --dir <corpus> --json
    python3 tools/crosscheck_competitor_inclusion_sigstore.py --dir <corpus> --write
    python3 tools/crosscheck_competitor_inclusion_sigstore.py --check
    python3 tools/crosscheck_competitor_inclusion_sigstore.py --selftest
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
sys.path.insert(0, os.path.join(HERE, "tools", "third_party"))

import sweep_competitor_corpus as sweep  # noqa: E402
import sigstore_merkle as sig  # noqa: E402

RECEIPT = os.path.join(HERE, "docs", "upstream-package", "competitor-defects",
                       "inclusion-second-implementation.json")
SWEEP_RECEIPT = os.path.join(HERE, "docs", "upstream-package", "competitor-defects",
                             "corpus-sweep-39daf704.json")


def _library_fold(v):
    """(status, detail). status in {valid, invalid, no-empty-root, unusable}."""
    tree_size = v.get("tree_size")
    root = (v.get("root") or "").lower()
    index = v.get("index")
    record_hex, proof = v.get("record_hex"), v.get("proof")
    if tree_size == 0:
        return "no-empty-root", "the vendored Sigstore fold has no MTH({}) to compare with"
    if tree_size is None or not root or index is None or record_hex is None or proof is None:
        return "unusable", "the vector does not state size, root, index, record and proof"
    if index < 0 or index >= tree_size:
        return "invalid", "index %d outside 0..%d-1 (the library would read out of range)" % (
            index, tree_size - 1)
    inner, border = sig._decomp_inclusion_proof(index, tree_size)
    if len(proof) != inner + border:
        return "invalid", "proof carries %d hashes, the library requires %d" % (
            len(proof), inner + border)
    try:
        leaf = sig._hash_leaf(bytes.fromhex(record_hex))
        hashes = [bytes.fromhex(p) for p in proof]
    except (ValueError, TypeError) as e:
        return "unusable", "malformed hex: %s" % e
    mid = sig._chain_inner(leaf, hashes[:inner], index)
    calc = sig._chain_border_right(mid, hashes[inner:])
    if calc.hex() == root:
        return "valid", "the Sigstore fold lands on the published root"
    return "invalid", "the Sigstore fold lands on %s.., not the published %s.." % (
        calc.hex()[:8], root[:8])


def _verdict_of(status):
    return {"valid": "accept", "invalid": "reject"}.get(status)


def build(corpus_dir, sweep_receipt=SWEEP_RECEIPT):
    with open(sweep_receipt, encoding="utf-8") as f:
        ours = json.load(f)
    by_file = {}
    for fam in ours["categories"].values():
        for row in fam["vectors"]:
            if "file" in row:
                by_file[row["file"]] = row

    inc_dir = os.path.join(corpus_dir, "inclusion")
    rows = []
    for name in sorted(os.listdir(inc_dir)):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(inc_dir, name), encoding="utf-8") as f:
            v = json.load(f)
        status, detail = _library_fold(v)
        publishes = (v.get("expect") or {}).get("result")
        verdict = _verdict_of(status)
        ours_row = by_file.get(name, {})
        ok_pub = (verdict == publishes) if verdict else None
        ok_sweep = None
        if ok_pub is not None and ours_row.get("replay") in ("consistent", "inconsistent"):
            ok_sweep = (ours_row["replay"] == "consistent") == ok_pub
        rows.append({
            "file": name,
            "id": v.get("id", name),
            "published": publishes,
            "library_status": status,
            "library_verdict": verdict,
            "agrees_with_published": ok_pub,
            "sweep_replay": ours_row.get("replay"),
            "agrees_with_sweep": ok_sweep,
            "detail": detail,
        })

    compared = [r for r in rows if r["library_verdict"]]
    totals = {
        "inclusion_vectors": len(rows),
        "compared": len(compared),
        "agree_with_published": sum(1 for r in compared if r["agrees_with_published"]),
        "agree_with_sweep": sum(1 for r in compared if r["agrees_with_sweep"] is True),
        "disagree_with_sweep": sum(1 for r in compared if r["agrees_with_sweep"] is False),
        "skipped_no_empty_root": sum(1 for r in rows if r["library_status"] == "no-empty-root"),
        "unusable": sum(1 for r in rows if r["library_status"] == "unusable"),
    }
    return {
        "what": "the competitor's inclusion vectors, folded by a vendored Sigstore implementation",
        "library": "tools/third_party/sigstore_merkle.py (upstream Rekor, Trillian-derived)",
        "corpus": "probityai/agent-evidence-vectors @ %s" % ours.get("head", "39daf704"),
        "manifest_digest": ours.get("manifest", {}).get("count") and _digest(ours),
        "covers": "inclusion only; consistency and canonical stay counted as ours in the sweep",
        "totals": totals,
        "vectors": rows,
    }


def _digest(sweep_receipt):
    import hashlib
    entries = sweep_receipt["manifest"]["files"]
    lines = "".join("%s\t%s\n" % (e["path"], e["sha256"]) for e in entries)
    return hashlib.sha256(lines.encode("utf-8")).hexdigest()


def _dump(report):
    return json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _summary(report):
    t = report["totals"]
    return "\n".join([
        "%d inclusion vectors, %d folded by the vendored Sigstore implementation"
        % (t["inclusion_vectors"], t["compared"]),
        "  agrees with the published verdict: %d of %d" % (t["agree_with_published"], t["compared"]),
        "  agrees with our sweep's row:       %d of %d (%d disagree)"
        % (t["agree_with_sweep"], t["compared"], t["disagree_with_sweep"]),
        "  not compared: %d (no MTH({}) in the library), %d unusable"
        % (t["skipped_no_empty_root"], t["unusable"]),
        "scope: inclusion only -- consistency and canonical remain our arithmetic",
    ])


def _compare(a_text, b_text):
    a, b = json.loads(a_text), json.loads(b_text)
    diffs = []
    for key in ("totals", "manifest_digest", "corpus"):
        if a.get(key) != b.get(key):
            diffs.append("%s: receipt %r vs run %r" % (key, a.get(key), b.get(key)))
    ra = {r["file"]: r for r in a.get("vectors", [])}
    rb = {r["file"]: r for r in b.get("vectors", [])}
    for path in sorted(set(ra) | set(rb)):
        if ra.get(path) != rb.get(path):
            diffs.append("vector %s differs" % path)
    return diffs


def _selftest():
    ok, fails = 0, []

    def check(label, cond):
        nonlocal ok
        if cond:
            ok += 1
        else:
            fails.append(label)

    leaf = b"selftest record"
    proof = [bytes([0x11]) * 32, bytes([0x22]) * 32]
    inner, border = sig._decomp_inclusion_proof(0, 4)
    check("the library asks 2 hashes for (index 0, size 4)", inner + border == 2)
    good = {
        "tree_size": 4, "index": 0, "record_hex": leaf.hex(),
        "proof": [p.hex() for p in proof],
    }
    mid = sig._chain_inner(sig._hash_leaf(leaf), proof[:inner], 0)
    root = sig._chain_border_right(mid, proof[inner:]).hex()
    good["root"] = root
    status, _ = _library_fold(good)
    check("a fold that lands on its root is valid", status == "valid")
    flipped = dict(good, root=("00" * 32))
    status, _ = _library_fold(flipped)
    check("a root the fold cannot reach is invalid", status == "invalid")
    short = dict(good, proof=[proof[0].hex()])
    status, _ = _library_fold(short)
    check("a proof of the wrong length is invalid", status == "invalid")
    empty = {"tree_size": 0, "root": "e3b0" * 16}
    status, _ = _library_fold(empty)
    check("size 0 is not compared, not passed", status == "no-empty-root")
    status, _ = _library_fold({"tree_size": 3})
    check("a vector missing fields is unusable", status == "unusable")
    check("a changed total is caught by the receipt comparison",
          len(_compare(_dump({"totals": {"compared": 1}}),
                       _dump({"totals": {"compared": 2}}))) >= 1)
    if fails:
        print("SELFTEST FAILED: %s" % "; ".join(fails))
        return 1
    print("SELFTEST OK: %d checks" % ok)
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dir", help="corpus root (the directory holding inclusion/)")
    p.add_argument("--json", action="store_true")
    p.add_argument("--write", action="store_true")
    p.add_argument("--check", action="store_true")
    p.add_argument("--selftest", action="store_true")
    args = p.parse_args(argv)
    if args.selftest:
        return _selftest()
    if not args.dir:
        p.error("--dir is required unless --selftest is given")

    report = build(args.dir)
    text = _dump(report)
    if args.write:
        os.makedirs(os.path.dirname(RECEIPT), exist_ok=True)
        with open(RECEIPT, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print(_summary(report))
        print("wrote %s" % RECEIPT)
        return 0
    if args.check:
        if not os.path.exists(RECEIPT):
            print("MISSING RECEIPT: %s" % RECEIPT)
            return 1
        with open(RECEIPT, encoding="utf-8") as f:
            stored = f.read()
        diffs = _compare(stored, text)
        if diffs:
            print("STALE RECEIPT: %d difference(s)" % len(diffs))
            for d in diffs[:10]:
                print("  " + d)
            return 1
        print("RECEIPT CURRENT: %d inclusion rows match"
              % report["totals"]["inclusion_vectors"])
        return 0
    if args.json:
        print(text, end="")
        return 0
    print(_summary(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
