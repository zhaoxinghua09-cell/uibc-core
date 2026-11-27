# CITES — where each of the 58 cases comes from

`docs/cites.json` maps every case in `conformance/manifest.json` to the documents it
rests on. This page explains how that map was built and what it deliberately does not claim.

## Coverage

| Measure | Count |
|---|---|
| Cases with a citation | **58 / 58** |
| Cases citing at least one public standard | **42 / 58** |
| Cases citing only this repository's own spec clause | **16 / 58** |

Public standards used: FIPS 180-4 (SHA-256) 14 · RFC 9162 (Merkle trees, transparency logs) 11 ·
draft-ietf-scitt-architecture (signed receipts) 6 · RFC 3339 (date and time) 5 · RFC 4648 (Base64) 3 ·
RFC 8032 (Ed25519) 3 · RFC 8785 (JCS) 1 · RFC 8259 (JSON) 1.

## Two rules this file follows

1. **Document level, not section level.** A row says `RFC 9162`, not `RFC 9162 Section 2.1`.
   A section number is added only after the section text has been read against the case;
   until then it is left out rather than guessed.
2. **No standard is attached where none applies.** Cases `01, 04, 05, 09, 11, 14, 16, 33, 38, 39, 42, 43, 44, 45, 46, 49`
   test this repository's own requirements — appended evidence must be declared, an index path must not
   leave the evidence tree, the declared count must match the files, one file must not be declared twice,
   a lifecycle event must not precede creation. There is no public clause that states these, so the row
   cites the spec clause instead. Attaching an RFC to them would be decoration.

## What this does not change

`conformance/manifest.json` is unchanged, so the shipped archive keeps its bytes:
`conformance/uibc-conformance-0.5.7.zip` is still 389,197 B with sha256
`fd37e0f841e6ed576d8ebf649d60d9011edceff477611968f7625ce90e0e512a`. Adding a citation is metadata; it
does not alter what any of the 58 cases asks a verifier to do.

## What you may and may not say about it

You may say: *"every case carries a citation; 42 of the 58 reach a public standard, the other 16 reach
only this repository's own spec."* You may not say *"all cases are grounded in RFCs"* — they are not.