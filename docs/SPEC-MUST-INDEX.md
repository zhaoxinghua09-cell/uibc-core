# SPEC-MUST-INDEX · 规范性条款索引（自动生成）

> 生成器：`tools/gen_must_index.py`；来源：`docs/*.md` 中所有含 `MUST` 的行（跳过代码块与引用块）。
> 本索引不改写原文，只做编号与对齐；编号一经发布不得复用。
> `映射检查` 一列为人工填写（S1–S19 见 `docs/CHECK-MATRIX.md`）；留空的即 **untested**，
> 按 `docs/CONFORMANCE.md` 的规定，untested 条款不得计入「已覆盖」。

| 编号 | 级别 | 类别 | 文件 | 行 | 条款原文（截断 120 字） | 映射检查 |
|---|---|---|---|---|---|---|
| MUST-00 | MUST | 条款 | `AER1-REPLAY-FULL.md` | 24 | §6 步骤 4 写得很硬：`receipt_schema_version` 为 `0.4` 或更高时 **MUST** 带 `metadata_hash`，且「a "0.4" receipt without metadata_hash... | _待填_ |
| — | MUST | 引用/评论 | `AER1-REPLAY-FULL.md` | 35 | 也就是说：**照规范写会在这 10 个向量上失败，照语料写会漏掉规范的一条 MUST。** 这不是实现者的选择问题，是规范与语料得先对齐。 | _待填_ |
| — | MUST | 引用/评论 | `AER1-SPEC-AUDIT.md` | 19 | §3.1 表 1：`metadata_hash` 标 **Cond.**，说明栏写 `REQUIRED when receipt_schema_version is "0.4" or later; a verifier MUST re... | _待填_ |
| MUST-01 | MUST | 条款 | `AER1-SPEC-AUDIT.md` | 20 | §6 步骤 4：`A "0.4" receipt without metadata_hash MUST fail.`（本地正文第 1069–1071 行） | _待填_ |
| — | MUST | 引用/评论 | `AER1-SPEC-AUDIT.md` | 32 | 判定**：规范与语料冲突，官方 runner 未实现该 MUST。我们两种模式都给：默认随语料（否则过不了 143/143），`--strict-metadata` 随规范（那 10 份会失败）。这不是我们写错，是规范自身没对齐。 | _待填_ |
| MUST-02 | MUST | 条款 | `AER1-SPEC-AUDIT.md` | 40 | §7.2（`seq`）：`a JSON number with an integer value. The representations 1 and 1.0 are equivalent; both are [accepted] .... | _待填_ |
| MUST-03 | MUST | 条款 | `COMPETITIVE-STATE.md` | 29 | \| A2A boundary-seal (Tyche) \| `a2a-tck` 100% MUST \| | _待填_ |
| MUST-04 | MUST | 条款 | `CROSSWALK-ASQAV-COMPLIANCE.md` | 5 | this file maps the draft's seven MUST checks onto what `uibc_core.verify` actually does | _待填_ |
| MUST-05 | MUST NOT | 条款 | `CROSSWALK-ASQAV-COMPLIANCE.md` | 20 | \| 2 \| Resolve the key through a trust anchor; MUST NOT trust a key embedded in the envelope \| S2 identity; pinned-... | _待填_ |
| MUST-06 | MUST NOT | 条款 | `CROSSWALK-ASQAV-COMPLIANCE.md` | 23 | \| 5 \| At least one anchor, and re-verify it cryptographically against the signed envelope; metadata presence alone ... | _待填_ |
| MUST-07 | MUST NOT | 条款 | `CROSSWALK-ASQAV-COMPLIANCE.md` | 24 | \| 6 \| Future-skew bound on `issued_at` (>300 s ahead ⇒ reject); past timestamps MUST NOT be rejected when within re... | _待填_ |
| MUST-08 | MUST NOT | 条款 | `CROSSWALK-ASQAV-COMPLIANCE.md` | 25 | \| 7 \| `policy_digest` resolves through the Audit Pack; recompute `SHA-256(JCS(artefact))`; a nonced form MUST NOT c... | _待填_ |
| — | MUST | 引用/评论 | `EXTERNAL-NODE-KIT.md` | 72 | **语料与规范不一致的两处**（我们实测撞到的，不是我们的 bug；数字由 `tools/aer1_spec_audit.py` 一条命令复现，详见 [`docs/AER1-SPEC-AUDIT.md`](AER1-SPEC-AUDI... | _待填_ |
| MUST-09 | MUST | 条款 | `GROUNDS.md` | 41 | \| `oracle-s16-token-byte` \| S16 \| `draft_mandated` \| `rfc3161.txt` 2.4.2 \| > The messageImprint MUST have the sa... | _待填_ |
| MUST-10 | MUST | 条款 | `GROUNDS.md` | 42 | \| `oracle-s17-receipt-body` \| S17 \| `draft_mandated` \| `draft-marques-asqav-compliance-receipts-01.txt` 4.3 \| > ... | _待填_ |
| MUST-11 | MUST | 条款 | `GROUNDS.md` | 43 | \| `oracle-s18-policy-artefact` \| S18 \| `draft_mandated` \| `draft-marques-asqav-compliance-receipts-01.txt` 4.2.2 ... | _待填_ |
| MUST-12 | MUST | 条款 | `LANDSCAPE-2026-11.md` | 172 | \| A2A boundary-seal \| a2a-tck 100% MUST \| capsule-emit #29 \| | _待填_ |
| MUST-13 | MUST | 条款 | `RELEASE-NOTES-0.5.1.md` | 28 | `docs/SPEC-MUST-INDEX.md`：20 行含 MUST 的自动索引，其中 16 条编号为条款，4 条标为引用/评论 | _待填_ |
| MUST-14 | MUST | 条款 | `REVIEW-LOG.md` | 327 | and a unique `run_id`, and say validators MUST reject decreases and replays. | _待填_ |
| MUST-15 | MUST | 条款 | `REVIEW-LOG.md` | 420 | and that deployments needing truncation detection MUST anchor the commitment externally and | _待填_ |
| MUST-16 | MUST NOT | 条款 | `REVIEW-LOG.md` | 421 | MUST NOT present the chain check as sufficient on its own. | _待填_ |

## 统计

- 命中含 MUST 的行：**21**
- 其中可作条款（已编号）：**17**；引用/评论（不编号）：4
- 已填映射：0（本轮只做编号，不改语义）

## 已知问题（本轮记录，不做静默修改）

1. **SHOULD / MAY 为 0**：规范把所有约束都写成 MUST，导致第三方无法分辨
   「不做就不合规」与「建议做」。整改需要在原文处逐条降级，属于语义变更，须单独批准。
2. **RFC 2119/8174 声明只存在于 draft**：正式规范首页缺少该声明，
   外部读者无法确认 MUST 的规范效力。
3. 本表未覆盖 `drafts/draft-zhao-uibc-evidence-chain-00.md`（草案阶段，措辞会变）。
