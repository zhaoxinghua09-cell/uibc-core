# GTP/1 — Global Trust Passport 规范（草案 v0.1）

**状态**：草案，未发布、未对外。**日期**：2026-11-19
**配套**：`repro_kit/vectors.json`（30 条语言中立向量）· `repro_kit/run.py`（零依赖参考运行器）
**关键词**：MUST / MUST NOT / SHOULD / MAY 按 RFC 2119 解释。

---

## 1. 目的

让**接收方（平台 C）在不访问签发方（平台 A/B）内部数据库的前提下**，验证一个 Agent 的：身份、证据完整性、评测版本、授权有效性，以及撤销状态。

本规范**不定义**新的密码学原语，只定义承载与校验规则。

---

## 2. 设计原则

1. **自证优先**：能靠 bundle 自证的，不放进注册中心。
2. **四签独立**：身份由注册方签、评测由评测方签、授权由授权者签、撤销由撤销源签。缺一即不可判定。
3. **默认拒绝**：任何字段缺失、未知版本、撤销不可确认，一律 DENY。
4. **可离线**：校验只依赖 bundle + 本地信任锚 + 可选撤销快照，不需要联网到签发方。

---

## 3. Bundle 结构

```json
{
  "bundle_version": "gtp/1",
  "identity": {
    "entity_id": "uibc:<22-char-base32>",
    "key_fp": "<sha256 of SubjectPublicKeyInfo, hex>",
    "agent_version": "1.1.0",
    "status": "REGISTERED|SUSPENDED|REVOKED",
    "issuer": "platform-A",
    "issued_at": "<ISO8601>",
    "sig": "<base64>"
  },
  "evidence": {
    "evidence_id": "ev-001",
    "entity_id": "uibc:...",
    "agent_version": "1.1.0",
    "source": "observed|declared",
    "producer": "monitor-1",
    "issued_at": "<ISO8601>",
    "ttl_days": 90,
    "digest": "<sha256 of canonical payload>",
    "sig": "<base64>"
  },
  "evaluation": {
    "entity_id": "uibc:...",
    "agent_version": "1.1.0",
    "score": 91,
    "rule_version": "rules/2",
    "engine_version": "engine/3",
    "corpus_version": "corpus/2026.11",
    "evaluator": "platform-B",
    "evaluated_at": "<ISO8601>",
    "report_digest": "<sha256>",
    "sig": "<base64>"
  },
  "authorization": {
    "auth_id": "auth-8842",
    "subject": "uibc:...",
    "scope": ["read", "write"],
    "expires_at": "<ISO8601>",
    "issuer": "auth-issuer",
    "sig": "<base64>"
  },
  "revocation": {
    "checked_at": "<ISO8601>",
    "source": "<feed url or id>",
    "serial": 1024,
    "revoked": ["uibc:..."],
    "sig": "<base64>"
  }
}
```

---

## 4. 校验算法（接收方 MUST 按序执行）

```
1  指纹     key_fp MUST 等于本地钉扎值；否则 DENY(identity)
2  证据签名  重算 canonical digest 与 sig；不一致 DENY(evidence_tampered)
3  证据时效  issued_at + ttl_days > now；否则 DENY(evidence_expired)
4  评测版本  (rule_version, engine_version) MUST 在本地兼容表内；否则 DENY(version_unknown)
5  评测签名  重算 report_digest + sig；不一致 DENY(evaluation_tampered)
6  授权      expires_at > now 且 requested_scope ⊆ scope；否则 DENY(auth_invalid)
7  撤销      snapshot SHOULD 存在；缺失 → DENY(no_revocation_source)
            snapshot 年龄 > max_snapshot_age → DENY(snapshot_stale)
            entity_id ∈ revoked → DENY(revoked)
8  以上全过  ALLOW
```

**第 7 步是强制项**：撤销不可确认时不得放行。这正是 `vectors.json` 中 V-17/V-18 覆盖的行为。

---

## 5. 签名 revocation feed（本规范的核心创新点）

### 5.1 为什么必须单独定义

今天所有平台的审计日志都在自己的库里；**跨平台的撤销状态没有任何标准**。Okta 的 XAA、支付网络的 trusted agent registry 各自解决自己域内的问题，跨域仍无解。

### 5.2 Feed 格式

