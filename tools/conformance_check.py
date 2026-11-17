#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check the conformance corpus without using this project's implementation.

Two deliberate restrictions make this a real check rather than a mirror:

  * canonical-JSON vectors are checked with a canonicalizer written here, using only
    `json` and `hashlib` from the standard library — it never imports `uibc_core`;
  * Ed25519 signatures are checked with the third-party `cryptography` package, not
    with our in-repo Ed25519.

So "the corpus passes" means: an implementation other than ours, built only from the
vector file, reproduces every expected value.

CLI:
  python tools/conformance_check.py            # check docs/conformance/vectors.json
  python tools/conformance_check.py --json     # machine-readable result
Exit code 0 = every vector reproduced, 1 = at least one mismatch.
"""

import hashlib
import json
import os
import sys

VECTORS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "docs", "conformance", "vectors.json")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def canonical_json(obj) -> str:
    """Minimal RFC 8785 canonical form for the value types used in the corpus.

    Sorted keys, no insignificant whitespace, no \\u escaping of non-ASCII, and
    UTF-8 output. Numbers are limited to integers and short decimals on purpose:
    the corpus does not test ECMAScript number formatting, and pretending it did
    would be a false claim.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(obj) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


GENESIS = "0" * 64


def check_chain(v: dict) -> tuple[bool, str]:
    """Recompute the linear links. Independent of uibc_core: JCS + sha256 only.

    Rule taken from the vector's own description, not from our code:
    receipt[0].previous_receipt_hash must be 64 zeros; every later receipt must carry
    the digest of its predecessor's envelope.
    """
    receipts = v["chain"]["receipts"]
    digests = [_digest(r["envelope"]) for r in receipts]
    if digests != v.get("expected_digests", digests):
        return False, "envelope digests differ from the published ones"
    reason = None
    if receipts[0]["previous_receipt_hash"] != GENESIS:
        reason = "genesis_not_64_zeros"
    for i in range(1, len(receipts)):
        if receipts[i]["previous_receipt_hash"] != digests[i - 1]:
            reason = reason or "previous_receipt_hash_mismatch"
    verdict = "valid" if reason is None else "invalid"
    if verdict != v["expected_verdict"]:
        return False, f"expected {v['expected_verdict']}, recomputed {verdict}"
    if reason and reason != v.get("expected_reason"):
        return False, f"reason {reason} != {v.get('expected_reason')}"
    return True, f"recomputed {verdict}" + (f" ({reason})" if reason else "")


def check_anchor(v: dict, root: str) -> tuple[bool, str]:
    """Hash the artifact and read the token's messageImprint with asn1crypto."""
    from asn1crypto import tsp

    art = os.path.join(root, v["artifact_path"])
    with open(art, "rb") as fh:
        art_digest = hashlib.sha256(fh.read()).hexdigest()
    if v.get("expected_artifact_sha256_hex") and art_digest != v["expected_artifact_sha256_hex"]:
        return False, "artifact digest differs from the published one"

    with open(os.path.join(root, v["token_path"]), "rb") as fh:
        raw = fh.read()
    resp = tsp.TimeStampResp.load(raw)
    token = resp["time_stamp_token"]
    content = token["content"]["encap_content_info"]["content"]
    # In most tokens the encapsulated content is a ParsableOctetString that has to be
    # parsed as a TSTInfo before message_imprint is addressable.
    if hasattr(content, "parsed") and content.parsed is not None:
        content = content.parsed
    imprint = content["message_imprint"]["hashed_message"].native
    bound = bytes(imprint).hex() == art_digest
    verdict = "bound" if bound else "not_bound"
    if verdict != v["expected_verdict"]:
        return False, f"expected {v['expected_verdict']}, token says {verdict}"
    return True, f"token messageImprint {'==' if bound else '!='} artifact digest ({verdict})"


def check_vectors(doc: dict, root: str) -> tuple[bool, list[dict]]:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.exceptions import InvalidSignature

    rows = []
    for v in doc["vectors"]:
        row = {"id": v["id"], "kind": v["kind"], "ok": False, "detail": ""}
        if v["kind"] == "canonical_json":
            got = canonical_json(v["input"])
            got_sha = hashlib.sha256(got.encode("utf-8")).hexdigest()
            if got != v["expected_canonical_utf8"]:
                row["detail"] = "canonical bytes differ"
            elif got_sha != v["expected_sha256_hex"]:
                row["detail"] = "sha256 differs"
            else:
                row["ok"] = True
                row["detail"] = "bytes and digest match"
        elif v["kind"] == "ed25519_signature":
            pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(v["public_key_hex"]))
            msg = bytes.fromhex(v["message_hex"])
            sig = bytes.fromhex(v["signature_hex"])
            try:
                pub.verify(sig, msg)
                verdict = "valid"
            except InvalidSignature:
                verdict = "invalid"
            if verdict == v["expected_verdict"]:
                row["ok"] = True
                row["detail"] = f"third-party verifier says {verdict}"
            else:
                row["detail"] = f"expected {v['expected_verdict']}, third-party verifier says {verdict}"
        elif v["kind"] == "receipt_digest":
            got = canonical_json(v["envelope"])
            got_sha = hashlib.sha256(got.encode("utf-8")).hexdigest()
            if got != v["expected_canonical_utf8"]:
                row["detail"] = "canonical bytes differ"
            elif got_sha != v["expected_sha256_hex"]:
                row["detail"] = "digest differs"
            else:
                row["ok"] = True
                row["detail"] = "envelope digest reproduced"
        elif v["kind"] == "receipt_chain":
            row["ok"], row["detail"] = check_chain(v)
        elif v["kind"] == "anchor_binding":
            row["ok"], row["detail"] = check_anchor(v, root)
        else:
            row["detail"] = "unknown vector kind"
        rows.append(row)
    return all(r["ok"] for r in rows), rows


def main(argv):
    with open(VECTORS, "r", encoding="utf-8") as fh:
        doc = json.load(fh)
    try:
        ok, rows = check_vectors(doc, ROOT)
    except ImportError as exc:
        print(f"SKIP: {exc}; `pip install -e .[verify]` provides cryptography and asn1crypto")
        return 2
    if "--json" in argv:
        print(json.dumps({"ok": ok, "vectors": len(rows), "rows": rows}, ensure_ascii=False, indent=2))
    else:
        for r in rows:
            print(f"{'PASS' if r['ok'] else 'FAIL'}  {r['id']:<26} {r['detail']}")
        print(f"\n{sum(1 for r in rows if r['ok'])}/{len(rows)} vectors reproduced by a non-uibc implementation")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
