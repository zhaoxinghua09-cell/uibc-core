# Staging: contribution for ietf-wg-scitt/examples

This directory stages a complete, PR-ready contribution to the IETF
SCITT WG examples repo, so it can be reviewed in place before it is
lifted over:

- `test-vectors/uibc-agent-evidence/` — the vector suite (lands at the
  same path in the examples repo)
- `signed-statements/uibc-agent-evidence-sample-manifest.scitt` — the
  sample package's SCITT Signed Statement (lands under
  `signed-statements/` in the examples repo)
- `README-section-for-examples-repo.md` — the section proposed for the
  examples repo's root README
- `PR-DESCRIPTION.md` — the proposed PR title and body

Everything here is byte-identical to the pack verified by its author:
the suite runner passes 10/10 mode checks, the 24-cell expectation
matrix is enforced by the source repo's generator gate, SHA256SUMS
covers every file, and the Signed Statement cross-verifies under two
independent Ed25519 backends (see the suite README).

## Note on the two binary files in this staging copy

The connector used for staging moves text only, so the two COSE
binaries travel here base64-encoded, with a `.b64` suffix:

- `signed-statements/uibc-agent-evidence-sample-manifest.scitt.b64`
- `test-vectors/uibc-agent-evidence/v1/sample-ed25519/statement.cose.b64`

Decode either with `base64 -d <file>.b64 > <file>` — the result is
byte-identical to the intended file and is covered by the suite's
SHA256SUMS (`statement.cose` entry), so the decode is verifiable in
place. In the actual examples-repo PR they are committed as raw
binaries under their plain names.
