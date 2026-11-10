# Agent evidence package vectors (UIBC) — test vectors

Test vectors from an independent agent-evidence implementation
([uibc-core](https://github.com/zhaoxinghua09-cell/uibc-core)): nine
verifiable evidence packages for autonomous AI agents (one clean, seven
single-mutation cases, one Ed25519-sealed public sample), each with the
verifier outcome reproducible from the shipped bytes, the full 24-cell
fixture × mode expectation matrix, and a proposed mapping onto SCITT
concepts (Signed Statement ↔ package seal, subject ↔ agent identity,
payload ↔ evidence-root manifest). No Transparency Service receipt is
included; the mapping — in particular where a verifier's three-valued
outcome (PASS / FAIL / INCONCLUSIVE) belongs in a SCITT profile for
agent evidence — is offered for WG discussion.

One case (the Ed25519 sample) also carries a SCITT Signed Statement —
a COSE hash-envelope statement over the package manifest — at
`signed-statements/uibc-agent-evidence-sample-manifest.scitt` and in
the case directory, with a zero-dependency verifier
(`verify_statement.py`). No Transparency Service receipt exists yet.

```
test-vectors/uibc-agent-evidence/README.md      mapping, verify steps, field reference
test-vectors/uibc-agent-evidence/manifest.json  case index + 24-cell expectation matrix
test-vectors/uibc-agent-evidence/SHA256SUMS     digest of every file in the suite
test-vectors/uibc-agent-evidence/run_vectors.py runner for the shipped cases
test-vectors/uibc-agent-evidence/v1/<case>/     package/ (byte-identical fixture) + expected.json
```

Verify:

```
( cd test-vectors/uibc-agent-evidence && sha256sum -c SHA256SUMS )
git clone https://github.com/zhaoxinghua09-cell/uibc-core
PYTHONPATH=uibc-core python3 test-vectors/uibc-agent-evidence/run_vectors.py test-vectors/uibc-agent-evidence
```
