# Nineteen checks, and a package for each one that makes it fail

**2026-11-19.** A check nobody can drive to FAIL is decoration: it costs a line
in the report and proves nothing. This page collects the opposite evidence —
for every check, at least one artefact a reader can run which makes that check
say FAIL.

Two sources, because two checks cannot be reached from inside a package:

| source | what it is | which checks it covers |
|---|---|---|
| `conformance/cases` | thirty-six packages, each broken in one declared way (`tools/export_conformance.py`) | S1–S8, S10–S15, S17, S18 |
| `tools/outsider_audit.py` | a real FreeTSA RFC 3161 token and four mutations of it; a head pinned outside the package and a rollback that only that pin can see | S16, S9 |

S9 cannot be reached from inside: a rolled-back package is internally
perfect — every hash, every checkpoint head, every seal recomputed. Only a
value observed elsewhere can tell it from the original, so the artefact for S9
is a *pair*: the pin, and the package that contradicts it. S16 likewise needs a
token signed by a key we do not hold; a self-minted "correct" one would prove
nothing, but mutating the real one is exactly reproducible.

## The matrix

Run `python3 tools/check_falsifiability.py` (after exporting the suite). Output
as measured on 2026-11-19:

| check | artefacts that force FAIL | first artefact |
|---|---|---|
| S1 | 1 | `11-add-an-undeclared-file` |
| S2 | 2 | `14-mismatch-agent-identity` + deep: an event naming another agent |
| S3 | 1 | `13-impossible-calendar-date` |
| S4 | 3 | `07-flip-one-byte-in-evidence` |
| S5 | 3 | `10-edit-the-evidence-root` |
| S6 | 2 | `17-tamper-the-seal` |
| S7 | 1 | `32-rewrite-index-metadata-content-untouched` |
| S8 | 2 | `32-rewrite-index-metadata-content-untouched` |
| S9 | 1 | outsider_audit: a rolled-back package against the old pin |
| S10 | 2 | `33-drop-engine-build-from-the-closure` |
| S11 | 2 | `12-duplicate-a-json-member-name` + deep: a byte-order mark |
| S12 | 2 | `13-impossible-calendar-date` |
| S13 | 4 | `18-replace-merkle-root` |
| S14 | 2 | `24-strip-base64-padding` |
| S15 | 4 | `26-corrupt-an-anchor-inclusion-proof` |
| S16 | 4 | outsider_audit: claim the token dates another file |
| S17 | 2 | `22-edit-a-receipt-body` |
| S18 | 2 | `30-edit-a-policy-artefact` |

**Nineteen of nineteen. Zero holes.** The tool exits non-zero if that ever
stops being true, and CI runs it inside the second-implementation job, where
the suite is already exported.

## What the uneven column says

One check still rests on a **single** artefact: S7. Where the five
single-sample checks used to be, four now have a second, differently shaped
mutation, and writing those second shapes found a real defect rather than a
second confirmation: an event naming another `agent_id` passed both S2 and S3
(F-007, fixed here, regression test `tests/test_identity_in_lifecycle.py`).

S7's second shape did not produce a fail, and that is not a hole in the check:
S7 only runs when the package carries an index metadata digest to compare
against, and the clean fixture does not, so the mutation has nothing to
contradict. A package that makes no claim cannot be caught lying about it. The
single S7 sample is the case where the claim exists and the bytes disagree.

This is the honest reading of the table: it certifies that every check *can*
fail, not that every check fails for *every* shape of attack. The next
strengthening is not a new check; it is a second and third mutation for those
five single-sample checks.

## Reproduce

```
$ python3 tools/export_conformance.py      # 36 cases, ~2-3 min
$ python3 tools/check_falsifiability.py    # prints the table, exits 0 with no holes
```

S16's four mutations run locally against `tests/fixtures/anchor/freetsa.tsr`
(a real TSA signature over `anchored_head.json`, taken 2026-11-17T08:11:35Z);
no network is touched.

## Why this is worth publishing

Most verifier projects can list their checks. Fewer can hand a stranger a
package that breaks each one. The difference between those two claims is the
difference between "we check this" and "you can check that we check this".
