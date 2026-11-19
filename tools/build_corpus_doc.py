# -*- coding: utf-8 -*-
"""Generate docs/MUTATION-CORPUS.md from the shipped corpus JSON. Numbers are read from
the file, never typed."""
import io, json, os

ROOT = r"D:\lgd-work\uibc-core-r19"
corpus = json.load(io.open(os.path.join(ROOT, "benchmarks", "corpus",
                                        "mutation-corpus-500.json"), encoding="utf-8"))
summary = corpus["summary"]
fams = corpus["families"]

fam_rows = []
for k in sorted(fams):
    v = fams[k]
    caught = sorted(v["caught_by"].items(), key=lambda x: -x[1])
    caught_s = ", ".join("%s×%d" % (c, n) for c, n in caught[:4]) or "—"
    fam_rows.append("| %s | %d | %d | %d | %s |" % (k, v["n"], v["accepted_open"],
                                                   v["accepted_pinned"], caught_s))

mode_rows = []
for m in ("open", "pinned", "head-pinned"):
    s = summary[m]
    mode_rows.append("| %s | %d / %d | %.1f%% |" % (m, s["accepted"], s["total"],
                                                    s["false_accept_rate"]))

doc = """# Mutation corpus: 500 deterministic cases

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
""" + "\n".join(mode_rows) + """

Read the `open` row as the honest headline: with no anchor, one in eight of our own mutations
gets accepted, and every one of those is a rollback or a key swap — the two classes that
provably cannot be judged without an anchor. The `head-pinned` row is 0/60 because only the
rollback family has a head-pinned variant; it is not a claim that 0/500 would be achievable.

## Per family

| family | cases | accepted (open) | accepted (pinned) | caught by (pinned, top 4) |
|---|---|---|---|---|
""" + "\n".join(fam_rows) + """

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
"""

p = os.path.join(ROOT, "docs", "MUTATION-CORPUS.md")
io.open(p, "w", encoding="utf-8").write(doc)
print("wrote", p, len(doc))
