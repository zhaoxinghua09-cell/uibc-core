# Conformance — re-run it yourself

<!-- facts: current -->


`uibc-core` claims a small, checkable set of behaviours. This page lists
each claim, the vector set that pins it down, and the exact command that
reproduces it. Nothing here asks to be believed: every row is a command
a stranger can run.

Reference version: PyPI carries **0.5.0** (seven releases, 0.5.0 latest); most
fixture trees quoted below were pinned at **0.3.0** and are unchanged since, so a
`v0.3.0` checkout reproduces them. Where the two differ the row says so. Verdict
semantics are specified in [verdict-and-seal-semantics.md](verdict-and-seal-semantics.md).

## Vector sets

| Set | What it pins | Expected result | Reproduce |
|---|---|---|---|
| Verdict fixture matrix (`fixtures/`, 8 packages × S1–S6 checks) | Three-valued verdicts: tampered / deleted / duplicated / reordered / migrated packages FAIL; unresolved cases stay INCONCLUSIVE, never PASS | 24 / 24 cells match `fixtures/EXPECTED.md` | `python fixtures/generate_fixtures.py` |
| Independent-verifier corpus | The bundled independent verifier (a second implementation path) agrees with the main verifier | 70 checks; the count of mismatches is whatever the run prints (0 at HEAD, and a non-zero value means SPEC BUG, not a typo to fix here) | `python independent_verifier/cross_check.py` |
| Memory-migration matrix (UIBC-MEM) | Migration preservation checks M0–M5 over faithful and attacked memory packages | 22 / 22 cells match `fixtures/MEMORY_EXPECTED.md` | `python fixtures/generate_memory_fixtures.py` |
| Unit + stress suite | Package behaviour incl. negative controls (bad inputs must fail) | **full suite OK (skipped=2)**, count pinned in `docs/EVIDENCE-INDEX.md` with `.[verify,interop]` (`skipped=16` without it — `docs/SKIPPED.md`); three anchor modules skip instead of fail when `cryptography`/`asn1crypto` are absent — `pip install -e ".[verify]" pytest` runs them. **pytest is a separate install, not an extra**: 13 test modules `import pytest` at module scope, so a bare `.[verify]` install reports them as `ImportError` (13 errors + 2 count-mismatch failures) even though the code is fine | `python -m unittest discover -s tests -p "test_*.py"` |
| Seal vectors | Ed25519 seal is plain RFC 8032; the published test vector is locked in the suite | Vector 1 passes; a substituted signer key FAILS S6 when the expected key is pinned (`--pubkey`) | unit suite, S6 cases |

A zero-install path exists for single packages: the browser verifier at
<https://zhaoxinghua09-cell.github.io/uibc-core/verify.html> runs the
same S1–S6 checks client-side.

## Language-neutral corpus

`docs/conformance/vectors.json` is a corpus for implementations that are not ours:
each vector embeds its own input and the exact expected output, so a program
written somewhere else can be measured without importing this repository.

| kind | vectors | what a conforming implementation must do |
|---|---|---|
| `canonical_json` | 10 | canonicalize the embedded object and match **both** the exact UTF-8 bytes and the SHA-256 |
| `ed25519_signature` (valid) | 3 | verify with any Ed25519 library; verdict `valid` |
| `ed25519_signature` (invalid) | 2 | reject a signature made over another message, and one with a single flipped byte |
| `receipt_digest` | 3 | hash the RFC 8785 JCS bytes of a receipt envelope and match the published digest |
| `receipt_chain` | 3 | recompute the linear links: first receipt carries 64 zeros, every later one carries its predecessor's digest; one valid chain, one broken link, one non-zero genesis |
| `anchor_binding` | 2 | hash the shipped artifact and parse a real RFC 3161 token; the token must bind the one file and must not bind the other |
| `merkle_root` | 2 | build the RFC 6962 tree (leaf = SHA-256(0x00‖leaf), node = SHA-256(0x01‖left‖right), odd tail promoted not duplicated) and match the root; one five-leaf tree and one single-leaf tree |
| `merkle_inclusion` | 3 | recompute the root from a leaf, its index, the tree size and the sibling path; the genuine path must be `included`, a tampered leaf and a wrong index must both be `not_included` |
| `policy_digest` | 1 | hash the RFC 8785 JCS bytes of a retained policy artefact and match the published digest |

The signature vectors publish the throwaway 32-byte seed (`00…01`) used to produce
them, so the values are reproducible rather than asserted. The seed is worthless
outside the corpus and must not be used for anything else.

```
python tools/conformance_vectors.py --check   # regenerate and compare byte for byte
python tools/conformance_check.py             # a checker that imports nothing from uibc_core
```
The second command implements its own canonicalizer with `json`/`hashlib`, verifies signatures
with the third-party `cryptography` package, recomputes the chain links itself, rebuilds the
Merkle roots and inclusion paths itself, and reads the token's `messageImprint` with
`asn1crypto`. Measured output: **29/29 vectors reproduced by a non-uibc implementation**. If the
corpus only passed under our own verifier it would prove nothing.

What it does **not** cover, and the difference matters:

* **No second implementation.** We ship the object a second implementation can be measured
  against; we do not ship that implementation. Tracekit and agent-receipts publish both.
  "We match Tracekit here" would be a false claim.
* **No end-to-end receipt schema validation.** A receipt is a composite: the seven steps here
  are published, the assembly rules are not. `docs/INTEROP-MATRIX.md` labels the untested cells
  as untested.
