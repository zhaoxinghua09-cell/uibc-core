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

Read M2a carefully. `PASS` from an older verifier is the *dangerous* outcome in a
migration vector - it means the old tool claimed success on something it could
not have judged. Here it is legitimate, because M2a uses only the commands both
releases implement, so 0.3.3 really did judge everything in the package.

M2b did not produce a silent PASS either: 0.3.3 already implements S16 and
reports INCONCLUSIVE without `asn1crypto`.

**What M2 has not established:** neither sub-case exercised a feature that is
genuinely new in 0.4.0 and unknown to 0.3.3. 0.3.3 already knows S16, so the
"new-only feature" case was not constructed. M2 therefore shows no silent PASS
in the two shapes tried, and is **not** closed. It stays open, and no forward
compatibility claim may be made from it.

## M3 - key rotation and pinning

Not run. Nothing claimed.

## What this changes in the repository's own claims

`VERSIONING.md` forward-compatibility row could previously only be filled with
intentions. After M1 it can carry one measured fact - a 0.3.3 package verifies
as PASS under 0.4.0 when it uses the shared vocabulary, and degrades to
INCONCLUSIVE, not FAIL, when it uses a type 0.4.0 does not know. M2 and M3 are
still open, so the row is not "verified" - it is "partially measured", and that
is the word it should carry.
