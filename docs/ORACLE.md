# A written oracle, and what it does not cover

`cross_check.py` asks whether two implementations agree. That question cannot rule out
both implementations misreading the specification in the same way: agreement is evidence
of determinism, not of correctness.

`tools/oracle_check.py` asks a different question. The expected verdict and the expected
first failing check are written into the tool **before** it runs, derived from
`fixtures/EXPECTED.md` (the hand-derived prior enforced by the fixture generator) and from
the `duplicated` line in `benchmarks.md`. Each implementation is then judged against that
table, not against the other. A shared misreading now fails here even when the two agree.

Run: `python tools/oracle_check.py` — exit 0 means every cell matched.

## The five cases, and why this is a start rather than a solution

| case | mutation | expected verdict | expected first failure |
|---|---|---|---|
| `oracle-clean` | none | PASS | — |
| `oracle-tampered` | appended bytes to an evidence file | FAIL | S4 |
| `oracle-deleted` | removed an evidence file | FAIL | S4 |
| `oracle-duplicated` | duplicated an index entry | FAIL | S5 |
| `oracle-unsealed` | removed `signatures/seal.json` | FAIL | S6 |

Measured on 2026-11-19, Windows, Python 3.13: 5 cases, 0 cells disagreeing, exit 0 —
both the reference verifier and the independently written one match all five rows.

## The ordering rule is part of the oracle

The report is not printed in check order. On a duplicated package the reference verifier
returned S11, S1, S2, S3, S4, S12, S7, S8, S5, S6 in that sequence. So "the first check
that failed" is undefined until the ordering is fixed, and a claimed first-failure code
without a stated ordering rule cannot be checked by anyone else. This tool fixes it:
**lowest check number that fails**. Two implementations can therefore be compared on
first-failure codes even though neither prints them in numeric order.

That difference is worth knowing before it bites: the first draft of this tool took report
order, and duly reported a disagreement between the two verifiers that did not exist.

## What this does not cover, stated plainly

- **Only S1–S6 are reachable by a package built through the CLI.** S7–S18 need packages
  with sealed digests, checkpoints, Merkle proofs, anchors and policy artefacts. There is
  **no oracle for S7–S18** at all; the nineteen checks are not nineteen covered checks.
- Five cases is a floor. The scheduled checks in `docs/CHECK-MATRIX.md` reach more of the
  surface, but a matrix cell is not an oracle: it records that an attack hits a check, not
  what the verdict and first failure must be.
- The expectations came from documents this project wrote. An oracle built from our own
  prior is a consistency instrument, not an external judge. It cannot create independence.
- Single host, single Python version, single mutation per case. A mutation that changes
  several things at once has no single expected first failure, so none is claimed here.

Adding a case to this table requires writing the expected verdict and first failure down
first, then running it. Editing the table after seeing an output is the failure mode the
table exists to prevent.