* **No floats in the receipt, chain or policy artefacts.** The corpus tests structure, linking
  and trees, not ECMAScript number formatting; saying otherwise would be a false claim.
* **Passing it does not make an implementation interoperable with our receipts.** It makes
  seven steps — canonical bytes, signature, receipt digest, linear link, Merkle root, Merkle
  inclusion, policy digest — plus anchor binding comparable, not the whole format.

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

## Third-party corpus: 288 vectors (Adversarial Execution Evidence v0.7)

The corpora above are ours. This one is not, and that is the point: when the corpus
and the reference verifier belong to someone else, a rail passing it is evidence
about the rail.

`agent-evidence-vectors` (0.36.3) ships 288 vectors for the `in-toto` predicate
`adversarial-execution-evidence/v0.7`, plus its own reference verifier, a
`coverage-unforced.json` listing normative requirements no vector forces, and an
`interpretation-decisions.json` recording which readings are forced by a vector
and which are merely permitted. `uibc_core/aee.py` is this repository's rail for
that contract: `<cmd> <vector-file>`, exit 0 = valid, last stdout line one JSON
object with `verdict`, `codes`, `result`, `tiers`.

```bash
pip install "agent-evidence-vectors==0.36.3" uibc-core==0.5.0
cd <corpus-root>            # the directory containing vectors/MANIFEST.json
python packaging/run_vectors.py --vectors vectors \
  --verifier "python -m uibc_core.aee" --report aee-report.json
```

Measured 2026-11-24 (Windows, Python 3.13.18), report kept at
[`docs/conformance/reports/aee-288-20261124.json`](conformance/reports/aee-288-20261124.json):

| Measurement | Value |
|---|---|
| totals | **288 vectors, 288 pass, 0 fail**; `rail = external` |
| composition | accept **63** / reject **223** / indeterminate **2** |
| conformance column | **PASS 288 / 288** |
| reason-parity column | PASS **223**, `-` 65 (accepts and indeterminates carry none) |
| `reasonParityMismatch` / `suiteRefusals` / `notExercised` | **0 / 0 / 0** |
| `result` tokens recomputed on accepts | `fail` 29 · `pass` 25 · `pass_indirect` 6 · `degraded` 3 |
| distinct failure codes on rejects | 63 |
| two consecutive runs | per-vector identical on `(id, status, conformance, reasonParity, gates, verdict, result, codes)` |

The last two rows are the substantive ones: this rail does not answer
valid/invalid only — it recomputes the `result` token across four values, which is
why a rejected statement carries a specific reason code instead of a shrug.

**What a pass does not mean.** It means no vector in that corpus, at that suite
revision, disagreed with this rail on the normative surface (`verdict`, `result`)
or on the measured surface (`codes`). The corpus's own two registries still apply:
requirements no vector forces, and readings that are permitted rather than forced.
A pass is not a claim of completeness, and not a claim of correctness against the
specification in the abstract.

## Declarations, for readers who want the edges rather than the results

- [`docs/conformance/pics.json`](conformance/pics.json) — what this implementation
  does, which check identifiers it emits, **which it declares absent**, what it
  explicitly cannot do, and key counts per transport (CLI 17 / MCP 17 / HTTP 22
  keys, the latter containing the other two's fields). Two identifiers need care:
  **S9** (`head pinned out-of-band`) and **S10** (`attestation closure declared`)
  are declared in the specification and listed as *not covered* in
  `docs/EVIDENCE-INDEX.md`, but a verify report never emits them — the report
  jumps S8 → S11. Absence there is neither a pass nor a failure.
- [`docs/conformance/pixit.json`](conformance/pixit.json) — environment, subject
  digest, exact commands, exclusions, and the fact that `as_of` is not a
  supported parameter.
- [`docs/conformance/aas1-mapping.json`](conformance/aas1-mapping.json) — gap
  analysis against AAS-1's twelve assertions: **8 partial, 4 none, 0 full.**
  A mapping table, not a conformance claim.

These sit under `docs/conformance/` rather than `conformance/` deliberately:
`conformance/` is byte-pinned by `MANIFEST.sha256` (627 entries), and adding
files there would silently make that pin incomplete.

## Conformance disclaimer and appeals

Passing any material here does not guarantee, and does not imply, full conformance
to any specification. The only claim a result carries:

> No violation was detected within the observed evidence boundary.

`certified`, `accredited`, `compliant` and `audited` are not used in this project
and must not be attached to its results.

Test material that cannot be appealed is test material that cannot be defended:

1. **File** an issue titled `[conformance-appeal] <case or check id>` with the
   identifier, observed vs expected behaviour, a minimal reproduction, and the
   authority relied on.
2. **Acknowledged within 5 working days** with a number `AP-YYYY-NNN`; the only
   admissible ground for refusal is a missing reproduction, and a refusal must
   say what is missing.
3. **Decided within 30 days**, decision and reasons published: `test-invalid`
   retires the case and labels past results as based on a retired case;
   `implementation-bug` records a failure with root cause; `spec-ambiguity`
   downgrades the case to a warning and turns the ambiguity into a specification
   proposal.

A decision changes whether a case's verdict stands. It does not rewrite reports
already issued — those are read under the ruleset in force at their date. Re-running
produces a new result.

## The standing challenge

The tamper cases above are also the entry level of the UIBC contest:
`contest/` in this repository carries the charter, the problem set
(P-01–P-07) and the intake runner. Break the seal under pinning, or
implement the semantics independently and disagree with us somewhere —
both are credited results.
