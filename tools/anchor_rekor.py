#!/usr/bin/env python3
"""Anchor a package head into Sigstore Rekor (public transparency log, v1).

Difference from TSA: a timestamp says "this digest existed at T". A transparency
log says "this digest sits at index N of a public ledger, here is the inclusion
proof, and the log's own root can be checked against it". arkforge anchors to
Rekor; this closes the same door, not a wider one.

What leaves the machine: a signature over the artifact bytes plus the public key.
Nothing else. This is public and cannot be withdrawn - run it only when the
release is one you are willing to publish.

Key type: ECDSA P-256. Rekor's `hashedrekord` rejects Ed25519 with a confusing
'"SHA-256" not in [SHA-512]' and rejects a SHA-512 retry with 'invalid signature'
(2026-11 tested three ways); P-256 works first time.

Usage:
    python tools/anchor_rekor.py --artifact <file> [--key <pem>]
    python tools/anchor_rekor.py --verify <entry.json> --artifact <file> [--uuid <uuid>]
"""

import argparse
import base64
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

REKOR = "https://rekor.sigstore.dev"


def _ec():
    from cryptography.hazmat.primitives.asymmetric import ec
    return ec


def load_or_make_key(path: str):
    from cryptography.hazmat.primitives import serialization
    if os.path.isfile(path):
        with open(path, "rb") as f:
            return serialization.load_pem_private_key(f.read(), password=None)
    key = _ec().generate_private_key(_ec().SECP256R1())
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as f:
        f.write(key.private_bytes(serialization.Encoding.PEM,
                                  serialization.PrivateFormat.PKCS8,
                                  serialization.NoEncryption()))
    print("generated new ECDSA P-256 key at %s (never commit it)" % path)
    return key


def public_pem(key) -> bytes:
    from cryptography.hazmat.primitives import serialization
    return key.public_key().public_bytes(serialization.Encoding.PEM,
                                         serialization.PublicFormat.SubjectPublicKeyInfo)


def hashedrekord_body(artifact: bytes, key) -> dict:
    from cryptography.hazmat.primitives import hashes
    sig = key.sign(artifact, _ec().ECDSA(hashes.SHA256()))
    return {
        "apiVersion": "0.0.1",
        "kind": "hashedrekord",
        "spec": {
            "signature": {
                "content": base64.b64encode(sig).decode(),
                "publicKey": {"content": base64.b64encode(public_pem(key)).decode()},
            },
            "data": {"hash": {"algorithm": "sha256",
                              "value": hashlib.sha256(artifact).hexdigest()}},
        },
    }


