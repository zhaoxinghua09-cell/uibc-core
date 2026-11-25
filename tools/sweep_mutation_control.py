"""Prove the corpus sweep can fail: mutate the real corpus and watch it refuse.

Why this exists
---------------
`sweep_competitor_corpus.py` reports "69 of 171 replayable, 0 contradict". A tool
that reports zero contradictions is making a negative claim, and a negative claim
from a tool nobody has seen fail is indistinguishable from a tool that always
says zero. The selftest checks twenty hand-built cases; twenty is still a sample.

So this control takes the *real* corpus -- the bytes the sweep already digested --
and perturbs them the way a broken vector would be broken: one nibble in a root,
one nibble in a record, one nibble in a proof hash, a dropped proof hash, an index
bumped out of range, a tree size that no longer matches the proof length. Every
perturbation is applied to an accept-side vector, which the sweep classified
`consistent`; if the detector works, each one must come back `inconsistent`.

A miss is not a curiosity, it is the whole point of the run: it would mean the
sweep could see a vector whose own numbers contradict its own verdict and still
report zero. The receipt lists every miss by name, so the claim "0 contradict"
carries the evidence that the detector could have contradicted it.

Determinism
-----------
Nothing is random. The byte to flip is chosen by `sha256(vector id ‖ family)`, so
anyone re-running against the same corpus gets the same mutations and the same
numbers, and the receipt can be checked rather than trusted.

Usage
-----
  python tools/sweep_mutation_control.py --dir <unpacked corpus> [--json]
  python tools/sweep_mutation_control.py --dir ... --write <receipt.json>
  python tools/sweep_mutation_control.py --selftest
"""

import argparse
import hashlib
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.dirname(_HERE))
import sweep_competitor_corpus as sweep

HEX = "0123456789abcdef"


def _pick(seed_text, limit):
    """A deterministic index in 0..limit-1."""
    digest = hashlib.sha256(seed_text.encode("utf-8")).hexdigest()
    return int(digest[:16], 16) % limit


def _flip_hex(value, seed_text):
    """Flip one nibble of a hex string, keeping its length."""
    if not value:
        return None
    i = _pick(seed_text, len(value))
    c = value[i].lower()
    new = HEX[(HEX.index(c) + 1) % 16] if c in HEX else "0"
    return value[:i] + new + value[i + 1:]


# --- families -------------------------------------------------------------
# Each family takes a vector and returns (mutated vector, label) or None when the
# vector has nothing of that shape (an empty proof has no hash to break).


def _incl_root(v):
    root = v.get("root") or ""
    flipped = _flip_hex(root, v.get("id", "") + "|root")
    if not flipped:
        return None
    return dict(v, root=flipped), "root"


def _incl_record(v):
    rec = v.get("record_hex") or ""
    flipped = _flip_hex(rec, v.get("id", "") + "|record")
    if not flipped:
        return None
    return dict(v, record_hex=flipped), "record"


def _incl_proof(v):
    proof = v.get("proof") or []
    if not proof:
        return None
    seed = v.get("id", "") + "|proof"
    i = _pick(seed, len(proof))
    flipped = _flip_hex(proof[i], seed)
    if not flipped:
        return None
    new = list(proof)
    new[i] = flipped
    return dict(v, proof=new), "proof[%d]" % i


def _incl_proof_drop(v):
    proof = v.get("proof") or []
    if not proof:
        return None
    return dict(v, proof=list(proof[:-1])), "proof[:-1]"


def _incl_index(v):
    index = v.get("index")
    if index is None:
        return None
    return dict(v, index=index + 1), "index+1"


def _incl_size(v):
    size = v.get("tree_size")
    if size is None:
        return None
    return dict(v, tree_size=size + 1), "tree_size+1"


def _cons_old_root(v):
    flipped = _flip_hex(v.get("old_root") or "", v.get("id", "") + "|old_root")
    if not flipped:
        return None
    return dict(v, old_root=flipped), "old_root"


