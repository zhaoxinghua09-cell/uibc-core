# Dispositions of objections

Every objection this corpus has received from someone who is not its author, what
was decided, and why — including the ones that were declined.

## Why publish refusals

A conformance corpus asks a stranger to accept that a set of bytes decides whether
their implementation is correct. The only evidence a stranger has about how that
set is maintained is what happens when somebody disagrees with it. A changelog
says what changed; it does not say what was proposed and turned down, which is
the half that tells a reader whether the change process is real.

A table that records only the objections its author was pleased to accept is
worse than no table: it reads as scrutiny while being selection. So the declined
rows stay, in the objector's frame.

## What a row is

| field | rule |
|---|---|
| id | `D-YYYYMMDD-NN`, permanent, never reused |
| who raised it | name/handle plus a link to the objection as posted |
| the objection in their words | quoted, unsoftened, no paraphrase in the first line |
| what was decided | accepted / declined / accepted in part / still open |
| the reason | the sentence that decided it: a check id, a specification line, or an admission that the text is silent |
| reversal condition | what evidence would reopen it; "none" is allowed but has to be written |

## The table

Empty. Not "nothing was ever refused" — nothing has been raised from outside this
repository yet. Padding it with our own resolved questions would be exactly the
selection this page exists to avoid.

| id | raised by | objection (their words) | decided | reason | reversal condition |
|---|---|---|---|---|---|
| — | — | — | — | — | no external objection on record as of 2026-11-20 |

## Related

- `docs/RUNS.md` — runs by someone else, transcribed
- `docs/RECEIPT-FORMAT.md` — what a quotable receipt must contain
- `docs/AUDIT-KIT.md` — the three questions an outsider can ask, and the sunset
  clause that applies if nobody does
