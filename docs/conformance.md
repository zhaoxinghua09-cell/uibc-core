# Conformance — re-run it yourself

`uibc-core` claims a small, checkable set of behaviours. This page lists
each claim, the vector set that pins it down, and the exact command that
reproduces it. Nothing here asks to be believed: every row is a command
a stranger can run.

Reference version: **0.3.0** (`pip install uibc-core==0.3.0`, or clone
this repository at the `v0.3.0` tree). Verdict semantics are specified in
[verdict-and-seal-semantics.md](verdict-and-seal-semantics.md).

## Vector sets

| Set | What it pins | Expected result | Reproduce |
|---|---|---|---|
| Verdict fixture matrix (`fixtures/`, 8 packages × S1–S6 checks) | Three-valued verdicts: tampered / deleted / duplicated / reordered / migrated packages FAIL; unresolved cases stay INCONCLUSIVE, never PASS | 24 / 24 cells match `fixtures/EXPECTED.md` | `python fixtures/generate_fixtures.py` |
| Independent-verifier corpus | The bundled independent verifier (a second implementation path) agrees with the main verifier | 70 checks, 0 mismatches | `python independent_verifier/cross_check.py` |
| Memory-migration matrix (UIBC-MEM) | Migration preservation checks M0–M5 over faithful and attacked memory packages | 22 / 22 cells match `fixtures/MEMORY_EXPECTED.md` | `python fixtures/generate_memory_fixtures.py` |
| Unit + stress suite | Package behaviour incl. negative controls (bad inputs must fail) | 164 tests OK | `python -m pytest -q` (or `python -m unittest discover tests`) |
| Seal vectors | Ed25519 seal is plain RFC 8032; the published test vector is locked in the suite | Vector 1 passes; a substituted signer key FAILS S6 when the expected key is pinned (`--pubkey`) | unit suite, S6 cases |

A zero-install path exists for single packages: the browser verifier at
<https://zhaoxinghua09-cell.github.io/uibc-core/verify.html> runs the
same S1–S6 checks client-side.

## Public re-run register

Independent and third-party re-runs we know of, with receipts. A listing
here records that the run happened and what it found — it is not an
endorsement in either direction.

| Date | Who | What | Result | Receipt |
|---|---|---|---|---|
| 2026-11-12 | Takao Sato (Poke-nushi), VATE reader (does not import uibc-core) | 18 selected S4/S5/S6 comparisons; receiving example pinned to the v0.3.0 tree: 22 conditions, 66 comparisons; reseal case with and without the expected key | All agree; reseal case: `not_assessed` without a key, key-mismatch reported with the published key | Comment on aeoess/agent-governance-vocabulary#177; package: github.com/Poke-nushi/Verifiable-Agent-Trust-Envelope |
| 2026-11-12 | tomjwxf (author of the consuming fixture — not an independent run) | Reproduction of `run_v120.json` against the frozen fixture | All 14 verdicts, 8 claims and codes match; `payment_ready: false` reproduced | Recorded in VeritasActa/e6-fixture#4 |

Ran it yourself? Open an issue with your environment, the commit or
release you ran, and your output — matching or not. A mismatch with a
receipt is a finding, and findings get fixed in the open (that is how
v0.3.0 got its seal semantics).

## The standing challenge

The tamper cases above are also the entry level of the UIBC contest:
`contest/` in this repository carries the charter, the problem set
(P-01–P-07) and the intake runner. Break the seal under pinning, or
implement the semantics independently and disagree with us somewhere —
both are credited results.
