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
| a language-neutral conformance corpus | **written since**: `docs/conformance/vectors.json` (15 vectors) with `tools/conformance_check.py`, which imports nothing from `uibc_core`. Still missing is the second *complete* implementation, not the corpus |
| signed tarball per release | not implemented; reproduction still depends on a branch |
| ISO/IEC 24970 clause-by-clause mapping | referenced, not mapped |
| reverse interoperability (they verify us) | no peer has been asked, so every such cell is unknown |
| a human expert, not a model | nothing in this log substitutes for one |

## Round 30 — an outsider run on a machine we do not own (2026-11-17)

Not a review round: a stranger-simulation. A Linux cloud host with no credentials, a different
network path, Python 3.12, clone of `main` at `e6519c3`. What it changed is recorded here because
two of its findings were defects, not opinions.

| step | command | result |
|---|---|---|
| clone + tests, **without** the `verify` extra | `python -m unittest discover -s tests -p "test_*.py"` | `Ran 295 tests ... OK (skipped=7)` — no failures, three anchor modules skip with the install line |
| tests **with** the extra | `pip install -e ".[verify]"` then the same | `Ran 305 tests ... OK (skipped=6)` |
| language-neutral corpus | `python tools/conformance_check.py` | `15/15 vectors reproduced by a non-uibc implementation` |
| corpus byte equality | `python tools/conformance_vectors.py --check` | `MATCH: 15 vectors reproduce exactly` |
| red team | `python tools/redteam_suite.py` | 15 cases; **RT03 returned PASS** (defect, below) |
| citations | `python tools/check_citations.py` | 41/45, failure set almost disjoint from the local run — see `docs/CITATION-REACHABILITY.md` |
| attestation | `python tools/attest.py` | `files_hashed=393`, `manifest_sha256=090a2198…4983`, commit `e6519c3`, version 0.3.3 |
| anchor bytes (the 3.11 CI failure) | `git hash-object tests/fixtures/anchor/anchored_head.json` | blob `3bb43a83…`, file sha256 `4ad23d91…`, 276 bytes — the CRLF fix holds on Linux, so the platform-specific failure is gone |

### Defect found: a symlink could point the verifier outside the package (RT03)

The case replaced an evidence file with a symlink to a file outside the package and the verifier
answered **PASS**, because it hashed whatever the path resolved to. A package that can make a
verifier read an arbitrary file is not a package that describes itself.

Fixed in `uibc_core/verify.py`: S4 now resolves each evidence entry and fails when it is a symlink
or resolves outside `evidence/`. Regression test: `tests/test_v15_symlink_containment.py` (skips on
Windows without symlink privilege, runs on Linux).

### Defect found: the citation checker reported network weather as dead links

Two of the four "failures" reproduced as 200 with a browser user agent, and one was fixed by an
alternate canonical source. Fixed in `tools/check_citations.py`: browser UA, retry on 5xx/429, and
an `ALTERNATES` map so a mirror counts. Details and the per-link table live in
`docs/CITATION-REACHABILITY.md`.

### What this round did **not** do

It is still our own code running on our own cloud host with our own credentials for the clone. It
demonstrates that the repository works for a machine we do not sit at; it does not make us a third
party. "A human expert, not a model" stays open.
## Round 31 — corpus extended to structure and anchoring (2026-11-17, same day)

Round 30's own closing line was the most damning item in it: "the corpus still
covers only canonicalization and Ed25519, with no second full implementation." Half
of that is now closed, and the record says which half.

**What changed.** `docs/conformance/vectors.json` went from 15 to 23 vectors, schema
`@2`, three new kinds:

* `receipt_digest` (3) — SHA-256 over the RFC 8785 JCS bytes of an envelope, incl.
  one with a nested `counts` object and a `policy_digest`, one with CJK text;
* `receipt_chain` (3) — the linear link from draft-marques-asqav-compliance-receipts-01
  §4.3: receipt[0] carries 64 zeros, every later receipt carries its predecessor's digest.
  One valid chain, one with a single corrupted link (envelopes untouched, so only the link
  is wrong), one with a non-zero genesis;
* `anchor_binding` (2) — the shipped RFC 3161 token must bind `anchored_head.json` and must
  not bind `ots_head.ots`. Both use the real token, not a stub.

**How it was checked, and by what.** `tools/conformance_check.py` imports nothing from
`uibc_core`: its own canonicalizer from `json`/`hashlib`, signatures via third-party
`cryptography`, chain links recomputed from the published rule, and the token's
`messageImprint` read with `asn1crypto`. Measured: **23/23 vectors reproduced by a non-uibc
implementation**.

