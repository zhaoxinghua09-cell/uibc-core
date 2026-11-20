# uibc-core conformance suite

36 packages. **30 must be refused** -- each began correct and then had exactly one thing broken, with the checks a verifier must report recorded in the manifest. **6 must be accepted** -- correct packages, unmutated or grown in a legitimate way, which a verifier must not refuse.

Both halves matter. A suite of only broken packages gives full marks to a verifier that refuses everything, which is worthless.

This exists so that a second implementer — or a reviewer, or a suspicious stranger — does not have to take our word for anything. Point your verifier at these packages and see what happens.

## Run it without cloning anything

The archive `uibc-conformance-0.4.1.zip` is self-contained: cases, manifest,
expected results, the runner and its README. Two commands, no repository, no
account:

```bash
python -m pip install uibc-core==0.4.1
python run.py
```

It prints `strict 36/36` against the reference verifier and writes
`receipt.json` (command, time, Python, platform, verifier version, manifest
hash, per-case verdicts) so a run can be cited. Point it at any other
implementation with `--verify "cmd {pkg}"`.

A negative control is worth knowing: a verifier that answers `PASS` to
everything scores **6/36** — the six cases that must be accepted. The suite
cannot be passed by refusing nothing.

## Run it with any verifier

```bash
python3 tools/run_conformance.py --verify "python3 my_verifier.py {pkg}"
```

`{pkg}` is replaced with the package directory. Your command must print JSON with:

```json
{"result": "FAIL", "checks": [{"id": "S4", "result": "FAIL"}]}
```

A mutated case counts as passed when your verifier **refuses it** (verdict `FAIL` or `INCONCLUSIVE`) **and names at least one expected check**. A positive case (`"expect": "accept"`) counts as passed when your verifier **does not refuse it** and reports no failing checks. The wording of your reasons is not compared — only which checks you refuse on. That distinction is deliberate: refusing without naming the right check means you noticed something was wrong but not what.

Without `--verify`, the suite runs against the verifier in this repo:

```bash
python3 tools/run_conformance.py
```

## What the expectations mean

| field | meaning |
|---|---|
| `expect` | `"accept"` on the five correct packages; absent on the mutated ones |
| `expected_checks` | checks that must appear as FAIL; taken from this repo's measured run, not from theory |
| `expected_result` | the top-level verdict this repo produces (`FAIL`, or `INCONCLUSIVE` for cases the format cannot decide) |
| `why` | one line on what was broken |
| `sha256` | over paths plus contents, so a rebuilt archive that drifted is caught |

## What a case cannot test

- reason strings, check ordering, or JSON shape beyond `result` and `checks`;
- anything needing a network, an external timestamp authority or a live endpoint — not reproducible for a stranger, so not a vector.

The suite is paired with a positive control: `fixtures/clean.uibc` must **not** be refused. A suite in which nothing passes only tests pessimism.

## Measured on three verifiers

| verifier | passed (of 36) | refused (of 36) |
|---|---|---|
| this repo, current | **36 / 36** | 30 / 36 |
| this repo, archived v0.2.1 (6 checks) ¹ | **0 / 34** | 34 / 34 |
| always returns PASS | 6 / 36 | 0 / 36 |
| always returns FAIL naming S1 | 1 / 36 | 36 / 36 |

Four readings worth separating:

- **current refuses exactly the 29 mutated packages** and accepts all five correct ones.
- **archived v0.2.1 refuses all 34**, the correct ones included: it cannot read the tree-and-chain or extended shapes, so its blanket refusal was hiding a forward-compatibility hole. That is a property of the old release, not a defect in the suite; the suite is how it became visible.
- **always-PASS gets 5** -- it clears the positive cases by never refusing, and fails every mutated one.
- **always-FAIL gets 1** -- a blanket refusal buys exactly the one case whose expected check happens to be S1.

The middle row is why the naming rule exists: the archived version says no to every package but never on the right grounds.

¹ measured against the 34-package suite it shipped with; the two cases added since are a positive Ed25519 seal and a flipped signature, and a verifier that cannot parse a package refuses it either way.

## Regenerating

```bash
python3 tools/export_conformance.py   # rebuilds cases/, manifest.json and the archive
```

Expectations come from `tools/outsider_audit.py`, so the suite and the audit report cannot drift apart.

## Decision vectors: the layer above verify

The 36 cases above answer *"does your verifier refuse a broken package?"* They say nothing
about what happens one layer up — `ALLOW` / `DENY` / `HOLD`, and what a revocation overlay
does to that answer. That layer is where a revocation gets silently ignored, so a second
implementer needs fixed inputs there too.

`conformance/decisions/` holds seven packages with their overlays and their expected
decisions:

| case | what | expected |
|---|---|---|
| 01 | correct package, no overlay | `ALLOW` / 0 |
| 02 | correct package + valid owner revocation | `DENY` / 2 |
| 03 | correct package + revocation, no anchor supplied | `HOLD` / 3 |
| 04 | correct package + revocation signed by another key | `HOLD` / 3 |
| 05 | correct package + a revocation belonging to another package | `HOLD` / 3 |
| 06 | one byte appended to an evidence file | `DENY` / 2 |
| 07 | tampered package + valid owner revocation | `DENY` / 2 |

Run it against this repo's gate:

```bash
python3 tools/run_decision_vectors.py
```

Or against any other implementation:

```bash
python3 tools/run_decision_vectors.py \
    --gate "python3 my_gate.py {pkg} --revocation {overlay} --pubkey {anchor}"
```

Your command prints JSON with `decision` (and optionally `exit_code`; if absent, the
process exit code is used). Flags for files a case does not carry are **dropped**, so one
command serves all seven cases: `--revocation {overlay}` disappears on case 01, and
`--pubkey {anchor}` disappears on case 03. The convention is the ordinary `--flag value`
(or `--flag=value`) shape; a command that cannot be expressed that way can be given a
second, plain form with `--gate-plain`.

This runner defect was found by running it: pointed at our own CLI with both flags, two
cases scored as errors and the summary read **5/7** — indistinguishable from a broken gate.
Absent flags are now stripped, and `test_external_mode_through_the_cli_scores_seven_of_seven`
pins it so the next edit cannot quietly reintroduce it.

**Two negative controls, measured** (see `tests/test_decision_vectors.py`): a gate that
answers `ALLOW` to everything scores **1/7**; a gate that answers `DENY` to everything
scores **3/7** — and it is wrong on both `HOLD` cases, because *"cannot verify"* is not
*"not revoked"*. A suite that a permissive stub can pass would be decoration.

The seeds are not shipped: rebuilding the suite produces the same cases in shape with
different keys, so it is reproducible as a *test*, not as *bytes*.

