#!/usr/bin/env python3
"""Express a UIBC receipt chain as in-toto Statements inside DSSE envelopes.

Why: receipts are only readable by our own scripts today. in-toto already defines the
container (Statement + Envelope), so mapping onto it costs one file and buys readers.

    _type        https://in-toto.io/Statement/v1
    predicateType https://uibc.dev/attestation/receipt-chain/v1
    payloadType  application/vnd.in-toto+json
    signature    over PAE(payloadType, payload), per the DSSE spec

Two rules this file refuses to break:
  1. The subject digest is `uibc_core.chain.receipt_digest(envelope)`, imported rather than
     re-implemented. A mapping that hashes receipts its own way would verify against itself
     and nothing else.
  2. A signature covers PAE, not the bare payload. Envelopes signed over the payload alone
     do not verify in other implementations.

Boundary: a signature says who signed this statement. It does not say the run was the only
run, nor that the signer is anyone in particular (keyid is just a digest of the public key).

Usage:
    python tools/interop/intoto_receipt.py sign   <chain.json> <out.dsse.json> [key.pem]
    python tools/interop/intoto_receipt.py verify <chain.json> <dsse.json> [pub.pem]
    python tools/interop/intoto_receipt.py tamper <dsse.json>     # then verify must FAIL
"""
import argparse
import base64
import datetime
import hashlib
import json
import os
import pathlib
import sys

PREDICATE_TYPE = "https://uibc.dev/attestation/receipt-chain/v1"
STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
PAYLOAD_TYPE = "application/vnd.in-toto+json"

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from uibc_core.chain import receipt_digest  # noqa: E402  the repo's own definition


def pae(payload_type, body):
    """DSSE pre-authentication encoding: len(type) type len(body) body, space separated."""
    t = payload_type.encode("utf-8")
    return b"DSSEv1 %d %s %d %s" % (len(t), t, len(body), body)


def load_chain(path):
    doc = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != "uibc-core/receipt-chain/0":
        raise SystemExit("not a receipt-chain/0 document: %r" % doc.get("schema"))
    return doc


def statement_for(receipt, index, chain):
    return {
        "_type": STATEMENT_TYPE,
        "subject": [{"name": "evidence/chain.json#receipts[%d].envelope" % index,
                     "digest": {"sha256": receipt_digest(receipt["envelope"])}}],
        "predicateType": PREDICATE_TYPE,
        "predicate": {
            "schema": chain["schema"],
            "index": index,
            "envelope": receipt.get("envelope"),
            "previous_receipt_hash": receipt.get("previous_receipt_hash"),
            "chain_length": len(chain["receipts"]),
            "note": "the predicate says where this receipt sits in this chain; it says nothing "
                    "about anything outside the chain",
        },
    }


def _key(path):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    p = pathlib.Path(path)
    if p.exists():
        return serialization.load_pem_private_key(p.read_bytes(), password=None)
    key = Ed25519PrivateKey.generate()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption()))
    os.chmod(p, 0o600)
    return key


