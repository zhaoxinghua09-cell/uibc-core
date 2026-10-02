> **Rights & Provenance**（统一权属块 · 依《LGD 对外表述规范》§3.2 A/B 段）:
>
> © 2026 赵兴华 / Steven Zhao·China (ORCID 0009-0001-0512-1237). All rights reserved.
> 理论署名 (attribution) : LGD（Lifecycle Governance Doctrine / 全程治理论）— SynomosAI initiative
> 名称状态 (name status)  : "SynomosAI" / "MedXpert" — 未申请实体注册、未申请商标注册 (not a registered legal entity; no trademark registered)
> 生产参考部署 (production reference, self-reported) : MedXpert ← 非认证、非背书、非监管认可
> 代码许可 (code license) : 本仓**代码** = Apache-2.0（以 LICENSE 为准）；**本文件 = 规范/理论文本，保留所有权利，不在 Apache-2.0 覆盖范围内**
> 引用格式 (cite as)      : uibc-core concept DOI 10.5281/zenodo.22821834
> 首次公开锚 (first public): commit `cb6f11b` · 2026-09-17 13:31:45 UTC；外部锚 Rekor logIndex 2883389783
> G0                     : 本件已随 uibc-core 公开仓发布（Steven 令·授权推送）。

# Use Case: Agent-Team Delivery of Regulated Medical-Device Compliance Work

> **Status:** use-case document (self-held full version; condensed discussion copy filed as FG-TIDA/use-cases#14, OPEN as of this writing (GitHub API, this revision cycle)).
> **License:** **© 2026 赵兴华 (Steven Zhao·China). All rights reserved.** Not covered by the Apache-2.0 code license of this repository.
> **Cross-references:** `docs/SPEC-PROPOSAL-v0.1.md` · `docs/TEST-CASE-late-evidence-reevaluation.md` · silent-failure catalog entries SF-005/006/011 (executable, pinned manifest via FG-TIDA/use-cases#23).

## 1. Problem

A medical-device regulatory team runs multi-agent workflows (drafting, standards lookup, gap analysis, submission packaging) where outputs feed regulatory decisions. The governing questions are not "is the model smart" but:

1. **Who is the agent** acting (identity, on whose behalf)?
2. **Who authorized it** to perform this action (authority delegation)?
3. **What is it allowed to do** (scope bounds)?
4. **Until when** (lifecycle: grant, expiry, revocation)?
5. **What evidence exists** for audit (verifiable record of all the above)?

## 2. concrete workflow (anchor: NMPA / FDA / EU MDR / PMDA compliance drafting)

| Step | Actor | Action | Evidence artifact required |
|---|---|---|---|
| W1 | Human lead | Delegates "draft 510(k) section outline" to agent A | delegation record: agent id, scope, expiry |
| W2 | Agent A | Produces draft + citations to standards | submission.uibc package: action list, source hashes |
| W3 | Agent A | Calls standards-lookup agent B | nested delegation, B's scope ⊆ A's scope |
| W4 | Verifier V | Checks package: hashes, signatures, scope conformance | verdict PASS/FAIL/INCONCLUSIVE + evidence root |
| W5 | Human lead | Accepts / rejects; triggers revision | decision bound to V's verdict id |
| W6 | (later) standards cited by W2 get revised | late-evidence re-evaluation obligation | cf. TEST-CASE-late-evidence-reevaluation.md |

## 3. Why generic agent frameworks do not close this alone

Lifecycle gaps observed in practice (verifier side): stale eligibility reuse, silent scope expansion in nested delegation, unverifiable "who did this" after team recomposition, and verdicts not bound to the evidence they were computed from. These map to the silent-failure catalog (SF-005/006/011) shipped as executable checks with a pinned manifest.

## 4. What UIBC contributes

- A **minimum evidence-package structure** (`submission.uibc`, PROPOSAL v0.1/v0.2.x) with lifecycle state rules.
- An **executable verifier** producing PASS / FAIL / INCONCLUSIVE — a verdict is always computable and bound to an evidence root.
- **Negative controls**: mutation corpora designed to prove the verifier fails loudly instead of silently passing malformed input.

## 5. Interoperability

Adapters (e.g. `adapters/a2a`, `adapters/tencentdb-agent-memory`) map agent-platform primitives into the package structure, so an existing multi-agent stack can produce verifiable delivery evidence without replacing the stack.

## 6. Open questions (for discussion)

- Signature scheme migration: HMAC-SHA256 (v0.2, stdlib-only) → Ed25519 + public key registry (planned v0.3).
- External timestamp anchoring and registry-based revocation checks (currently out of scope, see README §scope).
- Cross-jurisdiction evidence acknowledgment (NMPA ↔ FDA ↔ EU MDR) — what must a foreign regulator be able to re-verify locally?
