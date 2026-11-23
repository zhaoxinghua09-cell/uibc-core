# Vendored third-party code

## `sigstore_merkle.py`

| | |
|---|---|
| upstream package | `sigstore` 4.6.0 (PyPI wheel `sigstore-4.6.0-py3-none-any.whl`, sha256 `df10bc2b87b821df0922405377305b875894e6ce6007175b3eddb3bcc9b23cfa`) |
| upstream file | `sigstore/_internal/merkle.py`, sha256 `b1615230cdfef424def912ab290332a2d1662320855fc2e47b4f6a6052b9943c`, 4,310 bytes |
| license | Apache License 2.0 (header retained in the file) |
| purpose | a second, independently written folding of RFC 6962 audit paths, used only by `tools/crosscheck_scitt_sigstore.py` and its test |
| change from upstream | exactly one: `from sigstore.errors import VerificationError` is replaced by a local `class VerificationError(Exception)`, so the vendored file has no install dependency. The arithmetic (`_decomp_inclusion_proof`, `_chain_inner`, `_chain_border_right`, `_hash_children`, `_hash_leaf`) is byte-for-byte upstream. |

Why a copy instead of a dependency: the cross-check exists to be a *second* implementation, and a step that only runs when a wheel is installable is a step that quietly disappears on an offline machine. The copy is pinned above by digest so a reader can diff it against upstream without trusting us.

What it does not give us: Sigstore's file contains no consistency-proof checker, so consistency SUBPROOF order is not covered by this one. It is covered by the Go check below, and `docs/THIRD-PARTY-CROSSCHECK.md` says which program covers what.

## `go-merklecheck/`

| | |
|---|---|
| upstream module | `github.com/transparency-dev/merkle` v0.0.2 (Google certificate-transparency lineage), Apache-2.0 |
| pinned by | `go.mod` (`require ... v0.0.2`) + `go.sum` (module and its `go-cmp` test dependency) |
| our code | `main.go` — a verifier that reads the case files and asks the module's `proof.VerifyInclusion` / `proof.VerifyConsistency` whether the case's own numbers hold. Nothing is vendored: the module is fetched and checksum-verified by the Go toolchain. |
| why it exists | it is the only one of the three third parties that carries an RFC 6962 **consistency** verifier, so it is what corroborates the SUBPROOF order this package scores |

Run it from the repository root:

```
cd tools/third_party/go-merklecheck && go build -o /tmp/merklecheck . && cd -
/tmp/merklecheck --dir docs/upstream-package/scitt-rfc9162/v1 --out tools/out/crosscheck_go.json --self-test
```

`go.sum` is why this can be trusted without trusting us: the toolchain refuses a module whose bytes do not match the recorded hashes.

