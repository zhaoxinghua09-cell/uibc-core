# Vocabulary (canonical terms)

| Term | Meaning |
|---|---|
| LGD | Theory layer: Registry · Evidence · Gates (有籍·有证·有门禁) |
| UIBC | Execution protocol making LGD checkable |
| Agent | Registered actor; identity is not a key |
| Event | Recorded action inside a run |
| Evidence | File + recorded hash; sealed into a package |
| Evidence Root | Hash over canonical serialization of all evidence (order-independent) |
| Run | A bounded execution with evidence |
| Evaluation | Judgement over a run |
| Verification | Independent re-check of a sealed package (steps S1–S6) |
| Certificate | Signed attestation "this package verified" (C1–C7) |
| Gate | Decision layer: ALLOW(0) / DENY(2) / HOLD(3) |
| Dispute | Flag attached to a package; flags never silently block |
| Revocation | Signed withdrawal that DOES block (after signature check) |
| Memory Package / Migration | UIBC-MEM unit + transfer between agents |
| Preservation | M2 Fact / M3 Attribution / M4 Citation / M5 Version |

Use these exact terms. Do not invent synonyms in machine-facing text.
