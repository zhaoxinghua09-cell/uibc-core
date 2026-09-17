# Benchmarks & attack fixtures

Fixtures are executable evidence: each is a `.uibc` package engineered to
provoke a specific verdict.

| Fixture | Class | Expected (open mode) | Expected (strict mode + key) |
|---|---|---|---|
| clean.uibc | baseline | PASS (S6 INCONCLUSIVE — seal present, no key) | PASS (S6 PASS) |
| tampered.uibc | content edit | FAIL (S4 hash mismatch) | FAIL (S4 + S6) |
| deleted.uibc | evidence removed | FAIL (S4 missing file) | FAIL (S4 + S6) |
| duplicated.uibc | duplicate index entry | FAIL (S5 root mismatch) | FAIL (S5 + S6) |
| reordered.uibc | lifecycle events shuffled | FAIL (S3 lifecycle violation) | FAIL (S3 + S6) |
| migrated.uibc | partial migration, not re-sealed | FAIL (S5 root mismatch) | FAIL (S5 + S6) |
| malicious.uibc | self-consistent forgery | PASS by design surface (S6 INCONCLUSIVE) | **FAIL (S6)** |
| malicious-keyswap.uibc | key substitution | PASS (UNDETECTABLE without owner key) | **FAIL (S6)** |

Canonical source of truth: `fixtures/EXPECTED.md` (machine-generated,
includes expected-vs-observed per fixture). If this page and EXPECTED.md
ever disagree, EXPECTED.md wins.

Regenerate: `python fixtures/generate_fixtures.py`.
Stress suite: 7 scenarios including signing throughput (~120k ops/s) and
strict S6 verification of a 500-entry package (<0.5s).

Known limit: `malicious-keyswap` where the attacker swaps in their own key
is only detectable when verifiers pin the owner's key externally — this is
the standing motivation for Ed25519 + a public key registry (v0.3).
