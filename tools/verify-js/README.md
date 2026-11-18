# A second implementation, in a second language

`verify.mjs` verifies a UIBC package using nothing but Node's standard library. It does not import `uibc-core`, reads no Python, and depends on no npm package. Everything it needs is RFC 8785 (canonical JSON), SHA-256, and the package's own file layout.

## What it decides, and what it refuses to pretend

| check | here | why |
|---|---|---|
| S1 package structure | yes | files and declarations are layout, not cryptography |
| S2 identity consistency | yes | two JSON documents compared |
| S4 evidence integrity | yes | SHA-256 over each file |
| S5 evidence root | yes | RFC 8785 + one hash |
| S6 seal signature | **Ed25519 only** | the public key is in the package, so a stranger can check it; an HMAC seal needs the owner's key and is reported INCONCLUSIVE |
| S7 index metadata | yes | field shapes, identifier syntax, and the digest carried in the manifest |
| S10 closure declared | yes | six components present and shaped like digests (declaration only) |
| S11 strict serialization | yes | duplicate members, control characters, UTF-8 |
| S12 timestamps and counts | yes | calendar arithmetic |
| S14 strict base64 | yes | pad bits, missing padding, stray characters |
| S13 Merkle / inclusion | **no** | needs the v1.1 tree |
| S15, S16, S17, S18 | **no** | anchors, RFC 3161, receipt chain, policies |
| S8, S9 | **no** | checkpoint head, out-of-band pin |


Because it cannot attest a signature, **it never returns `PASS`**. A structurally sound package comes back `INCONCLUSIVE`, and that sentence is the honest one: nothing was found wrong, and nothing was proven either.

## Measured against the suite

```
node tools/verify-js/verify.mjs conformance/cases/01-the-shipped-package-untouched
```

```
strict 23/36   refused 30/36      (tools/run_conformance.py --verify "node ... {pkg}")
```

| | value | reading |
|---|---|---|
| packages in scope | 23 of 36 | 6 correct + 17 whose expected check is among the ten |
| out of scope | 13 | the ones needing Ed25519, RFC 3161 or the tree |
| identical FAIL set to Python | 17 | the second implementation reaches the same verdict for the same reason |
| named an expected check | 17 (+6 positives) | what the suite scores |
| refusals | 30 of 36 | the 30 mutated packages, and none of the correct ones |

The number that matters is **identical FAIL set to Python: 17**, plus 17 cases where it names the same expected check Python does. Two implementations built from the spec, with no shared code, agreeing on which packages are broken and why, is the difference between "we have tests" and "anyone can check".

## Two bugs this exercise found in its own work

1. **A case that was mislabelled.** The "one more declared evidence file" package had its declaration written under the wrong member name, so the file was in fact *undeclared* while the case claimed otherwise. The JS verifier refused it, which is how it surfaced. The case now grows the package through the shipped CLI, and its name matches what it does.
2. **A false positive in the JS verifier.** It counted `evidence/.lock` — the lock file a writer leaves behind — as an undeclared file. Hidden files are machinery, not evidence, and are now skipped.

Neither was a hypothetical: both were caused by running a second implementation against the same corpus.
