# The neighbourhood, surveyed rather than admired

**2026-11-19.** Every figure below comes from one PyPI JSON request and one
GitHub REST request per project, stored in `docs/PEERS.json`. Nothing is quoted
from a README, because a README is what a project chose to say about itself.

## Read this first: these are not all competitors

| project | what it actually is |
|---|---|
| `agent-action-capsule` | **same problem, different answer** — an agent action capsule with a SCITT profile and a public log |
| `agent-evidence-vectors` | **same problem, different answer** — conformance corpora and reference verifiers for agent evidence records |
| `sigstore` | adjacent infrastructure — signing and transparency for software distributions, not for agent runs |
| `in-toto` | adjacent framework — supply-chain attestations, not agent lifecycle evidence |
| `c2pa-python` | adjacent standard — content provenance for media, not agent behaviour |
| `slsa-github-generator` | adjacent framework — build provenance |

Treating the last four as "competitors to beat" would be a category error, and
this page does not do it. What they are useful for is a **bar**: they show what
maturity looks like in this neighbourhood, and they show which properties we
claim that nobody else bothers to claim.

## The published numbers

| | version | releases | last upload | stars | forks | created | issues open |
|---|---|---|---|---|---|---|---|
| **uibc-core** | 0.4.0 (unreleased) / 0.3.3 on PyPI | 4 | 2026-11-15 | 11 | 2 | 2026-09-17 | 5 |
| agent-action-capsule | 0.17.0 | 23 | 2026-11-18 | 2 | 6 | 2026-06-13 | 66 |
| agent-evidence-vectors | 0.37.0 | 43 | 2026-11-15 | — | — | — | — |
| sigstore | 4.5.1 | 67 | 2026-10-20 | 340 | 107 | 2022-01-13 | 58 |
| in-toto | 3.1.0 | 31 | 2026-04-25 | 1,056 | 176 | 2016-05-24 | 61 |
| c2pa-python | 0.39.0 | 78 | 2026-11-12 | 109 | 40 | 2023-09-28 | 13 |
| slsa-github-generator | — | — | — | 611 | 190 | 2022-03-28 | 297 |

In **distribution** we are last of the seven and not close: 4 releases against
23–78, 11 stars against 2–1,056. On the numbers a stranger would use to decide
whether a project is real, we are the least real thing on this page. That is a
fact about reach, not about quality, and the rest of this page is about a
different axis — but it is the first table for a reason.

## The axis we actually lead on: how much of the work can be re-checked

The question a skeptical reader asks is not "what does it claim" but "what can I
re-run". Here is the same survey on that axis, with our own columns filled from
this repository's own gates.

| property | uibc-core | AAC | agent-evidence-vectors | sigstore | in-toto |
|---|---|---|---|---|---|
| verdict is three-valued (pass / fail / **cannot decide**) | yes, 20 checks, INCONCLUSIVE is a distinct outcome | no — `ok: true/false` plus exit codes | no — conformance vectors, binary | mostly binary; transparency log adds ambiguity | binary |
| a second implementation in another language | yes — JavaScript verifier, shares no code | no (scanned: no `.mjs/.js/.rs/.go`) | vectors are consumable by any implementation, none shipped by them | no in this repo | yes, a Go implementation — in a different, adjacent domain |
| CI asserts the two implementations agree case by case | yes — 36/36, and a named check for 30 of 36 | — | — | — | — |
| a stranger's one-command audit, no credentials | yes — `tools/outsider_audit.py`, `VERDICT: OK` in 0.3 s | no equivalent | vectors only | no | no |
| hostile-input suite published with expected verdicts | yes — 10 cases, both implementations must refuse | no | — | — | — |
| external RFC 3161 token verified, and mutations refused | yes — real FreeTSA token, 4 mutations caught | — | — | — | — |
| public transparency log of its own | **no** | yes — 15,134 entries | no | yes — Rekor | — |
| merged contributions accepted by upstream third parties | **zero** | at least three merged (2026-06-26, 2026-07-15 ×2) | — | — | extensive |
| measured cost at 20,000 evidence files | 1.104 s, 60 MiB | not measured by us | — | — | — |

## What this table honestly says

**Lead, by a wide margin, on re-checkability.** Six independent ways for an
outsider to disagree with us — a second implementation, a CI assertion that they
agree, a one-command audit, a hostile-input suite, a public conformance corpus,
and a cost measurement — is more than anybody else on this page maintains
publicly. Two of those (the CI agreement assertion, the one-command audit) we
have not seen anywhere else in this space at all.

**Behind, by a wide margin, on adoption.** Zero rows in the upstream table, no
public log, four releases, eleven stars. No amount of checking changes that; it
changes only when something gets sent, which is the account holder's call.

**The uncomfortable middle: the second implementation.** It is the strongest
thing we have, and by the peer's own RFC 7942 rule it does not count as
independence, because the same author wrote both. It is a property of the code,
not of the world. Calling it "external validation" would be the kind of claim
this repository exists to avoid.

## Where this leaves "beat the competition"

The two facts do not cancel. In a review, "we can prove more about our output
than anyone else here, and nobody has yet used it" is a defensible position, and
it is a more interesting one than "we have more stars". What it does mean is that
the next marginal gain is not another check — it is the first row in the
adoption table, and that needs a release and one person outside this repository.

## Reproduce the numbers

```
$ python3 /tmp/peers.py        # one PyPI + one GitHub request per project
```

The survey script is twenty lines and quoted in `/tmp/peers.py`; the raw
responses are in `docs/PEERS.json`.
