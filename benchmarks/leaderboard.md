# Leaderboard

Generated from `benchmarks/submissions/*.json` by `benchmarks/build_leaderboard.py`.
Re-run `python benchmarks/run_benchmarks.py` to reproduce a row; the record carries the
measured commit and machine so a reader can tell whether two rows are even comparable.

**Suite runs**

| implementation | commit | mutation open (false accepts) | pinned | head-pinned | redteam refused | skipped | machine |
|---|---|---|---|---|---|---|---|
| uibc-core | `21f3abd` | 2/21 (9.5%) | 1/21 (4.8%) | 0/21 | 12/15 | 0 | Linux py3.12.11 |
| uibc-core | `21f3abd` | 2/21 (9.5%) | 1/21 (4.8%) | 0/21 | 11/15 | 1 | Windows py3.13.18 |

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
