# Cross-implementation check: a third party's receipt, verified offline

This directory contains a runnable check against a receipt **we did not issue**:
a public Zambo receipt (AER-1, `draft-zambo-aer1-26`), at

    https://zambo.dev/run/5f908958-6c31-4293-b239-b2122699e14b

Run it:

```bash
python tools/zambo_interop_check.py
```

## What it establishes

| item | value (2026-11-18) |
|---|---|
| canonical bytes on their page | 678 B (base64 → JSON), `receipt_schema_version` `0.4` |
| their published digest | `sha256:b0880874…c82bc` |
| our `canonicalize()` output | **same 678 bytes**, same digest |
| `side_effects.declaration_hash` | `45aad38f…1bfee`, recomputed → match |
| envelope signature | **none** — the page itself says issuer authentication is not checked |

So: two independent implementations canonicalize the same receipt to the same
bytes. That is a real interop fact, and it is the only claim made here.

## What it does not establish

* **Not** "we verified Zambo's receipt." Without a signature, a digest match only
  proves the bytes are self-consistent — anyone can edit the payload and
  recompute the digest. Issuer authentication is out of scope for both sides here.
* **Not** "we pass AER-1." This is one receipt, digested; not the 143-vector
  conformance suite.
* **Not** a comparison of anchoring strength. Their anchor is a Nostr relay
  publication (`zambo-receipt-anchor/1`); ours is RFC 3161 (FreeTSA token with
  CA in-repo) plus an OpenTimestamps submission that is still a **pending
  calendar statement**, not a Bitcoin block attestation.

## Why this exists

A cross-implementation result is worth more than a claim about one. If their
canonicalization and ours agree byte-for-byte, the remaining differences are
about *who authenticates the issuer* and *where the timestamp comes from* — which
is a design question, not a compatibility problem, and can be discussed with
evidence instead of adjectives.

The test in `tests/test_zambo_interop.py` skips when the page is unreachable:
"cannot fetch" must never become "verified" in an offline CI run.
