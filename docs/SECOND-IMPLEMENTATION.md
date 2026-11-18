# A second implementation, in a second language

`tools/verify-js/verify.mjs` checks a UIBC package with nothing but Node's
standard library. It imports no `uibc-core`, runs no Python, and installs no
npm package: RFC 8785 canonical JSON, SHA-256, and the package's own layout.

The point is not that a second implementation exists. The point is that it can
**disagree**, and that when it does, the disagreement is a finding rather than
an inconvenience.

## What it decides

Seven of the nineteen checks: S1 structure, S2 identity, S4 evidence integrity,
S5 evidence root, S7 index metadata (shape **and** the metadata digest carried
in the manifest), S11 strict serialization, S12 timestamps and counts.

**Not** S6 signatures, S13 Merkle proofs, S14/S15/S16/S17/S18, S8, S10 — those
need Ed25519, RFC 3161 and the v1.1 tree. It therefore **never returns PASS**: a
sound package is INCONCLUSIVE, because nothing was found wrong and nothing was
proven either.

## Measured

```
strict 16/34   refused 29/34
```

| | value |
|---|---|
| packages in scope | 16 of 34 (5 correct + 11 whose expected check is among the seven) |
| out of scope | 18 |
| identical FAIL set to Python | 10 |
| named the same expected check | 11 (+5 positives) |

Two implementations written from the specification, sharing no code, agreeing
on which packages are broken and for which reason — that is the difference
between "we have tests" and "anyone can check".

## Two bugs the exercise found in its own work

1. **A mislabelled case.** The "one more declared evidence file" package wrote
   its declaration under the wrong member name, so the file was undeclared
   while the case name said otherwise. The JS verifier refused it, which is how
   it came to light. The case now grows the package through the shipped CLI.
2. **A silent catch hiding a defect.** The metadata-digest comparison caught an
   exception (an `undefined` member is not JSON) and the `catch` made a tampered
   note look fine. Fixed by mapping absent members to `null`, which is what the
   Python side writes.

Neither was hypothetical: both came from running a second implementation
against the same corpus. That is the only way this kind of defect surfaces.

## What it is not

- Not a replacement: 12 of 19 checks still have no second implementation.
- Not a ratification: agreeing with ourselves is not third-party witnessing.
  The external witness count is still zero, and this document does not change it.
