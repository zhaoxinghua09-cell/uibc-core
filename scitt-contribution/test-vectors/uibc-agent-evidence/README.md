# uibc-agent-evidence test vectors (v1)

Conformance vectors for **verifiable evidence packages for autonomous AI
agents**, contributed by the [uibc-core](https://github.com/zhaoxinghua09-cell/uibc-core)
project (an independent, open-source reference implementation), together
with a **proposed mapping** onto SCITT concepts. Feedback on the mapping
is the point of the contribution.

## What a UIBC evidence package is

An agent's work is sealed into a package (a directory tree):

```
package/
  identity.json     who the agent is (the subject)
  lifecycle.json    append-only lifecycle events
  manifest.json     the statement: identity + evidence index + evidence root
  evidence/         the evidence files themselves
  signatures/
    seal.json       the issuer seal over identity+manifest
```

A verifier runs six checks — S1 structure, S2 identity, S3 lifecycle,
S4 evidence hashes, S5 evidence root, S6 seal — and returns a
**three-valued verdict**: `PASS`, `FAIL`, or `INCONCLUSIVE`
(an unresolved check caps the verdict; absence of evidence is never
reported as a pass). Verdict semantics are specified in
`docs/verdict-and-seal-semantics.md` in the source repo.

## Proposed mapping to SCITT

| SCITT | UIBC counterpart | Status |
|---|---|---|
| Signed Statement | The seal (`signatures/seal.json`) over identity+manifest; for the sample package, additionally a COSE_Sign1 hash-envelope statement over its manifest | One real example included: `v1/sample-ed25519/statement.cose` (also at `signed-statements/uibc-agent-evidence-sample-manifest.scitt` in this repo) |
| Statement subject | `identity.json` (agent identity) | Direct counterpart |
| Statement payload | `manifest.json`, committing to the evidence root `sha256(canonical-json(sorted(content_hashes)))` | Direct counterpart |
| Issuer signature algorithm | Ed25519 (EdDSA) public seals since v0.3.0; HMAC-SHA256 owner seals in the golden fixtures | Same algorithm family as this repo's `valid-eddsa` vector |
| Receipt / Transparency Service registration | **None yet** | Open step: register the sealed statement with a Transparency Service and carry the receipt alongside the package |
| Verification outcome | Three-valued verdict (PASS / FAIL / INCONCLUSIVE) with per-check results | No SCITT counterpart; proposed as profile-level information |

This suite does **not** claim SCITT conformance. It contributes the
vectors of a working agent-evidence system, one genuine SCITT-format
Signed Statement for the sample package (COSE hash envelope, EdDSA —
payload = SHA-256 of the package manifest, signed with the same key
that seals the package; no Transparency Service receipt exists yet,
so it is a Signed Statement, not a Transparent Statement), and one
concrete question for the WG: *where should a verifier's three-valued
outcome live in a SCITT profile for agent evidence?*

## Cases (v1/)

Eight cases are the source repo's golden fixtures — one clean package
and seven single-mutation derivatives (tampered, deleted, duplicated,
reordered, migrated, malicious, malicious-keyswap), sealed with an
HMAC-SHA256 owner seal. The ninth, `sample-ed25519`, is the public
sample package sealed with Ed25519; its owner public key ships as
`owner.pub` so the pinned mode is reproducible by anyone. This case
also carries `statement.cose`: a SCITT Signed Statement (COSE hash
envelope) over the package manifest, signed with the same key
(SPKI PEM in `issuer-key.pub`), verifiable with
`verify_statement.py` in this directory — standard library only.

Each case directory holds `package/` (generated from the source
fixture definitions — see Provenance for exactly what that means;
the sample package is a byte-identical copy) and `expected.json`
(the outcomes reproducible from the shipped bytes).

## Verify

```bash
# Integrity of the vendored bytes (paths are relative to this directory):
( cd test-vectors/uibc-agent-evidence && sha256sum -c SHA256SUMS )

# Shipped cases (open mode for all; open + pinned for the Ed25519 sample):
git clone https://github.com/zhaoxinghua09-cell/uibc-core
PYTHONPATH=uibc-core python3 test-vectors/uibc-agent-evidence/run_vectors.py test-vectors/uibc-agent-evidence
# expected: 10 mode checks, ALL OK, exit 0

# The sample package's SCITT Signed Statement (zero-dependency verifier):
python3 test-vectors/uibc-agent-evidence/verify_statement.py test-vectors/uibc-agent-evidence/v1/sample-ed25519
# expected: "STATEMENT VALID", exit 0

# The full 24-cell expectation matrix (8 fixtures x open/strict/attacker-key)
# is enforced in the source repo — fixture keys are ephemeral by design,
# so strict modes are reproduced by rebuilding, not from shipped bytes:
( cd uibc-core && python3 fixtures/generate_fixtures.py )
# expected: "[MATRIX GATE] OK - all 24 cells match the prior.", exit 0
```

## Field reference

- Verdicts: `PASS` (every check passed), `FAIL` (at least one check
  failed), `INCONCLUSIVE` (no failure, but at least one check could
  not be resolved — e.g. a seal is present but no key is available).
- `assurance` (in reports): `public-key` (Ed25519 seal verified),
  `owner-key` (HMAC seal verified with the owner key), `unattested`.
- Checks: S1 structure · S2 identity · S3 lifecycle · S4 evidence
  hashes · S5 evidence root · S6 seal.
- Known boundary, stated in the source repo and kept here on purpose:
  the seal binds identity+manifest; the manifest binds the evidence
  root; the root binds the **sorted** content hashes, so evidence
  **order is not attested** by the root (lifecycle order is checked
  separately at S3). A key-substituted package (`malicious-keyswap`)
  verifies against the attacker's key — only pinning the owner's key
  out-of-band detects it. These limits are part of the vectors, not
  footnotes.
- Reference readings (normative for these vectors — an independent
  reader building only from the texts must apply the same rules to
  reach the same verdicts):
  - **S3 is positional.** The lifecycle is evaluated as an ordered
    list: position 0 must be `REGISTER`, and each entry's
    `previous_event` must name the immediately preceding entry *in
    the file*. Reordering entries — even with the pointers kept
    self-consistent — breaks the chain at the first displaced
    position, so `reordered` is S3 FAIL. Reconstructing the order by
    following pointers alone is a different rule and yields a
    different verdict.
  - **S5 counts duplicates.** The evidence root is computed over the
    sorted *list* of per-entry content hashes, duplicates counted
    (a multiset). Duplicating an index entry therefore changes the
    computed root, so `duplicated` is S5 FAIL. Hashing a deduplicated
    *set* of hashes is a different rule and yields a different
    verdict.
  - **Statement payload vs seal.** The COSE statement's payload is
    the SHA-256 of the manifest *file bytes* (whitespace-sensitive);
    the package seal signs the *canonical JSON* of identity+manifest
    (whitespace-insensitive). Reformatting `manifest.json` changes
    the statement payload while leaving the seal valid. The statement
    therefore binds the exact manifest bytes shipped in the package;
    consumers must not re-serialize the manifest before checking the
    payload.

## Provenance

The eight HMAC fixture packages were generated on 2026-11-10 with
the uibc-core 0.3.0 fixture generator, from the same fixture
definitions as the golden fixtures in `zhaoxinghua09-cell/uibc-core`
(`main @ dc9eba3146e4e32bb1356f24ce8d72249a64702a`, v0.3.0).
Generation embeds wall-clock timestamps and the current schema
string (`uibc-core/0.3.0-proposal`), so these trees are **not**
byte-identical to the fixture copies checked into the source repo at
that commit (those read `uibc-core/0.2.2-proposal`). The
`sample-ed25519` package **is** a byte-identical copy of
`examples/sample-package`. All expected outcomes in this suite were
reproduced from the shipped bytes with the source verifier before
submission; the 24-cell matrix was reproduced via the generator gate
on the same date.

Corrections (2026-11-14), after an independent review by Konrad
Gruszka, who rebuilt a reader from the texts alone: an earlier
revision of this suite described the fixture packages as
byte-identical copies of the source fixtures — they are not, as
detailed above — and the sample statement's CWT `iat` read
1762740000 (2025-11-10), one year early. The statement has been
re-issued with `iat` 1794276000 (2026-11-10), same key, same
payload; the reference readings above were added in the same round.
