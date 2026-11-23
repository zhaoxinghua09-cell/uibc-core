# Third-party cross-check: pymerkle against the SCITT RFC 9162 package

Status: **hash-tree arithmetic only, 49/49 inclusion cases agree, 1 case the library cannot read.** Not an external run. Last run 2026-11-23 on company machine, pymerkle 6.0.0.

## Why this exists

Every number in `docs/upstream-package/scitt-rfc9162/` was produced by this repository's own verifier, and every verdict was produced by the same code. That is internal consistency, not corroboration: the code that made the number also certifies it. The one thing a reader outside this project can check cheaply is whether *somebody else's* RFC 6962 implementation builds the same trees.

`tools/crosscheck_scitt_pymerkle.py` does exactly that and nothing more. It hands pymerkle, in its `rfc6962` mode, the leaf texts each case says its tree holds, and asks two questions:

1. is the root pymerkle builds equal to the case's `root_true`?
2. is that root equal to the case's `reconstructed_root` when the case claims VALID, and unequal when it claims INVALID?

## Result (2026-11-23)

| quantity | value |
|---|---|
| inclusion cases in the package | 50 |
| compared by the third-party library | 49 |
| library root == `root_true` | 49 / 49 |
| library root == `reconstructed_root` exactly when VALID, differs when INVALID | 49 / 49 |
| mutated-leaf self-test (one flipped leaf per case, must be detected) | 49 / 49 |
| cases the library cannot read | 1 (`fail-empty-tree`) |

The one unreadable case is `tree_size=0`. pymerkle defines no root for an empty tree at all, so `MTH({}) = SHA-256("") = e3b0c442…` is **not corroborated by this library**. The constant is still scored in the package and still checked by the standalone and Node checks; it is recorded here as uncorroborated by a third party rather than counted as agreement.

## What this does not cover, and what it must not be called

- **Not an independent external run.** `docs/EXTERNAL-RUNS.json` stays unchanged; a library is not a person, and this row does not appear in it.
- **No proof paths.** pymerkle is handed leaf text and asked for roots. The package's proof-path folding, and the INVALID_INCLUSION_PATH verdicts specifically, are not re-derived by the library.
- **Consistency proofs not covered.** The 23 consistency-side checks in this package are scored by our verifier only; pymerkle's consistency API needs a tree it built itself, and a structural comparison of proof shapes was out of scope here.
- **Nothing about deployment.** No COSE_Sign1 statement, no receipt, no signature, no TSA timestamp. A pass above says the hash-tree arithmetic is met by a second implementation; it says nothing about a deployment end to end.

## How to reproduce

```
python -m pip install "pymerkle==6.0.0"
python tools/crosscheck_scitt_pymerkle.py --out tools/out/crosscheck_pymerkle.json --self-test
```

`--self-test` flips one leaf in every case and demands the comparison notice, so a checker that agreed with everything could not pass. Without pymerkle installed the tool exits 2 with the install line and the CI job installs a pinned version; in the test suite the check skips rather than passing silently.
