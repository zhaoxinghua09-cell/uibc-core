# Leaderboard

Generated from `benchmarks/submissions/*.json` by `benchmarks/build_leaderboard.py`.
Re-run `python benchmarks/run_benchmarks.py` to reproduce a row; the record carries the
measured commit and machine so a reader can tell whether two rows are even comparable.

**Suite runs**

`disclosure` is the only column that is not a measurement: it says whether the submitter
publishes a CDP-1 coverage ledger (`coverage/`). A row marked `UNDISCLOSED` is still shown,
with its numbers, but it is **not ranked** — a rate without a statement of what was not
tested cannot be compared to one that has it.

| implementation | commit | mutation open (false accepts) | pinned | head-pinned | redteam refused | skipped | disclosure | machine |
|---|---|---|---|---|---|---|---|---|
| uibc-core | `21f3abd` | 2/21 (9.5%) | 1/21 (4.8%) | 0/21 | 12/15 | 0 | cdp-1 19/20 | Linux py3.12.11 |
| uibc-core | `21f3abd` | 2/21 (9.5%) | 1/21 (4.8%) | 0/21 | 11/15 | 1 | cdp-1 19/20 | Windows py3.13.18 |

**External verifiers measured by `benchmarks/run_external.py`** (same mutant bytes, submitted
command, exit 0 = accept)

| implementation | commit | false accepts | base accepted | verifier command |
|---|---|---|---|---|
| uibc-iverify | `158a82d` | 2/21 (9.5%) | True | `python D:\lgd-work\uibc-iverify\ivcli.py {pkg}` |

`false accepts` counts mutations the verifier accepted, i.e. it believed a mutated package was
intact. `refused` counts hostile inputs rejected as expected. `skipped` counts cases that could
not be constructed on that machine — a gap, not a pass.

A row is a measurement of a named commit on a named machine, not a claim of superiority:
implementations that ship different suites are not comparable, which is why the totals above
are shown beside every rate.

Rows whose `disclosure` column starts with `UNDISCLOSED` are listed for measurement only and
are **not ranked**: a false-accept rate says what a verifier accepted, not what it never tested.
CDP-1 (see `coverage/README.md`) is the file that states the second half, and a submitter who
does not publish it has not made a comparable claim.
