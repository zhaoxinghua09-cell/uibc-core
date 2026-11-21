# Mutation corpus: 500 deterministic cases

This file ships the full corpus, not a summary of it. `benchmarks/corpus/mutation-corpus-500.json`
contains one row per case: which family it belongs to, what was mutated, and what each of the
three verification modes returned for it — including the ids of the checks that fired.

**as of** `main` at the commit that carries this file; every number below is read from that JSON
by `tools/build_corpus_doc.py`, never typed.

## What it is, and what it is not

It is a deterministic corpus: all parameters are derived from an index, there is no random seed
anywhere, and the same command produces the same 500 cases on any machine. That property is
what makes an outsider's reproduction meaningful.

It is **not** a strength claim. The 17 families were chosen by the authors. Nobody has reviewed
that list for what it leaves out. A low false-accept rate over families we invented says
nothing about families we did not think of.

## Three modes

`open` — a bare verifier with no caller-supplied anchor. `pinned` — the caller pins the
expected head. `head-pinned` — the verifier carries state from a previous acceptance.

| mode | accepted / total | false-accept rate |
|---|---|---|
| open | 60 / 500 | 12.0% |
| pinned | 20 / 500 | 4.0% |
| head-pinned | 0 / 60 | 0.0% |

Read the `open` row as the honest headline: with no anchor, one in eight of our own mutations
gets accepted, and every one of those is a rollback or a key swap — the two classes that
provably cannot be judged without an anchor. The `head-pinned` row is 0/60 because only the
rollback family has a head-pinned variant; it is not a claim that 0/500 would be achievable.

## Per family

| family | cases | accepted (open) | accepted (pinned) | caught by (pinned, top 4) |
|---|---|---|---|---|
| blob-byte | 98 | 0 | 0 | S4×98, S8×98 |
| evidence-add | 24 | 0 | 0 | S4×24, S12×24, S7×24, S8×24 |
| evidence-drop | 6 | 0 | 0 | S8×5, S5×5, S6×4, S12×2 |
| identity-scalar | 12 | 0 | 0 | S6×12, S3×6 |
| index-metadata | 24 | 0 | 0 | S7×24, S8×24 |
| keyswap | 40 | 40 | 0 | S6×40 |
| lifecycle-actor | 16 | 0 | 0 | S3×16, S6×16, S8×8 |
| lifecycle-drop | 6 | 0 | 0 | S8×6, S6×6, S3×1 |
| lifecycle-insert | 24 | 0 | 0 | S3×24, S8×24, S6×24 |
| lifecycle-ts | 30 | 0 | 0 | S3×30, S12×30, S6×30, S8×29 |
| manifest-delete | 8 | 0 | 0 | S6×8, S5×1 |
| manifest-extra | 24 | 0 | 0 | S6×24 |
| manifest-scalar | 40 | 0 | 0 | S6×40, S12×7, S5×4, S8×4 |
| rollback | 20 | 20 | 20 | — |
| root-extra | 24 | 0 | 0 | S1×24 |
| sig-byte | 64 | 0 | 0 | S6×64 |
| truncation | 40 | 0 | 0 | S8×40, S6×20 |

## Reproduce it

```bash
python tools/mutation_corpus.py --out /tmp/corpus.json     # regenerate (~2-3 min)
python tools/corpus_selfcheck.py --receipt my-receipt.md     # compare against the shipped file
```

`corpus_selfcheck.py` regenerates into a temporary directory, compares every case id's verdicts
and the failed-check sets against the shipped JSON, and writes a receipt that carries the
commit, the Python version, the wall clock, and a sha256 of the row set. It exits 0 only on
`MATCH`. A receipt produced by someone who is not us is worth more than any sentence in this
document, so that is the artifact to send us.

What the self-check does **not** establish: that the corpus is complete, that the families were
chosen fairly, or that the verifier is strong. It establishes one thing — this repository's
numbers can be regenerated from this repository's code.

## Known gaps (stated here, not in an appendix)

- 17 families, chosen by the authors, unreviewed by anyone outside.
- Ours is not the first corpus of this shape; `draft-sirkkavaara-vaara-receipt-03` ships public
  vectors with its own independent checker, and arXiv:2608.16178 reports 500 adversarial
  mutation trials with a 100% detection rate. What we add is per-case verdict disclosure for
  an offline package verifier, not a new class of test.
- Zero third-party reproduction receipts so far. That is a fact about this project, not a
  statement about the method.
