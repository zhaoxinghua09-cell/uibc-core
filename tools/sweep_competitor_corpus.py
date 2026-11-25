"""Sweep a competitor's corpus with arithmetic only, and say what it cannot judge.

Why this exists
---------------
The three size-zero vectors we vendored (`docs/upstream-package/competitor-defects/`)
were found by reading, and three is a sample. A sample proves nothing about the
other 168. This tool walks a whole unpacked upstream corpus, replays each vector
against RFC 6962 / RFC 9162 arithmetic, and answers two separate questions.

Question 1: can the file be replayed at all without the upstream code?
Question 2: when it can, do the file's own numbers agree with the verdict the
            file publishes?

Only the second answer is interesting per vector, and it has three shapes:

  consistent      accept + the root its numbers produce matches; or reject + a
                  check the numbers themselves fail (fold mismatch, proof of the
                  wrong length, index outside 0..size-1, sizes inverted, a proof
                  that does not chain)
  inconsistent    accept + a root its numbers do not produce: the file publishes
                  a root made of leaves and calls it valid
  not replayable  no numbers to fold (tokens, chains, canonical digests: a
                  signature or a canonicaliser decides), or missing fields

A category we cannot replay is reported as zero replayable out of N, never as a
pass. The point of the sweep is the ratio, not a green tick.

Usage
-----
  python tools/sweep_competitor_corpus.py --dir <unpacked corpus> [--json]
  python tools/sweep_competitor_corpus.py --dir ... --manifest <HEAD> [--json]
      also digest every file, so a later reader can prove which bytes were swept
      without shipping 17 MB of somebody else's corpus
"""

import argparse
import hashlib
import json
import os
import sys

EMPTY_ROOT = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.dirname(_HERE))
try:
    from tools.verify_rekor_inclusion import (_decomp_incl_proof, fold, leaf_hash,
                                              root_from_consistency_proof)
except ImportError:
    from verify_rekor_inclusion import (_decomp_incl_proof, fold, leaf_hash,
                                        root_from_consistency_proof)
try:
    from tools import jcs
except ImportError:
    import jcs


def _sha256_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _inclusion(v):
    """('match'|'mismatch'|'none', detail)."""
    tree_size = v.get("tree_size")
    root = (v.get("root") or "").lower()
    if tree_size is None or not root:
        return "none", "no tree_size or no root"
    if tree_size == 0:
        if root == EMPTY_ROOT:
            return "match", "size 0 carries the empty-tree root"
        return "mismatch", "size 0 carries a root that is not the empty-tree root"
    index = v.get("index")
    if index is None:
        return "none", "no index"
    if index < 0 or index >= tree_size:
        return "mismatch", "index %d outside 0..%d-1: the numbers say reject" % (
            index, tree_size)
    record_hex = v.get("record_hex")
    proof = v.get("proof")
    if record_hex is None or proof is None:
        return "none", "no record_hex or no proof to fold"
    inner, border = _decomp_incl_proof(index, tree_size)
    want = inner + border
    if len(proof) != want:
        return "mismatch", "proof carries %d hashes, size %d at index %d needs %d" % (
            len(proof), tree_size, index, want)
    try:
        leaf = leaf_hash(bytes.fromhex(record_hex))
        folded = fold(leaf, index, tree_size, [bytes.fromhex(p) for p in proof])
    except (ValueError, TypeError) as e:
        return "none", "malformed numbers: %s" % e
    if folded.hex() == root:
        return "match", "folded root matches the published root"
    return "mismatch", "folded %s.. != published %s.." % (
        folded.hex()[:8], root[:8])


def _consistency(v):
    """('match'|'mismatch'|'none', detail)."""
    old_size = v.get("old_size")
    new_size = v.get("new_size")
    old_root = (v.get("old_root") or "").lower()
    new_root = (v.get("new_root") or "").lower()
    if old_size is None or new_size is None or not old_root or not new_root:
        return "none", "no sizes or no roots"
    if old_size == 0:
        if old_root == EMPTY_ROOT:
            return "match", "old_size 0 carries the empty-tree root"
        return "mismatch", "old_size 0 carries a root that is not the empty-tree root"
    if new_size < old_size:
        return "mismatch", "new_size %d < old_size %d: the numbers say reject" % (
            new_size, old_size)
    proof = v.get("proof") or []
    try:
        computed = root_from_consistency_proof(
            old_size, new_size, [bytes.fromhex(p) for p in proof],
            bytes.fromhex(old_root))
    except (ValueError, TypeError) as e:
        # A proof the RFC arithmetic cannot walk is a proof the numbers reject.
        return "mismatch", "the proof does not chain: %s" % e
    if computed.hex() == new_root:
        return "match", "second root recomputed from the first matches"
    return "mismatch", "recomputed %s.. != published %s.." % (
        computed.hex()[:8], new_root[:8])


