# A written oracle, and what it still cannot see

`cross_check.py` asks whether two implementations agree. That question cannot rule out
both implementations misreading the specification the same way: agreement is evidence
of determinism, not of correctness.

`tools/oracle_check.py` asks a different question. The expected verdict and the expected
first failing check are written into the tool **before** it runs, from `fixtures/EXPECTED.md`,
the `duplicated` line in `benchmarks.md`, and the committed incidence table in
`docs/CHECK-MATRIX.md`. Each implementation is then judged against that table, not against
the other. A shared misreading fails here even when the two agree.

Run: `python tools/oracle_check.py` — exit 0 means every scored cell matched.

## Measured 2026-11-19, Windows, Python 3.13

**19 cases, 0 cells disagreeing with the oracle, `ORACLE: PASS`, exit 0.**

| case | what is broken | expected | first failure |
|---|---|---|---|
| oracle-clean | nothing | PASS | — |
| oracle-tampered | bytes appended to an evidence file | FAIL | S4 |
| oracle-deleted | evidence file removed | FAIL | S4 |
| oracle-duplicated | index entry duplicated | FAIL | S5 |
| oracle-unsealed | `signatures/seal.json` removed | FAIL | S6 |
| oracle-s12-id-only | duplicate id, **re-sealed**, root repaired | FAIL | S12 |
| oracle-s01-undeclared-file | file added under `evidence/` | FAIL | S1 |
| oracle-s02-identity | `agent_id` does not match the index | FAIL | S2 |
| oracle-s03-calendar | 30 February in the lifecycle log | FAIL | S3 |
| oracle-s07-index-metadata | index metadata rewritten, content untouched | FAIL | S7 |
| oracle-s08-log-truncated | lifecycle log truncated under a checkpoint | FAIL | S8 |
| oracle-s10-closure | `engine_build` dropped from the closure | FAIL | S10 |
| oracle-s11-duplicate-member | duplicate JSON member name | FAIL | S11 |
| oracle-s13-merkle-root | Merkle root replaced | FAIL | S13 |
| oracle-s14-base64-padding | base64 padding stripped | FAIL | S14 |
| oracle-s15-anchor-time | anchor dated 30 February | FAIL | S15 |
| oracle-s16-token-byte | one byte flipped in the RFC 3161 token | FAIL | S16 |
| oracle-s17-receipt-body | first receipt body edited | FAIL | S17 |
| oracle-s18-policy-artefact | policy artefact edited after sealing | FAIL | S18 |

**Coverage: 17 of 19 checks have a written expectation.** S9 (a rolled-back package
against an old pin) and S19 (freshness) do not: both need state carried in from an
earlier run, and neither can be built by a single CLI invocation. That is the honest
size of the claim "19 checks": seventeen of them can be made to fail on purpose and
their failure predicted.

## The ordering rule is part of the oracle

The report is not printed in check order. On a duplicated package the reference verifier
returned `S11, S1, S2, S3, S4, S12, S7, S8, S5, S6` in that sequence. So "the first check
that failed" is undefined until the ordering is fixed, and a claimed first-failure code
with no stated ordering rule cannot be checked by anyone else. This tool fixes it:
**lowest check number that fails**.

The first draft took report order and duly reported a disagreement between the two
verifiers that did not exist. Recorded here rather than quietly fixed.

## What the second implementation actually sees — a finding, not a footnote

The independent verifier implements V1–V6. Every case whose expected first failure is
above S6 is therefore **outside its sight**, and the tool records that as `n/a` instead of
scoring it. `oracle-s12-id-only` shows why that matters: the reference verifier returns
`FAIL` at S12 while the independent one returns **`PASS`**. It is not lying. It does not
implement the identifier rule, so on a package that breaks only that rule it has nothing
to object to.

That is the concrete measure of how much "two implementations agree" is worth. They agree
on the six checks both implement, and beyond that the second implementation contributes
nothing. Restating the qualitative note in `INDEPENDENCE.md` as a number: agreement covers
**6 of 19 checks**, and 13 checks have one implementation only.

## What this is not

- **Not independent judgement.** Expectations were drawn from documents this project
  wrote, and the S7–S18 rows come from `docs/CHECK-MATRIX.md`, which shares provenance
  with the mutation functions in `tools/outsider_audit.py`. These rows lock in verdicts
  and first-failure codes against regressions; they do not constitute an outside opinion.
- **Not exhaustive.** One mutation per case, one host, one Python version. A mutation that
  breaks several things at once has no single expected first failure, so none is claimed.
- **Not a coverage claim.** A check that no case reaches is a check with no evidence here,
  however long the list of checks is.

Adding a case means writing the expected verdict and first failure down **first**. Editing
the table after seeing an output is the failure mode this tool exists to prevent.
