# Benchmarks & attack fixtures

Fixtures are executable evidence: each is a `.uibc` package engineered to
provoke a specific verdict.

| Fixture | Class | Expected (open mode) | Expected (strict mode + key) |
|---|---|---|---|
| clean.uibc | baseline | PASS | PASS |
| tampered.uibc | content edit | FAIL (S4) | FAIL (S4) |
| deleted.uibc | evidence removed | FAIL (S4) | FAIL (S4) |
| duplicated.uibc | duplicate entry | FAIL (S4) | FAIL (S4) |
| reordered.uibc | entry order shuffle | PASS (order-independent root) | PASS |
| migrated.uibc | version migration | PASS + migration note | PASS |
| malicious.uibc | self-consistent forgery | UNDETECTED by design surface | **FAIL (S6)** |
| malicious-keyswap.uibc | key substitution | INCONCLUSIVE | **FAIL (S6)** |

Regenerate: `python fixtures/generate_fixtures.py`.
Stress suite: 7 scenarios including signing throughput (~120k ops/s) and
strict S6 verification of a 500-entry package (<0.5s).

Known limit: `malicious-keyswap` where the attacker swaps in their own key
is only detectable when verifiers pin the owner's key externally — this is
the standing motivation for Ed25519 + a public key registry (v0.3).
