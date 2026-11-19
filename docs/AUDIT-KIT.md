# AUDIT-KIT.md — three questions an outsider can ask, and the command that answers each

This document exists because "trust us" is not evidence. Everything below runs offline, needs no account, and produces numbers you can compare against ours. If your numbers differ from ours, that is the most useful thing you can send us.

## Question 1: can every check be made to fail?

A check nobody can make fail is decoration.

```
python3 tools/export_conformance.py
python3 tools/check_falsifiability.py
```

It asks, for each of the **nineteen** checks, whether a package we publish can drive that check to `FAIL`. Two checks cannot be reached from inside a package, so they are covered separately by the outsider audit (a real RFC 3161 token and four mutations of it for S16; a head observed outside the package, then a rollback only that observation can see, for S9).

**What to compare:** the count of checks with a published artefact, and the identity of any check without one.

## Question 2: is every field judged by somebody?

```
python3 tools/check_field_coverage.py --json
```

It copies the clean fixture, replaces **one leaf field** with a different value of the same shape — a 64-hex digest gets one character flipped, a UUID its first character, a string gets `-altered`, a boolean is negated — runs `verify`, and records **every check whose result moved**, in either direction.

An empty set is not automatically a defect: a note field or a media type legitimately changes nothing. The point is that every field now has a recorded answer, and a reviewer can disagree with the answer instead of guessing it.

**What to compare:** the list of fields that move nothing, and whether each of them is argued for in `docs/FIELD-COVERAGE.md`.

## Question 3: does a verifier we did not write agree?

```
python3 tools/run_conformance.py --verify "<your verifier command>"
```

The suite is 36 packages derived from one correct package, each broken in exactly one declared way. A case passes only if the verifier reports `FAIL` and names at least one of the expected checks; cases that must be accepted must not be refused.

If you write your own verifier, point this at it. That is the single most useful contribution anyone can make to this project, and it is the one thing we cannot do for ourselves.

## What this kit does not establish

| Not established | Why it matters |
|---|---|
| Independent human reproduction | The receipts in `docs/external-review/` are from external models, not people. Machine review does not carry a person's accountability. |
| Scientific validity of any score | No criterion correlation, no inter-rater study, no calibration against labelled risk. See `LIMITATIONS` in this directory. |
| Production use | Every artefact here is from an experimental environment. No customer authorisation exists, so `deployed` would be false. |
| Correctness against the real world | Passing 36 packages means the verifier refuses the 30 declared mutations and accepts the 6 correct ones. It does not mean the model of evidence is right. |

## Reporting a result

Send the command, the version you ran (`git rev-parse HEAD` or the installed version), the date, and the raw output. We publish disagreements, including the ones where we turn out to be wrong — see `failure_corpus/` for how that is recorded.
