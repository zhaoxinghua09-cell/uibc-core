# Reproduction register / 复跑登记册

**What this is.** A list of people who ran the numbers and said what happened. Nothing more.

**What this is not.** An endorsement, a certification, a ranking, or a customer list. A row
here means "someone executed the commands", not "someone vouches for the subject".

## Rules

1. **Disagreements are kept.** An entry that reports a mismatch stays in the file, marked
   `DISPUTED`, with both sides' evidence. Deleting a disputed row would make the register
   worthless the first time it disagreed with us.
2. **No ranking, no ordering by prestige.** Rows are chronological. There is no "verified
   partner" tier.
3. **We never fill in a third party's row.** If the runner does not submit it, it does not
   exist. A maintainer-written row for an outsider is the one failure mode that cannot be
   repaired later.
4. **A row must be reproducible from what it states** — commit, tool version, command, and
   the receipt hash. A row that cannot be re-run is gossip.
5. **Affiliation is declared, not inferred.** "Non-affiliated" means no employment, contract,
   or payment relationship with the subject (including the maintainer).

## How to submit

Run:

```
python tools/reproduce_gate.py --repo <uibc-core> --uibc <uibc[.exe]> \
       --profile docs/assurance/far-profile.json --out <dir>
```

Then send the generated `reproduction_receipt_*.md` (or the four fields below) with:

| field | meaning |
|---|---|
| `date` | when it ran |
| `who` | name or handle, plus affiliation (or "none") |
| `environment` | OS, python, uibc version, commit |
| `result` | `ALL COMPARISONS MATCH` or the list of disagreements |
| `receipt_sha256` | the hash the tool printed |
| `how` | rough method: fresh clone? clean venv? any local modification? |

Rows are added by the runner, by opening a PR that appends a line to the table below.

## Before you open that PR

The register's rule 4 says a row must be reproducible from what it states. That is
checked now, not trusted:

```
python tools/check_register_row.py --register REPRODUCTION-REGISTER.md
python tools/check_register_row.py --receipt <receipt.json> \
       --claim-commit <commit> --claim-sha256 <sha256 of that file>
```

The first command validates every row; CI runs it on every pull request, so a row with
a six-character hash, a blank affiliation, or a claim of agreement that never names
the command will fail before a maintainer reads it. The second cross-checks your own
receipt against what your row claims.

A **disagreement is not a failure.** Rule 1 keeps those. The checker rejects rows that
cannot be checked, not rows that say something inconvenient.

You can also open the issue form "Reproduction receipt"; the maintainer will ask you
to convert it into a PR row, and rule 3 still applies — the row is yours, not ours.

## Register

| date | who | affiliation | subject (commit) | result | receipt sha256 | notes |
|---|---|---|---|---|---|---|
| 2026-11-12 | Takao Sato (Poke-nushi) | none declared | v0.3.0 fixture set, 18 S4/S5/S6 comparisons | all agree | n/a (pre-tool run, 2026-11-12) | Ran a reading, not this script: 22 conditions, 66 comparisons, reseal with and without expected key. Registered by the maintainer at the time — the one row in this file that the maintainer wrote, kept for history and marked as such. |

> Note on that first row: it predates `tools/reproduce_gate.py`, so it does not exercise the
> script. It is listed because deleting it would look like tidying, and it is flagged because
> rule 3 exists. A row produced by this script is the only kind that counts as a re-run.

## Why this file exists at all

The published numbers are self-reported. Self-reported numbers are the weakest evidence class
in the whole document set — a reader has to trust the authors' arithmetic. One honest row from
someone who does not work with us converts a self-report into something checkable. That is the
entire value: not marketing, transfer of trust.

And the reason it is written down before there is anything in it: a register created after the
first friendly row arrives tends to be shaped around that row.
