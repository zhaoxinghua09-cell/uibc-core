# Specifications

Normative documents in this repository:

| Document | Status | Path |
|---|---|---|
| Core protocol & package format | PROPOSAL v0.1 | [docs/SPEC-PROPOSAL-v0.1.md](../docs/SPEC-PROPOSAL-v0.1.md) |
| Governance six layers | PROPOSAL v0.1 | [docs/governance.md](../docs/governance.md) |
| API surface & exposure scope | Decision v1.0 (read-only public) | [docs/api-scope.md](../docs/api-scope.md) |
| Adoption path | Guide | [docs/adoption-guide.md](../docs/adoption-guide.md) |

Implementation status (single source of truth = this repo's git log):

- submit / verify (S1–S6, open + strict) — implemented
- HMAC sealing + keygen — implemented
- gate (ALLOW/DENY/HOLD, exit 0/2/3) — implemented
- certificates (C1–C7) — implemented
- UIBC-MEM migration + 4 Preservations — implemented
- Independent verifier (zero shared code) — implemented, cross-check 70/70

Stability: everything is PROPOSAL; fields may change before v1.0.
Pin git tags if you build against this.
