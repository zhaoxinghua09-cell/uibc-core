# uibc-core conformance suite

58 packages. **52 must be refused** -- each began correct and then had exactly one thing broken, with the checks a verifier must report recorded in the manifest. **6 must be accepted** -- correct packages, unmutated or grown in a legitimate way, which a verifier must not refuse.

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

It prints `strict 58/58` against the reference verifier and writes
`receipt.json` (command, time, Python, platform, verifier version, manifest
hash, per-case verdicts) so a run can be cited. Point it at any other
implementation with `--verify "cmd {pkg}"`.

A negative control is worth knowing: a verifier that answers `PASS` to
everything scores **6/58** — the six cases that must be accepted — and a verifier
that answers `INCONCLUSIVE` to everything scores the same 6/58 under the default
rule. The suite cannot be passed by refusing nothing, and by default it cannot tell
those two apart either; `--strict-verdict` is how you make it.

## Run it with any verifier

```bash
python3 tools/run_conformance.py --verify "python3 my_verifier.py {pkg}"
```

`{pkg}` is replaced with the package directory. Your command must print JSON with:

```json
{"result": "FAIL", "checks": [{"id": "S4", "result": "FAIL"}]}
```

A mutated case counts as passed when your verifier **refuses it** (verdict `FAIL` or `INCONCLUSIVE`) **and names at least one expected check**. A positive case (`"expect": "accept"`) counts as passed when your verifier **does not refuse it** and reports no failing checks. The wording of your reasons is not compared — only which checks you refuse on. That distinction is deliberate: refusing without naming the right check means you noticed something was wrong but not what.

Because "does not refuse" is the whole accept-side rule, three very different
behaviours score exactly the same 6/58: always answering `PASS`, always answering
`INCONCLUSIVE`, and looking only at the evidence root. Measured 2026-11-27 on the
0.5.6 archive. If you want the suite to also check *what* a verifier concludes, pass
`--strict-verdict`: the verdict must then equal the `expected_result` this repo
declares for the case (01–05 `INCONCLUSIVE`, 06 `PASS`, the 52 mutated ones `FAIL`).
That number was already in the manifest and was never used for scoring. The reference
verifier is 58/58 under both rules; the three stubs above fall to 1/58, 5/58 and 1/58
under the strict one.

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

## Measured on five verifiers (0.5.6 archive, 58 cases)

Measured 2026-11-27 on this machine, same corpus, same command shape.

| verifier | default rule | `--strict-verdict` | the 52 broken | the 6 correct |
|---|---|---|---|---|
| this repo, current | **58 / 58** | **58 / 58** | 52 / 52 | 6 / 6 |
| always returns `PASS` | 6 / 58 | 1 / 58 | 0 / 52 | 6 / 6 |
| always returns `INCONCLUSIVE` | 6 / 58 | 5 / 58 | 0 / 52 | 6 / 6 |
| always returns `FAIL`, naming S1 | 1 / 58 | 1 / 58 | 1 / 52 | 0 / 6 |
| looks only at the evidence root | 6 / 58 | 1 / 58 | 0 / 52 | 6 / 6 |

Four readings worth separating:

- **current refuses exactly the 52 mutated packages** and neither refuses nor misjudges the 6 correct ones.
- **three stubs tie at 6/58 under the default rule** — always-`PASS`, always-`INCONCLUSIVE`, and a roots-only checker. That is the reason `--strict-verdict` exists: under it they separate into 1, 5 and 1.
- **always-`FAIL` gets 1** -- a blanket refusal buys exactly the one case whose expected check happens to be S1.
- **the archived v0.2.1 (6 checks), measured against the 34-package suite it shipped with, scored 0 / 34 while refusing 34 / 34**: it cannot read the tree-and-chain or extended shapes, so its blanket refusal was hiding a forward-compatibility hole. That is a property of the old release, not a defect in the suite; the suite is how it became visible.

The naming rule exists because "no" without the right ground is not a judgement.

## Regenerating

```bash
python3 tools/export_conformance.py   # rebuilds cases/, manifest.json and the archive
```

Expectations come from `tools/outsider_audit.py`, so the suite and the audit report cannot drift apart.

## Decision vectors: the layer above verify

The 58 cases above answer *"does your verifier refuse a broken package?"* They say nothing
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
scores **3/7** — and it is wrong on the one `ALLOW` case and on the **three** `HOLD` cases
(03 no anchor, 04 another key, 05 somebody else's package), because *"cannot verify"* is not
*"not revoked"*. A suite that a permissive stub can pass would be decoration.

### A result file, so a second project can compare without reading this page

```bash
python3 tools/run_decision_vectors.py \
    --gate "python3 my_gate.py {pkg} --revocation {overlay} --pubkey {anchor}" \
    --sut-label "my_gate 1.4" --sut-result sut-result.json
```

The file carries the four things a comparison needs and nothing that has to be trusted:

```json
{"implementation": "my_gate 1.4",
 "corpus": {"suite": "conformance/decisions", "digest": "f59e9f83…", "cases": 7},
 "summary": {"matched": 7, "total": 7},
 "cases": [{"id": "01", "what": "…",
            "expected": {"decision": "ALLOW", "exit": 0},
            "observed": {"decision": "ALLOW", "exit": 0},
            "verdict": "MATCH"}]}
```

Three properties are measured, not asserted:

* **the digest is over the suite bytes, in a fixed order** — not a commit id, because a
  stranger may hold a tarball or a mirror with no history. Measured: a working-tree checkout
  and a `git archive` of the same commit produce the same digest; appending one byte to one
  file inside the suite changes it (`test_one_byte_of_a_case_moves_the_digest`). Line
  endings count as bytes here: the suite is checked out of git as stored (`core.autocrlf=false`,
  no `eol` rewrite inside `conformance/decisions/`), so a checkout that rewrites text files
  will produce a different digest — visibly different, which is the next-best outcome to
  agreement, and the reason the digest is published rather than kept private.
* **disagreement is recorded per case**, never summarised into a score — the file names which
  cases diverged and what each side actually answered.
* **the scope line travels with the data**: agreement on these seven decisions, nothing more;
  a `MISMATCH` is a difference to look at, not a defect in either side; one run is not an audit.

A digest that depended on checkout order, hash seed or line endings would be a number two
people cannot compare, which is worse than no number.

### The other half: comparing two result files

```bash
python3 tools/compare_sut_results.py mine.json theirs.json [third.json …]
```

It prints one row per case with what every implementation answered, and exits `0` when they
all agree, `1` when any case diverges, `2` when the files **cannot** be compared. The `2` is
the point: a comparison engine that is generous with evidence is worse than none, so it
refuses three situations outright —

* **different corpus digests** — a difference between two files about different inputs is a
  difference about inputs, and publishing it as an implementation difference would be false;
* **files disagreeing on what was *expected*** — that is a corpus defect, and comparing
  observations against two different expectations produces a number nobody can defend;
* **the same label on two files** — either the same run twice, or an ambiguous name; the
  table would be unreadable either way.

Divergence is printed, never scored: every divergent case keeps both answers, and the
output says the difference is a question about the specification rather than a verdict
about either side.

The seeds are not shipped: rebuilding the suite produces the same cases in shape with
different keys, so it is reproducible as a *test*, not as *bytes*.
