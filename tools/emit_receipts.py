#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Emit action receipts in the ASQAV draft's wire shape from a uibc package.

This is the adapter promised in docs/CROSSWALK-ASQAV-COMPLIANCE.md rows 1 and 3:
the package format is untouched; what changes is that we can also hand an
auditor a receipt whose field names are the draft's (`type`, `issued_at`,
`issuer_id`, `action_ref`, `policy_digest`, `payload_digest`,
`previousReceiptHash`, `signatureObject`).

Usage:
  python tools/emit_receipts.py --package fixtures/clean.uibc \
      --issuer did:web:example.eu --out tools/out/receipts.json [--count 3]

Every emitted receipt is verified before it is written: if the verifier rejects
our own output, the tool exits non-zero instead of shipping it.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from uibc_core import compliance as comp  # noqa: E402
from uibc_core.canonical import hash_obj  # noqa: E402
from uibc_core.ed25519 import publickey  # noqa: E402
from uibc_core.signing import ed_generate_seed  # noqa: E402


def _load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--issuer", default="did:web:example.eu")
    ap.add_argument("--out", required=True)
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--seed-hex", default=None,
                    help="32-byte hex seed; generated when omitted (not persisted)")
    args = ap.parse_args(argv)

    seed = bytes.fromhex(args.seed_hex) if args.seed_hex else ed_generate_seed()
    pub = publickey(seed)

    manifest = _load(os.path.join(args.package, "manifest.json"))
    payload_digest = "sha256:" + (manifest.get("evidence_root")
                                  or hash_obj(manifest))

    pol_path = os.path.join(args.package, "evidence", "policies.json")
    if os.path.isfile(pol_path):
        policies = _load(pol_path).get("policies") or [{}]
        policy_digest = policies[0].get("digest") or ("sha256:" + "0" * 64)
    else:
        policy_digest = "sha256:" + "0" * 64

    receipts, prev = [], comp.GENESIS
    for i in range(args.count):
        action = {"package_head": manifest.get("head") or "",
                  "sequence": i,
                  "emitted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
        body = comp.build_receipt(
            action,
            issued_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            issuer_id=args.issuer,
            policy_digest=policy_digest,
            payload_digest=payload_digest,
            previous_receipt_hash=prev)
        signed = comp.sign_receipt(body, seed)
        prev = comp.receipt_digest(signed)
        receipts.append(signed)

    problems, checked = comp.verify_chain(receipts, pinned_pubkey=pub,
                                          now=datetime.now(timezone.utc))
    if problems:
        print("SELF-VERIFY FAILED; refusing to write:")
        for p in problems[:5]:
            print("  " + p)
        return 2

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    doc = {"schema": "asqav/compliance-receipts@1",
           "meta": {"generated_at_utc":
                    time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "source_package": os.path.basename(args.package.rstrip("/\\")),
                    "verifier": "uibc_core.compliance"},
           "public_key_hex": pub.hex(),
           "receipts": receipts}
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)

    print("receipts=%d verified=%d" % (len(receipts), checked))
    print("kid=%s" % receipts[0]["signatureObject"]["kid"])
    print("public_key_hex=%s" % pub.hex())
    print("OUT=%s" % args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
