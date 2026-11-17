# Conformance corpus

`docs/conformance/vectors.json` is a small, language-neutral corpus: each vector
embeds its own input and the exact expected output, so an implementation written
somewhere else can be measured against our format without importing our code.

## What it covers

| kind | vectors | what a conforming implementation must do |
|---|---|---|
| `canonical_json` | 10 | canonicalize the embedded object and match **both** the exact UTF-8 bytes and the SHA-256 |
| `ed25519_signature` (valid) | 3 | verify the signature with any Ed25519 library; verdict `valid` |
| `ed25519_signature` (invalid) | 2 | reject a signature made over another message, and one with a single flipped byte |

The signature vectors publish the throwaway 32-byte seed (`00…01`) used to produce
them, so the values are reproducible rather than asserted. The seed is worthless
outside the corpus and must not be used for anything else.

## What it does **not** cover, and the difference matters

* **No second implementation.** We ship the object a second implementation can be
  measured against; we do not ship that implementation. Tracekit and agent-receipts
  publish both. Saying "we match Tracekit here" would be false.
* **No receipt structure, chain, anchoring or policy vectors.** Those steps have
  tests, not vectors. A reader who needs those should read `docs/INTEROP-MATRIX.md`,
  where the untested cells are labelled as untested.
* **Passing it does not make an implementation interoperable with our receipts.**
  It makes the two primitive steps — canonical bytes and signature — comparable.

## Why the checker is not our verifier

`tools/conformance_check.py` implements its own canonicalizer with `json` and
`hashlib` only, and verifies signatures with the third-party `cryptography`
package, never with our in-repo Ed25519. If the corpus only passed when checked
by our own code, it would prove nothing.

Current result on this machine:

```
15/15 vectors reproduced by a non-uibc implementation
```

## Reproduce

```bash
python tools/conformance_vectors.py --check   # on-disk corpus == fresh build
python tools/conformance_check.py             # a foreign checker reproduces all 15
python -m unittest tests.test_v15_conformance_corpus -v
```

`tests/test_v15_conformance_corpus.py` runs both, so a drifting canonicalizer
breaks CI rather than the published corpus.