def _cons_new_root(v):
    flipped = _flip_hex(v.get("new_root") or "", v.get("id", "") + "|new_root")
    if not flipped:
        return None
    return dict(v, new_root=flipped), "new_root"


def _cons_proof(v):
    proof = v.get("proof") or []
    if not proof:
        return None
    seed = v.get("id", "") + "|cons_proof"
    i = _pick(seed, len(proof))
    flipped = _flip_hex(proof[i], seed)
    if not flipped:
        return None
    new = list(proof)
    new[i] = flipped
    return dict(v, proof=new), "proof[%d]" % i


def _cons_proof_drop(v):
    proof = v.get("proof") or []
    if not proof:
        return None
    return dict(v, proof=list(proof[:-1])), "proof[:-1]"


def _cons_new_size(v):
    size = v.get("new_size")
    if size is None:
        return None
    return dict(v, new_size=size + 1), "new_size+1"


def _canon_digest(v):
    flipped = _flip_hex(v.get("canonical_sha256") or "", v.get("id", "") + "|digest")
    if not flipped:
        return None
    return dict(v, canonical_sha256=flipped), "canonical_sha256"


def _canon_len(v):
    length = v.get("canonical_len")
    if length is None:
        return None
    return dict(v, canonical_len=length + 1), "canonical_len+1"


FAMILIES = {
    "inclusion": [("root_byte", _incl_root), ("record_byte", _incl_record),
                  ("proof_byte", _incl_proof), ("proof_drop", _incl_proof_drop),
                  ("index_bump", _incl_index), ("size_bump", _incl_size)],
    "consistency": [("old_root_byte", _cons_old_root), ("new_root_byte", _cons_new_root),
                    ("proof_byte", _cons_proof), ("proof_drop", _cons_proof_drop),
                    ("size_bump", _cons_new_size)],
    "canonical": [("digest_byte", _canon_digest), ("len_bump", _canon_len)],
}

# A tree size that moves without moving any hash is not a change this arithmetic
# can see, and pretending otherwise would be the sweep flattering itself. RFC 6962
# roots do not commit to their size -- a seven-leaf proof also folds to its root at
# a claimed eight -- so "the numbers still agree" is the correct answer for that
# mutation, and it is counted apart from the ones the detector is expected to catch.
SIZE_FAMILIES = {"size_bump"}


def ambiguity_groups(corpus_dir):
    """Vectors that share a record, an index and a proof but not a tree size.

    If the corpus contains such a group, the size ambiguity is not hypothetical:
    somebody wrote both readings down. Counted so the doc can say which rather
    than assert.
    """
    incl = os.path.join(corpus_dir, "inclusion")
    groups = {}
    if not os.path.isdir(incl):
        return {"groups_with_two_sizes": 0, "ids": []}
    for name in sorted(os.listdir(incl)):
        if not name.endswith(".json"):
            continue
        v = _load(os.path.join(incl, name))
        if not v:
            continue
        key = (v.get("record_hex"), tuple(v.get("proof") or []), v.get("index"))
        groups.setdefault(key, []).append((v.get("tree_size"), v.get("id", name)))
    split = [(k, v) for k, v in groups.items() if len({s for s, _ in v}) > 1]
    return {"groups_with_two_sizes": len(split),
            "ids": sorted(i for _k, v in split for _s, i in v)}


