# A stranger's first ten minutes, done for real

**2026-11-19.** Everything below was run in a directory that had never seen this
project, with no credentials, no token, and nothing installed. The point is to
find out what a stranger actually meets, not what the documentation says they
will meet.

The machine: a Linux host, Python 3.12, the same one the rest of the documents
were measured on. A first attempt on a machine like this is what the numbers
below describe; a Windows attempt would differ, and that is said where it
matters.

## Route 1: clone and run the audit

```
$ git clone --depth 1 https://github.com/zhaoxinghua09-cell/uibc-core
real  0m2.3s          # 6.4 MB, 626 files without .git

$ python3 tools/outsider_audit.py
real  0m0.3s
...
red team s16: 4 cases (real FreeTSA token)
  atk  claim the token dates another file       FAIL      -> FAIL         ok
  atk  misdeclare the token digest              FAIL      -> FAIL         ok
  atk  flip one byte in the token               FAIL      -> FAIL         ok
  atk  drop the CA bundle                       FAIL      -> FAIL         ok
interop    : SKIPPED (--kit not supplied; a skip is not a pass)
verifier   : verify.py  sha256 41c734f3ca804e0f o  (from this repo: True)
VERDICT    : OK
```

**Two commands, 2.6 seconds, no network beyond the clone, no dependencies.**
That is the good news, and it is real: a stranger with `git` and `python3`
reaches a verdict before finishing a cup of tea.

The audit is honest in the way that matters here — `interop` reports SKIPPED
rather than passing, and the S16 line states plainly that the timestamp covers
a file kept in the repo, not this package's head. A stranger reading it knows
exactly what was and was not proven.

## Route 2: the published package

This is where a stranger meets the problem we have been writing about, and it
takes ninety seconds to find:

```
$ python3 -m venv venv && venv/bin/pip install uibc-core
Successfully installed uibc-core-0.3.3

$ venv/bin/uibc verify fixtures/clean.uibc
"statement": "No violation was detected, but verification is incomplete: ..."
```

Verifying works. What does not match is **what the verifier checks**:

| | checks reported on the same clean package |
|---|---|
| `pip install uibc-core` (0.3.3, published 2026-11-15) | S1, S2, S3, S4, S5, S6 — **6** |
| `main` (0.4.0, this repository) | S1, S2, S3, S4, S5, S6, S11, S12 — **8** |

Both reach INCONCLUSIVE, which is correct for an unsigned package. But the
stranger who installed from PyPI is running a verifier with two fewer checks
than the one every document in this repository describes, and `main` is
`0.4.0` while PyPI is `0.3.3`. Nothing in the README says so at the point of
installation.

That is the whole adoption problem in one table: the code is better than the
package, and the package is what a stranger gets.

## What a stranger would conclude

Two honest sentences, and both are true today:

1. *"The repository is unusually self-checking — it hands me a command and a
   verdict, and it tells me what it skipped."*
2. *"The package I can install is not the one the documents describe."*

The second sentence is the one that stops adoption, and it cannot be fixed
with more tests. It is fixed by publishing `0.4.0`, which is step 1 in
`docs/UPSTREAM-SUBMISSION-PLAN.md` and needs the account holder.

## What this page is for

It is the first row of bucket 4 in `docs/IMPLEMENTATION-STATUS.md` — except it
does not count, because this was run by the author. It is a rehearsal, and its
value is that it found the exact sentence a stranger would say. When a person
who is not the author runs the same two commands, that row becomes real.
