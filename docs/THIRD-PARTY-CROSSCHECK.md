# Third-party cross-check: three foreign implementations against the SCITT RFC 9162 package

Status: **all 63 cases and both proof kinds are answered by an implementation from another project: transparency-dev/merkle (Google CT lineage) agrees on 63/63 verdicts, including all 13 consistency SUBPROOF orders. pymerkle rebuilds roots 49/49 and Sigstore's folding code re-derives every audit path it can read 42/42. None of the three is an external run.** Last run 2026-11-24 on company machine.

## Why this exists

Every number in `docs/upstream-package/scitt-rfc9162/` was produced by this repository's own verifier, and every verdict was produced by the same code. That is internal consistency, not corroboration: the code that made the number also certifies it. The one thing a reader outside this project can check cheaply is whether *somebody else's* RFC 6962 implementation reaches the same numbers.

Three independent checks do that, and they are deliberately different in what they are fed:

| | `crosscheck_scitt_pymerkle.py` | `crosscheck_scitt_sigstore.py` | `third_party/go-merklecheck` |
|---|---|---|---|
| third party | pymerkle 6.0.0, RFC 6962 mode (installed) | Sigstore 4.6.0 merkle arithmetic (vendored, see `tools/third_party/NOTICE.md`) | `transparency-dev/merkle` v0.0.2, Google CT lineage (fetched, `go.sum`-pinned) |
| input | leaf **texts** | declared leaf **digest** + audit **path** | the case's **own numbers**: digest/path/roots |
| output | tree root built from scratch | root folded along the path | **verdict**, via `proof.VerifyInclusion` / `proof.VerifyConsistency` |
| question | does a foreign tree builder agree with our true roots and our VALID/INVALID split? | does a foreign path folder reproduce our `reconstructed_root`, and hit `root_true` exactly when VALID? | do the case's numbers verify exactly when the case claims VALID, for **both** proof kinds? |

Between the three, building a tree, folding an inclusion path, and checking a consistency SUBPROOF are each answered by code this project did not write.


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

## Result — transparency-dev/merkle (Go), both proof kinds (2026-11-24)

| quantity | value |
|---|---|
| cases in the package | 63 |
| cases the Go verifier read | 63 |
| verdict agreement (verifies exactly when the case claims VALID) | 63 / 63 |
| inclusion cases | 50 / 50 |
| consistency cases (SUBPROOF order) | 13 / 13 |
| mutated-path self-test (one flipped nibble per non-empty VALID path) | 36 / 36 |
| VALID cases with no path to mutate (`tree_size=1`, equal sizes) | 3 |

This is the first foreign answer for the part the other two could not touch: **the SUBPROOF order this package scores**. pymerkle never reads a path, and Sigstore's file has no consistency checker at all, so until this program the consistency proof order rested on our verifier and the standalone checker alone.

The program feeds the module nothing but the case's own numbers — declared leaf digest, index, sizes, path arrays, declared roots — and asks its verifier for a yes or a no. It does not rebuild trees, so it cannot share a bug with our generator; and it is Go, so it cannot share a bug with the Python that produced the files.

Three VALID cases carry an empty path (`valid-tree1-index0`, `valid-empty-leaf`, `cons-9-9`), so the mutation self-test has nothing to flip there; they are excluded from the 36 and named here rather than quietly dropped.

## What this does not cover, and what it must not be called

- **Not an independent external run.** `docs/EXTERNAL-RUNS.json` stays unchanged; three libraries are not a person, and none of them appears in it.
- **Consistency proofs covered as order, not as full composition.** The Go verifier reads the SUBPROOF array it is given and checks both roots; it does not recompute the leaves, so it cannot notice if a case's leaf texts were wrong in a way that kept the roots self-consistent. That link is pymerkle's (24/26 endpoint roots, the 2 others deliberately tampered) and the `digest_hex == SHA-256(0x00‖leaf_input)` pin.
- **Leaf text is not hashed by the Sigstore or Go checks.** The Sigstore path seeds from the declared digest; the Go program uses it as given. Each check covers one link of the chain; only their combination covers the chain.
- **Nothing about deployment.** No COSE_Sign1 statement, no receipt, no signature, no TSA timestamp. A pass above says the hash-tree arithmetic, path folding and consistency order are met by foreign code; it says nothing about a deployment end to end.

## How to reproduce

```
python -m pip install "pymerkle==6.0.0"
python tools/crosscheck_scitt_pymerkle.py --out tools/out/crosscheck_pymerkle.json --self-test

python tools/crosscheck_scitt_sigstore.py --out tools/out/crosscheck_sigstore.json --self-test

cd tools/third_party/go-merklecheck && go build -o /tmp/merklecheck . && cd -
/tmp/merklecheck --dir docs/upstream-package/scitt-rfc9162/v1 \
  --out tools/out/crosscheck_go.json --self-test
```

The Sigstore check needs no install: the arithmetic is vendored with its upstream digest in `tools/third_party/NOTICE.md`, so it runs on a machine with nothing but Python and is not skipped when the network is down. The Go check needs a Go toolchain and network for the first fetch; `go.sum` pins the module bytes, and the test builds with `-mod=readonly` so a hash mismatch fails instead of being rewritten. `--self-test` flips one leaf (pymerkle) or one nibble of the first path node (Sigstore, Go) in every case and demands the comparison notice, so a checker that agreed with everything could not pass. Without pymerkle installed the pymerkle tool exits 2 with the install line and the CI job installs a pinned version; in the test suite that check skips rather than passing silently, and so does the Go test when no toolchain is on the runner's PATH.
