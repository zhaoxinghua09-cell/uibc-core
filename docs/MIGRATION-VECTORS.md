# MIGRATION-VECTORS.md — three cases that must hold across a version boundary

The versioning policy (`VERSIONING.md`) requires three vectors at every boundary. This document states them, the exact recipe to build each one, and **the verdict required before anyone runs it**. An expectation written after the run is a description, not a test.

## M1: old package, new verifier

```bash
python3 -m venv /tmp/old && . /tmp/old/bin/activate
pip install uibc-core==0.3.3
uibc init  --out /tmp/m1                 # build a package with the old tool
deactivate

python3 -m venv /tmp/new && . /tmp/new/bin/activate
pip install -e .
uibc verify /tmp/m1                       # verify it with the current tool
```

| Decision point | Required verdict |
|---|---|
| The package carries everything the old format required | `PASS` (or `INCONCLUSIVE` if the clean fixture is unsigned — check `conformance/manifest.json` for the base case rule first) |
| The old package omits something the new format requires | `INCONCLUSIVE`, naming the missing item |
| Any other outcome | A defect in the new verifier |

## M2: new package, old verifier

```bash
# with the current tool installed
uibc init --out /tmp/m2                    # a package that carries current-only fields
# then, in the old environment
uibc verify /tmp/m2
```

| Decision point | Required verdict |
|---|---|
| The old verifier reads a field it does not know | **`INCONCLUSIVE`** |
| The old verifier returns **`PASS`** | **Protocol-level defect. Do not release.** |
| The old verifier crashes | Poor, but not worse than `PASS` |

This is the most important of the three. `PASS` on input the verifier did not understand is silent failure at the version level, and it is the same defect shape as `F-008` (a field written by every package and read by no check).

## M3: package signed before a key rotation

Run 2026-11-19; results in `MIGRATION-RESULTS.md` §M3. The commands below are
the ones the CLI actually accepts — this section previously showed
`init --out … --key …` and `verify --pin …`, none of which exist, so the
recipe as published could not be followed. Kept here as the corrected version.

```bash
uibc keygen --ed25519 --out keys-a          # writes keys-a (seed) and keys-a.pub
uibc init m3
uibc register m3 --agent-id agent-m3 --owner "<owner>" --key-custody self_held
uibc event m3 --type ACTIVATE --actor "<owner>"
uibc evidence m3 --file note.txt --type ACTION
uibc submit m3 --key keys-a                 # Ed25519 seal: third-party verifiable
uibc keygen --ed25519 --out keys-b          # simulated rotation, throwaway pair
uibc verify m3                              # no pin
uibc verify m3 --pubkey keys-b.pub          # pin points at the new key
uibc verify m3 --pubkey keys-a.pub          # pin points at the signing key
```

| Case | Required verdict | Observed 2026-11-19 |
|---|---|---|
| No pin supplied | `PASS`, `trust_level: unanchored` | **PASS, `unanchored`** |
| Pin points at the new key, package signed by the old one | `FAIL`, naming the key mismatch | **FAIL** — S6: "public key does not match the pinned `--pubkey` (possible key substitution or wrong pin)" |
| Pin points at the old key and the old key is marked revoked | *not implemented* | **no such input exists** (see below) |
| Pin points at the old key, still valid | `PASS`, `trust_level: anchored` | **PASS, `anchored`** |

Two corrections to what this section claimed before it was run:

1. **The unpinned case is not `FAIL`.** An open-mode verification reads the
   public key out of the package it is testing, so a self-consistent package
   passes — and that is correct behaviour, not a defect. The thing that must
   never happen is calling it `anchored`. The verifier distinguishes the two
   explicitly, and its `limitations` text says so: "in open mode the seal's
   public key is read out of the package under test, so a passing signature
   proves internal consistency only (`unanchored`)".
   So the distinction that matters is **`unanchored` vs `anchored`**, not
   `PASS` vs `FAIL`. `demo` step 7 still teaches the trap: the unpinned PASS is
   byte-for-byte the same verdict a forger's own key would produce.
2. **"Key marked revoked" has no implementation path.** `verify` takes no
   key-status input at all. Revocation in this repository targets a *package*
   (`revocation.json`, `target_root` = the package's `evidence_root`;
   `GOVERNANCE.md` §3) and terminates at `gate` — `DENY` on a valid signature,
   `HOLD` when the revocation is unverifiable. A pinned key that has been
   revoked is, today, indistinguishable from a pinned key that is still valid.
   That row is **out of scope until a key-status source exists**; it is recorded
   as unimplemented rather than quietly deleted, because a reader who needs it
   must be able to see that it is missing.

## Status

All three vectors have now been run: M1 and M2 on 2026-11-19, M3 on 2026-11-19
after its recipe was corrected. M3 closed with three findings — a recipe that
did not run as written, a required verdict that was wrong about the unpinned
case, and one sub-case (`key marked revoked`) that has no implementation at all.
The expected verdicts above were declared before the run, which is the only
thing that makes them testable; where reality disagreed, the table now shows
reality and names the disagreement instead of being quietly rewritten.

## How this gets closed

1. Build the three vectors as scripts under `tools/`, one command each, no manual steps.
2. Record the raw output in `docs/MIGRATION-RESULTS.md` with the date and the two version numbers.
3. Add the outcome to the release record's `Interoperability Test` field.
