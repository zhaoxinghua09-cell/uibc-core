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

The shape is published as JSON Schema, so a consumer does not have to read
prose: `interop/verify-report.schema.json` (draft 2020-12). It pins the three
things a reader can get wrong - `FAIL` must name the failing check, `ERROR` must
carry a reason and exit 3, and `PASS`/`INCONCLUSIVE` must not carry failed
checks. `tools/report_lint.py <file.jsonl` checks any producer's file against
those rules without needing a third-party library, so the schema can be used
rather than merely quoted.

The line carries this project's verdict vocabulary and check ids. A consumer
mapping FAIL / INCONCLUSIVE onto its own scale is making its own claim, not ours.

## Read a SCITT/COSE Transparent Statement

`cose_min.py` verifies the shape this project emits. It is not a reader for
anyone else's wire form: a tagged COSE_Sign1 with CWT claims, an observer
position at a private-use label, and RFC 9942 receipts is outside that subset.
`uibc_core/scitt_cose.py` reads that shape under the `aee-scitt-cose/v0.1`
profile, in the order the profile's Section 6 gives:

```bash
# one statement, with its own trust inputs and verification time in the file
python uibc_core.pyz verify-cose --vector v11816a7dc863a687.json

# a corpus: every member judged, one line per member, plus a score
python uibc_core.pyz verify-cose --manifest MANIFEST.json --statements statements/ \
       --report runs.jsonl --json-out score.json
```

`--at <epoch>` fixes the instant `exp` and `nbf` are judged against. Without it
the vector's own `verificationTime` is used, and the wall clock only where the
file carries none — the choice is visible in the output rather than implicit in
the code.

A refusal carries a code, because "invalid" alone tells a relying party nothing:

| stage | codes |
| --- | --- |
| decode | `unreadable`, `payload-absent` |
| deterministic encoding | `protected-header-not-deterministic` |
| crit (RFC 9052 §3.1) | `critical-parameter-unprotected`, `critical-parameter-unprocessable`, `observer-position-not-critical` |
| algorithm (RFC 9864 §4.2) | `algorithm-deprecated` (-8), `algorithm-mismatch` (-7 and anything else) |
| key and signature | `issuer-key-unknown`, `issuer-key-ambiguous`, `signature-invalid` |
| CWT claims (RFC 9597) | `cwt-claims-absent`, `cwt-claims-duplicated`, `cwt-claims-incomplete`, `subject-digest-mismatch`, `issuer-identity-mismatch` |
| validity window | `statement-expired`, `statement-not-yet-valid` |
| receipt (RFC 9942) | `receipts-absent`, `receipt-vds-absent`, `receipt-vds-unregistered`, `receipt-algorithm-mismatch`, `inclusion-proof-absent`, `inclusion-proof-unapplicable`, `receipt-subject-mismatch`, `receipt-key-unknown` |

The root an inclusion proof is checked against is recomputed by this reader with
its own RFC 9162 Section 2.1.3.2 walk. It does not import `merkle.py` and it does
not read a root out of the file: a verifier that shares arithmetic with the code
that produced the inputs cannot disagree with them, which is the same rule the
profile itself asks of an implementer replaying its corpus.

Results come out as a second report shape, `uibc-scitt-cose-report/1`
(`interop/scitt-cose-report.schema.json`), rather than reusing the package
report: that report names failing checks as `S`-ids, and this profile refuses on
named faults no `S`-id describes. `tools/report_lint.py` validates either shape
and says which rules it applied.

Measured, 2026-11-27, against `probityai/agent-evidence-vectors`
(`corpora/vectors-scitt-cose`, 27 members, `corpusDigest 79d651d3…`): **27 of 27
answers conform** to the answers the corpus declares, judged at the instant its
own witnesses use (`1789041600` = 2026-09-10T12:00Z). Judged at each vector's own
`verificationTime` the count is **26 of 27**, and the member that differs is the
expiry one: its `exp` (1789038000) is after the `verificationTime` that file
carries (1788955200) and before the corpus' witness clock. That is the corpus'
clock question, not our reader's: the verdict is the same bytes answered
differently at a different instant, and both numbers are published rather than
the flattering one alone. 27/27 is our reading of their published corpus; their
rail has not been re-run against this build, so it is not their scoring.

## What this does not do

It does not import a foreign corpus wholesale. A corpus in someone else's layout
needs that corpus's own reader: which files form a package, what each vector
means, and which verdict counts as agreement. `tools/bring_your_own.py` takes the
layout you give it, one directory per case, and stops there. The
`scitt-cose-carriage-conformance` corpus used to be a concrete case of that gap;
since 2026-11-27 it has a reader in this repository, and `CONSUMERS.json` records
how far that reading goes instead of claiming it settles the question.

It also does not certify anything. One person, one machine, one run.
