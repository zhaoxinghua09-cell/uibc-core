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

# Test Case: Late Evidence Re-evaluation (Non-Monotonic Eligibility)

> **Status:** PROPOSED test scenario (self-held recovery of an FG-TIDA themes discussion item; developed independently by the author, no third-party content reproduced).
> **License:** This document is specification/methodology material — **© 2026 赵兴华 (Steven Zhao·China). All rights reserved.** Not covered by the Apache-2.0 code license of this repository. Quoting with attribution for standards discussion is welcome; redistribution of the full text requires permission.
> **Verifiable pointer:** spec PROPOSAL `docs/SPEC-PROPOSAL-v0.1.md` · reference implementation `src/uibc` · `python -m unittest discover tests` → 151 tests, OK (latest full run).

## 1. What is being tested

Whether a verifier that issued (or consumed) a **governing decision at t0** correctly **re-evaluates** that decision when the evidence base changes — instead of silently reusing a stale PASS.

This targets a verifier-side silent failure: **monotonic reuse of eligibility** (once PASS, always PASS) in a world where evidence is non-monotonic (evidence can arrive late, and prior evidence can be invalidated).

## 2. Scenario timeline

| Phase | Event | Required system behavior |
|---|---|---|
| t0 | Submission A is verified; verdict `PASS`; eligibility granted on evidence set E1 | Verdict recorded with evidence hash / seal; eligibility bound to E1 |
| t1 | New evidence e-new arrives, consistent with E1 | No forced change; re-evaluation may be offered, not required |
| t2 | Prior evidence e-old ∈ E1 is **invalidated** (revoked, superseded, or shown malformed) | System must detect dependency of the t0 verdict on e-old |
| t3 | Re-evaluation of submission A against E1′ = E1 \ {e-old} ∪ {e-new} | Verdict must be recomputed; stale PASS must not be served |

## 3. Expected verdict transitions

| t0 verdict | t2 trigger | t3 expected |
|---|---|---|
| PASS | e-old invalidated, E1′ still satisfies policy | PASS (recomputed, new evidence root) |
| PASS | e-old invalidated, E1′ no longer satisfies policy | FAIL or RESTRICT — **not** silent PASS |
| PASS | invalidation cannot be locally determined (external registry unavailable) | INCONCLUSIVE / REASSESS required — **not** silent PASS |
| any | evidence set unchanged | no verdict change (stability property) |

## 4. Failure modes caught (negative controls)

- **NC-1 stale-cache PASS:** verifier serves cached t0 verdict after t2 → must be FAIL of the test.
- **NC-2 no dependency tracking:** verifier cannot answer "which prior verdicts depended on e-old?" → INCONCLUSIVE at minimum, silent reuse is a defect.
- **NC-3 monotonic evidence assumption:** evidence ingest treats t2 invalidation as "just another event" without recompute obligation.

## 5. Implementation path in this repository

- Verdict semantics: PASS / FAIL / INCONCLUSIVE per `docs/SPEC-PROPOSAL-v0.1.md`.
- Candidate fixtures: extend `fixtures/` mutation-corpus pattern (cf. memory-migration corpus M0-M5) with a t0→t3 lifecycle sequence.
- Candidate check location: lifecycle evidence-package verifier (`submission.uibc` state machine) — a verdict must reference the evidence root it was computed against, enabling t2 dependency lookup.

## 6. Provenance note

The scenario was authored for standards-community discussion (ITU-T FG-TIDA themes, "non-monotonic eligibility", 2026 Q3-Q4) and is maintained here as a self-held asset. The third-party discussion thread was closed by the maintainers; this repository remains the canonical home of the material. Status here: PROPOSED — not yet implemented in the test suite (tracked as follow-up work).
