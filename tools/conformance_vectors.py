#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate a language-neutral conformance corpus (JSON vectors + fixed digests).

Why this exists: our tests are Python tests. "We have 303 tests" tells an outsider
that *somebody* checked *our* implementation; it does not let an implementation
written elsewhere check itself against our format. The competing projects that do
this better — Tracekit (two verifier implementations) and agent-receipts (8 published
vectors) — publish a corpus, not a test count.

The vector file is deliberately boring: each entry embeds its own input and the exact
canonical byte string plus its SHA-256. Anyone can verify an entry with `sha256sum`
and a JSON canonicalizer they wrote themselves, without importing a single line of
our code. We do not ship a second implementation with this; we ship the object a
second implementation can be measured against, and say so.

Vectors come from fixtures this repository already publishes, so nothing here is a
hand-written "expected" that could quietly disagree with the code path.

CLI:
  python tools/conformance_vectors.py            # write docs/conformance/vectors.json
  python tools/conformance_vectors.py --check    # regenerate in memory and compare to disk
"""

import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uibc_core.canonical import canonicalize, sha256_hex  # noqa: E402
from uibc_core import ed25519  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "docs", "conformance", "vectors.json")

# --- inputs: small, self-contained, and chosen to punish a lazy canonicalizer ---

CANONICAL_CASES = [
    ("c01-empty-object", {}),
    ("c02-key-order", {"b": 1, "a": 2}),
    ("c03-nested", {"z": {"y": [3, 2, 1]}, "a": "s"}),
    ("c04-unicode", {"name": "张 三", "role": "агент"}),
    ("c05-numbers", {"i": 7, "f": 1.5, "neg": -2, "zero": 0}),
    ("c06-escapes", {"q": "he said \"hi\"", "nl": "a\nb", "tab": "a\tb"}),
    ("c07-bools-null", {"t": True, "f": False, "n": None}),
    ("c08-array-order", {"xs": [1, "a", None, {"k": "v"}]}),
    ("c09-deep", {"a": {"b": {"c": {"d": [{"e": 1}]}}}}),
    ("c10-empty-containers", {"o": {}, "a": []}),
]

# one fixed seed, printed in the vector file, so a stranger can reproduce the signature
SEED_HEX = "0" * 63 + "1"  # 32-byte seed (64 hex chars), deliberately trivial and public
MESSAGES = [
    ("m01-ascii", b"uibc conformance vector 01"),
    ("m02-utf8", "边界检查".encode("utf-8")),
    ("m03-empty", b""),
]


def build():
    vectors = []

    for vid, obj in CANONICAL_CASES:
        canon = canonicalize(obj).decode("utf-8")
        vectors.append({
            "id": vid,
            "kind": "canonical_json",
            "input": obj,
            "expected_canonical_utf8": canon,
            "expected_sha256_hex": sha256_hex(canonicalize(obj)),
            "check": "canonicalize(input) must equal expected_canonical_utf8 byte for byte, "
                     "and sha256 of it must equal expected_sha256_hex",
        })

    pub = ed25519.publickey(bytes.fromhex(SEED_HEX))
    pub_hex = pub.hex()
    for mid, msg in MESSAGES:
        sig = ed25519.sign(bytes.fromhex(SEED_HEX), msg)
        vectors.append({
            "id": mid,
            "kind": "ed25519_signature",
            "seed_hex": SEED_HEX,
            "public_key_hex": pub_hex,
            "message_utf8": msg.decode("utf-8") if msg else "",
            "message_hex": msg.hex(),
            "signature_hex": sig.hex(),
            "expected_verdict": "valid",
            "check": "verify(public_key_hex, message, signature_hex) must return valid; "
                     "no private key is published, only a throwaway seed for reproduction",
        })

    # rejection vectors: the same signature over a different message must not verify
    msg0 = MESSAGES[0][1]
    sig0 = ed25519.sign(bytes.fromhex(SEED_HEX), msg0)
    vectors.append({
        "id": "r01-signature-other-message",
        "kind": "ed25519_signature",
        "public_key_hex": pub_hex,
        "message_hex": (msg0 + b"x").hex(),
        "signature_hex": sig0.hex(),
        "expected_verdict": "invalid",
        "check": "verify must reject: the signature was made over a different message",
    })
    vectors.append({
        "id": "r02-signature-tampered-byte",
        "kind": "ed25519_signature",
        "public_key_hex": pub_hex,
        "message_hex": msg0.hex(),
        "signature_hex": (bytes.fromhex(sig0.hex())[:-1] + bytes([sig0[-1] ^ 0x01])).hex(),
        "expected_verdict": "invalid",
        "check": "verify must reject: one signature byte flipped",
    })

    doc = {
        "schema": "uibc-core/conformance-vectors@1",
        "generated_by": "tools/conformance_vectors.py",
        "what_this_is": "Inputs and expected bytes for the canonical-JSON and Ed25519 steps only. "
                        "It is not a full-receipt corpus and it does not contain a second implementation.",
        "how_to_use": "For each vector of kind canonical_json, canonicalize the embedded input with your own "
                      "implementation and compare both the exact bytes and the SHA-256. For kind "
                      "ed25519_signature, verify with any Ed25519 library and compare the verdict. "
                      "A conforming implementation reproduces every expected value; it needs no code from us.",
        "not_claimed": [
            "that we publish a second implementation — we do not",
            "that these vectors cover receipt structure, chains, anchoring or policy — they do not",
            "that passing them makes an implementation interoperable with our receipts — it does not",
        ],
        "vectors": vectors,
    }
    return doc


def main(argv):
    doc = build()
    if "--check" in argv:
        with open(OUT, "r", encoding="utf-8") as fh:
            on_disk = json.load(fh)
        if on_disk != doc:
            print("MISMATCH: docs/conformance/vectors.json differs from a fresh build")
            return 1
        print(f"MATCH: {len(doc['vectors'])} vectors reproduce exactly")
        return 0
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2, sort_keys=False)
        fh.write("\n")
    print(f"wrote {OUT}: {len(doc['vectors'])} vectors")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
