# Reproduction record

Required by the gate the maintainers apply to their own material (S7-C5): interpreter,
commands, expected exit codes, observed output, cross-machine status, integrity check.

**As of 2026-11-25. Commit `4e72ee0` (+ uncommitted tools at the time of writing, so this
record describes the branch, not a tagged release).**

## Interpreter and platform

- Python **3.13.18**, Windows **AMD64**
- Reference verifier version reported by `python -m uibc_core.cli --version` → `0.5.5`
- No virtualenv, no extra packages beyond the repository's declared requirements

## Commands, expected and observed

| # | Command | Expected | Observed (2026-11-25) |
|---|---|---|---|
| 1 | `python tools/axis_report.py --out out/axis_report` | 30 cases compared, divergence list empty | `合计 30 例，一致 30，分歧 0。` exit 0 |
| 2 | `python demo/head_chain.py` (with `--repo` if run from outside) | honest chain accepted, 6 attacks rejected | `用例 7/7 符合预期`, `总判定 PASS`, exit 0 |
| 3 | `uibc verify conformance/oracle/cases/oracle-clean --key <seed> --bundle-out X.json --trustlist Y.json` | verdict PASS, trust level `trusted` | `"result": "PASS"`, `"level": "trusted"`, exit 0 |
| 4 | `cosign_head.py verify --file out/head_cosign.json …` | both roles hold, keys distinct | `"ok": true`, `"distinct_keys": 2`, exit 1 on any tampered copy |
| 5 | `python -m pytest -q tests/test_cli_stdout_encoding.py tests/test_iverify_pubkey_pin.py tests/test_bundle_builder_args.py tests/test_status_page.py` | all pass | `26 passed, 5 skipped` |

The seed for case 3 comes from `conformance/oracle/keys.json` (`oracle-clean`). No key is
stored in this repository; the corpus keys are test keys and must not be used elsewhere.

## Cross-machine

**Not verified.** Every number above was produced on the machine named in the gate
directory, Windows AMD64 / Python 3.13.18. A second machine has not run them. Do not read
this record as cross-platform evidence.

## Integrity

```
sha256(conformance/oracle/expected.json)[:16] = 75c4d6dc67ce45ce
```

A mismatch means the corpus changed after this record was written; treat the numbers above
as superseded until re-run.

## What this record does not show

- It does not show that the verifier is correct; it shows what the verifier does.
- It does not show coverage: 30 cases are below the scale of the published corpora we cite.
- There is no second implementation behind these numbers. See the implementation report's
  section 3 for what that costs us.
