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
---

## Round 34 — the same verdicts from a different machine, a different OS, a different egress

Everything in Rounds 30–33 was produced on one Windows box, through one network egress. That
is the exact weakness a skeptical reader names first: "you ran it in your own environment."
This round re-ran the two central claims from scratch on a Linux host with a different public
IP, an anonymous clone (no token), a fresh dependency install, and a different Python minor
version (3.12.11 vs 3.13 locally).

| check | local (Windows, 3.13) | second egress (Linux, 3.12.11) |
|---|---|---|
| anonymous `git clone` | n/a (working copy) | success, `main` = `816e69f`, 4.7 MB |
| `docs/conformance/vectors.json` bytes | 23178 B, sha256 `51494762…66d043` | **HTTP 200, 23178 B, sha256 `51494762…66d043`** — byte-identical |
| independent checker over the 29 vectors | `29/29 vectors reproduced` | `29/29 vectors reproduced by a non-uibc implementation` |
| full test suite | `OK (skipped=7)` | `OK (skipped=10)` (platform-specific skips, no failures) |
| external corpus, 288 vectors | 288 pass / 0 fail | **288 pass / 0 fail**; `rail: external`; 288 of 288; `suiteRefusals 0`; `reasonParityMismatch 0` |

Commands, so a third party can redo it (Linux):

```bash
git clone --depth 1 https://github.com/zhaoxinghua09-cell/uibc-core.git && cd uibc-core
python3 tools/conformance_check.py                      # 29/29
python3 -m unittest discover -s tests -p "test_*.py"   # OK
pip install "agent-evidence-vectors==0.37.0"
PYTHONPATH=$PWD agent-evidence-vectors --verifier "python3 -m uibc_core.aee"   # 288/288
```

What this settles: the verdicts are not an artifact of one machine, one OS or one Python
build; a stranger who follows the four commands gets the same numbers.
What it does **not** settle: independence of authorship. The 29-vector checker is still
written by this repo's author, and the cross-egress run used our own code. It is a portability
and reproducibility claim, not an independence claim.

### Ownership note added this round

AER-1 is not ours. The corpus our crosswalk consumes is `https://zambo.dev/aer1/corpus.json`
(fetched 2026-11-18: HTTP 200, 15706 bytes, `aer1-evaluated-corpus/1`, `kit_version 1.5.7`,
`draft: draft-zambo-aer1-26`, 143 vectors / 146 checks, `base_corpus_digest
sha256:b9a740e7…ceb87`), defined by Zambo. `docs/AER1-CROSSWALK-RESULT.md` maps to their
*categories*; it is not a vector-level conformance run and must never be described as
"passing AER-1".

Also fixed here: `docs/EXTERNAL-NODE-KIT.md` said strict base64 and Merkle inclusion had no
equivalent implementation in this repository. They do (`uibc_core/aee.py::_b64decode_strict`,
`uibc_core/merkle.py::verify_inclusion`); the honest remaining limitation is that we have not
executed AER-1 vector-by-vector.
## Outside AI review, 2026-11-19 (SiliconFlow / DeepSeek-V3)

A reviewer read a fact pack — narrow claim, measured numbers, our own admitted gaps — and
returned CONDITIONAL with three must-fix items. Recorded here because a review that only
appears in a summary is not a review.

- **Lock model (accepted, fixed).** `freshness.record()` now takes `<state>.lock` with
  `O_EXCL` and raises `Busy`; the verifier reports that as INCONCLUSIVE with
  "observation not recorded" — neither PASS nor FAIL, because neither happened. The
  alternative was two interleaved read-modify-writes keeping one observation and dropping
  the other, which is the failure a high-water mark exists to prevent.
- **Third-party verification count = 0 (accepted, not closed).** Independence still rests on
  two implementations by one author. It is written in the report, not argued away.
- **No CI dispatch on this branch (accepted, not closed).** `pull_request` workflows do not
  fire for this branch; the clean-clone run on a separate host is the evidence instead.
