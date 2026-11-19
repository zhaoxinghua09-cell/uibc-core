# Composition verifier · 组合裁决器（对外唯一口径）

<!-- facts: current -->


> One sentence: **uibc takes several records produced by different parties under
> different profiles and returns one recomputable three-valued verdict — PASS, FAIL,
> or INCONCLUSIVE — and never turns "could not decide" into "passed".**

## 1. The gap we sit in (quoted, not asserted)

`draft-kuehlewind-audit-architecture-00` lays out an auditing architecture for agent
delegation and lists work items WI-1 … WI-11 (record formats, identity profiles, context
propagation, transparency-service integration, …). Its companion method draft states the
missing piece directly:

> "That architecture does not specify how an Auditor, or any independent party,
> deterministically verifies that a set of such records — produced by different parties,
> in different profiles, and composed into one case — is internally consistent and
> correctly derives an audit conclusion."
> — `draft-mih-agent-accountability-conformance-00`

and, in the same document:

> "What no enumerated item covers is what the Auditor does once the records are in hand:
> establishing, deterministically and testably, that the composed set is consistent."

That is the work item this repository implements. Not a new record format, not a new
gateway: **the step after the records exist**.

## 2. What we actually do

| step | mechanism | check |
|---|---|---|
| bind the case | one package = manifest + identity + lifecycle + evidence index + seal | S1, S2 |
| bind the state | `lifecycle_head` over the seal-covered event log; sequence continuity | L8–L12 |
| bind the evidence | evidence root over content hashes; index metadata digest | S4, S5, S7 |
| bind the package to a point in time | `checkpoint_head` = lifecycle head + evidence root + index digest + count | S8 |
| detect replacement | compare `checkpoint_head` with a head observed **outside** the package | S9 |
| decide | three values, fail-closed; `INCONCLUSIVE` is never reported as `PASS` | verdict |
| say how strong the answer is | `trust_level = anchored / unanchored / unattested` | anchor rule |
| record refusals | append-only phantom ledger, one entry per gate decision | phantom |

Verification is offline and does not call the issuer. The whole claim is reproducible:

```bash
python -m uibc_core.cli demo          # build, seal, verify, tamper, catch
python benchmark/run.py               # 21-class benchmark, undocumented acceptance = 0
python -m unittest discover -s tests  # 602 tests
```

## 3. What we do NOT claim (the part that keeps us honest)

- **No new format.** Portable offline-verifiable bundles are already specified elsewhere:
  `draft-stone-aivs-01` (bundle with a stdlib-only self-verifier) and
  `draft-sharif-agent-audit-trail-03` (hash-chained audit records with an attestation
  closure). We reuse their shape and do not claim novelty in it.
- **No gate original.** Pre-action authorization is a shipping product category
  (APort / OAP v1.0 and several MCP gateways). Our only defensible difference is the
  admission predicate: **`PASS` + `anchored`**, so "could not decide" holds rather than
  passes.
- **No witnessing.** We have no independent witness and no transparency-log
  countersignature, so the strongest level reachable is `anchored`. `witnessed` is a
  strict superset we do not reach (`draft-maintainer-1f916-agent-record-01`).
- **No scoring.** No single number, no ranking — consistent with GAR-08 and ERC-8004,
  which both refuse to compress multi-dimensional signals into one score.
- **No behavioral judgement.** A package can be perfectly intact and describe something
  that should never have been allowed. Integrity is not correctness.

## 4. Relation to adjacent work (so a reviewer can place us in one glance)

| adjacent work | it answers | we answer |
|---|---|---|
| `draft-raskar-scitt-agent-provenance-00` | what a package digest binds | whether the *set* of bound packages is mutually consistent |
| `draft-stone-aivs-01` | how to carry a session bundle and self-verify it | how to decide across bundles |
| `draft-noa-scitt-ai-agent-receipt-01` | terminal verdict per receipt | the verdict for the composite case |
| `draft-sato-soos-gar-08` | governance decision (ALLOW / DENY / ESCALATE / SUSPEND) | verifiability (PASS / FAIL / INCONCLUSIVE) — a different axis |
| `draft-schrock-ep-authorization-evidence-chain-02` | five evidence grades for authorization | three coarse grades + explicit anchor strength |
| `draft-noctem-cogitator-witness-protocol-00` | witness root including blocked calls (phantom entries) | the same, plus a verdict over the set |

## 5. Where this could plug in

- AUDIT architecture **WI-6 / WI-9**: our package as the verifiable payload behind an
  Action Record; the Auditor's composition step is the part we implement.
- SCITT: a uibc package is an application-specific statement payload; the verdict is
  what a relying party asks for after collecting several statements.
- Medical-device lifecycle: with **21 CFR 892.2055** (final order 2026-06-17, the first
  device type whose regulation requires a PCCP), the "version history + evidence of
  implemented changes" a label must carry is exactly a sequence of packages and
  checkpoints.

## 6. Status

PROPOSAL, not a ratified standard. No third-party review to date; the internal
pre-release review (red team 11 cases, anonymous-clone outsider run, external-model
review) is recorded in the project report and is **not** a substitute for independent
evaluation.

**Implemented and runnable as of 2026-11-17** (`uibc_core/composition.py`, checks K1-K8):

```bash
python tools/compose_demo.py            # 7 scenarios, one deterministic verdict each
python -m uibc_core.composition case.json
```

| scenario | verdict | code |
|---|---|---|
| three origins, refs closed | PASS | - |
| payload edited, digest untouched | FAIL | K1 |
| sequence gap in one origin | FAIL | K3 |
| dangling cross-origin reference | FAIL | K5 |
| stacked, not composed | INCONCLUSIVE | K7 |
| record dated before what it cites | FAIL | K4 |
| single origin | INCONCLUSIVE | K7 |

The failures are the deliverable: a case assembled from three different producers
gets a verdict **named by code**, not by prose, and two of the seven outcomes are
`INCONCLUSIVE` on purpose - a set that is merely stacked, or that has one origin, must
never be reported as a case.

