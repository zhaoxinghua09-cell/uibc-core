# Receipts as in-toto Statements (DSSE)

`intoto_receipt.py` maps each receipt of a `uibc-core/receipt-chain/0` document onto an
in-toto `Statement/v1`, wraps it in a DSSE envelope (`application/vnd.in-toto+json`) and
signs it with ed25519.

```
python tools/interop/intoto_receipt.py sign   conformance/cases/02-.../evidence/chain.json /tmp/case02.dsse.json
python tools/interop/intoto_receipt.py verify conformance/cases/02-.../evidence/chain.json /tmp/case02.dsse.json
python tools/interop/intoto_receipt.py tamper /tmp/case02.dsse.json   # then verify must FAIL
```

Measured on `cases/02` (two receipts, 2026-11-24):

```
signed 2 receipt(s) -> /tmp/case02.dsse.json (keyid ccf51afc05049d1b)
VERIFY OK: 2 envelope(s), signatures + statement types + subject digests + prev-hash chain all agree
```

| our field | in-toto field |
|---|---|
| `receipt.envelope` | `subject[0].digest.sha256 = receipt_digest(envelope)` |
| `previous_receipt_hash` | `predicate.previous_receipt_hash`, recomputed by the verifier |
| chain position | `predicate.index` / `chain_length` / `envelope` |
| our format version | `predicateType = https://uibc.dev/attestation/receipt-chain/v1` |
| signature | DSSE over `PAE(payloadType, payload)` |

Three choices worth stating:

1. **The digest is imported, not re-derived.** `receipt_digest` comes from
   `uibc_core.chain`, so the mapping cannot drift from the chain checker. A private
   re-implementation would verify against itself only.
2. **The signature covers PAE.** Signing the bare payload produces envelopes that other
   DSSE implementations reject.
3. **The public key inside the envelope is a convenience field, not a trust anchor.**
   Real distribution belongs in an independent channel (`.well-known`, OIDC). Otherwise
   the file certifies itself.

## Negative tests (all run, all fail as required)

| attack | result |
|---|---|
| flip one byte of a payload | `receipt[0] signature FAIL` and `receipt[1] previous_receipt_hash != receipt_digest(prev envelope)` |
| change `previous_receipt_hash` | second assertion above fires |
| verify with a different public key | `receipt[0] signature FAIL` |
| drop one envelope | `envelope count 1 != receipts 2` |

## What this does not buy

- Not a production key: the signer is whoever holds the local key. Key distribution and
  rotation are out of scope here.
- Not `in-toto-verify`: the official binary has not been run against these envelopes yet.
- Not a transparency log: nothing here is append-only or witnessed. That needs a service
  with a public identity, not another script.