def _canonical(v):
    """Their canonical digests, against RFC 8785 rather than against their code."""
    text = v.get("text")
    want = (v.get("canonical_sha256") or "").lower()
    want_len = v.get("canonical_len")
    if text is None or not want:
        return "none", "no text or no canonical_sha256"
    try:
        _data, _out, raw = jcs.canonicalise_text(text)
    except jcs.NonIntegral as e:
        return "none", "outside what JCS covers here: %s" % e
    except ValueError as e:
        return "none", "text is not JSON: %s" % e
    if hashlib.sha256(raw).hexdigest() == want and (want_len is None or len(raw) == want_len):
        return "match", "JCS(text) reproduces the published digest and length"
    return "mismatch", "JCS(text) gives %s.. / %d bytes, not %s.. / %s" % (
        hashlib.sha256(raw).hexdigest()[:8], len(raw), want[:8], want_len)


def _token(v):
    """Can the signature be checked from the file alone? Say what was tried.

    Never "match": a verdict that also depends on schema semantics is not decided
    by cryptography, so the honest answer stays "no", with the attempt recorded.
    """
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError:
        return "none", "cryptography is not installed, so no signature was attempted"
    pk = v.get("public_key")
    text = v.get("text")
    if not pk or text is None:
        return "none", "no public key or no text"
    try:
        body = json.loads(text)
    except ValueError:
        return "none", "text is not JSON, so there is nothing to sign over"
    sig_hex = body.get("signature") or ""
    if not sig_hex:
        return "none", "the text names no signature"
    try:
        pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(pk))
        sig = bytes.fromhex(sig_hex)
    except (ValueError, TypeError) as e:
        return "none", "public key or signature is not hex: %s" % e
    stripped = {k: val for k, val in body.items() if k != "signature"}
    tried = []
    for label, obj in (("JCS(body without signature)", stripped),
                       ("JCS(body with an empty signature)", dict(stripped, signature=""))):
        try:
            pub.verify(sig, jcs.canonicalise(obj).encode("utf-8"))
            tried.append(label + " VERIFIES")
        except Exception:
            tried.append(label + " does not verify")
    return "none", ("the signature would have to cover bytes the vector does not "
                    "state; " + "; ".join(tried))


REPLAY = {"inclusion": _inclusion, "consistency": _consistency,
          "canonical": _canonical, "token": _token}

NOT_NUMERIC = {
    "token": "a signature over bytes the vector does not state, plus schema semantics",
    "chain": "a record chain: signatures over records decide, and the vector does not "
             "state the signed bytes",
}

VERDICTS = ("consistent", "inconsistent", "none")


def classify(expects, arith):
    """What the published verdict rests on. Never guesses the vector's intent."""
    if arith == "none" or expects not in ("accept", "reject"):
        return "none"
    if expects == "accept":
        return "consistent" if arith == "match" else "inconsistent"
    return "consistent" if arith == "mismatch" else "inconsistent"



def run(corpus_dir):
    out = {"corpus": os.path.abspath(corpus_dir), "categories": {}}
    for kind in sorted(os.listdir(corpus_dir)):
        sub = os.path.join(corpus_dir, kind)
        if not os.path.isdir(sub):
            continue
        vectors = []
        for name in sorted(os.listdir(sub)):
            if not name.endswith(".json"):
                continue
            path = os.path.join(sub, name)
            try:
                v = json.load(open(path, encoding="utf-8"))
            except ValueError as e:
                vectors.append({"id": name, "file": name, "expects": None,
                                "replay": "none", "detail": "not JSON: %s" % e})
                continue
            expects = (v.get("expect") or {}).get("result")
            if kind in REPLAY:
                arith, detail = REPLAY[kind](v)
            else:
                arith, detail = "none", NOT_NUMERIC.get(kind, "no rule")
            vectors.append({"id": v.get("id", name), "file": name,
                            "class": v.get("class"), "expects": expects,
                            "arith": arith,
                            "replay": classify(expects, arith), "detail": detail})
        counts = {"vectors": len(vectors),
                  "replayable": sum(1 for x in vectors if x["arith"] != "none"),
                  "accept_published": sum(1 for x in vectors if x["expects"] == "accept"),
                  "reject_published": sum(1 for x in vectors if x["expects"] == "reject"),
                  # A signature is not a verdict, but "can the signature be checked
                  # at all" is a fact worth counting: it decides whether the vectors
                  # are opaque or merely schema-bound.
                  "signature_verifies": sum(
                      1 for x in vectors
                      if "without signature) VERIFIES" in (x.get("detail") or ""))}
        for k in VERDICTS:
            counts[k] = sum(1 for x in vectors if x["replay"] == k)
        out["categories"][kind] = {"counts": counts, "vectors": vectors,
                                   "why_not_numeric": NOT_NUMERIC.get(kind, "")}
    t = {"vectors": sum(c["counts"]["vectors"] for c in out["categories"].values())}
    for k in ("replayable", "accept_published", "reject_published") + VERDICTS:
        t[k if k in VERDICTS else "n_" + k] = sum(
            c["counts"][k] for c in out["categories"].values())
    out["totals"] = t
    return out


