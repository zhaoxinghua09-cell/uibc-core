# VERSIONING.md — 规范版本与兼容性政策

Version 1.0 · 2026-11-19 · Owner: Xinghua Zhao (Steven Zhao) · ORCID 0009-0001-0512-1237

## 1. What counts as the protocol

The protocol is the set of elements that, if changed, would cause an existing third-party verifier to reach a different verdict. Those elements are:

- the evidence envelope structure;
- the per-item digest chain and its root;
- the seal format (Ed25519 signature and `key_id` derivation);
- the three-valued verdict vocabulary (`PASS` / `FAIL` / `INCONCLUSIVE`);
- the precedence rule that a missing required element yields `INCONCLUSIVE` and never `PASS`.

Everything else is an extension. Extensions may be added, omitted or replaced without a protocol version increment.

## 2. Version numbering

| Change | Increment |
|---|---|
| Any element in §1 | **minor version** (new capability, compatibility analysed) |
| Any element in §1 that changes verdict semantics | **major version** |
| Extensions, documentation, tooling | patch version |

A patch release may never alter a verdict. If a change alters a verdict, it is not a patch.

## 3. Required fields for every release

Each release record MUST state:

| Field | Content |
|---|---|
| **Backward Compatibility** | Can the new verifier validate older packages? yes / no / partial, with the test that demonstrates it |
| **Forward Compatibility** | What does the previous verifier do with the new package? The answer must be `INCONCLUSIVE`, never `PASS` |
| **Breaking Changes** | Itemised, each with its replacement path |
| **Deprecation** | Notice period in releases and the removal release |
| **Migration** | Steps and commands from N to N+1 |
| **Security Impact** | Fixes and exposures introduced |
| **Interoperability Test** | Which corpus was run, on which implementations, with what result |

A release missing any of these fields is not published.

## 4. Forward compatibility rule

The single most important rule in this document:

> **A new field must cause an older verifier to return `INCONCLUSIVE`, never `PASS`.**

An old verifier that silently accepts an unknown field is a silent-failure generator: it reports success on input it did not understand. Every new field therefore ships with a negative test proving the old verifier does not return `PASS`.

## 5. The conformance corpus is part of the version

The test corpus is not external to the protocol. Its content and its version are recorded in the release record. Changing the corpus version is a compatibility-relevant change even when no code changes.

## 6. Migration test set (required before any freeze)

Three vectors are mandatory for every version boundary:

1. package from N → verifier from N+1
2. package from N+1 → verifier from N
3. package signed before a key rotation → verifier after rotation

Each vector declares its expected verdict in advance. A vector whose expected verdict is written after the run is not a test, it is a description.

## 7. Current state (2026-11-19, recorded honestly)

Three version identities coexist and do not agree:

| Where | Version |
|---|---|
| Repository main branch | 0.4.0 |
| Package index | 0.3.3 |
| Archival DOI record | 0.3.0 |

This is a defect, not a state to be explained. Until the archival record matches the released code, the phrase "current version" refers to the repository and must say so.

## 8. Version floor (added 2026-11-19, after M2 was actually run)

**A PASS from an older verifier is not a safety signal.** That is not a slogan here; it is a measured result.

Reproduction (`docs/MIGRATION-RESULTS.md`, M2c): a package is sealed by 0.4.0 carrying `identity.key_custody: "hsm"` - a provenance claim meaning the signing key lives in hardware. 0.4.0 judges it and reports PASS with `key_custody: hsm`. 0.3.3 was then used on the same bytes: it has no notion of `key_custody` at all (`Select-String` over its shipped source finds the token zero times), never inspected the claim, and returned **PASS, exit 0**.

So an older verifier will certify a claim it cannot see. This cannot be fixed by editing code: a published release cannot be recalled. Any policy that depends on "our verifier would have caught it" is depending on the newest verifier being the one that actually ran.

What this requires instead:

1. **The artefact carries its floor.** A package declares the minimum verifier version able to judge everything it contains. The builder writes it; it is a field, not a comment.
2. **The consumer compares.** Registries, gates and CI compare the declared floor with the verifier's own version before treating a PASS as meaningful. A verifier below the floor must not be trusted to PASS, and must not be quoted as having PASSed.
3. **Unknown stays INCONCLUSIVE.** A verifier that meets the floor but does not recognise a value reports INCONCLUSIVE naming it (`S4` for an unknown evidence type, per #178). PASS is reserved for "I judged everything here and it holds".
4. **Nobody claims retroactive coverage.** Documents may not say a later check would have caught an earlier artefact. It did not run.

Point 1 is implemented as of 2026-11-19: `uibc submit` writes
`manifest.min_verifier_version`, and a verifier older than that floor reports
**S1 INCONCLUSIVE** naming both versions (`tests/test_version_floor.py`).

But the floor has a limit that must be stated plainly, because it is the same
lesson as M2c one level up: **an older verifier cannot be made to obey a field it
has never heard of.** 0.3.3 contains `min_verifier_version` zero times - measured
by search over its shipped source - so a package that declares a floor of 0.4.0
is still PASSed by 0.3.3, exit 0, with the declaration silently ignored.

Therefore point 2 is not a convenience, it is the load-bearing control: the floor
only protects anything when a consumer compares it before trusting a PASS. A
package's own declaration cannot defend itself against a verifier that does not
read it.

Until consumers actually perform that comparison, this section records a
partially closed rule rather than a closed one, and forward compatibility stays
**partially measured**.

## 9. Amendments

Changes to §1 or §4 follow the seven-step procedure in `GOVERNANCE.md` and require a major version.