def control(corpus_dir):
    """Mutate every replayable accept-side vector and see what the sweep says."""
    base = sweep.run(corpus_dir)
    out = {"corpus": os.path.abspath(corpus_dir),
           "before": {"vectors": base["totals"]["vectors"],
                      "replayable": base["totals"]["n_replayable"],
                      "consistent": base["totals"]["consistent"],
                      "inconsistent": base["totals"]["inconsistent"]},
           "ambiguity": ambiguity_groups(corpus_dir),
           "families": [], "ambiguous": [], "unexplained": []}
    applied = detected = ambiguous = 0
    for kind, cats in base["categories"].items():
        if kind not in FAMILIES:
            continue
        fams = []
        for label, fn in FAMILIES[kind]:
            n = hit = amb = 0
            for vec in cats["vectors"]:
                # Only a vector the sweep called consistent is a fair test: a
                # rejected one has already failed, so nothing can be learned by
                # breaking it further.
                if vec["replay"] != "consistent" or vec["expects"] != "accept":
                    continue
                raw = _load(os.path.join(corpus_dir, kind, vec["file"]))
                if raw is None:
                    continue
                got = fn(raw)
                if got is None:
                    continue
                mutated, what = got
                arith, detail = sweep.REPLAY[kind](mutated)
                verdict = sweep.classify(mutated.get("expect", {}).get("result"), arith)
                n += 1
                if verdict == "inconsistent":
                    hit += 1
                elif label in SIZE_FAMILIES:
                    amb += 1
                    out["ambiguous"].append({"kind": kind, "id": vec["id"],
                                             "mutation": what, "detail": detail})
                else:
                    out["unexplained"].append({"kind": kind, "id": vec["id"],
                                               "family": label, "mutation": what,
                                               "sweep_says": verdict, "detail": detail})
            fams.append({"family": label, "applied": n, "detected": hit,
                         "ambiguous": amb,
                         "unexplained": n - hit - amb,
                         "expected_to_detect": label not in SIZE_FAMILIES})
            applied += n
            detected += hit
            ambiguous += amb
        out["families"].append({"kind": kind, "families": fams})
    out["totals"] = {"applied": applied, "detected": detected,
                     "ambiguous": ambiguous,
                     "unexplained": applied - detected - ambiguous}
    return out


