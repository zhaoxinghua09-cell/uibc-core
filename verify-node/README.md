# verify-node — a receipt checked by a second language

`verify_receipt.mjs` verifies a `uibc-receipt-v1` receipt **without importing any of
this repository's Python**. Node's `node:crypto` does the Ed25519 work; the RFC 6962
Merkle fold, the canonical payloads and the two domain strings are re-derived here
from the published definition.

## Run

```bash
node verify-node/verify_receipt.mjs path/to/receipt.json
```

Exit code 0 and `"all": true` means every check passed.

## What it checks

| Check | What it proves |
|---|---|
| `inclusion_proof` | the leaf folds to the checkpoint root at this index and tree size |
| `checkpoint_signature` | the operator signed `CHECKPOINT_DOMAIN ‖ canonical(checkpoint without sig)` |
| `witness_cosignature` | the witness signed `WITNESS_DOMAIN ‖ sha256(canonical{format,tree_size,root})` |
| `domain_separation_attack_rejected` | the operator's signature does not pass as a cosignature |
| `tampered_proof_rejected` | flipping one proof node breaks the fold |

## What it deliberately does not check

The **package semantics** (S1..S12) are Python-only, and so is the statement binding
(record shape → leaf digest), because that needs the record the log stored. This file
covers the receipt layer: Merkle fold, two signatures, domain separation.

Stating the boundary matters more than the coverage: a second-language *receipt*
verifier is a real interop step, and it is not "the whole verifier runs in two
languages".

## Where the numbers came from

Measured 2026-11-27 on the two receipts this repository published
(`uibc-receipt-v1-example.json` and the Rekor-anchored one): 5/5 checks true on both,
Node v22.23.2. The in-tree test `tests/test_receipt_node_parity.py` builds a fresh
receipt (5 leaves, index 2, throwaway keys) and asserts the same five checks, skipping
itself when `node` is absent.
