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

## Read the results from another harness

A harness that wants to run this verifier over its own vectors needs one line
per vector, not one pretty JSON document per package:

```bash
python uibc_core.pyz verify ./one-package --report runs.jsonl --vector-id v-17
python uibc_core.pyz verify-dir ./my-vectors --report runs.jsonl
```

Each line is `{"format": "uibc-verify-report/1", "vector": ..., "result": ...,
"checks_failed": [...], "verifier_id": ..., "verifier_version": ..., "when_utc":
..., "exit": 0|1}`. `--report` appends, so a batch run accumulates in one file and
a failing package cannot erase the lines already written. A failing package still
gets a line — that is the case a harness most needs — and so does an input we cannot
read at all: hand it a single statement file instead of a package directory and the
line says `result: ERROR`, `exit: 3`, and the reason. `no line` would be indistinguishable
from `this vector was silently dropped`, which is precisely what a foreign rail reported
as `external-output-absent` when it handed us single statements. `verify-dir` exits non-zero
when any child is not PASS and prints `n/m packages PASS`; an empty directory exits
3 and writes nothing, because "nothing was judged" must not read as "all passed".

The line carries this project's verdict vocabulary and check ids. A consumer
mapping FAIL / INCONCLUSIVE onto its own scale is making its own claim, not ours.

## What this does not do

It does not import a foreign corpus wholesale. A corpus in someone else's layout
needs that corpus's own reader: which files form a package, what each vector
means, and which verdict counts as agreement. `tools/bring_your_own.py` takes the
layout you give it, one directory per case, and stops there. The
`scitt-cose-carriage-conformance` corpus is a concrete case of that gap: the
external rail reports that this package has no reader for it, and
`CONSUMERS.json` records the absence with the numbers instead of guessing at one.

It also does not certify anything. One person, one machine, one run.
