# Robustness benchmark — submission format `uibc-bench/1`

This directory exists so that a robustness claim can be **checked instead of believed**.
It ships the runner, the schema, and this repository's own submission. It does not rank
anyone who has not submitted here, and it does not promote a number that cannot be re-run.

## What is measured

Two suites are driven from the checkout, and both already write their own result JSON;
the runner only merges them. Nothing in the record is typed by hand.

| suite | what it does | cases |
|---|---|---|
| `mutation` | applies 21 mutations to a sealed evidence package and asks the verifier for a verdict in three key modes (`open`, `pinned`, `head-pinned`) | 21 × 3 |
| `redteam` | feeds 15 hostile inputs to a registered agent (path traversal, absolute paths, symlink-out, NaN injection, forged tail receipt, policy-artefact swap, time backfill, …) | 15 |

A mutation that is **accepted** is a false accept. A hostile input that is **refused**
(counted as `FAIL` by the suite) is the expected behaviour; `PASS` is only expected where
the case is documented as pass-by-design (for example an unanchored seal verifying under
`open`, which proves provenance and not authorship).

## Record shape

```json
{
  "schema": "uibc-bench/1",
  "submitter": "org or person",
  "implementation": "name of the verifier",
  "commit": "the commit actually measured",
  "run_at_utc": "ISO-8601 with explicit offset",
  "machine": {"system": "...", "release": "...", "python": "...", "machine_arch": "..."},
  "suites": {
    "mutation": {"total": 21, "modes": {"open": {"accepted": 0, "total": 21, "false_accept_rate": 0.0}, "pinned": {}, "head-pinned": {}}, "cases": []},
    "redteam":  {"total": 15, "refused_as_expected": 0, "passed_by_design": 0, "skipped": 0, "cases": []}
  },
  "claim": {"boundary_sentence": "...", "not_claimed": ["..."]},
  "notes": ["..."]
}
```

Rules the schema enforces by convention:

1. **`commit` must be the commit that was measured**, not the branch you intend to ship.
2. **`machine` is mandatory.** A number measured on one platform is not a number about all platforms —
   this repository produced a 0-test run on Windows purely because of a path-separator defect.
3. **`skipped` is reported separately** and never folded into a pass. A case that could not be
   constructed (no symlink privilege, for example) is a gap, not a success.
4. **`claim.not_claimed` is mandatory.** A submission without a written list of what its numbers
   do *not* support is rejected.

## Run it

```bash
python benchmarks/run_benchmarks.py --out benchmarks/submissions/<name>.json \
    --submitter "<org/team>" --implementation "<verifier name>"
```

One line of output, one record file. The record embeds every case row, so a reader can
re-derive the totals rather than trust them.

## Submit

Add `benchmarks/submissions/<name>.json` in a pull request, plus one sentence saying which
commit it measured and on which machine. A submission is a record, not a claim of superiority:
[`leaderboard.md`](leaderboard.md) is generated from the files present, and lists the
`not_claimed` line beside every score.

## What this is not

- It is not a conformance suite. Conformance is measured separately against the specification's
  own tests and against third-party vectors.
- It is not a security audit. 21 mutations and 15 hostile inputs are a floor, not a ceiling.
- It is not a comparison of implementations with different suite sizes: the totals are published
  precisely so a reader can see when they are not comparable.

> A uibc PASS means: within the observed evidence boundary, no violation was detected. It does not
> claim the agent was correct, safe, or wise; that the recorded inputs were true or complete; or
> that any real-world outcome followed.