def post_entry(body: dict, timeout: int = 25):
    data = json.dumps(body).encode()
    req = urllib.request.Request(REKOR + "/api/v1/log/entries", data=data,
                                 method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return True, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return False, {"error": "HTTP %s: %s" % (e.code, e.read().decode("utf-8", "replace")[:300])}
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        return False, {"error": "unreachable: %s" % e}


def get_entry(uuid: str, timeout: int = 25):
    try:
        with urllib.request.urlopen(REKOR + "/api/v1/log/entries/" + uuid, timeout=timeout) as r:
            return True, json.loads(r.read().decode())
    except Exception as e:
        return False, {"error": str(e)}


def _inclusion_status(payload: dict, body_bytes: bytes):
    """Report what we can honestly say about Rekor's inclusion proof.

    Rekor's `inclusionProof` is a Trillian-side partial proof (20 siblings for a
    3.8e9-leaf tree, and it does not verify as a full RFC 6962 path from the leaf
    with our own merkle walker - 2026-11 tested both sibling orders). Verifying it
    properly needs Rekor's signed checkpoint (log key + tile hashes). So we do
    **not** claim independent inclusion verification here; the caller gets an
    explicit "not verified" flag rather than a green light.
    """
    proof = (payload.get("verification") or {}).get("inclusionProof") or {}
    return {"verified": False,
            "reason": "rekor inclusion proof needs the log's signed checkpoint; "
                      "not independently verified by this tool",
            "tree_size": proof.get("treeSize"),
            "log_index_in_tree": proof.get("logIndex")}


def verify_entry(entry_doc: dict, artifact: bytes):
    problems = []
    try:
        uuid, payload = list(entry_doc.items())[0]
    except Exception as e:
        return False, {}, ["entry document has no entries object (%s)" % e]

    digest = hashlib.sha256(artifact).hexdigest()
    try:
        body_bytes = base64.b64decode(payload["body"])
    except Exception as e:
        return False, {}, ["entry has no readable body (%s)" % e]
    try:
        rec = json.loads(body_bytes.decode())
    except Exception as e:
        return False, {}, ["cannot decode entry body (%s)" % e]

    spec = rec.get("spec", {})
    claimed = spec.get("data", {}).get("hash", {}).get("value")
    if claimed != digest:
        problems.append("log entry hashes %r, artifact hashes %r" % (claimed, digest))

    try:
        from cryptography import x509  # noqa: F401  (ensures cryptography is importable)
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        sig = base64.b64decode(spec["signature"]["content"])
        pem = base64.b64decode(spec["signature"]["publicKey"]["content"])
        pub = serialization.load_pem_public_key(pem)
        pub.verify(sig, artifact, ec.ECDSA(hashes.SHA256()))
    except Exception as e:
        problems.append("signature in the log entry does not verify (%s)" % e)

    info = {
        "uuid": uuid,
        "log_index": payload.get("logIndex"),
        "log_id": payload.get("logID"),
        "integrated_time": payload.get("integratedTime"),
        "tree_size": ((payload.get("verification") or {}).get("inclusionProof") or {}).get("treeSize"),
        "inclusion": _inclusion_status(payload, body_bytes),
    }
    return (not problems), info, problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact", help="file to anchor (its digest goes to the log)")
    ap.add_argument("--key", default=os.path.join("tools", "out", "rekor_ec_key.pem"))
    ap.add_argument("--out-dir", default="tools/out")
    ap.add_argument("--verify", help="rekor entry JSON to check against an artifact")
    ap.add_argument("--uuid", help="with --verify, re-fetch the entry from Rekor first")
    ap.add_argument("--timeout", type=int, default=25)
    args = ap.parse_args()

    if not args.artifact:
        print("need --artifact")
        return 2

    if args.verify:
        doc = json.load(open(args.verify, encoding="utf-8"))
        if args.uuid:
            ok, fetched = get_entry(args.uuid, args.timeout)
            if not ok:
                print(json.dumps({"verified": False, "problems": [fetched["error"]]}, indent=2))
                return 3
            doc = fetched
        ok, info, probs = verify_entry(doc, open(args.artifact, "rb").read())
        print(json.dumps({"verified": ok, "info": info, "problems": probs},
                         indent=2, ensure_ascii=False, default=str))
        return 0 if ok else 3

    artifact = open(args.artifact, "rb").read()
    key = load_or_make_key(args.key)
    ok, resp = post_entry(hashedrekord_body(artifact, key), args.timeout)
    if not ok:
        print(json.dumps({"status": "unanchored", "reason": resp["error"]}, ensure_ascii=False))
        return 2

    out = os.path.join(args.out_dir, "rekor_entry.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(resp, f, indent=2)
    v_ok, vinfo, vprobs = verify_entry(resp, artifact)
    rec = {"status": "anchored" if v_ok else "unanchored",
           "rekor": REKOR,
           "artifact_sha256": hashlib.sha256(artifact).hexdigest(),
           "public_key_sha256": hashlib.sha256(public_pem(key)).hexdigest(),
           "info": vinfo,
           "problems": vprobs}
    rec_path = os.path.join(args.out_dir, "rekor_anchor.json")
    with open(rec_path, "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=2, ensure_ascii=False, default=str)
    print(json.dumps(rec, indent=2, ensure_ascii=False, default=str))
    print("RESULT_JSON=%s" % rec_path)
    return 0 if v_ok else 3


if __name__ == "__main__":
    sys.exit(main())
