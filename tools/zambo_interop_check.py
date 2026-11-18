#!/usr/bin/env python3
"""Verify a third party's receipt digest without contacting their service logic.

Target: a public Zambo receipt page (AER-1). What this checks, and nothing more:
  * the page's "Canonical bytes" decode to JSON,
  * our own canonicalization of that JSON reproduces the same bytes and sha256,
  * side_effects.declaration_hash re-computes over the declared block,
  * whether the envelope carries a signature (it does not; the page says so).

What this deliberately does NOT do: authenticate the issuer. A receipt with no
signature is self-consistent by construction -- anyone can edit the payload and
recompute the digest. Reporting "matches" here means the digest binds the bytes,
not that Zambo produced them.

Usage:
    python tools/zambo_interop_check.py
    python tools/zambo_interop_check.py --url https://zambo.dev/run/<id>
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
import urllib.request

from uibc_core.canonical import canonicalize, hash_obj

DEFAULT_URL = "https://zambo.dev/run/5f908958-6c31-4293-b239-b2122699e14b"
UA = {"User-Agent": "uibc-core-interop/1.0"}


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=45) as f:
        return f.read().decode("utf-8", "replace")


def extract(page: str) -> tuple[bytes, str, str | None]:
    """Return (canonical_bytes, claimed_digest, claimed_declaration_hash)."""
    tail = page[page.index("Canonical bytes"):]
    b64 = re.search(r"[A-Za-z0-9+/=]{60,}", tail).group(0)
    raw = base64.b64decode(b64 + "=" * (-len(b64) % 4))
    claimed = re.search(r"sha256:([0-9a-f]{64})", page)
    decl = re.search(r'"declaration_hash"\s*:\s*"sha256:([0-9a-f]{64})"', page)
    return raw, (claimed.group(1) if claimed else None), (decl.group(1) if decl else None)


def check(url: str = DEFAULT_URL) -> dict:
    page = fetch(url)
    raw, claimed, claimed_decl = extract(page)
    doc = json.loads(raw)

    ours = canonicalize(doc)
    ours_sha = hashlib.sha256(ours).hexdigest()

    side = doc.get("side_effects") or {}
    decl_body = {k: v for k, v in side.items() if k != "declaration_hash"}
    decl_sha = hash_obj(decl_body).split(":")[-1] if decl_body else None
    # the claim lives inside the envelope, not in the page markup
    claimed_decl = (side.get("declaration_hash") or "").split(":")[-1] or None

    signed = any(("sig" in k.lower()) for k in doc)

    return {
        "url": url,
        "canonical_bytes": len(raw),
        "claimed_digest": claimed,
        "recomputed_digest": ours_sha,
        "digest_match": claimed == ours_sha,
        "bytes_identical": ours == raw,
        "schema": doc.get("receipt_schema_version"),
        "signed": signed,
        "claimed_declaration_hash": claimed_decl,
        "recomputed_declaration_hash": decl_sha,
        "declaration_match": (claimed_decl == decl_sha) if claimed_decl else None,
        "issuer_authenticated": False,
    }


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=DEFAULT_URL)
    args = ap.parse_args(argv[1:])
    try:
        r = check(args.url)
    except Exception as e:  # network or page shape changed; never guess a verdict
        print(f"INCONCLUSIVE: {type(e).__name__}: {e}")
        return 2
    print(json.dumps(r, indent=2))
    ok = r["digest_match"] and r["bytes_identical"] and (r["declaration_match"] is not False)
    print("\nverdict =", "DIGEST_BINDS_BYTES (issuer NOT authenticated)" if ok else "MISMATCH")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
