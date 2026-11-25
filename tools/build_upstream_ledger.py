"""How far a stranger gets on each upstream vector, from the file alone.

The published corpus is 171 vectors. This tool does not try to judge them; it
records, per vector, which of three reach levels the file itself supports:

    verdict          the published verdict follows from arithmetic on the file's
                     own numbers (RFC 6962/9162 folding, RFC 8785 canonical
                     bytes) -- the same rule set `sweep_competitor_corpus.py`
                     applies.
    signature-only   no arithmetic, but every signature the file carries
                     verifies under the key the file carries. That is a
                     necessary condition, not a verdict: the acceptance rule
                     lives in a schema none of these files ship.
    nothing          neither applies: the text will not parse, names no
                     signature, or the signature does not verify.

Nothing here is inferred from a vector's name. Names appear only as labels.

Usage:
    python tools/build_upstream_ledger.py --dir <corpus> --write
    python tools/build_upstream_ledger.py --dir <corpus> --check
    python tools/build_upstream_ledger.py --dir <corpus> --json
    python tools/build_upstream_ledger.py --selftest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import jcs  # noqa: E402
import sweep_competitor_corpus as sweep  # noqa: E402

RECEIPT = os.path.join(os.path.dirname(HERE), "docs", "upstream-package",
                       "competitor-defects", "corpus-ledger-39daf704.json")

REACH = ("verdict", "signature-only", "nothing")

# Family prose: what the file does not carry. Kept separate from measurements so
# no number in the receipt depends on a sentence written by hand.
MISSING = {
    "inclusion": "nothing: leaf, index, proof and tree size are all stated",
    "consistency": "nothing: both roots, both sizes and the proof are all stated",
    "canonical": "nothing: the text and its expected digest and length are stated",
    "token": "the acceptance rule (which claims are required, of what type, how "
             "tagged) -- the text states claims, key and signature, not the rule",
    "chain": "the rule that links consecutive records (chain-break, sequence-gap, "
             "truncation, measurement) -- the records state per-record claims and "
             "signatures, not the hash that chains them",
}


def _sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _verify_ed25519(key_hex, sig_hex, body):
    """True if sig verifies over the RFC 8785 bytes of body. Never raises."""
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
    except ImportError:  # pragma: no cover - cryptography is a test dependency
        return None
    try:
        pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(key_hex))
        pub.verify(bytes.fromhex(sig_hex), jcs.canonicalise(body).encode("utf-8"))
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def _sig_layer(kind, v):
    """(status, detail) for the signature layer of one vector.

    status is one of: verified, failed, no-key, no-signature, unparsable,
    not-applicable.
    """
    if kind == "inclusion" or kind == "consistency" or kind == "canonical":
        return "not-applicable", "arithmetic decides these; no signature is involved"

    if kind == "token":
        text = v.get("text")
        pk = v.get("public_key")
        if text is None:
            return "unparsable", "the vector carries no text"
        try:
            body = json.loads(text)
        except ValueError:
            return "unparsable", "the text is not JSON, so nothing can be checked"
        if not isinstance(body, dict):
            return "unparsable", "the text is JSON but not an object"
        sig_hex = body.get("signature") or ""
        if not pk:
            return "no-key", "the vector carries no public key"
        if not sig_hex:
            return "no-signature", "the text names no signature"
        stripped = {k: val for k, val in body.items() if k != "signature"}
        if _verify_ed25519(pk, sig_hex, stripped) is True:
            return "verified", "JCS(body without signature) verifies"
        if _verify_ed25519(pk, sig_hex, dict(stripped, signature="")) is True:
            return "failed", ("verifies only with an empty signature field present, "
                              "so the signed bytes are not the ones JCS exports")
        return "failed", "JCS(body without signature) does not verify"

    if kind == "chain":
        pk = v.get("public_key")
        records = v.get("records")
        if not isinstance(records, list) or not records:
            return "unparsable", "no records to sign"
        if not pk:
            return "no-key", "the vector carries no public key"
        ok = 0
        unsigned = 0
        for rec in records:
            sig = rec.get("signature") if isinstance(rec, dict) else None
            if not sig:
                unsigned += 1
                continue
            body = {k: val for k, val in rec.items() if k != "signature"}
            if _verify_ed25519(pk, sig, body) is True:
                ok += 1
        detail = "%d of %d record signatures verify under the shipped key" % (
            ok, len(records))
        if unsigned:
            detail += "; %d record(s) carry no signature" % unsigned
        return ("verified" if ok == len(records) else "failed"), detail

    return "not-applicable", "no layer is defined for this family"


def _reach(arith, sig_status):
    if arith != "none":
        return "verdict"
    if sig_status == "verified":
        return "signature-only"
    return "nothing"


def build(corpus_dir):
    """Walk the corpus and return the ledger (no I/O beyond reads)."""
    base = sweep.run(corpus_dir)
    rows = []
    for kind in sorted(base["categories"]):
        for x in base["categories"][kind]["vectors"]:
            path = os.path.join(corpus_dir, kind, x["file"])
            try:
                v = json.load(open(path, encoding="utf-8"))
            except ValueError:
                v = {}
            sig_status, sig_detail = _sig_layer(kind, v)
            rows.append({
                "path": "%s/%s" % (kind, x["file"]),
                "family": kind,
                "id": x["id"],
                "expect": x.get("expects"),
                "arith": x["arith"],
                "signature": sig_status,
                "reach": _reach(x["arith"], sig_status),
                "detail": sig_detail,
            })
    rows.sort(key=lambda r: r["path"])

    families = {}
    for r in rows:
        f = families.setdefault(r["family"], {
            "vectors": 0, "verdict": 0, "signature-only": 0, "nothing": 0,
            "signature_verified": 0, "missing": MISSING.get(r["family"], "")})
        f["vectors"] += 1
        f[r["reach"]] += 1
        if r["signature"] == "verified":
            f["signature_verified"] += 1

    totals = {"vectors": len(rows)}
    for name in REACH:
        totals[name] = sum(1 for r in rows if r["reach"] == name)
    totals["signature_verified"] = sum(
        1 for r in rows if r["signature"] == "verified")

    manifest = sweep.manifest(corpus_dir)
    ledger = {
        "what": "how far a stranger gets on each upstream vector, from the file alone",
        "corpus": "probityai/agent-evidence-vectors @ 39daf704",
        "manifest": {"count": manifest["count"],
                     "digest": _manifest_digest(manifest)},
        "families": families,
        "totals": totals,
        "vectors": rows,
    }
    return ledger


def _manifest_digest(manifest):
    """sha256 over 'path<TAB>sha256<LF' lines, sorted by path."""
    lines = "".join("%s\t%s\n" % (e["path"], e["sha256"])
                    for e in sorted(manifest["files"], key=lambda e: e["path"]))
    return _sha256_bytes(lines.encode("utf-8"))


def _dump(ledger):
    return json.dumps(ledger, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _summary(ledger):
    t = ledger["totals"]
    n = t["vectors"]
    lines = ["%d upstream vectors, judged only by what the file states" % n]
    for name in REACH:
        lines.append("  %-15s %3d  (%2d%%)" % (
            name, t[name], round(100.0 * t[name] / n)))
    lines.append("  signatures that verify: %d" % t["signature_verified"])
    for fam in sorted(ledger["families"]):
        f = ledger["families"][fam]
        lines.append("  %-12s %3d  verdict %2d  signature %2d  nothing %2d" % (
            fam, f["vectors"], f["verdict"], f["signature-only"], f["nothing"]))
    return "\n".join(lines)


def _compare(stored_text, fresh_text):
    """Field-level differences between two receipts, or [] when identical."""
    a = json.loads(stored_text)
    b = json.loads(fresh_text)
    out = []
    for key in ("manifest", "totals", "families"):
        if a.get(key) != b.get(key):
            out.append("%s differs: %s vs %s" % (key, a.get(key), b.get(key)))
    ra = {r["path"]: r for r in a.get("vectors", [])}
    rb = {r["path"]: r for r in b.get("vectors", [])}
    for path in sorted(set(ra) | set(rb)):
        if ra.get(path) != rb.get(path):
            out.append("vector %s differs" % path)
    return out


def _selftest():
    """Invariants, plus a small synthetic corpus whose answers are known."""
    ok = 0
    fails = []

    def check(label, cond):
        nonlocal ok
        if cond:
            ok += 1
        else:
            fails.append(label)

    import tempfile

    d = tempfile.mkdtemp()
    c = os.path.join(d, "corpus")
    os.makedirs(os.path.join(c, "token"))
    os.makedirs(os.path.join(c, "chain"))
    # one token whose signature verifies, one whose signature is a single flipped byte
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    priv = Ed25519PrivateKey.generate()
    pk = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    body = {"alg": "EdDSA", "iss": "x", "verdict": "accept"}
    sig = priv.sign(jcs.canonicalise(body).encode("utf-8")).hex()

    def write(path, obj):
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(obj, fh)

    write(os.path.join(c, "token", "T-ok.json"),
          {"id": "T-ok", "public_key": pk,
           "text": json.dumps(dict(body, signature=sig)),
           "expect": {"result": "accept"}})
    flipped = ("%02x" % (int(sig[:2], 16) ^ 1)) + sig[2:]
    write(os.path.join(c, "token", "T-bad.json"),
          {"id": "T-bad", "public_key": pk,
           "text": json.dumps(dict(body, signature=flipped)),
           "expect": {"result": "reject"}})
    write(os.path.join(c, "token", "T-text.json"),
          {"id": "T-text", "public_key": pk, "text": "{not json",
           "expect": {"result": "reject"}})

    led = build(c)
    check("sums to the number of vectors",
          sum(led["totals"][k] for k in REACH) == led["totals"]["vectors"])
    check("verifies the token it can check",
          [r for r in led["vectors"] if r["id"] == "T-ok"][0]["reach"] == "signature-only")
    check("flipped byte is a failure, not a pass",
          [r for r in led["vectors"] if r["id"] == "T-bad"][0]["signature"] == "failed")
    check("unparsable text is nothing, not signature-only",
          [r for r in led["vectors"] if r["id"] == "T-text"][0]["reach"] == "nothing")
    check("no arithmetic family here, so no verdict rows",
          led["totals"]["verdict"] == 0)
    text = _dump(led)
    check("receipt round-trips", _compare(text, text) == [])
    check("a changed total is caught", len(_compare(text, text.replace(
        '"vectors": 3', '"vectors": 4'))) >= 1)

    # The shipped receipt must be internally consistent, if it is present.
    if os.path.exists(RECEIPT):
        stored = json.load(open(RECEIPT, encoding="utf-8"))
        check("shipped receipt sums to its own total",
              sum(stored["totals"][k] for k in REACH) == stored["totals"]["vectors"])
        check("shipped receipt families sum to totals",
              sum(f["vectors"] for f in stored["families"].values())
              == stored["totals"]["vectors"])
        check("shipped receipt has no row without a reach",
              all(r.get("reach") in REACH for r in stored["vectors"]))

    if fails:
        print("SELFTEST FAILED: %s" % "; ".join(fails))
        return 1
    print("SELFTEST OK: %d checks" % ok)
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dir", help="corpus root (contains inclusion/ consistency/ ...)")
    p.add_argument("--json", action="store_true", help="print the ledger as JSON only")
    p.add_argument("--write", action="store_true", help="write the receipt")
    p.add_argument("--check", action="store_true", help="fail if the receipt is stale")
    p.add_argument("--selftest", action="store_true")
    args = p.parse_args(argv)

    if args.selftest:
        return _selftest()
    if not args.dir:
        p.error("--dir is required unless --selftest is given")

    ledger = build(args.dir)
    text = _dump(ledger)

    if args.write:
        os.makedirs(os.path.dirname(RECEIPT), exist_ok=True)
        with open(RECEIPT, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        print(_summary(ledger))
        print("wrote %s" % RECEIPT)
        return 0
    if args.check:
        if not os.path.exists(RECEIPT):
            print("MISSING RECEIPT: %s" % RECEIPT)
            return 1
        stored = open(RECEIPT, encoding="utf-8").read()
        diffs = _compare(stored, text)
        if diffs:
            print("STALE RECEIPT: %d difference(s)" % len(diffs))
            for d_line in diffs[:10]:
                print("  " + d_line)
            return 1
        print("RECEIPT CURRENT: %d vectors match field for field"
              % ledger["totals"]["vectors"])
        return 0
    if args.json:
        print(text, end="")
        return 0
    print(_summary(ledger))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
