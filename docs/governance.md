# UIBC Governance Layers — 治理六层规范 v0.1 (PROPOSAL)

Status: PROPOSAL（与 SPEC v0.2 同级，未经独立实现核验前不得宣称 ratified）
Spec version: 0.2.0
Date: 2026-09-18
依据：XLGD/LGD/UIBC 历史总档案 v0.1.0（§分层表）+ 2026-09-17 路线评审

---

## 0. 定位

LGD 三原则：**有籍（Registry）·有证（Evidence）·有门禁（Gates）**。
当前 uibc-core 已覆盖：身份（Registry/L1-L7）、证据（Evidence Root）、执行（包格式）、
实验（Benchmark fixtures）、攻击（Break UIBC）、验证（Verifier S1-S6）、签名雏形（S6）。

本规范补齐其余六层的**最小可验证语义**。原则：每层只定义「能被 verifier 检查的
最小对象」，不定义流程、不定义机构——与"协议开放、商业在外围"纪律一致。

核心纪律（继承档案）：`Fact ≠ Evidence ≠ Claim ≠ Verification ≠ Trust`。
六层全部只操作 Evidence 及其下，永不直接产出 Trust。

---

## 1. Dispute（争议）——"不同意见怎么办"

**对象**：`dispute.json`（包外文件，指向某个已密封包）

```json
{
  "dispute_id": "d-<uuid>",
  "target_package": "<package fingerprint (SHA-256 of manifest.json)>",
  "target_root": "<被质疑的 evidence_root>",
  "reason_code": "EVIDENCE_DISPUTED | IDENTITY_DISPUTED | PROCESS_DISPUTED",
  "disputer": "<agent_id of the disputing party>",
  "created_at": "<ISO8601>",
  "evidence": ["<dispute 支持证据文件哈希，可空>"]
}
```

**可验证属性**：
- D1 dispute 的 target_root 必须与目标包 manifest 的 evidence_root 一致（防挂错对象）
- D2 dispute 本身不可修改（文件哈希自证：dispute_id = SHA-256(canonical(dispute body))）
- D3 verifier 遇到已登记 dispute 的包 → verify 结果附加 `disputed: true` 标记，**不改变 PASS/FAIL**（争议≠失败，这是与 Revocation 的关键区别）

## 2. Correction（纠错）——"错了怎么办"

**原则**：历史不可篡改，纠错是**追加**，不是覆盖。
**对象**：lifecycle 事件类型 `CORRECTION`（payload 指向被纠正的 event_id）。

**可验证属性**：
- C1 CORRECTION 事件必须引用一个已存在的 event_id（previous_event 链不断）
- C2 被纠正的事件**保留原状**，不允许任何改写（verifier 遇改写即 S4 FAIL）
- C3 同一 event_id 被多次 CORRECTION 合法，按时间序生效

## 3. Revocation（撤销）——"失效怎么办"

**对象**：`revocation.json`（包外，由密钥持有者签发——v0.2 HMAC 语义下= owner）

```json
{
  "revocation_id": "r-<uuid>",
  "target_root": "<被撤销包的 evidence_root>",
  "reason_code": "KEY_COMPROMISED | EVIDENCE_INVALID | OWNER_REQUEST",
  "key_id": "<owner key_id>",
  "signature": "<HMAC(key, canonical(revocation body))>",
  "revoked_at": "<ISO8601>"
}
```

**可验证属性**：
- R1 撤销必须可验签（用 key_id 对应的 owner key；无 key 则撤销本身 INCONCLUSIVE）
- R2 撤销是**终态**：被撤销包 verify 附加 `revoked: true`，且门禁（GATE）必须 DENY
- R3 撤销不可被"未撤销"覆盖（v0.1 无撤销的撤销；需纠错时走 CORRECTION 链留痕）

**Dispute vs Revocation 的边界**：Dispute=第三方说"我有异议"（标记不阻断）；
Revocation=持有者说"这个作废"（验签后阻断门禁）。

## 4. Accountability（责任）——"谁授权"

**对象**：已存在于 identity.json 的 `owner` 字段 + lifecycle 的 `actor` 字段。
本层 v0.1 不新增对象，只**收紧可验证属性**：

- A1 每个 lifecycle 事件必须携带 actor，且 actor 非空（现有 S1 已查结构，此处升级为语义检查）
- A2 agent 的 `owner` 是该包全部证据的责任主体；verifier 报告必须输出 owner（现有 inspect 已满足）
- A3 密封（submit）行为的 actor 视为 owner 本人（v0.2 HMAC 下由 key 归属保证）

## 5. Continuity（连续性）——"变化后还是不是它"

**原则**（继承档案 + 2026-09-17 讨论）：不回答"是不是同一个 Agent"这个哲学问题，
拆成可分别验证的维度：

| 维度 | 验证语义 |
|---|---|
| Identity Continuity | agent_id 不变（注册即锚定，L1） |
| Memory Continuity | UIBC-MEM 层（G4 任务），迁移前后 Fact/Attribution/Citation/Version 四项 Preservation |
| Capability Continuity | v0.2 不实现，仅预留 `capability` 字段位 |
| Responsibility Continuity | owner 不变；owner 变更 = lifecycle OWNER_TRANSFER 事件（v0.1 预留类型） |
| Lifecycle Continuity | 事件链 previous_event 不断链（现有 S3/S4 已覆盖） |
| Evidence Continuity | evidence_root 重算一致（现有 S5 已覆盖） |

**可验证属性**：Co1 Identity Continuity = agent_id 存在且未撤销；Co2 其余维度各自独立的
验证器在后续版本交付，本规范只锁定维度命名与边界。

## 6. Provenance（来源）——"AI 怎么公正引用"

**对象**：证据条目的 `type` 已含 ACTION/OUTPUT 等。本层新增证据类型约定：

- `PROVENANCE` 类型证据：记录"本包引用的外部来源"（URL/文献/上游包 root）
- P1 PROVENANCE 条目必须含 `source_hash`（引用内容的哈希）与 `source_locator`（可定位描述）
- P2 verifier 不验证外部内容可达性（只验证哈希格式与登记存在）——诚实边界：我们证明"引用了什么"，不证明"引用还对不对"

---

## 7. 与现有 S1-S6 的关系

- S1-S6 全部保持不变；六层是**附加检查**，通过 verifier 报告的 `governance` 字段输出
- 门禁（GATE，任务 G2）执行规则：REVOKED → DENY(exit 2)；DISPUTED → 标记+人工决策
  （不自动 DENY）；其余沿用 verify 结果
- 本规范所有对象格式为 PROPOSAL，G5 独立验证器交叉核验通过后升 DRAFT

## 8. 诚实边界

1. HMAC 对称签名下，Revocation 验签只有 owner 自己能做——第三方无法区分
   "真撤销"与"伪造撤销"，这是 v0.2 已知边界（换钥同理），Ed25519+v0.3 收窄
2. Continuity 六维度中 3 个是占位（Capability/Responsibility/Memory 部分），
   不许在对外文案中宣称"已支持全部连续性验证"
3. Provenance 不做内容真实性判断，永不宣称"来源可信"，只宣称"来源已登记"
