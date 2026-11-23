# GTP-1 Profile：如何消费 AIP / AgIS / Clawdentity 的撤销产物

**日期**：2026-11-19 · **状态**：草案，未对外 · **实现**：`proposals/p25_profile_conformance/profile.py`（14/14 实跑）

---

## 1. 为什么是"适配层"而不是"第 5 份草案"

撤销已有 4 份 IETF 草案（AIP / AgIS / Clawdentity / ACAP）。再写一份只是增加混乱。

本 profile 只做一件事：**当接收方拿到这些草案的撤销产物时，按统一规则判定，保证不漏撤**。

---

## 2. 字段映射

| GTP-1 概念 | AIP（draft-singla） | AgIS（draft-ayoub） | Clawdentity |
|---|---|---|---|
| 签发者 | `iss` | `agent_id`（等价主体） | JWT `iss` |
| 版本/序号 | `jti`（CRL 标识） | — | JWT `jti` |
| 签发时间 | `iat`（unix） | `updated_at` | `iat` |
| 有效期 | `exp` | `cache.ttl_seconds` | `exp` |
| 被撤销对象 | `revocations[].agentDid` | `status`（本体状态） | `revocations[].agentDid` |
| 撤销粒度 | `type` = full / scope / delegation / principal | 无（实体级） | 无（实体级） |
| 撤销范围 | `scopes_revoked` | — | — |
| 历史不可篡改证明 | **无** | **无** | **无** |
| 签名 | EdDSA（Revocation Object） | 未见签名要求 | EdDSA（JWT） |

---

## 3. 三条显式偏离（必须写在产品文档里）

| 偏离 | 草案默认 | 本 profile | 后果 |
|---|---|---|---|
| **无历史证明即拒绝** | CRL 是"当前快照"，静默接受 | strict 模式 `DENY:no_history_proof` | 拒绝可用性换抗重放；宽松模式用于过渡期 |
| **`unknown` 即拒绝** | AgIS 把 unknown 交本地策略 | `DENY:status:unknown(fail_closed)` | 宁可误拒，不可错放 |
| **超 max_age 即拒绝** | Clawdentity 明文 fail-open（缓存未超 max age 仍放行） | `DENY:stale(fail_closed)` | 与主流相反，需自负可用性代价 |

这三条不是"我们更安全"的口号，而是**可测的行为差异**：P03 / P08 / P12 就是它们各自的用例。

---

## 4. 实跑结果（14/14）

| 用例 | 含义 |
|---|---|
| P01–P02 | AIP CRL：撤销命中 / 未命中 |
| P03 | AIP 在 strict 模式因缺历史证明被拒 |
| P04–P05 | AIP `scope_revoke` 的粒度正确（封 payments 不封 read） |
| P06 | AIP CRL 超 15 分钟 → 拒绝 |
| P07–P10 | AgIS：revoked / unknown / ttl 过期 / compromised 均拒绝 |
| P11 | Clawdentity 签名有效且命中 → 拒绝 |
| P12 | Clawdentity 超 max age → 拒绝（**覆盖其 fail-open**） |
| P13 | 旧 CRL 重放（iat 回退）→ 拒绝 |
| P14 | 签名伪造 → 拒绝 |

---

## 5. 诚实边界（这三条决定了它能做什么、不能做什么）

1. **样本是按草案文本构造的，不是真实抓取的产物**。截至 2026-11-19 未找到任何公开的 AIP/AgIS/Clawdentity 实例在跑，因此**不构成真实互操作验证**（NOT VERIFIED）。要变成真互操作，必须拿到对方真实 CRL。
2. **签名位置是我按"EdDSA over JWT"假设的**。AIP 用 Revocation Object 而非 JWT，我做了归一化，可能与实际实现不一致。
3. **只覆盖"消费侧"**，不覆盖"生产侧"。我们不生成 CRL，只判定如何读它们。

---

## 6. 这条路的真实价值

如果 AIP / Clawdentity 被 WG 采纳，我们不是被替代，而是**变成它们的测试套件**——因为它们都缺"消费侧一致性用例"。

如果它们没被采纳，这套 profile 就是"撤销语义的可执行定义"，仍然可用。

两条路都指向同一个动作：**先跑通、再发布**，而不是先喊领先。
