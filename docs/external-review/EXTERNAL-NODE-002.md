# External node 002 — Iman Schrock, on a Mac we do not control

**Annotation, 2026-11-22, at the operator's request.** The run recorded below did not exercise
our independent verifier. At the time of the run, `independent_verifier/iverify.py` had no
command-line entry point; a caller that shelled out to it read exit code 0 unconditionally,
so `independent=PASS` was recorded without a verification having run. The `independent=PASS`
in this record therefore does not evidence an independent evaluation; the `reference=PASS`
part stands. The defect was fixed in PR #356 (merged 2026-11-21T00:50:18Z, head `2196f9d3`,
with an entry point and value-level rules V1-V10). Cite the corrected run after PR #356 for
both verifiers. The returned artefact and the numbers below are kept unchanged so the
history stays readable.

Received 2026-11-20 13:29 +0800 by email (`team@emiliaprotocol.ai`), as an attachment, not as
prose. The first answer to the same letter was a decline; the run below came two hours later,
unprompted, so the record keeps both.

## Who ran it, and where

| field | value |
|---|---|
| operator | Iman Schrock (EMILIA Protocol) |
| host OS | macOS 27.2.1, arm64 |
| Python | 3.12.14 |
| privileges | not stated; a fresh local copy of the repository, our commands |
| install | none — clean copy, no `pip install`, `tools/external_node_check.py` as published |
| commit at run time | `8160ac60c514a80e729d517a3f0fff7a8fa99810` (2026-11-20T05:11:47Z) |
| run time (UTC) | `2026-11-20T05:13:32Z` |

## What was returned

`external_node_check.py --out external_node_result.json`, unedited:

```
independent=PASS  reference=PASS(12ms)  probes=3/3 rejected  -> CONSISTENT
```

The probe set, as reported by the runner: `value:timestamp-without-zone`, `value:feb29-1900`,
`value:uppercase-uuid` — all three `FAIL` where `FAIL` was expected, 3/3.

| artefact | sha256 | file |
|---|---|---|
| returned receipt | `24e59eac0df14128259233c1e7060f92c1c66f6cee91b91e0a0bdc25649b85f3` | [`EXTERNAL-NODE-002-returned.json`](EXTERNAL-NODE-002-returned.json) |
| our re-run at the same commit, Windows 11 / Python 3.13.18 | `e0c9c3cb033c0dfe4f4b014289205fa8710a05846fa7ee70189d09606d8453f0` | [`EXTERNAL-NODE-002-ours-rerun.json`](EXTERNAL-NODE-002-ours-rerun.json) |

The two receipts are not the same file and are not meant to be: different platform, different
Python, different timings. What they share is the verdict line — `CONSISTENT`, 3/3 probes
rejected — and that is the only thing we claim from them. Side by side:

| | their run | our re-run |
|---|---|---|
| verdict | `CONSISTENT` | `CONSISTENT` |
| independent verifier | exit 0 | exit 0 |
| reference verifier | `PASS`, 12 ms | `PASS`, 11 ms |
| probes rejected | 3/3 | 3/3 |
| commit | `8160ac6…` | `8160ac6…` |

## What this does and does not establish

1. **Two implementations, one author.** `independent` here means "written from the spec without
   sharing code with the reference verifier" — both live in this repository and both were
   written here. A third party executing them does not turn them into independent authorship.
2. **Third-party execution, not third-party interest.** The runner maintains a related
   specification, and the run was requested by us in a cold letter. The independence is in who
   executed the check and on whose machine, not in who asked, and not in whether the asker and
   the runner were strangers. He says so himself in the thread: "You're welcome to count this
   as an external run by EMILIA Protocol."
3. **It is not a security audit.** `CONSISTENT` means the two verifiers agree on the base
   package and reject three packages that must be rejected. It says nothing about whether the
   evidence inside a package is true.
4. **The three negative cases were chosen here.** In the thread the runner proposes exactly
   that criterion and offers to add a fourth case if we want a claim about *both* verifiers
   rejecting them. The current set supports the narrower claim only, and it is recorded as the
   narrower claim.
5. **The number moves by one, not by a trend.** 1 was a node, 2 is two nodes; neither is a
   sample.

Earlier declines are kept in the record too. APS (Tymofii Pidlisnyi) replied on
2026-11-20 14:15 +0800 that the run has to wait until early December; that is a pending
acceptance, not a node, and it is not counted.
