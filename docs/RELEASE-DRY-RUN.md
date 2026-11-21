# 0.4.0 dry run: does the package we would publish carry the claims it makes?

**2026-11-19.** Built from `c7effaa4`, on the same Linux host the rest of these
documents were measured on. Nothing was uploaded.

The trial in `docs/STRANGER-TRIAL.md` found that the *code* is better than the
*package*, because PyPI still had 0.3.3. That raised an obvious question the
same week: **if we published 0.4.0 today, would the package be as good as the
code?** This page answers it with measurements rather than intent.

## What was built

```
$ python3 -m build --sdist --wheel
uibc_core-0.4.0.tar.gz    792 KB
uibc_core-0.4.0-py3-none-any.whl    113 KB
```

## Finding 1: the sdist could not check itself

The first sdist carried `tests/` but not the data those tests read. Unpacking
it and running the suite in place:

| build | tests collected | result |
|---|---|---|
| clone of `main` (reference) | 526 | OK, 16 skipped (measured before `.[verify,interop]` existed) |
| sdist, first build (no `MANIFEST.in`) | **290** | **6 failures, 97 errors** |
| sdist, after listing fixtures/tools/conformance | 475 | 13 failures, 57 errors |
| sdist, after adding everything `tests/` reads under `tests/` | 482 | 3 failures, 35 errors |
| sdist, after grafting **every** top-level directory | **526** | **OK, 16 skipped** |

Every failure in all three broken runs was the same kind: `no such file or
directory` for a fixture, a tool, or an independent-verifier script. Not one was
a logic failure.

**The lesson is the shape of the curve, not the endpoint.** Each fix revealed
only the next missing directory, because a test suite does not complain about
what it never got to run. Guessing which directories matter loses this argument
four times in a row; grafting every top-level directory and pruning build
output wins it once. The reasoning is recorded in `MANIFEST.in` itself, so the
next person who wonders why it is aggressive finds the measurements there.

Without this fix, `pip install uibc-core` would have shipped a package whose
tests could not be run — and "526 tests green" would have been true of a git
clone only, which is exactly the class of claim this repository tries not to
make.

## Finding 2: the wheel is the code

```
$ pip install uibc-core-0.4.0-py3-none-any.whl
$ python -c "import uibc_core; print(uibc_core.__version__)"
0.4.0

$ uibc verify fixtures/clean.uibc
checks: S11, S1, S2, S3, S4, S5, S6, S12   (8)
```

Eight checks on the clean package — the same set `main` reports, and the two
that 0.3.3 lacked (S11, S12) are present. The wheel does not carry fixtures, and
does not need to: a verifier verifies what it is given.

## What this changes

The 0.4.0 release is no longer an unknown. The package builds, the sdist
reproduces the full suite byte-for-byte in test count, and the wheel carries the
same checks as the source. What remains is an upload and a tag, which needs the
account holder — and, per `docs/UPSTREAM-SUBMISSION-PLAN.md`, nothing else in
the adoption route can start before it.

A guard was added so this cannot silently regress: CI now builds an sdist and
runs the suite from the unpacked archive, so a future change that starts reading
a directory `MANIFEST.in` does not carry fails on the pull request rather than
in a stranger's hands.

## Reproduce it

```
$ python3 -m build --sdist --wheel
$ mkdir -p /tmp/sd && tar xzf dist/uibc_core-0.4.0.tar.gz -C /tmp/sd
$ cd /tmp/sd/uibc_core-0.4.0 && python3 -m unittest discover -s tests -p "test_*.py"
Ran 526 tests ... OK (skipped=16)
```
