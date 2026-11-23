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

What it does not give us: Sigstore's file contains no consistency-proof checker, so consistency SUBPROOF order stays corroborated by our verifier and the standalone checker only. This is restated in `docs/THIRD-PARTY-CROSSCHECK.md` rather than glossed over.