```json
{
  "feed_version": "gtp-rev/1",
  "issuer": "platform-A",
  "serial": 1024,
  "issued_at": "2026-11-19T12:00:00Z",
  "next_expected_by": "2026-11-19T18:00:00Z",
  "entries": [
    {"entity_id": "uibc:...", "kind": "IDENTITY|EVIDENCE|AUTHORIZATION|VERSION",
     "target": "...", "reason_code": "key_compromise", "effective_at": "<ISO8601>",
     "scope": "all|dependents"}
  ],
  "sig": "<base64 over canonical(entries+serial+issued_at)>"
}
```

### 5.3 三条硬规则

| 规则 | 说明 |
|---|---|
| **serial 必须单调递增** | 接收方 MUST 拒绝 serial ≤ 已见最大 serial 的 feed（防回滚攻击） |
| **必须带 `next_expected_by`** | 超过该时间未更新 → 快照视为 stale → DENY（这正是 V-17） |
| **只增不删（链式哈希）** | `h_i = SHA256(h_{i-1} ‖ canon(entry_i))`；删除或改写任一历史条目，重算 head 必变 → 拒绝 |

### 5.3.1 签名与密钥生命周期（v0.2 增补）

- 签名算法 **MUST** 为 Ed25519（草案 v0.1 曾以 HMAC 演示，HMAC 不可用于生产：能验的人也能签）。
- feed 内 MUST 携带 `signer_fp`（对公钥 Raw SPKI 取 SHA-256），且该指纹 MUST 已被**钉扎给该 issuer**。签名有效但指纹未钉扎 → `REJECT:signer_not_pinned`（签名有效 ≠ 身份可信）。
- **轮换**：由旧钥签名的 `KEY_ROTATION` 条目（`old_fp` / `new_fp`）是唯一合法的换钥路径。**轮换 feed 必须携带全部历史条目**，否则先被"只增不删"拒绝——这一点已由测试 T16 实证。
- **撤销**：`KEY_REVOKED` 条目使该指纹进入撤销集，此后由它签发的 feed 一律 `REJECT:key_revoked`。
- 已撤销指纹与已吊销实体 MUST 分开存储：前者封密钥，后者封对象。

### 5.4 快照获取方式（三种，按环境选）

1. **拉取（推荐起步）**：C 定时 GET feed，本地缓存 + 记录 `fetched_at`、`serial`。
2. **推送**：feed 变更时 webhook 通知 C；C 仍需签名校验。
3. **随 bundle 携带**：签发方把最新快照放进 bundle（`revocation` 字段）；C 校验签名与时效。**最简单，但时效依赖签发方。**

### 5.5 时效参数（建议值）

| 场景 | max_snapshot_age |
|---|---|
| 支付/删除类高风险 | **15 分钟** |
| 一般受控写操作 | 1 小时 |
| 只读 | 24 小时 |

**不得**用"30 天"这类宽松值——`p23` 实验的 D10 已证明后果。

---

## 6. 与现有标准的关系（不对抗，只补位）

| 现有 | 我们如何对接 |
|---|---|
| IETF `draft-aap-oauth-profile`（agent.id / task.purpose / 委托链 claims） | 把 AAP claims 作为 `identity` / `authorization` 的**可选扩展字段** |
| IETF `draft-hardt-oauth-aauth`（per-instance identity + HTTP Message Signatures） | `key_fp` 可直接取该签名的密钥指纹 |
| Web Bot Auth（IETF WG，Cloudflare/Google/AWS 支持） | bundle 可作为 Web Bot Auth 签名之外的**证据层** |
| Mastercard Verifiable Intent / Visa TAP | 支付域的认证结果可作为 `evaluation` 的一种（需注明 `domain: commerce`） |
| Google AP2 | `authorization.scope` 可映射 AP2 的 Intent/Cart Mandate 摘要 |

**原则**：不发明新身份体系，只在已有的签名与令牌之上补"**证据与撤销的可验证层**"。

---

## 7. 一致性要求

实现若声称符合 GTP/1，MUST 通过 `repro_kit/vectors.json` 全部 30 条（≥80% 为"部分符合"，MUST 显式声明未通过项，不得沉默）。

---

## 8. 未决问题（应进 RLP）

1. `entity_id` 的碰撞处理（同一 creator 同名不同项目）
2. 多撤销源并存时的合并规则（当前只支持单源）
3. 离线场景下 `next_expected_by` 与设备时钟漂移的容错
4. 评测语料版本变更是否需要强制复评（当前只判 version，不判 corpus）
