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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "conformance", "vectors.json")

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

# --- receipt and chain layer (added 2026-11-17) -----------------------------
#
# The first corpus covered the two primitive steps. These vectors cover the two
# structural claims a regulator actually asks about:
#   * a receipt's digest - SHA-256 over the RFC 8785 JCS encoding of its envelope;
#   * the linear link - every receipt carries previous_receipt_hash, the digest of
#     its predecessor's envelope, and the first receipt of a chain carries 64 zeros
#     (draft-marques-asqav-compliance-receipts-01 section 4.3).
# Deliberately no floats in these envelopes: the corpus tests structure and linking,
# not ECMAScript number formatting, and saying otherwise would be a false claim.

RECEIPT_CASES = [
    ("h01-receipt-minimal",
     {"receipt_id": "r-0001", "issued_at": "2026-11-17T08:11:35Z",
      "agent_id": "agent-0001", "verdict": "PASS"}),
    ("h02-receipt-with-policy",
     {"receipt_id": "r-0002", "issued_at": "2026-11-17T09:02:11Z",
      "agent_id": "agent-0001", "verdict": "HOLD",
      "policy_digest": "sha256:" + "a" * 64,
      "previous_receipt_hash": "0" * 64,
      "counts": {"events": 12, "failures": 1}}),
    ("h03-receipt-unicode",
     {"receipt_id": "r-0003", "issued_at": "2026-11-17T10:00:00Z",
      "agent_id": "张三的 agent", "note": "边界检查 —— 不转义"}),
]

CHAIN_OF_THREE = [c[1] for c in RECEIPT_CASES]