**What this round does not close, stated rather than implied.** There is still no second
*implementation* — we ship the object to measure against, not the measurer's code, and
Tracekit and agent-receipts ship both. Receipt **schema** validation, **policy** resolution
and **Merkle inclusion** still have tests and not vectors, so `docs/INTEROP-MATRIX.md` keeps
those cells as untested. The new vectors also deliberately contain no floats: the corpus tests
structure and linking, not ECMAScript number formatting.

**One trap worth recording.** `asn1crypto` returns the token's encapsulated content as a
`ParsableOctetString`; `token["content"]["encap_content_info"]["content"]["message_imprint"]`
raises `TypeError: 'ParsableOctetString' object is not subscriptable`. The imprint lives one
`.parsed` hop further in.

## Round 32 — Merkle inclusion and policy digests join the corpus (2026-11-18)

Round 31 closed the chain and anchor gap and left two named holes: Merkle inclusion had
tests but no vectors, and a `policy_digest` was a number nobody outside could recompute.
Both are now vectors. Corpus 23 → **29**, schema `@3`.

**New kinds.**

* `merkle_root` (2) — five leaves and one leaf. RFC 6962: leaf = SHA-256(0x00‖leaf),
  node = SHA-256(0x01‖left‖right), split at the largest power of two below the length, odd
  tail promoted rather than duplicated. A one-leaf tree's root is that leaf, which catches
  implementations that hash an inner node anyway.
* `merkle_inclusion` (3) — one genuine path, one tampered leaf, one right-leaf-wrong-index.
  The third is the interesting one: same leaf, same proof, index 1 instead of 2, and a
  conforming verifier must say `not_included`, because the index decides left/right at every
  step. It is the cheap shortcut a verifier that ignores the index would happily pass.
* `policy_digest` (1) — SHA-256 over the JCS of a retained policy artefact, with CJK text in
  the artefact so escaping differences surface.

**How it was checked.** `tools/conformance_check.py` rebuilt the whole Merkle layer
independently — its own `_leaf`/`_node`/`_root`, and `_root_from_path` walking the path
top-down using the split rule and the index, not our bottom-up `fn/sn` walk. Measured:
**29/29 vectors reproduced by a non-uibc implementation**; `--check` → `MATCH: 29 vectors
reproduce exactly`; full suite `Ran 306 tests … OK (skipped=2)`.

**Still not closed, same wording as before, because it has not changed.** No second
*implementation*; no end-to-end receipt schema validation; no floats anywhere in the corpus
(these vectors test structure, linking, trees and policy digests, not ECMAScript number
formatting).

One more honest note: the independent checker is written by the same maintainer as the
implementation. It imports nothing from `uibc_core` and its Merkle rebuild is a separate code
path, but "written by someone else" is a claim we still cannot make, and Round 30's public
re-run register is the only place where a genuinely foreign run is recorded.

## Round 33 — the rail meets a foreign corpus (2026-11-18)

`uibc_core/aee.py` existed since #65 and had never been pointed at the corpus it
was written for. Today it was.

| item | value |
|---|---|
| corpus | `probityai/agent-evidence-vectors` 0.37.0, suiteRevision 32 |
| corpus digest | `bf3e5befd71640757ff1b3f0af63507364b823b5e3f9059678f72f64a46e11c1` |
| manifest | `5f828f57e4e6845a48d802ae6c9a32d3365b092aa7d23969a2daa7438ac7f368` |
| command | `uv tool run "agent-evidence-vectors==0.37.0" --verifier "python -m uibc_core.aee"` |
| result | **288 vectors, 288 pass, 0 fail**; `rail: external`; `vectorsExecuted 288 of 288`; `suiteRefusals 0`; `reasonParityMismatch 0` |

What this does and does not settle. It settles the sentence that appeared in Rounds
30–32: "no second implementation, nobody has run us independently" — **for the AEE
rail**. A corpus written by someone else, driving verifiers through its own contract,
executed our code across every vector with no refusal. It does **not** settle the same
sentence for uibc-core's own 29-vector corpus: that checker is still ours.

Windows caveat worth keeping: the corpus tool crashes printing its report path when the
suite runs from a `D:` directory (`ValueError: path is on mount 'D:', start on mount 'C:'`).
Run it from a `C:` directory with `PYTHONPATH` pointing at the checkout; the verdicts are
unaffected.