<!-- SPDX-License-Identifier: Apache-2.0 -->
# scitt-rfc9162 test vectors (v1)

A self-contained, append-only set of **RFC 9162 SHA-256 hash-tree** vectors:
**inclusion paths and consistency proofs**, **63 vectors in seven classes** — 35
`VALID` (29 inclusion, 6 consistency), 12 `INVALID_INCLUSION_PATH`, 7
`INVALID_CONSISTENCY_PROOF`, 2 `INVALID_LEAF_INDEX`, 1 `INVALID_LEAF_DIGEST`, 2
`INVALID_TREE_SIZE`, and 4 `VALID_BUT_SIZE_UNAUTHENTICATED` (the ambiguity
class, described below). Class counts are computed from the vectors themselves
(`manifest.json` → `class_counts`), not typed in by hand.

Each vector declares `kind` (`inclusion` or `consistency`) in its
`expected.json`; a reader who only implements inclusion can skip the
consistency half and still score 50 of the 63.

Tree shapes covered: 1, 2, 3, 4, 5, 6, 7, 8, 9, 15, 16, 17, 31, 32, 33, 63, 64,
65 leaves; indices include left edge, right edge, interior, and the single tail
leaf of a `2^n | 1` split. Every shape was chosen to exercise a different fold
branch, not to reach a round number. Consistency sizes covered: 1→2, 2→5, 3→7,
4→8, 6→9, 9→9, plus six tampered proofs and one impossible size relation.

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

A consistency vector (`kind: consistency`) replaces those fields with:

| Field | Meaning |
|---|---|
| `old_size`, `new_size` | the two tree sizes, as a verifier would receive them |
| `old_root`, `new_root` | the roots of the honest prefix tree and the honest larger tree |
| `consistency_path` | the RFC 6962 §2.1.2 proof, hex, **in the order the recursion appends nodes** |
| `reconstructed_old_root`, `reconstructed_new_root` | the two roots rebuilt from `old_root` + path |
| `result` | `VALID`, or `INVALID_CONSISTENCY_PROOF` |

### Consistency proofs: the array order is scored, not decorative

The proof array is in **recursion order**: nodes produced by the descent first,
the sibling the same level appended last. That is not a convention this package
invented for convenience — it is the order the text's `SUBPROOF` produces, and
it is measurable. Reading the same array **in reverse** scores 18 of the 23
known-good external consistency cases used to calibrate this checker; the
forward order scores 23 of 23. A reader who reverses the array will therefore
get five wrong verdicts on this set too, which is exactly the kind of
disagreement these vectors are meant to surface.

The verifier behind this half was itself written from the recursion text and
**calibrated against those 23 external cases before it judged anything of
ours**. Its first form was an iterative loop that seeded both roots from
`old_root` even when `old_size` is not a power of two: 20 of 23. The two
iterative variants tried afterwards scored 20 of 23 as well. Only the recursive
form scored 23 of 23. That record is here rather than in a commit message
because a corpus author who cannot show their checker was wrong at some point
has not shown their checker can be wrong.

One input is **genuinely** not scored: a consistency proof with `old_size = 0`.
RFC 6962 §2.1.2 defines `SUBPROOF` for `1 <= m <= n`, says nothing about
`m = 0`, and conforming implementations differ (the Go CT libraries accept it
as trivially true; this package would refuse it). It is listed in
`manifest.json` → `underspecified_inputs` with that reason. This is the opposite
case from `tree_size = 0` above: there the text *did* decide and an earlier
draft wrongly called it unspecified. The distinction is the point — "the text
does not say" is a claim that has to be checked against the text, both when it
is used to score and when it is used to excuse.

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
sha256sum -c SHA256SUMS                                  # 64/64 OK (`shasum -a 256 -c` on macOS)
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

## Second implementation, same author

```bash
node tools/check_scitt_vectors_node.mjs --self-test
```

The tree algebra in that file is written again in JavaScript, sharing no code
with `uibc_core`, the builder or the Python standalone checker. It walks the
same 63 vectors and must reach `VERDICT: PARITY`.

**What this is not.** It is not an independent run. The same author wrote it, so
the external run ledger does not count it, and neither should a reader: a
second implementation by the same hand proves the *vectors* are written down
concretely enough to be met twice, not that a stranger can meet them. For that,
the invitation in `docs/INVITE-ONE-PAGE.md` is the only route.

