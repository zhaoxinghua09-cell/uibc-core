# uibc-core conformance suite

29 packages. Each began as a correct package and then had **exactly one** thing broken. For each, the manifest records the checks a verifier must report.

This exists so that a second implementer — or a reviewer, or a suspicious stranger — does not have to take our word for anything. Point your verifier at these packages and see what happens.

## Run it with any verifier

```bash
python3 tools/run_conformance.py --verify "python3 my_verifier.py {pkg}"
```

`{pkg}` is replaced with the package directory. Your command must print JSON with:

```json
{"result": "FAIL", "checks": [{"id": "S4", "result": "FAIL"}]}
```

A case counts as passed when your verifier **refuses it** (verdict `FAIL` or `INCONCLUSIVE`) **and names at least one expected check**. The wording of your reasons is not compared — only which checks you refuse on. That distinction is deliberate: refusing without naming the right check means you noticed something was wrong but not what.

Without `--verify`, the suite runs against the verifier in this repo:

```bash
python3 tools/run_conformance.py
```

## What the expectations mean

| field | meaning |
|---|---|
| `expected_checks` | checks that must appear as FAIL; taken from this repo's measured run, not from theory |
| `expected_result` | the top-level verdict this repo produces (`FAIL`, or `INCONCLUSIVE` for cases the format cannot decide) |
| `why` | one line on what was broken |
| `sha256` | over paths plus contents, so a rebuilt archive that drifted is caught |

## What a case cannot test

- reason strings, check ordering, or JSON shape beyond `result` and `checks`;
- anything needing a network, an external timestamp authority or a live endpoint — not reproducible for a stranger, so not a vector.

The suite is paired with a positive control: `fixtures/clean.uibc` must **not** be refused. A suite in which nothing passes only tests pessimism.

## Measured on three verifiers

| verifier | refused + named | refused at all |
|---|---|---|
| this repo, current | 29 / 29 | 29 / 29 |
| this repo, archived v0.2.1 (6 checks) | 0 / 29 | 29 / 29 |
| a verifier that always returns PASS | 0 / 29 | 0 / 29 |

The middle row is why the naming rule exists: the archived version says no to every package but never on the right grounds.

## Regenerating

```bash
python3 tools/export_conformance.py   # rebuilds cases/, manifest.json and the archive
```

Expectations come from `tools/outsider_audit.py`, so the suite and the audit report cannot drift apart.
