# Concepts

An autonomous agent performs runs. UIBC makes three questions answerable
about any run, without trusting the runner:

1. **Who did it?** — Identity (an `Agent identity ≠ cryptographic key`;
   keys are held, identity is registered).
2. **What proof exists?** — Evidence: files sealed into a package whose
   hashes form a Merkle-style `evidence_root` over canonical serialization.
3. **May it proceed?** — Gates: a verifier turns checks (S1–S6) into a
   governed decision: `ALLOW` / `DENY` / `HOLD`.

A **submission package** (`.uibc`) is the unit of transport. A
**certificate** is a signed attestation that a package passed verification
at a point in time. **UIBC-MEM** extends the same machinery to verifiable
memory migration between agents.

Governance layers (Dispute / Correction / Revocation / Accountability /
Continuity / Provenance) are specified in
[docs/governance.md](../docs/governance.md) as PROPOSAL v0.1.
