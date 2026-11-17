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


def canonical_json(obj) -> str:
    """Minimal RFC 8785 canonical form for the value types used in the corpus.

    Sorted keys, no insignificant whitespace, no \\u escaping of non-ASCII, and
    UTF-8 output. Numbers are limited to integers and short decimals on purpose:
    the corpus does not test ECMAScript number formatting, and pretending it did
    would be a false claim.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def check_vectors(doc: dict) -> tuple[bool, list[dict]]:
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
        else:
            row["detail"] = "unknown vector kind"
        rows.append(row)
    return all(r["ok"] for r in rows), rows


def main(argv):
    with open(VECTORS, "r", encoding="utf-8") as fh:
        doc = json.load(fh)
    try:
        ok, rows = check_vectors(doc)
    except ImportError:
        print("SKIP: the `cryptography` package is required to check the signature vectors")
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
