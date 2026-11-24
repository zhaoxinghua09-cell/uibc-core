# Competitive landscape, measured 2026-11-24

Scope: who else is working on agent identity and on agent-state adjudication, and where each of them actually stands. Every row carries its basis: **标准** (GB/Z 185 text), **规范** (published spec), **实测** (we fetched or called it), **读码** (we read the published source).

This document exists because we keep being tempted to say "we are ahead". The table below is what "ahead" has to mean, one row at a time, including the rows where we are not.

## 1. Identity-code track (GB/Z 185.2)

| Actor | What they have | Standing | Basis |
|---|---|---|---|
| **AIP reference implementation** (中国电子技术标准化研究院 + 北京邮电大学, `atomgit.com/aip-pub`) | Seven-part standard turned into code: registry, CA, discovery, interaction, tool calling, monitoring. | The reference. Anything we claim about GB/Z 185 has to be consistent with this, not with our reading of it. | 实测 (project README + repo list) |
| — version actually live | **v2.2.0, 2026-08-31** — the July press release still says v2.1.0 | Their own announcement is stale by one release; treat any third-party claim of "v2.1.0 is current" as out of date. | 实测 (README version history) |
| — what v2.2.0 added | Streaming + notification interaction, identity binding between claimed sender and mTLS certificate, **AAC (Agent Access Control) protocol**, Ed25519 by default, Ansible deployment. | AAC is now *theirs*, not a concept we can claim to have introduced. | 读码 + 实测 |
| — identity code form since v2.0.0 | "AIC 智能体身份码引入 OID 形式，具备全球唯一性" | The OID form is already the reference implementation's choice. Our eight-field reader is not novel; the *verification stance* is what we can own. | 实测 (v2.0.0 changelog entry) |
| **aipmc-basic** (Rust, MIT, crates.io 0.0.2, 2026-10) | Reads identity codes as **ten** fields with a 4-char Base36 CRC-16/CCITT-FALSE; salt not published. | Diverges from GB/Z 185 in three places: one extra field, a checksum the standard does not define, instance length 1–9 vs the standard's 1–10. A third-party implementation wearing the standard's name. | 读码 |
| **agent.idfactory.cn / iaisp.teleinfo.cn** | 200+ nodes, 1,181 identity codes, 13,526 expressions of interest (2026-07-21) | The allocation side. We are a reader of it, not a participant — and the self-service entry is open, which we have not used yet. | 实测 (HTTP 200, 77 agents listed) |
| Community state | An open discussion asking the community to *design* identity codes for platform users | Allocation guidance is still being asked for in public. Nothing about our verification work fills that gap. | 实测 (discussion list) |

### What a third party can actually read

The reference implementation's landing page reports 16.45 K downloads. Downloads are not inspection: `tools/probe_reference_repos.py` asks the AtomGit API, with no account and no token, what files each repository's default branch contains.

Measured 2026-11-24:

| Repository | Branch | Readable files | Content |
|---|---|---|---|
| ACPs-community | main | **0** | no files at all |
| ACPs-SDK | master | 1 | README.md |
| ACPs-CA-Server | master | 1 | README.md |
| ACPs-CA-Client | master | 1 | README.md |
| ACPs-CA-Challenge | master | 1 | README.md |
| ACPs-Registry-Server | master | 1 | README.md |
| ACPs-Discovery-Server | master | 1 | README.md |
| ACPs-Demo-Project | master | 1 | README.md |
| Agent-Interconnection-Protocol-Project | master | 1 | README.md |

So the only cross-check available to an anonymous third party is the **changelog**, not the code. Our own claims have to be held to a different standard than theirs, and we can say so without pretending it is a defect in their project: an account wall may be deliberate.

Two consequences we accept:

1. **We cannot claim "cross-checked against the reference implementation."** We can claim "read its published version history and protocol names." Row 7 below stays *partial* for a new reason: the code is not anonymously readable.
2. **Our own verifiability is measurable, and should be measured.** The same question put to this repository, anonymously, returns **1,865 files** on `main`, and the `codeload` tarball answers **200** with no token. Same date, same network, opposite result. That contrast is a fact we can put in front of anyone, and it is the only place on this track where "ahead" means "inspectable".
## 2. DID track (`did:cn`)

