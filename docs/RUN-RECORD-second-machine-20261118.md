# Second machine, same suite — run record (2026-11-18)

This is not a third-party node. It is the same author, a different machine and a different
operating system, running the published command against `main` at `4e44ea5`.

| item | value |
|---|---|
| machine | cloud Linux host (x86_64) |
| interpreter | Python 3.12.11 |
| commit | `4e44ea58` (`main`) |
| command | `python3 -m unittest discover -s tests -p "test_*.py"` |
| result | `Ran 316 tests in 29.248s` — `OK (skipped=5)` |
| install step | none; no third-party package was installed |

## The five skips

All five are `test_v14_ots_anchor` checks that require the optional `opentimestamps`
package. They are skipped, not failed, because the verifier itself is kept dependency-free.
A verbose run additionally skips one `test_quickstart` self-seeding check once the corpus
is already present, which is why that run reports `skipped=6`.

## Why this record exists

`README.md` carried both `313` and `305` for the same command, and neither matched a fresh
run. This run is the measurement the numbers were corrected to. If you reproduce it on your
own machine and get a different count, that difference is data — the suite's total depends on
Python version and on whether the optional anchor packages are installed, so please state the
environment alongside the number rather than quoting a bare figure.

External verification nodes remain **0**. Nothing here changes that.