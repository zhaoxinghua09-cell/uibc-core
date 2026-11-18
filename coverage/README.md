# CDP-1 — Coverage Disclosure Ledger

A verifier can be asked one question it usually answers with silence: **"which of your
requirements have no test?"** This directory answers it in a file that can be checked by
someone who does not trust the answer.

## Files

| file | role |
|---|---|
| `cdp-1.schema.json` | JSON Schema for a ledger. Three statuses, and the `reason/owner/review_by` fields become mandatory the moment a status is not `EXERCISED`. |
| `ledger.uibc-core.json` | This project's ledger, **generated from repository evidence**, not typed by hand. |
| `../tools/coverage_ledger.py` | `--build` regenerates from `docs/CHECK-MATRIX.md`, `docs/conformance/vectors.json` and `benchmarks/submissions/`; `--check` validates. |

The normative form of these rules is drafted in
[`drafts/draft-zhao-cdp-coverage-disclosure-00.md`](../drafts/draft-zhao-cdp-coverage-disclosure-00.md)
— **a local draft, not submitted** to any registry.

## Three rules

1. **Silence is not a pass.** Every entry carries a status. An entry without one invalidates the ledger.
2. **A gap must be named.** `UNTESTED` and `EXEMPT` entries require a `reason`, an `owner` and a `review_by` date. "Not tested" alone is insufficient — it has to say why and who will close it.
3. **The ledger is derived, not authored.** `--build` reads the attack matrix, the conformance vectors and the benchmark records. A specification change that leaves the ledger stale fails `--check` (statement digests no longer match).

## Four statuses, not three

`EXERCISED` / `UNTESTED` / `EXEMPT` describe *our own* surface. When a ledger covers a project we
do not control, a fourth status is required: **`NOT_PUBLIC`** — the publisher has not disclosed
enough for the entry to be decided. `NOT_PUBLIC` carries a reason and may not be counted as a
pass. A peer ledger that turns silence into a pass is invalid under the same checker.

`disclosure_completeness` is therefore defined as `(total - not_public) / total`: the share of
entries on which a public disposition exists. It is `1.0` for our own ledger (we can see all of
it) and roughly `0.57–0.67` for the three peer ledgers, because the unobservable rows are
labelled rather than guessed.

## Peer ledgers

`coverage/peers/` holds ledgers built **only from public facts** for three projects in the same
neighbourhood: `aac.cdp.json`, `eqr.cdp.json`, `asqav.cdp.json`. They are not accusations: each
`NOT_PUBLIC` row states what was looked for and what was not found on the measurement date.

## Run it

```bash
python tools/coverage_ledger.py --build   # rebuild from local evidence
python tools/coverage_ledger.py --check   # exit 1 on any violation
```

Current output on `main` (2026-11-19):

```
BUILT coverage/ledger.uibc-core.json  entries=20 exercised=19 untested=1 named_gap_ratio=1.0
OK cdp-1  own entries=20 exercised=19 untested=1 not_public=0 disclosure=1.0 named_gap_ratio=1.0 peers_validated=3
```

## What the single `UNTESTED` entry says

`R1` — "every normative MUST in the specification is enumerated as its own ledger entry
with a test mapping" — is **not done**. The 18 checks in `docs/CHECK-MATRIX.md` are
exercised (36 attacks, none of the checks unreached), but the specification's normative
statements are not yet enumerated one by one. The ledger says so, names the owner and
sets a review date, instead of letting a reader assume 100% coverage.

That disclosure is the point. A format that only lists what passed has no way to express
"here is what I did not test", and a relying party cannot price a risk it is not told about.

## Why this is not a marketing table

The same structure already exists where certification is real: DO-178C, ISO 26262,
IEC 62304 and ASPICE all require bidirectional requirement-to-test traceability, and their
tooling treats "requirements without test coverage" as a first-class, visible state. Agent
receipt specifications publish formats, vectors and pass rates; as of 2026-11-19 none of
the twelve surveyed systems publishes this object. See
`../../docs/COMPETITIVE-STATE.md` and the survey in `D:\Workbuddy\发布前审查_20261119\`.

## What CDP-1 does not prove

- that an `EXERCISED` test is a *good* test (reach, not strength, is what the matrix records);
- that the requirement list is complete — completeness of the enumeration is itself `R1`, and it is currently untested;
- that the ledger was not edited after generation: that requires the signature and the timestamp anchor, which are `signature: null` today and are the next step.
