# Third-party cross-check: two foreign implementations against the SCITT RFC 9162 package

Status: **hash-tree arithmetic and audit-path folding only. pymerkle rebuilds roots (49/49); Sigstore's folding code re-derives every audit path it can read (42/42). Neither is an external run.** Last run 2026-11-24 on company machine.

## Why this exists

Every number in `docs/upstream-package/scitt-rfc9162/` was produced by this repository's own verifier, and every verdict was produced by the same code. That is internal consistency, not corroboration: the code that made the number also certifies it. The one thing a reader outside this project can check cheaply is whether *somebody else's* RFC 6962 implementation reaches the same numbers.

Two independent checks do that, and they are deliberately different in what they feed on:

| | `crosscheck_scitt_pymerkle.py` | `crosscheck_scitt_sigstore.py` |
|---|---|---|
| third party | pymerkle 6.0.0, RFC 6962 mode (installed) | Sigstore 4.6.0 merkle arithmetic (vendored, see `tools/third_party/NOTICE.md`) |
| input | leaf **texts** | declared leaf **digest** + audit **path** |
| output | tree root built from scratch | root folded along the path |
| question | does a foreign tree builder agree with our true roots and our VALID/INVALID split? | does a foreign path folder reproduce our `reconstructed_root`, and does it hit `root_true` exactly when the case says VALID? |

Between the two, both halves of the arithmetic — building a tree and folding a path — are met by code this project did not write.

## Result — pymerkle, roots (2026-11-23)

| quantity | value |
|---|---|
| inclusion cases in the package | 50 |
| compared by the third-party library | 49 |
| library root == `root_true` | 49 / 49 |
| library root == `reconstructed_root` exactly when VALID, differs when INVALID | 49 / 49 |
| mutated-leaf self-test (one flipped leaf per case, must be detected) | 49 / 49 |
| cases the library cannot read | 1 (`fail-empty-tree`) |
| consistency cases (both endpoints' roots) | 13 |
| endpoint roots the library builds | 26 |
| endpoint roots equal to the declared root | 24 |
| endpoint roots differing by design (declared root is the tampered one) | 2 (`cons-fail-new-root`, `cons-fail-old-root`) |
| mutated-leaf self-test on consistency endpoints | detected (26 mismatches) |

The one unreadable case is `tree_size=0`. pymerkle defines no root for an empty tree at all, so `MTH({}) = SHA-256("") = e3b0c442…` is **not corroborated by this library**. The constant is still scored in the package and still checked by the standalone and Node checks; it is recorded here as uncorroborated by a third party rather than counted as agreement.

## Result — Sigstore, audit paths (2026-11-24)

| quantity | value |
|---|---|
| inclusion cases in the package | 50 |
| paths folded by the third-party code | 42 |
| folded root == `reconstructed_root` | 42 / 42 |
| folded root == `root_true` exactly when VALID, differs when INVALID | 42 / 42 |
| mutated-path self-test (one flipped nibble per path, must be detected) | 40 / 40 |
| paths the library refuses | 7 |
| cases with no path at all (`tree_size=0`) | 1 (`fail-empty-tree`) |

The seven refusals are the malformed paths, and they are refusals for a checkable reason rather than a shrug: Sigstore's `_decomp_inclusion_proof(index, size)` fixes how many siblings a path of that shape must carry, so `fail-empty-path`, `fail-path-short`, `fail-path-short-tampered`, `fail-path-short-tree3`, `fail-path-short-tree32`, `fail-path-too-long` and `fail-wrong-tree-size` fail a length test before any hashing happens. Each of those seven is an INVALID case in this package, so "the library will not even fold it" is the verdict the package asserts; the test suite pins that correspondence instead of counting the seven as agreement.

This is the half pymerkle could not reach: `INVALID_INCLUSION_PATH` verdicts are now re-derived by code that reads the path.

## What this does not cover, and what it must not be called

- **Not an independent external run.** `docs/EXTERNAL-RUNS.json` stays unchanged; a library is not a person, and neither row appears in it.
- **Consistency proofs not covered as proofs.** Sigstore's vendored file contains no consistency checker at all, and pymerkle is never handed a SUBPROOF. The 13 consistency cases are corroborated at the endpoint-root level only (24/26 agree, the 2 that differ are the deliberately tampered declared roots). The SUBPROOF order this package scores stays corroborated by our verifier and the standalone checker only.
- **Leaf text is not hashed by the Sigstore path.** The path check seeds from the case's declared `digest_hex`, which is the pymerkle check's job (and `digest_hex == SHA-256(0x00‖leaf_input)` is pinned separately). Each check covers one link of the chain, and neither alone covers the whole chain.
- **Nothing about deployment.** No COSE_Sign1 statement, no receipt, no signature, no TSA timestamp. A pass above says the hash-tree arithmetic and path folding are met by foreign code; it says nothing about a deployment end to end.

## How to reproduce

```
python -m pip install "pymerkle==6.0.0"
python tools/crosscheck_scitt_pymerkle.py --out tools/out/crosscheck_pymerkle.json --self-test

python tools/crosscheck_scitt_sigstore.py --out tools/out/crosscheck_sigstore.json --self-test
```

The Sigstore check needs no install: the arithmetic is vendored with its upstream digest in `tools/third_party/NOTICE.md`, so it runs on a machine with nothing but Python and is not skipped when the network is down. `--self-test` flips one leaf (pymerkle) or one nibble of the first path node (Sigstore) in every case and demands the comparison notice, so a checker that agreed with everything could not pass. Without pymerkle installed the pymerkle tool exits 2 with the install line and the CI job installs a pinned version; in the test suite that check skips rather than passing silently.