def manifest(corpus_dir):
    entries = []
    for root, _dirs, files in os.walk(corpus_dir):
        for name in sorted(files):
            if not name.endswith(".json"):
                continue
            path = os.path.join(root, name)
            entries.append({
                "path": os.path.relpath(path, os.path.dirname(corpus_dir)).replace(os.sep, "/"),
                "bytes": os.path.getsize(path),
                "sha256": _sha256_file(path),
            })
    return {"files": entries, "count": len(entries)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", help="unpacked corpus directory")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--manifest", metavar="HEAD",
                    help="also digest every file, labelled with this upstream HEAD")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)

    if a.selftest:
        body = b'{"verdict":"ALLOW"}'
        one = {"tree_size": 1, "index": 0, "proof": [],
               "record_hex": body.hex(), "root": leaf_hash(body).hex()}
        assert _inclusion(one)[0] == "match"
        assert _inclusion(dict(one, root="00" * 32))[0] == "mismatch"
        assert _inclusion({"tree_size": 0, "root": EMPTY_ROOT})[0] == "match"
        assert _inclusion({"tree_size": 0, "root": "54" * 32})[0] == "mismatch"
        # The proof-length rule: a hash short of what the size needs is a reject.
        short = dict(one, tree_size=2, index=0, root=leaf_hash(body).hex())
        assert _inclusion(short)[0] == "mismatch"
        assert "needs 1" in _inclusion(short)[1]
        # The index rule, and the inverted-size rule.
        assert _inclusion(dict(one, index=-1))[0] == "mismatch"
        assert _consistency({"old_size": 3, "new_size": 2, "old_root": "00" * 32,
                             "new_root": "11" * 32, "proof": []})[0] == "mismatch"
        # Canonical digests are judged against RFC 8785, not against their code.
        assert _canonical({"text": '{"b":1,"a":2}',
                           "canonical_sha256": hashlib.sha256(b'{"a":2,"b":1}').hexdigest(),
                           "canonical_len": 13})[0] == "match"
        assert _canonical({"text": '{"b":1,"a":2}',
                           "canonical_sha256": "00" * 32,
                           "canonical_len": 13})[0] == "mismatch"
        # Classification is where a sweep can flatter itself, so it is tested.
        assert classify("accept", "match") == "consistent"
        assert classify("accept", "mismatch") == "inconsistent"
        assert classify("reject", "mismatch") == "consistent"
        assert classify("reject", "match") == "inconsistent"
        assert classify("accept", "none") == "none"
        print("selftest: 15/15")
        return 0

    if not a.dir:
        ap.error("--dir is required unless --selftest")

    result = run(a.dir)
    if a.manifest:
        result["manifest"] = manifest(a.dir)
        result["head"] = a.manifest
    if a.json:
        print(json.dumps(result, indent=2))
        return 0

    print("corpus: %s" % result["corpus"])
    print("%-12s %7s %10s %8s %10s %8s %6s"
          % ("kind", "vectors", "replayable", "accept", "reject", "consist", "inconsist"))
    for kind, c in result["categories"].items():
        n = c["counts"]
        print("%-12s %7d %10d %8d %10d %8d %6d%s"
              % (kind, n["vectors"], n["replayable"], n["accept_published"],
                 n["reject_published"], n["consistent"], n["inconsistent"],
                 ("   (%s)" % c["why_not_numeric"]) if c["why_not_numeric"] else ""))
    t = result["totals"]
    print("TOTAL %d vectors, replayable without their code %d (%.0f%%), consistent %d, "
          "inconsistent %d, not replayable %d"
          % (t["vectors"], t["n_replayable"],
             100.0 * t["n_replayable"] / max(1, t["vectors"]),
             t["consistent"], t["inconsistent"], t["n_vectors"] if False else
             t["vectors"] - t["n_replayable"]))
    for kind, c in result["categories"].items():
        for v in c["vectors"]:
            if v["replay"] == "inconsistent":
                print("  INCONSISTENT %s/%s: %s" % (kind, v["id"], v["detail"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
