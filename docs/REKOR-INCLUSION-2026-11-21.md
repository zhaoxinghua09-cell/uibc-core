# SPDX-License-Identifier: Apache-2.0
# Our Rekor inclusion proof verifies. The failure was ours.

Published 2026-11-21. It retires a claim this project made in public for weeks:
*"the Rekor inclusion proof does not verify, by our reading or by a third party's."*

That claim was wrong, and the fault was ours, not the log's. This page records the
wrong claim, the two mistakes behind it, and the command that now proves inclusion.

## The claim as it was made

- `README.md` carried a warning: inclusion proofs do not verify.
- `docs/ECOSYSTEM-MAP.md` used it as the example of "the one thing we publish that
  others do not": a failed verification, published rather than hidden.
- A third-party verifier (`rekor_log_verifier`) failed on the same proof with a
  different root, which we read as corroboration.

Two independent readings failing together looked like evidence about Rekor. It
was evidence about a shared assumption — both readers had the same two mistakes.

## Mistake 1: hashing the body twice

The leaf of a Rekor tree is

```
leaf = SHA-256(0x00 ‖ body_bytes)
```

where `body_bytes` is the base64-decoded entry body **as served**. We hashed
`SHA-256(body_bytes)` first and then applied the leaf prefix to that digest:

```
wrong: SHA-256(0x00 ‖ SHA-256(body_bytes))
```

That constructs a completely different leaf. No inclusion path can ever fold it
to the published root, which is exactly the symptom we reported.

## Mistake 2: folding against the wrong index

The entry carries **two different indices**:

| Field | Value on entry `108e9186…59c` (2026-11-21) |
|---|---|
| `entry.logIndex` | `2883389783` |
| `entry.verification.inclusionProof.logIndex` | `2761485521` |

A proof folds against the index it is **about** — its own `logIndex`. Folding
against `entry.logIndex` gives a root that never matches. We do not claim to
know what the top-level field means (a shard-relative index is one plausible
reading); we claim only that the proof verifies against its own index and
nothing else.

This is also why it looked like tampering: a mismatched root is what tampering
produces, and it took both mistakes to produce it from honest data.

## What now proves

```bash
pip install "uibc-core[verify]"        # cryptography, for the signature step only
python tools/verify_rekor_inclusion.py --log-index 2883389783
```

If `cryptography` is missing, the tool says so and reports
`checkpoint.signature_verified: null` — it never prints a pass for a step it did
not run.

The tool:
1. decodes the body and computes `SHA-256(0x00 ‖ body)`;
2. folds the proof against `proof.logIndex` / `proof.treeSize`;
3. compares the folded root with `proof.rootHash`;
4. compares that root with the root line of the checkpoint;
5. verifies the checkpoint's own signature against the log's public key
   (`https://rekor.sigstore.dev/api/v1/log/publicKey`, ECDSA P-256, SHA-256).

Step 5 matters because a root printed in an unsigned document proves only that
someone printed a root. The signed bytes are the three text lines (origin, size,
root) each newline-terminated; the signature line is `— <signer> <base64>`, whose
first four bytes are the key id (`c0d23d6a` for `rekor.sigstore.dev -
1193050959916656506`) followed by a DER ECDSA signature.

On 2026-11-21 all five comparisons pass, for our entry and for the third party's:

```
verified=True  proof.index=2761485521  entry.index=2883389783
checkpoint.signature_verified=True  key_id=c0d23d6a  curve=secp256r1
```

The same tool, same rules, verifies the DFR (`dfr.derappar.at`) entry
`108e9186…c439bd6b455…` — a **third party's** entry, not ours, on a different
origin. The defect was in the reading, so it was in every reading we did, ours
and theirs.

## What this does not prove

- **Nothing about consistency between tree sizes.** Inclusion at one `treeSize`
  says the entry is in that tree; it does not say that tree is an extension of the
  tree at any earlier size. A consistency proof is the missing step, and the tool
  does not attempt one.
- **The meaning of `entry.logIndex` is not established.** We record the
  difference and use the proof's index. Anyone who knows the intended semantics
  should say so, and the tool's comment will follow the answer, not lead it.
- **The log's anti-equivocation behaviour is not audited.** A valid signature
  proves the log signed this root once, not that it never signed a conflicting one.
- **Nothing here says Rekor is wrong.** It says our reading was wrong, twice,
  and that a third-party verifier shared the mistake rather than correcting it.

## What stays true

The habit that produced this — publishing failures with reproduction steps
instead of quietly deleting them — is the reason the mistake was findable at
all. A project that had published only passing counts would have had nothing to
correct, and would still be making the claim.