def _chain_doc(envelopes, break_at=None, genesis="0" * 64):
    """Build a chain document, with the declared predecessor digests recomputed.

    `break_at` corrupts the declared hash at that index, which is how the two
    rejection vectors are made: the link is what is wrong, not the digest.
    """
    receipts = []
    prev = genesis
    for i, env in enumerate(envelopes):
        declared = genesis if i == 0 else prev
        if break_at is not None and i == break_at:
            declared = ("f" * 64) if declared != ("f" * 64) else ("e" * 64)
        receipts.append({"envelope": env, "previous_receipt_hash": declared})
        prev = sha256_hex(canonicalize(env))
    return {"schema": "uibc-core/receipt-chain@1", "receipts": receipts}


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

    # ---- receipt layer ------------------------------------------------------
    for vid, env in RECEIPT_CASES:
        canon = canonicalize(env).decode("utf-8")
        vectors.append({
            "id": vid,
            "kind": "receipt_digest",
            "envelope": env,
            "expected_canonical_utf8": canon,
            "expected_sha256_hex": sha256_hex(canonicalize(env)),
            "check": "digest of a receipt envelope = sha256 over its RFC 8785 JCS bytes; "
                     "canonicalize(envelope) must equal expected_canonical_utf8 and its "
                     "sha256 must equal expected_sha256_hex",
        })

    # ---- chain layer --------------------------------------------------------
    valid = _chain_doc(CHAIN_OF_THREE)
    vectors.append({
        "id": "k01-chain-valid",
        "kind": "receipt_chain",
        "chain": valid,
        "expected_verdict": "valid",
        "expected_digests": [sha256_hex(canonicalize(e)) for e in CHAIN_OF_THREE],
        "check": "recompute each envelope digest; receipt[0].previous_receipt_hash must be "
                 "64 zeros; receipt[i].previous_receipt_hash must equal digest of "
                 "receipt[i-1].envelope; verdict valid",
    })
    broken = _chain_doc(CHAIN_OF_THREE, break_at=1)
    vectors.append({
        "id": "k02-chain-broken-link",
        "kind": "receipt_chain",
        "chain": broken,
        "expected_verdict": "invalid",
        "expected_reason": "previous_receipt_hash_mismatch",
        "expected_digests": [sha256_hex(canonicalize(e)) for e in CHAIN_OF_THREE],
        "check": "the same chain with receipt[1].previous_receipt_hash replaced: the "
                 "envelopes are untouched, so only the link is wrong; verdict invalid",
    })
    nonzero = _chain_doc(CHAIN_OF_THREE, genesis="a" * 64)
    vectors.append({
        "id": "k03-chain-nonzero-genesis",
        "kind": "receipt_chain",
        "chain": nonzero,
        "expected_verdict": "invalid",
        "expected_reason": "genesis_not_64_zeros",
        "expected_digests": [sha256_hex(canonicalize(e)) for e in CHAIN_OF_THREE],
        "check": "receipt[0] declares a predecessor it cannot have: a chain whose first "
                 "link is not 64 zeros must be rejected",
    })

    # ---- anchor layer -------------------------------------------------------
    # The token is a real RFC 3161 token from freetsa.org over the digest of the file
    # shipped beside it. A stranger reproduces this by hashing the file and parsing the
    # token with any ASN.1 library; no code of ours is needed.
    anchor_file = os.path.join(ROOT, "tests", "fixtures", "anchor", "anchored_head.json")
    with open(anchor_file, "rb") as fh:
        anchor_digest = hashlib.sha256(fh.read()).hexdigest()
    vectors.append({
        "id": "a01-anchor-binds-the-shipped-file",
        "kind": "anchor_binding",
        "token_path": "tests/fixtures/anchor/freetsa.tsr",
        "artifact_path": "tests/fixtures/anchor/anchored_head.json",
        "expected_artifact_sha256_hex": anchor_digest,
        "expected_verdict": "bound",
        "check": "sha256 of artifact_path must equal expected_artifact_sha256_hex and the "
                 "token's messageImprint must equal the same digest; parse the token with "
                 "any ASN.1/RFC 3161 library",
    })
    vectors.append({
        "id": "a02-anchor-does-not-bind-another-file",
        "kind": "anchor_binding",
        "token_path": "tests/fixtures/anchor/freetsa.tsr",
        "artifact_path": "tests/fixtures/anchor/ots_head.ots",
        "expected_artifact_sha256_hex": None,
        "expected_verdict": "not_bound",
        "check": "the same token against a different file: the digests must disagree, and "
                 "a verifier must say not_bound rather than bound",
    })

    # ---- merkle layer -------------------------------------------------------
    # RFC 6962: leaf = SHA-256(0x00 || bytes), node = SHA-256(0x01 || left || right),
    # an odd tail is promoted rather than duplicated (duplicating it would let two
    # different trees share a root). Anyone can recompute these with sha256 alone.
    from uibc_core import merkle as _merkle

    items = [b"evidence-1", b"evidence-2", b"evidence-3", b"evidence-4", b"evidence-5"]
    leaves = [_merkle.leaf_hash(i) for i in items]
    vectors.append({
        "id": "l01-merkle-root-five-leaves",
        "kind": "merkle_root",
        "leaves_utf8": [i.decode() for i in items],
        "expected_root_hex": _merkle.root_hash(leaves).hex(),
        "check": "leaf = sha256(0x00 || leaf bytes); node = sha256(0x01 || left || right); "
                 "split the list at the largest power of two below its length, promote an odd "
                 "tail instead of duplicating it; root of 5 leaves must equal expected_root_hex",
    })
    one = [b"only-leaf"]
    vectors.append({
        "id": "l02-merkle-root-single-leaf",
        "kind": "merkle_root",
        "leaves_utf8": [one[0].decode()],
        "expected_root_hex": _merkle.leaf_hash(one[0]).hex(),
        "check": "a one-leaf tree's root is that leaf's hash, not sha256 of an inner node",
    })

    idx = 2
    proof = _merkle.audit_path(leaves, idx)
    vectors.append({
        "id": "l03-inclusion-index-2",
        "kind": "merkle_inclusion",
        "leaves_utf8": [i.decode() for i in items],
        "leaf_utf8": items[idx].decode(),
        "index": idx,
        "size": len(items),
        "proof_hex": [h.hex() for h in proof],
        "expected_root_hex": _merkle.root_hash(leaves).hex(),
        "expected_verdict": "included",
        "check": "recompute the root from this leaf, its index, the tree size and the sibling "
                 "path; it must equal expected_root_hex and the verdict must be included",
    })
    vectors.append({
        "id": "l04-inclusion-tampered-leaf",
        "kind": "merkle_inclusion",
        "leaves_utf8": [i.decode() for i in items],
        "leaf_utf8": "evidence-3-altered",
        "index": idx,
        "size": len(items),
        "proof_hex": [h.hex() for h in proof],
        "expected_root_hex": _merkle.root_hash(leaves).hex(),
        "expected_verdict": "not_included",
        "check": "the same path with one byte changed in the leaf: recomputed root must differ, "
                 "verdict not_included",
    })
    vectors.append({
        "id": "l05-inclusion-wrong-index",
        "kind": "merkle_inclusion",
        "leaves_utf8": [i.decode() for i in items],
        "leaf_utf8": items[idx].decode(),
        "index": 1,
        "size": len(items),
        "proof_hex": [h.hex() for h in proof],
        "expected_root_hex": _merkle.root_hash(leaves).hex(),
        "expected_verdict": "not_included",
        "check": "the right leaf with the wrong index: a verifier must not accept it, because the "
                 "index decides left/right at every step",
    })

    # ---- policy layer -------------------------------------------------------
    policy_body = {"rules": [{"id": "R-1", "effect": "HOLD", "predicate": "missing_signature"}],
                   "version": "2026-11", "reviewer": "张三"}
    vectors.append({
        "id": "p01-policy-artefact-digest",
        "kind": "policy_digest",
        "artifact": policy_body,
        "expected_canonical_utf8": canonicalize(policy_body).decode("utf-8"),
        "expected_sha256_hex": sha256_hex(canonicalize(policy_body)),
        "check": "a policy_digest is SHA-256 over the RFC 8785 JCS bytes of the retained artefact; "
                 "canonicalize(artifact) must equal expected_canonical_utf8 and hash to "
                 "expected_sha256_hex",
    })

    doc = {
        "schema": "uibc-core/conformance-vectors@3",
        "generated_by": "tools/conformance_vectors.py",
        "what_this_is": "Inputs and expected bytes for seven steps: canonical JSON, Ed25519 "
                        "signatures, receipt envelope digests, the linear chain link, "
                        "Merkle roots and inclusion paths (RFC 6962), policy artefact digests, "
                        "and two anchor-binding cases against a real RFC 3161 token. "
                        "It is not a full-receipt corpus and it does not contain a second "
                        "implementation.",
        "how_to_use": "For each vector, reproduce the expected value with your own "
                      "implementation: canonical_json - compare bytes and SHA-256; "
                      "ed25519_signature - verify with any Ed25519 library and compare the "
                      "verdict; receipt_digest - hash the JCS bytes of the envelope; "
                      "receipt_chain - recompute the links and compare the verdict; "
                      "merkle_root - build the RFC 6962 tree and compare the root; "
                      "merkle_inclusion - recompute the root from the leaf, index, size and "
                      "path; policy_digest - hash the JCS bytes of the artefact; "
                      "anchor_binding - hash the artifact and parse the token, then compare "
                      "the messageImprint. A conforming implementation needs no code from us.",
        "not_claimed": [
            "that we publish a second implementation — we do not",
            "that these vectors validate a receipt schema end to end — they do not; a receipt "
            "is a composite of steps that are published here and rules that are not",
            "that passing them makes an implementation interoperable with our receipts — "
            "it makes seven steps comparable, not the whole format",
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
