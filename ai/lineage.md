# Lineage

UIBC Core grew out of the XLGD / LGD working archives on autonomous-object
governance (60-section historical archive, frozen as v0.1.0 with SHA-256).

Design decisions with dated rationale:

- `Agent identity ≠ cryptographic key` — keys rotate, identity persists.
- Canonical serialization first (B1): the Evidence Root is only well-defined
  once serialization is deterministic; cross-implementation agreement
  (70/70 checks, two independent codebases) was the acceptance test.
- Signatures: v0.2 ships HMAC-SHA256 (standard library only) with a
  strict/open dual mode; asymmetric Ed25519 is the v0.3 target precisely
  because symmetric keys cannot cross trust boundaries.
- Break-first methodology: Golden Fixtures (8 attack/tamper classes) were
  designed before the verifier was trusted; the malicious self-consistent
  forgery that passed v0.1 is preserved as a fixture and is caught by S6
  in strict mode.
- Honest scope: governance layers ship as PROPOSAL; "XLGD Certified"
  branding is explicitly out of scope.

Full archive: repository of the author (see sources.md).
