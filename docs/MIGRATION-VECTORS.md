# MIGRATION-VECTORS.md — three cases that must hold across a version boundary

The versioning policy (`VERSIONING.md`) requires three vectors at every boundary. This document states them, the exact recipe to build each one, and **the verdict required before anyone runs it**. An expectation written after the run is a description, not a test.

## M1: old package, new verifier

```bash
python3 -m venv /tmp/old && . /tmp/old/bin/activate
pip install uibc-core==0.3.3
uibc init  --out /tmp/m1                 # build a package with the old tool
deactivate

python3 -m venv /tmp/new && . /tmp/new/bin/activate
pip install -e .
uibc verify /tmp/m1                       # verify it with the current tool
```

| Decision point | Required verdict |
|---|---|
| The package carries everything the old format required | `PASS` (or `INCONCLUSIVE` if the clean fixture is unsigned — check `conformance/manifest.json` for the base case rule first) |
| The old package omits something the new format requires | `INCONCLUSIVE`, naming the missing item |
| Any other outcome | A defect in the new verifier |

## M2: new package, old verifier

```bash
# with the current tool installed
uibc init --out /tmp/m2                    # a package that carries current-only fields
# then, in the old environment
uibc verify /tmp/m2
```

| Decision point | Required verdict |
|---|---|
| The old verifier reads a field it does not know | **`INCONCLUSIVE`** |
| The old verifier returns **`PASS`** | **Protocol-level defect. Do not release.** |
| The old verifier crashes | Poor, but not worse than `PASS` |

This is the most important of the three. `PASS` on input the verifier did not understand is silent failure at the version level, and it is the same defect shape as `F-008` (a field written by every package and read by no check).

## M3: package signed before a key rotation

```bash
uibc keygen --out /tmp/keys-a
uibc init   --out /tmp/m3 --key /tmp/keys-a
uibc keygen --out /tmp/keys-b              # rotate
uibc verify /tmp/m3                       # no pin supplied
uibc verify /tmp/m3 --pin /tmp/keys-b     # pin points at the new key
```

| Case | Required verdict |
|---|---|
| No pin, no record of the old key | `FAIL` — the seal cannot be attributed |
| Pin points at the new key, package signed by the old one | `FAIL`, naming the key mismatch |
| Pin points at the old key and the old key is marked revoked | `INCONCLUSIVE` |
| Pin points at the old key, still valid | `PASS` |

The distinction that matters: an unattributable seal is not "probably fine". `demo` step 7 shows a package that passes without a pin; that step exists to teach exactly this trap.

## Status

None of the three has been run to completion yet. The expected verdicts above were declared before the run, which is the only thing that makes them testable. Until they run green, `VERSIONING.md` section 3's "Forward Compatibility" field cannot honestly be filled in for any release.

## How this gets closed

1. Build the three vectors as scripts under `tools/`, one command each, no manual steps.
2. Record the raw output in `docs/MIGRATION-RESULTS.md` with the date and the two version numbers.
3. Add the outcome to the release record's `Interoperability Test` field.
