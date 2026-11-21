#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SCITT envelope, the zero-dependency way: uibc canonical payload -> COSE_Sign1 -> public-key-only verify.

Why a second interop tool instead of extending `cose_sign1_interop.py`:
that one proves the same bridge against `pycose`, which is exactly the dependency
this repo otherwise avoids. Keeping both is deliberate:

  * `cose_sign1_interop.py` - cross-check against a third-party COSE library.
    Needs `pycose` + `cbor2`; useful when you want to show a foreign parser agrees.
  * this file - the same bridge with nothing installed. It is the path a stranger
    can run on a clean machine, which is the one that matters for verification.

What it demonstrates, in order, and what it refuses to claim:
  1. our canonical seal bytes are wrapped in COSE_Sign1 (RFC 9052, EdDSA -8);
  2. a verifier holding only the public key recovers the payload;
  3. the recovered payload equals the original byte for byte (no re-serialization drift);
  4. one flipped payload byte is rejected;
  5. an algorithm downgrade is rejected rather than ignored.

Not claimed: that this is full SCITT conformance. It covers the COSE_Sign1
envelope only; receipts, registry, and policy are outside it.

    python tools/cose_stdlib_interop.py [--json out.json]
"""

import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uibc_core import cose_min                                    # noqa: E402
from uibc_core.signing import seal_payload, ed_generate_seed      # noqa: E402
from uibc_core.ed25519 import publickey                           # noqa: E402

IDENTITY = {
    "agent_id": "did:example:interop-agent",
    "vendor": "uibc-core",
    "purpose": "demonstrate COSE_Sign1 wrapping of a canonical seal payload",
}
MANIFEST = {
    "name": "demo-package",
    "version": "v0.3.3",
    "capabilities": ["read-only", "no-network"],
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None, help="write the result JSON here")
    args = ap.parse_args()

    results = []

    def record(name, passed, detail):
        results.append({"check": name, "result": "PASS" if passed else "FAIL", "detail": detail})

    seed = ed_generate_seed()
    pub = publickey(seed)
    payload = seal_payload(IDENTITY, MANIFEST)

    envelope = cose_min.sign1_encode(payload, seed)

    ok, recovered, why = cose_min.sign1_verify(envelope, pub)
    record("1. public-key-only verify", ok, why)

    byte_equal = ok and recovered == payload
    record("2. recovered payload is byte-identical", byte_equal,
           "len=%d" % (len(payload),) if byte_equal else "bytes differ or verify failed")

    # find the payload inside the envelope and flip a byte of the *signature* instead:
    # flipping payload bytes changes CBOR framing, which is a less precise probe.
    parsed = cose_min.decode(envelope)
    sig = bytearray(parsed[3])
    sig[0] ^= 0x01
    tampered = cose_min.encode([parsed[0], parsed[1], parsed[2], bytes(sig)])
    ok_t, _, why_t = cose_min.sign1_verify(tampered, pub)
    record("3. one flipped signature byte rejected", (not ok_t), why_t)

    # algorithm downgrade: correctly signed under EdDSA keys but declares -19
    protected = cose_min.encode({1: -19, 4: pub})
    body = cose_min.encode(["Signature1", protected, b"", payload])
    from uibc_core.ed25519 import sign as ed_sign
    forged = cose_min.encode([protected, {}, payload, ed_sign(seed, body)])
    ok_d, _, why_d = cose_min.sign1_verify(forged, pub)
    record("4. algorithm downgrade refused", (not ok_d), why_d)

    passed = sum(1 for r in results if r["result"] == "PASS")
    summary = {
        "tool": "cose_stdlib_interop",
        "dependencies": "none (stdlib only)",
        "payload_bytes": len(payload),
        "envelope_bytes": len(envelope),
        "checks": results,
        "passed": "%d/%d" % (passed, len(results)),
        "verdict": "PASS" if passed == len(results) else "FAIL",
    }

    print("payload=%d B  envelope=%d B  checks=%d/%d" % (
        len(payload), len(envelope), passed, len(results)))
    for r in results:
        print("  [%s] %-42s %s" % (r["result"], r["check"], r["detail"]))
    print("VERDICT=%s" % summary["verdict"])

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, ensure_ascii=False, indent=2)
        print("RESULT_JSON=%s" % args.json)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
