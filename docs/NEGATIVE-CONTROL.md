# The gate, tested against itself

A check that has never failed is indistinguishable from a check that cannot fail.
`tools/assert_second_impl.py` was written to catch the second implementation
drifting from the first, and on the day it was added it passed — which proves
nothing on its own. So it was made to fail on purpose, twice in the working tree
and once through the real pipeline.

## In the working tree: the check reacts to what it claims to catch

| what was broken | result |
|---|---|
| S15's verdict forced to pass | names cases 26, 27, 28, 29 — "a failure for another reason is not coverage" — exit 1 |
| S15 removed from the covered set | names the same four as out of scope — exit 1 |
| both restored | `36/36 packages agree`, exit 0 |

The first row is the important one. Forcing a check to pass does not merely
produce a number; it produces the specific failure the suite is supposed to
prevent, and the script named all four packages that expect S15 rather than
reporting a count.

## Through the pipeline: the branch actually cannot move

`docs/SECOND-IMPLEMENTATION.md` claims the coverage figure is enforced by CI.
That claim was tested the only way a reviewer should accept it: a pull request
that removes `S15` from `COVERED` while four packages still expect it.

* pull request **#134** — `NEGATIVE CONTROL: drop S15 from the covered set (must be blocked)`
* the `second-implementation` job completed with **failure**
* `mergeable_state` stayed **blocked** for the entire ten-minute poll (30 samples), against a baseline of 4–5 samples to `clean` for ordinary pull requests
* the pull request was **closed without merging**, and its branch deleted

Before this test, the branch protection required only `test (3.13)`. It now
requires `test (3.13)` **and** `second-implementation`, with `strict: true` and
`enforce_admins: true`, so the gate applies to the maintainer's own pushes as
well.

## What this does and does not establish

It establishes that the coverage claim is machine-enforced on every push and
pull request, and that a pull request which breaks it cannot be merged.

It does not establish that the checks are *correct*, only that they are
*consistent across two implementations*. Two implementations can agree and both
be wrong about the same thing — that is why the conformance suite is judged
against the spec text in `docs/CONFORMANCE.md`, and why `OUTSIDER-RUN.md` exists
for a pass that none of our own machinery performed. External witnesses, as of
this writing: zero.
