# External node 001 — Wang Guigui, on a host we do not control

Received 2026-11-19 10:49 +0800 by email, in reply to a request to run the suite somewhere
else. Reported here verbatim in substance; nothing was re-worded to make the result
look better, and the part that found a bug is kept.

## Who ran it, and where

| field | value |
|---|---|
| operator | Wang Guigui (Correctover — AI Reliability) |
| host OS | Debian GNU/Linux 13 (trixie), kernel 5.10.134 x86_64, container |
| Python | 3.12.14 |
| privileges | unprivileged, uid 1001, no `sudo` |
| install | none — clean clone, no `pip install`, README commands run verbatim |
| HEAD at run time | `8a95747a72de3c72c2556a42137e921640200b40`, committed 2026-11-19T02:16:42Z |

## What he got

1. `python -m uibc_core.cli demo` — all eight steps behaved as advertised, including the
   pinned-key `FAIL` on the substituted-key seal (step 8).
2. `python -m unittest discover tests` — **`Ran 605 tests in 61.8s`, `OK (skipped=22)`, exit 0.**
3. `python independent_verifier/cross_check.py` — **exit 1**, two rows disagreeing:

```
fixture:duplicated   S4   V4   FAIL           PASS   MISMATCH
fixture:duplicated   S5   V5   INCONCLUSIVE   FAIL   MISMATCH

checks compared: 70, mismatches: 2
AGREEMENT: FAIL - SPEC BUG
```

## Why this receipt matters more than a clean one would

The two mismatches land exactly on the defect this repository had already filed against
itself: duplicated `evidence_id` was being answered by a structural check in one
implementation and by the identifier rule in the other. He found it from the outside, on a
different OS, without being told where to look — which is the only kind of confirmation a
self-report can never be.

He then did something not asked for: fetched `refs/pull/169/head` (`343d906`) and re-ran
`cross_check.py` there — **70 checks, 0 mismatches, `AGREEMENT: PASS - spec determinism holds`,
exit 0** — and noted that the default branch still carried the bug until the fix merged.
That fix is now in `main` as #186 (`cedbfa9`), together with the symbol-link skip repair (#186)
and a Linux run record (#189).

## Checked on our side (2026-11-19)

Quoting figures nobody here can recompute is the smallest form of hearsay, so
`tools/verify_external_node_report.py` exports `8a95747` and runs the same two
commands on hardware we control:

```
exported 8a95747 (713 files)
  compared: 70  mismatches: 2  agreement: FAIL - SPEC BUG
  tests: 605  skipped: 1
VERDICT: MATCHES THE RECEIPT (605 tests, 2 mismatches)
```

Both figures match his exactly. The skip count does not: he saw 22, we see 1,
because skips follow which extras are installed - which is also why no document
should carry a skip count, and why the suite size is now cited from
`docs/EVIDENCE-INDEX.md` rather than typed.

What the match establishes: **605 and 2 are properties of that commit, not of
his machine.** A host with a different Python and a different operating system
arrived at the same pair because the code produced them.

What it does not establish: that his host behaved like ours, or that his report
was audited. It is a recomputation, not a review of him.

## The honest limit on this node

He is a correspondent in the same W3C working group as this project. That makes this
**third-party execution** on a machine we do not control, with a named operator who has no
incentive to flatter us — but it is not third-party *interest*: he is not a disinterested
auditor, and one node is a node, not a sample. It also arrived because we asked; a node
that arrives because it was asked for is still weaker evidence than one that arrives
unprompted.

Counted at stage **L4 external node**, value **1**. The three lines that are still zero —
external document citing this repository, adoption by any group, and independent
reproduction by someone with no connection to the project — stay zero and stay visible.

## What is now owed back to him

Current `main` (post-#186/#195/#197) is not the branch he tested. A re-run on today's
`main` is the next ask, and the natural way to close the loop: his first run found a bug,
his second can confirm the fix, both on his own hardware.
