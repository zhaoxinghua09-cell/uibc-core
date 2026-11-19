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

## 8. Amendments

Changes to §1 or §4 follow the seven-step procedure in `GOVERNANCE.md` and require a major version.