- **"May be covered by RFC 9162" (rejected, with a correction).** RFC 9162 is Certificate
  Transparency version 2; Signed HTTP Exchanges is RFC 8878. CT's STH plus consistency
  proof addresses log-side freshness, not a verifier's own memory — `basis.py` now says
  which layer each covers.
- **Open-mode false accept 9.5% (accepted).** Already published as the uncovered-type
  budget; it now also sits next to the narrow claim rather than in a table alone.

The reviewer saw text only and had no repository access, so this is recorded as a
self-consistency opinion, not as an independent replay.

## Positioning check, 2026-11-19 (S19 is not a new mechanism)

Four sources found while re-checking the claim that a verifier-side high-water mark is novel:

- `draft-chang-delta1-settlement-00` §7.2 and §12.4 require a monotonic `sequence_number`
  and a unique `run_id`, and say validators MUST reject decreases and replays.
- `draft-maintainer-1f916-agent-record` checkpoints Ed25519 logs with RFC 6962 Merkle heads
  and countersignatures by independent witnesses, and defines a three-valued verdict.
- `draft-wilder-scitt-physical-site-engage-receipt-05` states the point plainly: a TEE proves
  it wrote the state it attests, not that the state is the most recent.
- `veritrail` (PyPI 0.3.0) ships hash-chained records and tells operators to publish the head
  hash to an external witness.

So the rule "an older but validly signed package must be refused" already exists in drafts and
in products. What is ours is narrower and should be described that way: an opt-in check inside
an offline package verifier, with the three INCONCLUSIVE cases written down and a red-team case
(RT16) that isolates it. No claim of invention; the `basis.py` note now names the drafts.

## Positioning check, academic axis, 2026-11-19 (rollback protection is a solved problem elsewhere)

The standard and product axes were checked earlier today. The academic axis turns up the same
rule under a different name, plus one number that is worse than ours.

