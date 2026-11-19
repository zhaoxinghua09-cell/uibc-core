# Migration vector results

> Every number and verdict below was produced by running the commands in
> `MIGRATION-VECTORS.md` on 2026-11-19. Nothing here is projected. Where a vector
> was not run, it says so and claims nothing.
>
> Environment: Windows 11 / PowerShell 7 / Python 3.13. Old release:
> `uibc-core==0.3.3` from PyPI. New release: this repository's working tree.

## M1 - a package sealed by 0.3.3, verified by 0.4.0

Three sub-cases. All three use the same key (`k1.hex`, key_id `8f089ff6d83f21b3...`).

| # | Package built by 0.3.3 with | Verified by 0.4.0 | Verdict |
|---|---|---|---|
| M1a | `--type action-log` (free-form string) | yes | **INCONCLUSIVE** (S4) |
| M1b | `--type ACTION` (a type both releases know) | yes | **PASS** |
| M1c | no evidence at all | yes | INCONCLUSIVE (S5) |

M1b is the first honest PASS this repository has recorded for a cross-release
package: a package sealed by the previous release, verified by the current one,
with every check resolved.

M1a is the interesting one. 0.3.3 accepted `--type` as a free-form string - its
`--help` listed no vocabulary and its source had no enum - so a package sealed
by that release can carry a type the current verifier does not know. The verifier
used to report that as **FAIL**, which asserts "I checked, and this is wrong".
It cannot assert that: the package could not have violated a rule that did not
exist when it was sealed, and the type was never checked against anything.

The rule now: unknown `evidence.type` -> **S4 INCONCLUSIVE**, detail naming the
type, top-level INCONCLUSIVE. A hash mismatch on the same entry is still **FAIL**
(`tests/test_evidence_type_vocabulary.py` pins both).

This was Issue #176. Option 1 of the two offered there was adopted: the smaller
change, and the one that matches what `VERSIONING.md` already says about unknown
fields.

## M2 - a package sealed by 0.4.0, verified by 0.3.3

| # | Package carries | 0.3.3 verdict |
|---|---|---|
| M2a | only features both releases implement | **PASS** (exit 0) |
| M2b | `evidence/external_anchor.json` carrying an unreadable token | **INCONCLUSIVE** (S16) |
| M2c | `identity.key_custody: "hsm"` - a field 0.3.3 does not have at all | **PASS** (exit 0) ← the defect |

Read M2a carefully. `PASS` from an older verifier is the *dangerous* outcome in a
migration vector - it means the old tool claimed success on something it could
not have judged. M2a is benign, because it uses only the commands both releases
implement, so 0.3.3 really did judge everything in the package.

**M2c is the defect, and it is conclusive.** `key_custody` is a provenance claim:
"the signing key lives in hardware". 0.4.0 validates the value against a known
set and reports PASS with `key_custody: hsm`. 0.3.3 does not contain the token
`key_custody` anywhere in its shipped source - verified by search, zero hits -
never inspected the claim, and returned **PASS, exit 0**.

So: **an older verifier will certify a claim it cannot see.** This is the
protocol-level failure the vector was written to catch, and it is not fixable by
editing this repository: a published release cannot be recalled. The only
mitigation is a version floor the artefact declares and the consumer compares -
recorded as `VERSIONING.md` §8.

## M2d - the floor, and what it cannot do

Implemented 2026-11-19: `uibc submit` writes `manifest.min_verifier_version`, and
`verify` reports **S1 INCONCLUSIVE** when its own version is below that floor.
Unit-pinned by `tests/test_version_floor.py` (floor 99.0.0 blocks PASS; floor at
or below passes; no floor changes nothing; a non-numeric floor does not crash).

The floor is measured; its limit is measured too. Searching the shipped source of
0.3.3 for `min_verifier_version` returns **zero hits**: an older verifier cannot
honour a declaration it does not know exists. A package that declares a 0.4.0
floor is still PASSed by 0.3.3.

That is the same lesson as M2c, one level up. **The floor is a control for
consumers, not a defence of the package.** It only changes anything when a
registry, gate or CI compares the declared floor against the verifier before
treating a PASS as evidence. Until that comparison happens somewhere real, this
row stays partially measured.

## M3 - key rotation and pinning

Run 2026-11-19, new release (this working tree, 0.4.1) against itself. Two
throwaway Ed25519 pairs were generated for the run; **the project's own signing
key was not rotated and was not touched** — the second pair exists only so a
"pin points at the wrong key" case can be produced. Seed files stayed in the
run directory and are not part of any artefact.

| # | Case | Verdict |
|---|---|---|
| M3a | no pin supplied | **PASS**, `trust_level: unanchored` |
| M3b | `--pubkey` = the newer (unrelated) key | **FAIL** (S6: "public key does not match the pinned `--pubkey`") |
| M3c | `--pubkey` = the signing key | **PASS**, `trust_level: anchored` |
| M3d | `--pubkey` = the signing key, that key marked revoked | **not run — no implementation exists** |

M3a and M3c are the same package, same bytes, verified twice. The only
difference is whether the verifier was handed an out-of-band public key. That
is exactly what `trust_level` is for: `unanchored` means "this signature is
internally consistent and a forger's own key would look identical"; `anchored`
means "the key used was supplied from outside the package". Publishing M3a's
`PASS` as if it were M3c's would be the misstatement this vector exists to
prevent.

M3d cannot be run. `verify` accepts no key-status input, so a revoked pinned key
and a valid pinned key produce the same verdict. Revocation in this repository
is a package-level object (`revocation.json`, `target_root` = `evidence_root`)
that terminates at `gate` (`DENY` on a valid owner signature, `HOLD` when the
revocation itself cannot be verified). Recording this as unimplemented rather
than dropping it: the row is a real gap in "can I still trust this after a
rotation", and the honest answer today is "not from the package alone".

Three defects in the published recipe were found by running it. `MIGRATION-VECTORS.md`
§M3 previously showed `init --out … --key …` — `init` takes only a path and
does no signing — and `verify --pin …`, when the flag is `--pubkey`. Its verdict
table also required `FAIL` for the unpinned case, which contradicts the
verifier's deliberate `unanchored` behaviour. All three are corrected there,
with the observed values beside the declared ones.

## What this changes in the repository's own claims

`VERSIONING.md` forward-compatibility row could previously only be filled with
intentions. After M1 it can carry one measured fact - a 0.3.3 package verifies
as PASS under 0.4.0 when it uses the shared vocabulary, and degrades to
INCONCLUSIVE, not FAIL, when it uses a type 0.4.0 does not know. M2 produced a
conclusive negative, and M3 adds the attribution dimension: the same package is
`PASS unanchored` or `PASS anchored` depending only on whether the verifier was
given an out-of-band key, and a rotated-away key is not detectable from the
package alone. The row is still "partially measured", not "verified" — no
registry or gate consumes the floor or the anchor yet, and M3d has no
implementation. That is the word it should carry.
