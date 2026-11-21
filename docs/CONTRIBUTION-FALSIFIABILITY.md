# A conformance suite for agent-evidence verifiers

This repository publishes a verifier. This document publishes the suite that
verifier is judged by — and, more to the point, the same suite can judge any
other implementation, including ones that share none of our code and none of
our format.

It exists because "two implementations agree" is a weak claim if both are scored
by the same party, and because "our verifier passes" is weaker still. A suite
that a stranger can point at their own binary, and get a report they can publish
without our involvement, is the smallest object that turns cross-implementation
agreement into something a third party can check.

## The contract a verifier must meet

A verifier under test is any command that:

1. takes one argument — a path to a package directory;
2. exits 0 for accept, non-zero for refuse;
3. prints JSON on stdout: `{"result": "PASS"|"FAIL"|"INCONCLUSIVE", "checks": [{"id": "S4", "result": "FAIL"}, ...]}`.

`checks` may be empty, but a refusal that names no check scores as a failure
below. That is deliberate: a verifier that refuses everything and explains
nothing is indistinguishable from one that refuses at random.

```
python3 tools/run_conformance.py --verify "your-verifier {pkg}" --name "your-verifier 1.2.3"
```

## What the suite contains

36 packages, each carrying exactly one property:

| half | packages | requirement |
|---|---|---|
| accept | 6 | a correct package must not be refused |
| refuse | 30 | a broken package must be refused **and** the refusal must name one of the checks the breakage actually violates |

The accept half exists because without it a verifier that refuses everything
scores full marks on the refuse half. This is the most common way a
conformance suite is quietly useless.

Coverage: 19 distinct checks (S1–S19), each violated by at least one package
whose expected check list is known in advance.

## How to read your own result

```
strict 36/36   refused 30/36
```

`strict` counts packages judged exactly as intended. `refused` counts how many
of the 36 your verifier refused — 30 is correct, 36 means you refused a package
that was fine, 29 means you let a broken one through. A report is publishable
when `strict` is 36 and the named-check rate is 30/30.

Current results, run on 2026-11-19:

| implementation | strict | refused | named check |
|---|---|---|---|
| `uibc-core` (Python) | 36/36 | 30/36 | 30/30 |
| `verify-js` (JavaScript, shares no code) | 36/36 | 30/36 | 30/30 |

## The falsifiability matrix

Separate from the 36 packages: 19 single-property mutations, each of which must
produce a non-zero verdict on a verifier that implements all 20 checks
(`tools/check_falsifiability.py`). A verifier that implements 12 checks should
report 12, not 19 — the matrix measures what is implemented, and a partial
implementation is visible rather than scored as "pass".

## Limits, stated up front

- **The packages are constructed by us.** 36 is not a sample of any real-world
  distribution, and no statistical claim follows from it.
- **The suite tests one format.** It cannot tell you whether your verifier is
  correct about agent evidence in general, only about the 36 properties encoded
  here.
- **Naming a check is not the same as naming the right check.** We score
  "any expected check named", not "the minimal explanation given". A verifier
  that over-reports checks will score full marks here and should not be
  described as precise on the strength of this suite.
- **A shared misreading survives.** Both of our implementations could read the
  spec the same wrong way. Only a third implementation, written from the prose
  alone, can rule that out. That is precisely the gap this document is meant to
  invite someone to close.

## If you run it on your implementation

Send the JSON with `--json` and the version string you passed to `--name`; a
table row like the one above is enough. Nothing here requires our verifier,
our keys, or our network.
