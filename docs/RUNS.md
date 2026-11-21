# Runs of this corpus by someone else

One row per run of the conformance corpus by an implementation **this repository
did not write** — or by this repository's own verifier, in which case the row says
so. A row is added when the run is posted publicly with a record a reader can
fetch. This file is transcribed, not summarised.

## Why this file exists

Two implementations written by the same author catch each other's transcription
errors and share one reading of the specification. They cannot catch a misreading
that both inherited. An outside run can. That is the only reason the number in
`docs/AUDIT-KIT.md` is marked "self-run" until somebody else runs it.

## What a row must carry

- **who ran it**, by the name or handle they posted under;
- **where**, as a link that resolves to the record itself, not to a summary of it;
- **which archive digest**, because a figure without a digest is a figure about
  nothing (`sha256` of the zip that was unzipped, not of the files inside);
- **the figure exactly as they posted it** — never rounded, never restated as a
  fraction of a different corpus, never converted into a percentage;
- **blind or directed**, in the runner's own words, because those are different
  evidence and are never added together. *Directed* means the runner read this
  repository's checks, its expected reasons, or its vectors before or during the
  run; that is not disqualifying, it is a different claim;
- **who wrote the code that ran** — `independent` (neither the corpus nor the
  verifier is ours), `same code` (they ran our verifier elsewhere), or
  `author` (we ran it, which is recorded here but cannot raise any count);
- **their own words**, quoted, so a row cannot soften what they said.

A run whose runner called it directed is recorded as directed here, whatever it
scored. A run with a disagreement is worth more than a clean pass and is recorded
with the disagreement in the row, not flattened into a fraction.

## The table

Empty. Not "no failures" — no entries. Every row above the line would need a link
that resolves, and there is none yet.

| date | runner | where posted | archive sha256 | blind/directed | code author | figure as posted | note |
|---|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — | no external run recorded as of 2026-11-20 |

## What this file does not do

It does not change the count by itself. A row is added only after the receipt
passes `tools/check_outward_receipt.py` and the relation field says the runner is
independent of the author. An anonymous receipt, or one from a contributor, can be
quoted as a run but is recorded as `same code` / `author`, never as an external
node.
