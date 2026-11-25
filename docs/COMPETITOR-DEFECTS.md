# A competitor's negative vectors, judged without their code (2026-11-25)

Context: this repository exists to make conformance evidence that a stranger can
recompute. The competitor `probityai/agent-evidence-vectors` publishes far more
vectors (65 suites / 3,069 vectors at v0.37.1; unchanged in kind at v0.38.0), and it
is worth asking whether their negatives test what they say they test. One class does
not.

## The finding

Three of their vectors declare an empty tree and carry a Merkle root that is not the
RFC 6962 empty-tree root (`e3b0c442…b855`):

| vector | declares | carries | published verdict |
|---|---|---|---|
| `INC-N-size-zero` | `tree_size: 0`, `index: 0` | root `5488b5f1…` | reject / `not-included` |
| `CON-N-old-size-zero` | `old_size: 0` | old_root `b3d9166b…` | reject / `not-consistent` |
| `TOK-N-tree-size-zero` | `poc_claims.tree_size: 0` | merkle_root `5604d10f…` | reject / `schema` |

A 0-leaf tree has exactly one possible root. These three carry three different ones,
none of them the right one, so the published `reject` is produced by the input
contradicting itself - not by the proof arithmetic. The consequence is practical, not
pedantic: **none of these three vectors can distinguish a verifier that handles empty
trees correctly from one that refuses them by accident.** A test whose only possible
outcome is "refuse" tests nothing about the code path it names.

## How it is checked

`tools/check_competitor_vectors.py` reads the vendored upstream bytes and reports
which code the data forces, independently of the `expect` block:

```
python tools/check_competitor_vectors.py \
    --dir docs/upstream-package/competitor-defects/v0.38.0 \
    --dir docs/upstream-package/competitor-defects/v0.38.0-counter
```

It trusts one constant, the one the RFC pins down, and one rule set: `index < tree_size`,
`old_size <= new_size`, equal sizes need an empty proof, `tree_size` must be an integer.
Verdict today: **upstream 0/3 agree** with their own published code; **counter-vectors
3/3 agree**. `tests/test_competitor_defects.py` pins both numbers, so neither can drift.

## What this does not claim

- Not that their implementation is wrong. Their verifier is not run and not read.
- Not that they intended anything. Only the bytes and the constant are compared.
- Not that we have more vectors. They have 3,069; we have 63. The claim here is about
  the *shape* of one negative class, not about volume, and volume is not a proxy for
  correctness in either direction.

## Where the bytes come from

`docs/upstream-package/competitor-defects/v0.38.0/` - byte-for-byte copies at upstream
commit `22764551` (release `v0.38.0`, corpus path
`vectors-poc-evidence/package/poc_evidence_vectors/corpus/`), sha256 and size per file
in `SHA256SUMS.json` beside them. The `v0.38.0-counter/` twins are ours and marked as
ours in each file's `source` field.

If upstream fixes these, re-fetch and re-judge: the tool is the oracle, not this page.