| Fact | Standing | Basis |
|---|---|---|
| Official spec repo `caict-4iot-dev/CN-DID-Method-Specification` | One README, 6,536 bytes, v1.0.0, unchanged since 2025-03-20, zero issues. | 实测 |
| Spec content | `create` / `resolve` / `update` / `deactivate`, DID Document with `service` and `serviceEndpoint`. | 规范 |
| Live namespace | Every registered agent reads `did:cn:agent:<base58>`, which the spec's own ABNF (`2DIGIT.3*5DIGIT.1*128DIGIT`) cannot produce. No published ABNF for the live form. | 实测 |
| Platform verification | `vcVerificationStatus` is `SKIPPED` on every resolve-verify call we made. | 实测 |
| Our adapter | `validate()` refuses the live form; `validate_live_agent_id()` recognises it and labels itself `published_abnf: False`. Both stop at `INCONCLUSIVE`. | 读码 |

Nobody else appears to have written down the divergence between the published ABNF and the served namespace. That is the one place on this track where we are first — and it is a finding, not a capability.

## 3. Adjudication track — the only track with real competition

| Actor | What they have | What we have that they do not | What they have that we do not | Basis |
|---|---|---|---|---|
| **AIP / AAC** | An access-control protocol inside a living reference implementation, with mTLS identity binding. | Refusal vocabulary: seven states, `INCONCLUSIVE` as a hard ceiling, a 49-cell state machine, `state_collapse` 0/4. | A running registry, CA, discovery, and deployments. | 实测 + 读码 |
| **AAC third-party implementations** (13) | Implementation breadth. | Same as above: none of them publish a refusal-state vocabulary or a collapse metric. | Breadth, integrations. | 实测 |
| **SCITT implementations** | Transparency-log receipts for signed statements. | Adjudication *states*, not just receipts. | A log with external anchoring. | 实测 |
| **EMILIA Protocol** | Policy expression and enforcement. | Refusal as a first-class, checkable outcome. | Enforcement deployment. | 实测 |

## 4. Where "best" is still a claim we cannot back

Eight criteria, scored on what is on disk and reachable today:

| # | Criterion | Status | Basis |
|---|---|---|---|
| 1 | Reads both code families | **Pass** | `agent_identity_code.py`, `did_cn.py` |
| 2 | Refuses to over-claim (no path to `VERIFIED` without evidence) | **Pass** | `_verdict()` returns `INCONCLUSIVE` only |
| 3 | Every published number regenerated from the tree | **Pass** | `check_doc_facts.py` → 0 mismatch |
| 4 | Differences documented with basis per row | **Pass** | `docs/TWO-CODES-DIFF.md` |
| 5 | Tests cover the hostile inputs | **Pass** | 1,156 cases across the suite |
| 6 | Reproducible by someone who is not us, offline | **Partial** | One-command bundle exists; no outside party has run it |
| 7 | Cross-checked against the reference implementation | **Partial** | Its default branches expose **0–1 files anonymously** (`tools/probe_reference_repos.py`), so the comparison is against the published changelog, not the code |
| 8 | Independently evaluated (separate identity, separate interest) | **0** | No evaluation has been performed |

Rows 6–8 are the actual gap. They are not closed by writing more code; they are closed by someone else doing the work, and pretending otherwise is exactly the over-claim this repository exists to avoid.

## 5. What we change because of this table

1. Stop describing the OID reader as novel — the reference implementation adopted the OID form in v2.0.0. Describe it as *strict reading plus a refusal ceiling*.
2. Drop any wording that treats AAC as emerging; it shipped in v2.2.0.
3. Keep the `did:cn` divergence finding, and put it to CAICT as a question rather than a correction.
4. Do not score ourselves on rows 6–8.
