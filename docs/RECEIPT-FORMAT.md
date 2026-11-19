# A receipt anyone can publish

The conformance archive is built so that a stranger can run it: one command, no
install, about six seconds, and it writes `receipt.json`. This page says what
that file has to contain before anyone — us included — may quote its number, and
where to put it.

Machine check: `python tools/check_outward_receipt.py receipt.json`

## The six things that make a receipt quotable

| field | what it must say | why a missing one voids the number |
|---|---|---|
| `verifier_version` | which version judged the cases, e.g. `0.4.1` | `unknown` means the run never got a verifier to speak; a 0/36 from that path is indistinguishable from a corpus that fails everything |
| `manifest_sha256` | digest of the corpus that was actually read | a table without the corpus digest cannot be compared with anybody else's table |
| `cases` and `passed` | totals, and `passed` must equal the number of rows with `ok: true` | a summary that contradicts its own rows is the one failure this format exists to catch |
| `rows` | one entry per case, with `id`, `ok`, and the verdict it observed | the rows are the evidence; the totals are only a summary of them |
| `command` | the exact command, naming the verifier | "it passed" without the command is an assertion, not a measurement |
| `run_by` | who ran it, on what machine | an unattributed receipt can be copied from our own report and still look new |

`tools/check_outward_receipt.py` refuses anything that fails the first five, and
refuses an empty `run_by` unless you pass `--allow-anonymous` — in which case the
receipt may still be quoted as *a run*, but it cannot be counted as a node report.

`run_by` is filled by `run.py` itself: run `python run.py --run-by "Your Name <you@example.org>"`
instead of editing the file afterwards. Our own receipt is anonymous because we are
not our own external node — the checker refuses it for node counting, and that is
the intended behaviour rather than an oversight.

## Where a receipt goes

Open a new issue with the **Conformance receipt** form
(`.github/ISSUE_TEMPLATE/conformance-receipt.yml`). It asks for the archive digest
you ran, your interpreter, the tail of the output, the file itself, and your
relation to the author.

The relation field is what decides which count moves:

- independent of the author → **external node report** (this is the number in
  `docs/EVIDENCE-INDEX.md` that has been 1 since EXTERNAL-NODE-001, and 0 before that)
- contributed code, same organisation, or paid → **self-reproduction**, published
  with the same prominence and counted separately

The form also asks **blind or directed** and **which verifier produced the numbers**.
Those are not decoration: a directed run is different evidence from a blind one and
the two are never added together. A row that lands is transcribed into
[`docs/RUNS.md`](RUNS.md) with the runner's own words, and any disagreement becomes a
permanent entry in [`docs/DISPOSITIONS.md`](DISPOSITIONS.md) — including the rows
that were declined, which stay visible.

This mechanism is simpler than the one `probityai/agent-evidence-vectors` already
publishes (`RUNS.md` / `DISPOSITIONS.md` / blind-and-directed labels), and the
comparison is written down against us in
[`docs/COMPETITIVE-STATE.md`](COMPETITIVE-STATE.md).

## What a receipt does not mean

Passing 36/36 says: a verifier this project wrote, running the corpus this
project wrote, on the machine you named, produced the table above. It does not
say the verifier is right, that the corpus is complete, or that any other
implementation behaves the same way.

The line we will not cross: **a number that was not measured is worse than a
number that is missing.** If your run ends with exit 3, no receipt is written by
design — that is a statement about your environment, not about the corpus, and
reporting it as a failure rate would be false.

If you ran on someone else's behalf rather than your own, the receipt is not enough to
say so: it records who ran, not who was allowed to. That second statement is a
delegation record, checked by `docs/DELEGATION.md` / `tools/check_delegation.py` — one
hop, bounded window, scope pinned to the corpus digest, and a caveat you cannot skip:
a record carrying its own key proves only that it was signed by its author.

## Sunset, in the other direction

`docs/AUDIT-KIT.md` carries our own commitment: if no unrelated party has run this
archive hash and published a receipt by **2027-05-19**, the catalogue line
"re-runnable by an outsider" gets downgraded to "self-run only". This page is the
mechanism that makes the commitment checkable rather than rhetorical: the receipt
format, the checker, and the form that turns a file into a public record.
