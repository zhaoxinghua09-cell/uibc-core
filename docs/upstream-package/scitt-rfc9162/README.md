<!-- SPDX-License-Identifier: Apache-2.0 -->
# scitt-rfc9162 test vectors (v1)

A self-contained, append-only set of **RFC 9162 SHA-256 hash-tree and
inclusion-path** vectors: **42 vectors in six classes** — 21 `VALID`, 12
`INVALID_INCLUSION_PATH`, 2 `INVALID_LEAF_INDEX`, 1 `INVALID_LEAF_DIGEST`, 2
`INVALID_TREE_SIZE`, and 4 `VALID_BUT_SIZE_UNAUTHENTICATED` (the ambiguity
class, described below). Class counts are computed from the vectors themselves
(`manifest.json` → `class_counts`), not typed in by hand.

Tree shapes covered: 1, 2, 3, 4, 5, 6, 7, 8, 9, 15, 16, 17, 31, 32, 33, 63, 64,
65 leaves; indices include left edge, right edge, interior, and the single tail
leaf of a `2^n | 1` split. Every shape was chosen to exercise a different fold
branch, not to reach a round number.

The seven path-structure vectors (`fail-path-short*`, `fail-path-swap*`) isolate
two properties that a verifier can check separately and get wrong separately:
**length** (a dropped sibling leaves the fold one level below the root) and
**order** (two siblings exchanged keep byte count and length identical, so only a
verifier that actually folds catches it).

> **A mismatch against your implementation is exactly the report these authors
> want.** Agreement on *rejection* is as load-bearing as agreement on
> acceptance. If any `fail-*` or `ambiguous-*` vector verifies in your verifier
> under the reading you believe is correct, that is a finding about one of us —
> please open an issue rather than staying silent.

## Layout

```
v1/<vector-id>/expected.json
manifest.json        index, with each expected block inlined
SHA256SUMS           every vector file and the manifest, byte-for-byte
.gitattributes       pins vectors as non-normalized
```

This shape follows the vector set the IETF SCITT WG `examples` repository
already merged (`test-vectors/scitt-cose`), so that a reviewer there sees a
familiar layout.

## What each vector gives you

Every `expected.json` carries everything needed to recompute the verdict
without any code from this project:

| Field | Meaning |
|---|---|
| `leaf_entry.leaf_input_hex` | the exact leaf input bytes, hex |
| `leaf_entry.digest_hex` | `SHA-256(leaf_input)` — check this first |
| `leaf_index`, `tree_size` | position and size as a verifier would receive them |
| `inclusion_path` | sibling digests, hex, in RFC 9162 order |
| `root_true` | the root of the honest tree |
| `reconstructed_root` | the root obtained by folding the given path |
| `result` | `VALID` for the positives; the named failure otherwise |

The two roots are the whole test: **for `VALID*` vectors they must be equal;
for the `fail-*` vectors they must differ.** For the negative vectors
`reconstructed_root` is computed from the tampered material, not asserted
by hand.

### What this set used to refuse to score, and now does

`manifest.json` carries a `retired_underspecified_inputs` list: inputs that
were once declared unscoreable here, with the reason they were retired.

**The one entry was wrong, and 2026-11-21 corrected it.**

| Input | Former handling | What the text actually says | Where it is now |
|---|---|---|---|
| `tree_size=0` with a `leaf_index` asserted | declared `underspecified`, deliberately not scored, on the reading that "two conforming readings disagree" about whether a fold is defined | **one reading exists.** RFC 9162 §2.1 fixes `MTH({})` = `SHA-256()` (`e3b0c442…`), and §2.1.1 defines `PATH(m, D[n])` only for `0 <= m < n`, so no leaf can sit in a tree of size 0 and the only correct verdict is a refusal | **scored**: `v1/fail-empty-tree`, `result = INVALID_TREE_SIZE`, `root_true = MTH({})` |

An earlier draft had carried that input as `fail-tree-size-zero`; it was
deleted on 2026-11-20 when the standalone checker disagreed with the builder.
The disagreement was real, but the conclusion drawn from it was not: a checker
that treats `size = 0` as an ordinary fold and a builder that refuses it are
not "two conforming readings", because the text fixes the constant and fixes
the domain of `PATH`. Deleting the vector left the empty-tree root unscored —
the one constant a corpus must pin if a second implementation is ever to agree
with it. It is now pinned by a vector.

