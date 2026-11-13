# PR title

Add uibc-agent-evidence test vectors (agent evidence packages, with a proposed SCITT mapping)

# PR description

This PR contributes a test-vector suite from **uibc-core**, an
independent open-source implementation of verifiable evidence packages
for autonomous AI agents, and proposes a mapping onto SCITT concepts
for discussion.

**What is included** (`test-vectors/uibc-agent-evidence/`):

- Nine evidence packages: eight generated with the source repo's
  fixture generator (v0.3.0, definitions as at `main @ dc9eba31`;
  generation embeds timestamps, so they are not byte-identical to
  the copies checked into the source repo — see the suite README's
  Provenance section) and one public sample package, byte-identical
  to the source repo's `examples/sample-package`: one clean package, seven
  single-mutation cases (tampered / deleted / duplicated / reordered /
  migrated / malicious / malicious-keyswap), and one public sample
  package sealed with Ed25519 (owner public key included, so the
  pinned verification mode is reproducible by anyone).
- `expected.json` per case with the outcomes reproducible from the
  shipped bytes; a runner (`run_vectors.py`) — 10 mode checks, all
  reproduced before submission.
- The full 24-cell expectation matrix (8 fixtures × open / strict /
  attacker-key modes) in `manifest.json`. Strict modes are reproduced
  via the source repo's generator gate (fixture keys are ephemeral by
  design); the gate was re-run for this submission: 24/24 cells match.
- `SHA256SUMS` covering every file, and a README with provenance,
  verify steps, and a field reference.

**The mapping** (detailed in the suite README): Signed Statement ↔
the package seal over identity+manifest; subject ↔ agent identity;
payload ↔ the manifest committing to the evidence root; Ed25519 seals
align with this repo's EdDSA vectors. For the sample package the PR
also includes the real thing: a **COSE_Sign1 hash-envelope Signed
Statement** over its manifest (`signed-statements/` and in the case
directory), signed with the same key that seals the package, with a
zero-dependency verifier — cross-checked against two independent
Ed25519 backends, with tamper and wrong-key controls rejected. Stated
plainly as **not** claimed: no Transparency Service receipt exists
yet, so it is a Signed Statement, not a Transparent Statement —
registering it is the open next step.

**The question for the WG**: UIBC verification is three-valued
(PASS / FAIL / INCONCLUSIVE — unresolved evidence caps the verdict
instead of passing). If agent evidence becomes a SCITT profile, where
should that outcome live?

The known limits are part of the vectors, not footnotes: the evidence
root binds sorted content hashes (order is not attested by the root),
and a key-substituted package verifies against the attacker's key —
only out-of-band pinning detects it (the `malicious-keyswap` case, the
standing argument for public-key seals).

Contributed by Xinghua Zhao (uibc-core maintainer), in an individual
capacity.

