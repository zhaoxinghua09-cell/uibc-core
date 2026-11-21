# fixtures-v041 — Ed25519-era fixtures for v0.4.1

This directory is **additive**. `fixtures/` is untouched and stays as the v0.3.0
HMAC-era record (under v0.4.1 its `clean` sample reads INCONCLUSIVE, which is
correct behaviour for a package sealed in a superseded scheme, and is why this
set exists).

Everything here is produced by `build.py` through the real CLI, so each package
is a genuine artifact, not a hand-written forgery. Only the mutations are
deliberate.

## Observed matrix

Generated 2026-11-19 against `uibc 0.4.1`, HEAD `59ce19cb2372c55c3b4af5239b2ab43ad3c88519`.
Full machine-readable output: `RESULTS.json`.

| case | open (no pin) | pinned to `owner.key.pub` | pinned to `attacker.key.pub` | non-PASS checks |
|---|---|---|---|---|
| `clean` | PASS | PASS | FAIL | — |
| `tampered` | FAIL | FAIL | FAIL | S4, S8, S5 |
| `deleted` | FAIL | FAIL | FAIL | S4, S8, S5 |
| `duplicated` | FAIL | FAIL | FAIL | S12, S7, S8, S5 |
| `reordered` | FAIL | FAIL | FAIL | S3, S8, S6 |
| `migrated` | FAIL | FAIL | FAIL | S8, S5 |
| `malicious` | **PASS** | **FAIL** | PASS | S6 (pin only) |
| `malicious-keyswap` | **PASS** | **FAIL** | PASS | S6 (pin only) |

Read the last two rows carefully. **An unpinned verifier accepts a package that a
stranger sealed.** Only pinning the owner's public key catches it (S6). That is
not a bug — it is the documented trust model — but it is the single fact most
worth telling anyone who asks "does open mode mean anything".

## What each case is

- `clean` — register, two lifecycle events, one ACTION evidence, sealed with the owner key.
- `tampered` — one byte appended to the evidence payload; index hash no longer matches.
- `deleted` — payload removed, index entry left behind.
- `duplicated` — the same index entry appears twice.
- `reordered` — lifecycle events 1 and 2 swapped by sequence number.
- `migrated` — payload replaced **and** its index hash rewritten, so S4 passes; the
  manifest's `evidence_root` then fails to recompute (S5). This is the
  "someone re-indexed the evidence" case, and it must not pass.
- `malicious` — manifest edited then re-sealed with the attacker's key.
- `malicious-keyswap` — the entire package built by the attacker under the same
  `agent_id`, sealed with the attacker's key.

## Re-run

```
python build.py <path-to-uibc.exe> <repo-root>
```

Then, for any case:

```
uibc verify fixtures-v041/<case>.uibc
uibc verify fixtures-v041/<case>.uibc --pubkey fixtures-v041/owner.key.pub
```

## Keys

- `owner.key.pub` — the publishable pin. This is what a verifier should trust.
- `attacker.key.pub` — the throwaway key used to demonstrate S6. Kept so the
  FAIL rows can be reproduced; it certifies nothing.
- The **private seeds are not in this repository** (they live in a temp dir during
  build and are discarded). A fixture set that shipped its signing seed would teach
  the wrong habit.

## Limits

This set covers byte tampering, deletion, duplication, reordering, re-indexing,
and seal substitution. It does **not** cover truncation, rollback, cross-field
consistency, or the 40-family space of the mutation corpus — those live in
`benchmarks/corpus/mutation-corpus-500.json`. Eight fixtures are a smoke test for
the verify path, not a security proof.
