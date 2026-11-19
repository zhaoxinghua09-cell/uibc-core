# Cross-check: we ran their vectors

Status: **done, local, no outbound action.**
Date: 2026-11-19.
Subject: the `scitt-cose` vector set published in `ietf-wg-scitt/examples`
(`test-vectors/scitt-cose`, upstream HEAD `727ee03d86fa2c2ca8c534584b870235a1b252df`).

---

## What this is, and what it is not

`docs/external-review/EXTERNAL-NODE-001.md` records the other direction: an
outside operator ran **our** code on **their** machine. This note records the
reverse: we ran **our** tree arithmetic over **their** committed vectors.

It is **not an audit of `scitt-cose`**, and it is **not** a claim that our
verifier agrees with theirs. It answers one narrow question: *do their
committed inclusion paths fold to the roots they state, when folded by an
implementation they did not write?*

## The one field that has to be read correctly

Their `expected.json` carries `leaf_entry`. It is the **SHA-256 digest of the
complete COSE_Sign1 statement bytes** — that is the leaf *input*, not the leaf
hash. RFC 9162's leaf hash is `SHA-256(0x00 || leaf_input)`.

Our first run treated `leaf_entry` as a leaf hash and folded directly from it.
**All five vectors disagreed.** That was our reading error, not their error.
Corrected run:

| vector | expected result | path folds to stated root? | adjudication |
|---|---|---|---|
| `valid-eddsa` | VALID | **yes** | required to match — matches |
| `valid-es256` | VALID | **yes** | required to match — matches |
| `fail-tampered-path` | INVALID | **no** | required to differ — differs |
| `fail-bad-statement-sig` | INVALID | yes | not adjudicated here (failure lives in signature) |
| `fail-unsupported-vds` | INVALID | no | not adjudicated here (failure lives in VDS) |

Result: `vectors: 5  mismatches: 0` → `THEIR PATHS FOLD TO THEIR STATED ROOTS`.

## Command

```bash
git clone --depth 1 https://github.com/ietf-wg-scitt/examples.git /tmp/scitt-ex
python tools/crosscheck_scitt_cose_vectors.py --dir /tmp/scitt-ex/test-vectors/scitt-cose
```

The tool imports only `uibc_core.merkle`; it needs no COSE library, because
folding a path involves no signature.

## Why the first failed run is kept in this note

Because it is the same event we keep asking outsiders to produce for us: a
different implementation, arriving at different numbers, writing down what
differed. Ours was a field-reading error and it is recorded as ours.

The difference from a self-test is the direction of the check: here the bytes
under test are **not ours**, and we cannot edit them to make the run pass.

## Bottom line

- Two valid vectors fold onto their stated roots under our implementation.
- The tampered-path vector folds away, as it must.
- Nothing here closes the external-record gap recorded in
  `docs/LANDSCAPE-2026-11.md` §8: their `INTEROP.md` still does not list this
  repository, and one project's arithmetic agreeing with another's committed
  bytes is not a place in anyone's record.