**What it does add.** `--self-test` feeds both checkers the same seven
deliberately broken vectors — the empty-tree constant used as the digest of an
empty leaf input, the empty-tree root replaced by an all-zero
digest, a size-0 fold result filled in, a size-0 vector marked `VALID`, a leaf
digest detached from its leaf input, and three consistency mutations (zeroed
old root, one proof node too many, the two sizes swapped) — and exits 1 unless
every one is caught. A checker that cannot fail its own mutations is
decoration, and this is the cheapest way to show the empty-tree rule, the
leaf-input binding and the consistency length rule are enforced rather than
described.

## The shapes that are *not* in this corpus, and why that is answerable

Fifty-five vectors cannot prove that the algebra works at size 10,000, and a
reader should not have to take that on trust. So the repository ships a sweep
that walks **every** shape up to a bound rather than every shape someone chose:

```bash
python tools/verify_tree_algebra_exhaustive.py --max-size 64 --self-test
python tools/verify_tree_algebra_exhaustive.py --max-size 64 --dump /tmp/inst.json
node tools/verify_tree_algebra_exhaustive.mjs /tmp/inst.json
```

| Bound | inclusion instances | consistency instances | disagreements |
|---|---|---|---|
| 128 (CI and locally) | 8,256 (sizes 1..128, every index) | 8,256 (every 1 ≤ m ≤ n ≤ 128) | **0** |

Two readings are compared: generation from `uibc_core`, verification from
`tools/check_scitt_vectors_standalone.py`, which imports nothing from it. The
Node sweep re-derives the roots again from the recorded bytes, so the second
language confirms the path or proof is self-sufficient rather than agreeing with
the program that produced it.

`--self-test` zeroes one path node and one proof node and requires both to be
caught: a sweep that cannot fail its own mutation is a loop, not a check.

**What this does not prove.** It proves our two readings agree on everything up
to 128 leaves. It does not prove either reading matches RFC 6962 — for that the
23 external consistency cases and the 147 external arithmetic cases are the only
evidence there is, and they are cited as external, not as ours.

## Every negative has a positive twin at the same shape

An audit on 2026-11-22 found eight `fail-*` vectors whose shape had no passing
vector: `16,9`, `4,1`, `3,1`, `8,5`, `5,0`, `7,6` (with two shapes shared). That
matters because a verifier that refuses *everything* at a given shape passes
those negatives and fails nothing — the corpus would be silent about the case it
was built to test.

Six positives were added, and the builder now enforces the rule as an invariant
in `--check`: every negative whose shape admits an honest tree must have a
positive at that shape. Two exemptions, both written down:

* a `size-zero` vector is a lie about a tree with no leaves, so no honest twin
  exists;
* a consistency vector with `old_size > new_size` has no extending tree at all.

The invariant is itself tested by dropping one positive at runtime and requiring
`--check` to fail (`test_a_negative_without_a_positive_twin_is_a_finding`). A rule
that cannot fail its own violation is a sentence, not a rule.

## Two "hash of nothing" constants, and why both are in here

The algebra has two values that are easy to conflate because both are *the hash
of nothing*:

```
MTH({})         = SHA-256()      = e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
leaf_hash(b"")  = SHA-256(0x00)   = 6e340b9cffb37a989ca544e6bb780a2c78901d3fb33738768511a30617afa01d
```

A tree of size 1 whose only leaf input is the empty byte string has the **second**
as its root. A tree of size 0 has the **first**. An implementation that keeps one
constant for both passes every vector in this corpus whose leaves are non-empty,
and fails only on these two:

| Vector | What it pins |
|---|---|
| `v1/valid-empty-leaf` | size 1, empty leaf input: `root_true` is `SHA-256(0x00)`, not `MTH({})` |
| `v1/valid-empty-tree2` | size 2, inputs `b""` and `b"\x00"`: the prefix applies to the empty input, and a single zero byte is a different leaf from no bytes at all |

Both checkers' `--self-test` feed exactly this mutation: the empty-tree constant
substituted for the digest of an empty leaf input. It is caught by the leaf-input
binding rule, which is the same rule that catches a leaf digest detached from its
input — but the conflation is a plausible bug rather than a deliberate tamper,
which is why it is written down separately.

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
  The consistency half stops at the algebra for the same reason: a consistency
  proof is checked here, a *signed* tree head that says which sizes to check is
  not shipped.
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
