# Review log — what was reviewed, by whom, and what changed

This file is the audit trail of the independent reviews this repository has been
through. It exists because a claim like "externally reviewed" is worthless unless a
reader can see which artifact was sent, what came back, and what was changed as a
result. Every receipt referenced here is stored verbatim in `docs/external-review/`.

Two things this log does **not** claim:

* it is not a certification, an audit opinion, or an endorsement;
* the reviewer is a language model (DeepSeek-V3 via the SiliconFlow API), not a
  person, a firm, or a standards body. "External" here means **not us** — a model
  we did not write, with no access to our reasoning — not "human expert".

Reproduce a round: `python tools/lens_review.py --all --go` (writes a dispatch, a
receipt and one hash-chained ledger record per lens).

## Rounds

| # | date | artifact | reviewer | question set | verdict | receipt |
|---|---|---|---|---|---|---|
| 23 | 2026-11-17 | `docs/ECOSYSTEM-MAP.md` v1 | DeepSeek-V3, temp 0 | fixed two-question template | NEEDS-CHANGE | `20261117_23_ecosystem-map-claims-v1_siliconflow_receipt.md` |
| 24 | 2026-11-17 | same, v2 | same | same | NEEDS-CHANGE | `20261117_24_…_v2_…_receipt.md` |
| 25 | 2026-11-17 | same, v3 | same | same | SAFE-AS-IS | `20261117_25_…_v3_…_receipt.md` |
| 26 | 2026-11-17 | `docs/ECOSYSTEM-MAP.md` | same | **expert** lens (standards / regulatory) | CONTINUE | `20261117_26_fourlens-expert_expert_receipt.md` |
| 27 | 2026-11-17 | `README.md` | same | **process** lens (can an outsider reproduce) | CONTINUE | `20261117_27_fourlens-process_process_receipt.md` |
| 28 | 2026-11-17 | `docs/INTEROP-MATRIX.md` | same | **adversary** lens | CONTINUE | `20261117_28_fourlens-adversary_adversary_receipt.md` |
| 29 | 2026-11-17 | `README.md` | same | **outsider** lens (five-minute trial decision) | CONTINUE | `20261117_29_fourlens-outsider_outsider_receipt.md` |

Ledger: `_registry.jsonl` in the `ai-seats-bridge` repository, records `seq=34..40`,
each carrying `prev` and `hash`, so a reader can check that no receipt was inserted
retroactively. The key is read into memory only; the ledger stores its SHA-256
prefix, never the key.

## What each round changed

**Round 23 → 24 (both NEEDS-CHANGE).** Two criticisms were accepted as correct:

1. A statement about NovaFabric's missing second implementation was a *paraphrase*,
   with no location given for the original text. Fixed by quoting verbatim
   ("Neither a second implementation nor that corpus exists yet") and linking the
   section: <https://arxiv.org/html/2609.12582>.
2. Calling Tracekit's two verifiers "two independent verifiers" was unfalsifiable —
   both are written by the same authors. Rewritten as "two verifiers by the same
   authors … (authors' own report, not a third-party replication)".

**Round 26 (expert).** Three findings, all acted on the same day:

* P1: the map leans on arXiv preprints; a committee reader will say "individual
  draft, not an adopted work item". Response: the map now states its source status
  above the table, instead of implying peer-reviewed status.
* P2: verdict words ("verified", "reports agreement") read as legal conclusions to
  a regulator. Response: the map now carries the narrow verdict statement, so the
  words appear next to the sentence that limits them.
* P3: **ISO/IEC 23053 (AI systems using machine learning) was absent.** Accepted —
  it was absent. A section "Standards we did not map" was added, which states that
  we have no mapping and that no project in the map has published one either. This
  is the one finding that added a fact we did not have.

**Round 27 (process).**

* P1: the weakest reproduction step is the dependency on a GitHub branch that could
  move or disappear. Accepted as a real risk; the fix (a signed tarball per release)
  is not implemented, and the README states the branch as it is rather than
  pretending otherwise.
* P2: the two identifiers (`logIndex 2883389783`, DOI `10.5281/zenodo.22456647`)
  could conflict with what a reader opens elsewhere. Accepted — this was a genuine
  ambiguity. The README now names **both** Rekor indices and says which object each
  belongs to, and separates the LGD concept DOI from the package DOI, which is not
  assigned.
* P3: "Rekor entry + SET signature — written and verified" cannot be checked
  without Sigstore's infrastructure. **Partly accepted**: the reviewer is right that
  the README did not say how, and wrong that it needs private keys — the SET verifies
  against the log's published public key. The table now carries a "how you check it
  yourself" column with the exact command.

**Round 28 (adversary).**

* P1: "cells that would require running their code are marked not tested, not
  works" can be turned against us as a way of claiming interoperability without
  testing it. Accepted; the matrix now states that the rejects are one synthetic
  envelope per peer and that **three rejects are not a win**.
* P2: the claim that agent-receipts publishes 8 conformance vectors was itself
  unverifiable from the document. Accepted; a link and the exact path
  (`spec/v0.1/SPEC.md`) were added, with the note that the count is their claim and
  that we did not run their vectors.
* P3: publishing our own failures can read as "failure is expected and acceptable".
  Accepted; both the matrix and the README now say the failed inclusion proof is a
  **defect, not a design choice** and not acceptable output.

**Round 29 (outsider).**

* P1: `external verification nodes: 0` signals a missing part without saying what
  it costs. Accepted; the README now states that zero means independence rests
  entirely on two implementations by one author.
* P2: the name ambiguity is buried under jargon; a clinician may still read UIBC as
  the iron-binding assay. Accepted; the name note moved to the first lines of the
  README, above everything else.
* P3: the reviewer's suggested sentence — "Independent audits by [named entity]
  confirmed the verifier rejects all 15 attack vectors with zero false negatives" —
  **was rejected and not used.** We have no such named auditor and no independent
  audit; the sentence would have been a fabricated endorsement. This is recorded
  because accepting a review does not mean accepting every sentence a reviewer
  offers.

## What is still open after these rounds

| open item | why it is still open |
|---|---|
| a verifier written by someone who is not us | needs a third party; cannot be manufactured |
| a language-neutral conformance corpus | not written; Tracekit and agent-receipts both have one |
| signed tarball per release | not implemented; reproduction still depends on a branch |
| ISO/IEC 24970 clause-by-clause mapping | referenced, not mapped |
| reverse interoperability (they verify us) | no peer has been asked, so every such cell is unknown |
| a human expert, not a model | nothing in this log substitutes for one |
