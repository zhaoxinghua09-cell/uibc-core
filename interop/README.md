# interop

Two things live here: a machine-readable statement of what this project hands to
others and what it takes from them (`CONSUMERS.json`), and the entry point for
testing **your** packages with **our** verifier (`tools/bring_your_own.py`).

`CONSUMERS.json` is deliberately blunt. Each entry says whether the format is
consumed, produced, or neither, and where the measurement came from. The entries
listed as *not consumed* are real absences: the SCITT COSE vectors that this
verifier currently cannot read are named there with the numbers, rather than left
for a reader to discover.

## Test your own packages

A case is one directory that is itself an evidence package, plus one line saying
what you expect from it:

```json
{"cases": [
  {"id": "mine-ok",     "path": "mine-ok",     "expect": "accept"},
  {"id": "mine-broken", "path": "mine-broken", "expect": "reject", "expected_checks": ["S4"]}
]}
```

Then:

```bash
python tools/bring_your_own.py --cases ./my-cases --expect ./my-expected.json \
    --pyz uibc_core.pyz --out my-receipt.json --run-by "<your name or handle>"
```

Or point it straight at the published archive, without cloning anything else:

```bash
python tools/bring_your_own.py --cases ./my-cases --expect ./my-expected.json \
    --pyz conformance/uibc-conformance-0.5.8.zip:uibc_core.pyz --out my-receipt.json
```

Judging does not trust the exit code. A verifier that exits 0 while refusing
everything would look successful otherwise:

- `accept` is ok when the verdict is not `FAIL` **and** no check reports `FAIL`;
- `reject` is ok when the verdict is `FAIL` or `INCONCLUSIVE` **and** at least
  one of the checks you named actually reports `FAIL`.

Exit codes: `0` every case behaved as you said, `1` some case did not, `3` the
run could not be set up (a case directory missing, the table unreadable, the
verifier absent). A setup problem outranks a verdict, and no receipt is written
when the run cannot be set up.

The receipt records `run_by` verbatim. Leave it unset and it stays null, so a
receipt written by this project's author and one written by a stranger are
distinguishable without anybody having to ask.

## What this does not do

It does not import a foreign corpus wholesale. A corpus in someone else's layout
needs that corpus's own reader: which files form a package, what each vector
means, and which verdict counts as agreement. `tools/bring_your_own.py` takes the
layout you give it, one directory per case, and stops there. The
`scitt-cose-carriage-conformance` corpus is a concrete case of that gap: the
external rail reports that this package has no reader for it, and
`CONSUMERS.json` records the absence with the numbers instead of guessing at one.

It also does not certify anything. One person, one machine, one run.