def sign(chain_path, out_path, key_path):
    from cryptography.hazmat.primitives import serialization

    chain = load_chain(chain_path)
    key = _key(key_path)
    pub = key.public_key().public_bytes(serialization.Encoding.PEM,
                                        serialization.PublicFormat.SubjectPublicKeyInfo)
    keyid = hashlib.sha256(pub).hexdigest()[:16]
    envelopes = []
    for i, receipt in enumerate(chain["receipts"]):
        body = json.dumps(statement_for(receipt, i, chain), sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False).encode("utf-8")
        envelopes.append({
            "payloadType": PAYLOAD_TYPE,
            "payload": base64.b64encode(body).decode("ascii"),
            "signatures": [{"keyid": keyid,
                            "sig": base64.b64encode(key.sign(pae(PAYLOAD_TYPE, body))).decode("ascii")}],
        })
    pathlib.Path(out_path).write_text(json.dumps({
        "schema": "uibc-core/intoto-dsse/1",
        "keyid": keyid,
        "public_key_pem": pub.decode("ascii"),
        "source": str(chain_path),
        "envelopes": envelopes,
        "at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print("signed %d receipt(s) -> %s (keyid %s)" % (len(envelopes), out_path, keyid))
    return 0


def verify(chain_path, dsse_path, pub_path=None):
    from cryptography.hazmat.primitives import serialization

    chain = load_chain(chain_path)
    doc = json.loads(pathlib.Path(dsse_path).read_text(encoding="utf-8"))
    pem = pathlib.Path(pub_path).read_bytes() if pub_path else doc["public_key_pem"].encode("ascii")
    pub = serialization.load_pem_public_key(pem)
    problems = []
    if len(doc["envelopes"]) != len(chain["receipts"]):
        problems.append("envelope count %d != receipts %d"
                        % (len(doc["envelopes"]), len(chain["receipts"])))
    previous = "0" * 64
    for i, (env, receipt) in enumerate(zip(doc["envelopes"], chain["receipts"])):
        body = base64.b64decode(env["payload"])
        try:
            pub.verify(base64.b64decode(env["signatures"][0]["sig"]), pae(env["payloadType"], body))
        except Exception:
            problems.append("receipt[%d] signature FAIL" % i)
            continue
        st = json.loads(body)
        if st.get("_type") != STATEMENT_TYPE:
            problems.append("receipt[%d] _type %r" % (i, st.get("_type")))
        if st.get("predicateType") != PREDICATE_TYPE:
            problems.append("receipt[%d] predicateType %r" % (i, st.get("predicateType")))
        want = receipt_digest(receipt["envelope"])
        got = st.get("subject", [{}])[0].get("digest", {}).get("sha256")
        if want != got:
            problems.append("receipt[%d] subject digest != receipt_digest(envelope) (%s vs %s)"
                            % (i, str(got)[:12], want[:12]))
        if receipt.get("previous_receipt_hash") != previous:
            problems.append("receipt[%d] previous_receipt_hash != receipt_digest(prev envelope)" % i)
        previous = receipt_digest(receipt["envelope"])
    if problems:
        print("VERIFY FAIL")
        for p in problems:
            print("  -", p)
        return 3
    print("VERIFY OK: %d envelope(s), signatures + statement types + subject digests + "
          "prev-hash chain all agree" % len(doc["envelopes"]))
    print("  boundary: proves who signed this statement; not that the run was unique or complete")
    return 0


def tamper(dsse_path):
    doc = json.loads(pathlib.Path(dsse_path).read_text(encoding="utf-8"))
    body = bytearray(base64.b64decode(doc["envelopes"][0]["payload"]))
    i = body.index(b"chain_length") + len(b"chain_length")
    while not (0x30 <= body[i] <= 0x39):
        i += 1
    body[i] = 0x37 if body[i] != 0x37 else 0x38
    doc["envelopes"][0]["payload"] = base64.b64encode(bytes(body)).decode("ascii")
    out = pathlib.Path(dsse_path).with_name("tampered_dsse.json")
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", out, "-- verifying it must now fail")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sign")
    s.add_argument("chain"); s.add_argument("out")
    s.add_argument("key", nargs="?", default=os.environ.get("UIBC_INTEROP_KEY", "interop-demo-key.pem"))
    v = sub.add_parser("verify")
    v.add_argument("chain"); v.add_argument("dsse")
    v.add_argument("pub", nargs="?", default=None)
    t = sub.add_parser("tamper")
    t.add_argument("dsse")
    a = ap.parse_args(argv)
    if a.cmd == "sign":
        return sign(a.chain, a.out, a.key)
    if a.cmd == "verify":
        return verify(a.chain, a.dsse, a.pub)
    return tamper(a.dsse)


if __name__ == "__main__":
    sys.exit(main())
