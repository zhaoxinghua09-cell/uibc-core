# The publisher check, done twice

`anchor_check.py` answers one question: **is this the package that publisher
signed, in that state?** It answers with Python, using `uibc_core.verify`.

`tools/verify-js/anchor.mjs` answers the same question with node:crypto and
`verify.mjs`. Different language, different crypto library, no shared code, no
call from one to the other.

```
$ node tools/verify-js/anchor.mjs bundle/
VERDICT: ANCHORED
seal     : verifies under the pinned key
head     : package checkpoint equals the pinned head
implementation: verify-js (independent of uibc-core)
```

Why this matters more than another check: a single implementation agreeing with
itself is a tautology. **Agreement between two is the only reason to believe
either** — and disagreement is a bug that has to be fixed before anyone trusts
the verdict.

## What each one actually does

| | Python (`anchor_check.py`) | Node (`anchor.mjs`) |
|---|---|---|
| seal signature | `uibc_core.verify` with the anchor's key | `node:crypto` Ed25519, anchor's key |
| key identity | package seal must verify under the pinned key | `seal.public_key` must **equal** `anchor.pubkey_b64` |
| pinned head | `verify(..., expect_head=...)` → S9 | `verify.mjs --expect-head` → S9 |
| RFC 3161 block | judged offline against the shipped CA | **not judged** — reported as such |
| exit 0 | ANCHORED only | ANCHORED only |

The last row of the second column is deliberate. Ranking a timestamp needs the
JCS digest of four pinned values plus a CA-chain check that `anchor_check.py`
implements; a verdict borrowed from the other implementation would not be a
second opinion, so `anchor.mjs` prints `not judged here` instead of guessing.

## Four scenarios, frozen in `tests/test_anchor_second_impl.py`

| scenario | Python | Node |
|---|---|---|
| baseline bundle | ANCHORED (0) | ANCHORED (0) |
| `checkpoint_head` replaced with zeros | FAILED | FAILED |
| `pubkey_b64` swapped for a stranger's | FAILED | FAILED |
| `anchor.json` deleted | refuses, non-zero | refuses, non-zero |

The exit codes differ in the middle rows (1 vs 2) on purpose — each tool keeps
its own convention — so the frozen fact is the **verdict word**, which is the
thing a stranger acts on.

## What it does not buy

- **The bundle is still the same bundle.** Both implementations read the same
  files; agreement proves the files say what they say, not that a third party
  produced them. That is what an external anchor is for, and it still does not
  exist (`docs/IMPLEMENTATION-STATUS.md`: zero).
- **The Node path skips the timestamp.** A bundle with a `tsa` block gets
  `timestamp: not judged here` from Node and an honest verdict from Python — two
  lines a reader can see and weigh.
- **Both trust the same canonicalization rule.** If JCS were implemented
  identically wrong in both, they would agree on a wrong answer. The mitigation
  is the same one used elsewhere here: the rule is small, published, and checked
  against RFC 8785 examples in `tests/`.