The lesson is written down rather than hidden: **"the text does not decide
this" is a claim about the text, and it has to be read in the text before it
is used to delete a test.** A corpus that leaves a constant undefined cannot
be met by an independent implementer, and that is the failure this vector
exists to prevent.

### Why the size asymmetry is written down

Declaring a `tree_size` **one larger** than the path assumes never changes the
reconstructed root in this algebra: the fold reads no additional node. So that
input cannot be an `INVALID_TREE_SIZE` vector — the root still matches — and it
is carried as `ambiguous-*` instead. `INVALID_TREE_SIZE` therefore covers only
"declared smaller" (path one short) and "declared zero" (no fold defined).
This was found by running a draft vector, not assumed: the draft's own
verifier reported it root-equal.

### The ambiguity vectors, stated plainly

Four vectors (`ambiguous-tree-size`, `-2`, `-4`, `-8`) sit in the
`VALID_BUT_SIZE_UNAUTHENTICATED` class. Each records an `alt_tree_size` at
which **the same inclusion path folds to the same root**. For example
`v1/ambiguous-tree-size` is `tree_size=7, leaf_index=5`; folding at
`tree_size=8` consumes the same three siblings and yields the same root, so a
verifier that trusts the declared size accepts both. This is a property of the
algorithm as written, reported on the SCITT list on 2026-11-15 and raised as an
erratum to RFC 9942 Section 5.2.1; it is not a defect in these vectors. Every
listed instance was found by exhaustive search over sizes 1..19 and indices,
not by hand — three of the first four candidates a human would guess turn out
*not* to exhibit it.

A relying party that needs the log size must take it from signed data (a signed
tree head, or an anchor whose signed payload carries both root and size).
**This set does not claim that any particular deployment binds it.**

## One-command verify

```bash
cd docs/upstream-package/scitt-rfc9162
sha256sum -c SHA256SUMS                                  # 31/31 OK (`shasum -a 256 -c` on macOS)
python tools/build_scitt_vector_package.py --check       # from the repo root
python tools/build_scitt_vector_package.py --check-drift # committed bytes == what build produces
```

The second command recomputes every vector from its declared inputs and
compares against the recorded values; it exits 1 on any disagreement. The third
is the stronger one: it rebuilds the package into a temp directory and demands
byte-identity with what is committed, in both directions. It exists because
`--check` reads only the manifest and therefore cannot notice that the builder
and the committed package have drifted apart — on 2026-11-20 that had already
happened (the builder knew 5 vectors, the manifest listed 6), and a plain
`build` run would have silently dropped one from the manifest.

## Tree construction (write it down, don't import it)

```
leaf[i]  = SHA-256(leaf_input_i)
node     = SHA-256(left || right)
split    = largest power of two below the subtree size   (RFC 9162)
leaf_input_i = "scitt-rfc9162 test vectors v1 :: <vector-id> :: leaf <i>"
```

Reconstruction rule: fold the path over `leaf_index` with `tree_size` using
the RFC 9162 verification loop; the fold result must equal `root_true` for
`VALID` vectors and must differ otherwise.

## What this set does not cover

Stated plainly, because it is the first thing a reviewer will ask:

- **No COSE_Sign1 statement or receipt bytes.** This project has no COSE
  library installed and will not ship signed bytes it cannot verify itself.
  The v1 set here therefore stops at the hash-tree algebra.
- **No transparency-log receipts, no witness cosignatures, no TSA timestamps.**
- **No negative vectors for signature failure** — there are no signatures to
  fail here. The IETF SCITT `examples` set `scitt-cose` already covers that
  layer with signed material; anyone needing it should use that set.

This set is deliberately narrower than `scitt-cose`, and it is
**not a replacement** for it.

## Provenance

Generated by `tools/build_scitt_vector_package.py` in
`github.com/zhaoxinghua09-cell/uibc-core`, from that repository's own
`uibc_core.merkle` implementation (Apache-2.0). Every byte here is
reproducible by running that script; nothing is vendored from elsewhere.