- Nimble (OSDI '23, `http://people.csail.mit.edu/stellal/papers/nimble-OSDI23.pdf`) exists to
  "detect rollback attacks, i.e. detect whether a data item retrieved from persistent storage is
  the latest version". That is S19, stated in one sentence, three years ago, with a Dafny proof.
- `arXiv:2608.16178` (Agent-Native Telemetry) reports 500 adversarial mutation trials covering
  "cross-batch sequence gaps" and "suffix truncations" with a 100% detection rate.
- `arXiv:2609.38266` (Janus) ships an offline verifier over an exported audit bundle that checks
  "sequence continuity" among other findings and reports each by severity. Offline bundle plus
  sequence continuity is our shape.
- `arXiv:2609.31490` rejects stale manifests explicitly (`reject-stale`).

So the mechanism claim stays retired. What remains ours is thin and should stay thin: this
verifier's opt-in check, its three INCONCLUSIVE cases, and RT16.

The uncomfortable part: our mutation benchmark is **21 cases per mode**, against a published 500
trials. 2/21 accepted in the open mode is a 9.5% false-accept rate on a sample small enough that
one case swings it by 4.8 points. Until the corpus is larger, the honest reading is "we have not
measured this well", not "we are stricter". Larger corpus is the next work item, not a claim.

## Mutation corpus, 2026-11-19: 500 cases instead of 21

The published false-accept number came from 21 mutation kinds, one instance each. With a sample
that size one case moves the rate by 4.8 points, so the number could not support any strictness
claim. `tools/mutation_corpus.py` keeps the same families but varies the parameter inside each
family - byte position, field, timestamp, sequence index, attacker key, rollback depth,
truncation length - and lands on **500 deterministic cases** (no RNG; every parameter comes
from the case list).

Measured on this tree with `python tools/mutation_corpus.py`:

| mode | accepted | total | false-accept |
|---|---|---|---|
| open | 60 | 500 | **12.0%** |
| pinned | 20 | 500 | **4.0%** |
| head-pinned | 0 | 60 | **0.0%** |

12.0% is higher than the 9.5% the 21-case benchmark reported, and the reason is structural,
not a regression: the corpus contains 40 key-swap cases and 20 rollback cases, and open mode
has no anchor to judge either by design. Everything else is caught, with the catching check
recorded per case: blob bytes 98/98, signature bytes 64/64, identity 12/12, manifest scalar
40/40, manifest extra 24/24, manifest delete 8/8, lifecycle events 76/76, index metadata
24/24, index-entry deletion 6/6, evidence added 24/24, extra root files 24/24, truncation
40/40. Key-swap: accepted in open (nothing to pin against), refused 40/40 when pinned.
Rollback: accepted in open and pinned, refused 20/20 with an external head.

### Correction: the gap this section first reported did not exist

The first version of this entry claimed a real gap - "dropping evidence index entries is
accepted 5 of 6 times when nothing covers the index". That was wrong, and wrong because of a
bug in our own generator: the cases were written as "keep the first N entries" with N from 1
to 6 against a base package that holds 2 entries, so five of the six "attacks" changed
nothing at all and were counted as accepted. A no-op is not a bypass.

The generator now removes an entry and then offers the attacker the repairs a careful attacker
would make: fix `evidence_count`, fix `evidence_index_digest`, both, both plus a fresh
attacker signature, and finally delete `evidence/index.json` outright. All six are refused in
open and pinned mode, caught by S8, S5, S6, S12, S7 and S1. So the hole was in the test, not
in the verifier - and the way it was found was by asking why a "5 of 6" number looked too
round to be believable.

Still not a strictness claim: 17 families chosen by us, and nobody outside has audited the
list.

---

## Positioning check, 2026-11-19 (second pass): AER-1 -26 closed part of the space

A re-read of the sources behind the S19 note found two citations out of date and one that
narrows our claim further. Fetched live from the Datatracker API and the PyPI JSON API on
2026-11-19; revisions last checked in the log above were correct for the drafts read then,
not for now.

- `draft-zambo-aer1` has moved from -25 to **-26**. Its Section 13 now says outright that a
  bare receipt "does not prove the execution belongs to any particular job", and that
  equivocation is mitigated by comparing against **previously anchored values rather than
  counts**. Sections 7 and 8 state that a chain or Merkle root alone does not stop truncation
  and that deployments needing truncation detection MUST anchor the commitment externally and
  MUST NOT present the chain check as sufficient on its own.
- `veritrail` has moved from 0.3.0 to **0.3.1**; the mechanism is unchanged (hash chain plus a
  head hash published to an external witness).
- `draft-pidlisnyi-aps` (-04), `draft-noa-scitt-ai-agent-receipt` (-01),
  `draft-schrock-ep-authorization-receipts` (-13), `draft-chang-delta1-settlement` (-00) and
  `draft-maintainer-1f916-agent-record` (-01) are unchanged since the first positioning pass.

What this means for S19: two of the three ideas the implementation rests on - "comparing a
sequence number is not by itself freshness" and "without an anchor a shorter history is
undetectable" - now have explicit counterparts in a published draft's normative text. The
remaining novel content is narrower than the earlier note implied: the rule is implemented as
an opt-in check inside an offline package verifier, with all three inconclusive cases written
into the code and isolated by red-team case RT16. Cite AER-1 -26 rather than -25 from now on.

Sources read on 2026-11-19:
- https://www.ietf.org/archive/id/draft-zambo-aer1-26.html
- https://pypi.org/project/veritrail/0.3.1/
- https://www.ietf.org/archive/id/draft-pidlisnyi-aps-04.html
- https://www.ietf.org/archive/id/draft-schrock-ep-authorization-receipts-13.html

---

## Positioning check, 2026-11-19 (third pass): the MCP receipt layer, and three more retractions

The first two passes read the IETF drafts we already cited, PyPI packages, and four arXiv
papers. Two areas had not been swept: the MCP receipt layer, which is the most crowded part
of this space in 2026, and the ITU-T SG17 work on trust and digital identity for agentic AI.
Both were swept on 2026-11-19 and both take away claims rather than add any.

What the sweep found:

- `draft-sirkkavaara-vaara-receipt-03` ships public conformance vectors **with standalone
  checkers** (`tests/vectors/*/_check_independent.py`) and states that no library of the
  issuer needs importing. It also specifies the "held set proves the gap" mechanism
  outright: a monotonic sequence with a running count signed into each record, an optional
  sealing record, and gap detection that needs no issuer access. It names the residual we
  left as INCONCLUSIVE - a pure suffix drop - and closes it with an RFC 3161 anchor over
  the running count.
- `draft-farley-acta-signed-receipts-03` has a reference implementation published on npm
  (`protect-mcp`, ScopeBlind) with four operating modes.
- `draft-nivalto-agentroa-route-authorization-00` submits per-hop receipts to a SCITT log
  to obtain non-equivocation and tail-truncation.
- `draft-marques-asqav-compliance-receipts-09` requires hash-chained receipts, mandatory
  RFC 3161 or OpenTimestamps anchoring, retention floors tied to named articles, and lists
  per-action freshness among its extension fields.
- `draft-klassen-eu2122-content-profile-03` publishes the verification key and records that
  all five checks ran and passed on 2026-10-08.
- The ITU-T SG17 liaison report of 2026-07-01 shows agentic-AI trust and digital identity as
  a standing work item, with three workshops scheduled inside 2026.

Three retractions follow from this, all recorded here rather than only in an internal note:

1. "We are unusual in shipping a harness an outsider can run in one command." Not unusual.
   Vaara ships vectors plus independent checkers with the draft; klassen records the checks
   running in the body of the draft. Recomputability is the entry ticket for this layer.
2. "Held-set gap detection, with tail truncation called out as a residual." Vaara specifies
   the mechanism, gives it fields, and closes the residual with an anchored running count.
   Even the honesty about the residual is not distinctive now.
3. "Per-action freshness has not been written into a specification." It has: the ASQAV
   compliance profile lists it among its extension fields.

What is left is narrower and weaker than in the second pass: three modes of false-accept
rate published side by side; `run_external.py`, which accepts an arbitrary external command
as the thing being tested; and the per-check evidence map described below.

### Correction: the "36 requirements / 11 tested / 25 named gaps" table is not in this repository

The first version of this entry named that table as the leading difference. It should not
have: the table comes from the thesis framework, not from this repository, and a reader
cannot regenerate it here. Searching the repository finds no 36-row requirement list, and
`drafts/draft-zhao-uibc-evidence-chain-00.md` contains no such table. A difference a reader
cannot check is not a difference; it is the same defect as the "5 of 6" case below, one
layer up.

What this repository does ship, and what a reader can check in one command, is narrower:

    python3 tools/build_evidence_index.py --json

That emits one row per check (20 rows, S0 through S19), the tests that name each check, the
red-team mentions, and two explicit lists: `no_test` (checks with no test at all, currently
0) and `no_red_team_mention` (checks no red-team case reaches, currently 1). It is built by
scanning `verify.py`, `tests/` and `tools/outsider_audit.py`, so it drifts only if the code
drifts. The distinguishing property is not the size of a table; it is that the table is
**generated from the code in the box, and says which rows are empty.**

If that thesis table is to be cited anywhere, it has to be published here first as a
machine-readable file with the same regenerable property. Until that happens, no entry in
this log should describe it as something this project ships. Each of those can be overtaken by one external run or one
citation.

Consequence: stop adding survey, and spend the effort on making those three things
recomputable by a third party. Sources read on 2026-11-19:

- https://datatracker.ietf.org/doc/html/draft-sirkkavaara-vaara-receipt-03
- https://www.ietf.org/archive/id/draft-farley-acta-signed-receipts-03.html
- https://www.ietf.org/archive/id/draft-nivalto-agentroa-route-authorization-00.html
- https://www.ietf.org/archive/id/draft-marques-asqav-compliance-receipts-09.html
- https://datatracker.ietf.org/doc/draft-klassen-eu2122-content-profile/
- https://www.ietf.org/lib/dt/documents/LIAISON/liaison-2026-07-01-itu-t-sg-17-iesg-iab-title-ls-update-of-sg17-on-agentic-ai-prior-and-after-the-sg17-5th-plenary-meeting-attachment-4.pdf