def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def selftest():
    """Every family is applied to a vector built to be right, and must be refused.

    The size family is the exception that has to stay an exception: a smaller tree
    size whose proof still folds to the published root cannot be refused by
    arithmetic, because the root does not commit to a size. Both directions are
    asserted, so a future change to the fold cannot quietly turn one into the
    other.
    """
    ra, rb, rc = b"a", b"b", b"c"
    l0, l1, l2 = (sweep.leaf_hash(x) for x in (ra, rb, rc))
    root2 = hashlib.sha256(b"\x01" + l0 + l1).digest()
    root3 = hashlib.sha256(b"\x01" + root2 + l2).digest()
    two = {"id": "T2", "tree_size": 2, "index": 0, "proof": [l1.hex()],
           "record_hex": ra.hex(), "root": root2.hex(),
           "expect": {"result": "accept"}}
    assert sweep._inclusion(two)[0] == "match"
    for label, fn in FAMILIES["inclusion"]:
        if label in SIZE_FAMILIES:
            continue
        got = fn(two)
        assert got is not None, "family %s did not apply" % label
        arith, _ = sweep._inclusion(got[0])
        assert sweep.classify("accept", arith) == "inconsistent", label
    # Two leaves to a claimed three: the proof length it needs changes, so this
    # one *is* visible.
    got = _incl_size(two)
    assert sweep.classify("accept", sweep._inclusion(got[0])[0]) == "inconsistent"
    # Right-edge leaf of a three-leaf tree, claimed as four: the proof it needs
    # also changes length, so this one is visible too.
    three = {"id": "T3", "tree_size": 3, "index": 2, "proof": [root2.hex()],
             "record_hex": rc.hex(), "root": root3.hex(),
             "expect": {"result": "accept"}}
    assert sweep._inclusion(three)[0] == "match"
    assert sweep._inclusion(_incl_size(three)[0])[0] == "mismatch"
    # The genuinely ambiguous shape: index 0 needs two hashes at both sizes, so a
    # three-leaf proof also folds to its root when the claim is four.
    amb = {"id": "T4", "tree_size": 3, "index": 0, "proof": [l1.hex(), l2.hex()],
           "record_hex": ra.hex(), "root": root3.hex(),
           "expect": {"result": "accept"}}
    assert sweep._inclusion(amb)[0] == "match"
    arith, _ = sweep._inclusion(_incl_size(amb)[0])
    assert arith == "match", "the size-only ambiguity has to stay visible as one"
    for label, fn in FAMILIES["consistency"]:
        good = {"id": "T5", "old_size": 1, "new_size": 2, "old_root": l0.hex(),
                "new_root": sweep.root_from_consistency_proof(
                    1, 2, [l1], l0).hex(), "proof": [l1.hex()],
                "expect": {"result": "accept"}}
        if label in SIZE_FAMILIES:
            continue
        got = fn(good)
        assert got is not None, label
        arith, _ = sweep._consistency(got[0])
        assert sweep.classify("accept", arith) == "inconsistent", label
    # One leaf growing to two is visible; two growing to three needs another hash.
    assert sweep.classify("accept", sweep._consistency(_cons_new_size(good)[0])[0]) \
        == "inconsistent"
    for label, fn in FAMILIES["canonical"]:
        text = '{"b":1,"a":2}'
        raw = b'{"a":2,"b":1}'
        got = fn({"id": "T6", "text": text,
                  "canonical_sha256": hashlib.sha256(raw).hexdigest(),
                  "canonical_len": len(raw), "expect": {"result": "accept"}})
        assert got is not None, label
        arith, _ = sweep._canonical(got[0])
        assert sweep.classify("accept", arith) == "inconsistent", label
    # A mutation must never be counted as a pass by accident: classify is reused.
    assert sweep.classify("accept", "none") == "none"
    total = sum(len(v) for v in FAMILIES.values())
    arithmetic = sum(1 for v in FAMILIES.values() for lb, _ in v if lb not in SIZE_FAMILIES)
    print("selftest: %d families (%d arithmetic checked, %d size-only shown to be "
          "ambiguous)" % (total, arithmetic, total - arithmetic))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", help="unpacked corpus directory")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write", metavar="PATH", help="write the receipt here")
    ap.add_argument("--head", metavar="SHA", help="upstream commit the corpus came from")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)

    if a.selftest:
        return selftest()
    if not a.dir:
        ap.error("--dir is required unless --selftest")

    r = control(a.dir)
    if a.head:
        # The receipt is meant to be committed, so it names the upstream commit
        # rather than whoever's checkout the corpus happened to sit in.
        r["head"] = a.head
        r["corpus"] = "unpacked corpus at upstream HEAD %s" % a.head
    if a.write:
        with open(a.write, "w", encoding="utf-8", newline="\n") as f:
            json.dump(r, f, indent=2, sort_keys=True)
            f.write("\n")
    if a.json:
        print(json.dumps(r, indent=2, sort_keys=True))
        return 0
    print("before: %(vectors)d vectors, %(replayable)d replayable, "
          "%(inconsistent)d inconsistent" % r["before"])
    for group in r["families"]:
        for fam in group["families"]:
            print("  %-11s %-14s applied %2d detected %2d ambiguous %2d unexplained %d"
                  % (group["kind"], fam["family"], fam["applied"],
                     fam["detected"], fam["ambiguous"], fam["unexplained"]))
    t = r["totals"]
    print("TOTAL applied %d, detected %d, ambiguous %d, unexplained %d"
          % (t["applied"], t["detected"], t["ambiguous"], t["unexplained"]))
    print("corpus vectors differing only by claimed tree size: %d group(s) %s"
          % (r["ambiguity"]["groups_with_two_sizes"], r["ambiguity"]["ids"]))
    for m in r["unexplained"]:
        print("  UNEXPLAINED %s/%s %s: %s"
              % (m["kind"], m["id"], m["family"], m["detail"]))
    return 0 if t["unexplained"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
