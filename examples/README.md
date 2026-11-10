# Worked example: a sample package you can verify right now

`sample-package/` is a complete, real uibc-core submission package for a
fictional support agent — identity, lifecycle, two evidence files, and an
Ed25519 seal. It is the fastest way to see what verification means here:
you need nothing from us to check it.

## Verify it as a stranger (no key, no permission)

From the repository root:

```
python -m uibc_core.cli verify examples/sample-package
```

Expected: result **PASS**, assurance **public-key**. The seal's public
key travels inside the package (`signatures/seal.json`), so your check
involves no secret and no one's cooperation.

## Verify it pinned to the sample owner

```
python -m uibc_core.cli verify examples/sample-package --pubkey examples/sample-owner.pub
```

Expected: **PASS**. Pinning binds the package to a *known* signer
instead of "whoever sealed this". Now copy the package, change one byte
in an evidence file, and re-run either command: **FAIL** at S4.

The stronger exercise — rewrite the evidence, recompute the hashes and
the root, re-seal with your own key — is scripted end-to-end by
`python -m uibc_core.cli demo` (steps 7–8 show both the unpinned result
and the pinned catch). The semantics behind every outcome are specified
in `docs/verdict-and-seal-semantics.md`.

## About the sample key

The sample owner's seed is `00 01 02 … 1f`, published in
`build_example.py` on purpose: the sample must be rebuildable by anyone,
byte for byte. It attests nothing about the real world and must never be
used for a real package. `uibc keygen --ed25519` generates a real one.
(The seed file itself is not committed; `build_example.py` regenerates
it alongside the package.)

Rebuild the sample with `python examples/build_example.py`.
