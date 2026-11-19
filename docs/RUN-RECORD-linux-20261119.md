# Run record — a second platform, 2026-11-19

This page exists because a claim nobody re-ran is a claim with no evidence behind it: the README says
"605 tests green on Linux", and until this run every measurement behind that sentence came from one Windows
host. Same author, so this is **L1 self-reproduction**, not an external node. It answers a narrower question:
does the same commit produce the same answers on a different kernel, and do the two platforms disagree only
where we already said they would.

## What was run

| | |
|---|---|
| Commit | `64124b7` (the squash of #188, after #169's fixes landed as `cedbfa9`) |
| Clone | `git clone --depth 1 https://github.com/zhaoxinghua09-cell/uibc-core.git` — public HTTPS, fresh directory, no local files carried over |
| Host | Cloud VM, Linux, `Python 3.12.11` |
| Time | 2026-11-19, afternoon CST |

```bash
python3 tools/external_node_check.py
python3 independent_verifier/cross_check.py
python3 -m unittest discover tests
python3 tools/redteam_robustness.py
```

## What it printed

| Command | Output, verbatim |
|---|---|
| `external_node_check.py` | `independent=PASS  reference=PASS(8ms)  probes=3/3 rejected  -> CONSISTENT` |
| `cross_check.py` | `checks compared: 70, mismatches: 0` / `AGREEMENT: PASS - spec determinism holds` |
| `unittest discover tests` | `Ran 605 tests in 49.666s` / `OK (skipped=2)` |
| `redteam_robustness.py` | `10 of 10 hostile inputs answered by both implementations and refused` |

## Where the two platforms disagree, and why that is the point

| | Linux (this run) | Windows (the same commit) |
|---|---|---|
| Suite | `Ran 605 tests`, `skipped=2` | `Ran 594 tests`, `skipped=24` |
| Red-team | 10 of 10 refused, 0 skipped | 9 of 10 refused, **1 skipped** |

On Windows one hostile fixture is a symlink, and a host without `SeCreateSymbolicLinkPrivilege` cannot build it
(`WinError 1314`). Before #186 that path returned silently from an `except OSError`, so the harness tested a
clean package and recorded the outcome as if the implementation had refused the hostile one, and three tests
were never collected without anyone being told. After #186 the case is `SKIPPED` with its reason, it can never
count as a pass, and the suite's own count is what the docs quote — which is why the Chinese README says 605 and
this host prints 594.

The two numbers are not a discrepancy to be reconciled away. They are the same fact stated twice: **the case
that cannot be built is reported as not built.**

## What this does not establish

- Not an external node. The same author wrote the code, the verifier and the harness; agreement between two
  implementations under one author is a consistency check, not independence.
- Not a security claim. A PASS means: within the observed evidence boundary, no violation was detected.
- One Linux distribution, one Python version. Nothing here speaks to 3.10, 3.13, ARM, or musl, beyond what the
  CI matrix already runs.
- The red-team corpus is ours. Ten inputs refused says the harness can fail things; it does not say the corpus
  is complete.

A run record is a photograph, not a certificate. If you ran it and got something else, open
`.github/ISSUE_TEMPLATE/external-node-report.yml` and paste what you saw — a different answer is more useful
here than a matching one.

## Later note (2026-11-19, same day)

This record is a snapshot of commit `64124b7` and its numbers are not retroactively
edited. `tools/oracle_check.py` and `tests/test_oracle.py` were added afterwards, so the
live suite count measured by `tools/check_doc_facts.py` is now 608, not 605. The Linux
platform behaviour in the tables above (2 skipped, `10 of 10 hostile inputs refused`) was
measured at `64124b7`; a fresh Linux run at the merged commit would be needed to restate it
for the new count, and this document does not claim that run happened.
