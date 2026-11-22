# GTP/1 互操作映射表（草案）

**日期**：2026-11-19 · **状态**：草案，未对外 · **原则**：**不对抗，只补位**

一句话：别人已经定义了"身份"和"授权"的语法，我们不重造，只在上面加一层**可独立复算的证据与撤销**。

---

## 1. 与 IETF 草案的字段映射

| 现有草案 | 它们定义了什么 | 映射到 GTP/1 的哪个字段 | 我们额外提供什么 |
|---|---|---|---|
| `draft-aap-oauth-profile-01`（AAP） | `agent.id`、`agent.runtime.attested`、`task.purpose`、委托链 claims | `identity.entity_id` ← `agent.id`；`identity.agent_version` ← `agent.runtime.attested` 的摘要；`authorization.scope` ← `task.purpose` 的收敛 | 这些 claim 的**证据绑定**（谁在何时用什么证据断言过） |
| `draft-hardt-oauth-aauth-protocol-05`（AAuth） | per-instance 身份、HTTP Message Signatures、missions、无预注册建身份 | `identity.key_fp` ← 该签名密钥的 SPKI 指纹；`authorization` 的 missions ← 多资源授权上下文 | missions 的**跨平台可验摘要**（C 平台不需要信任 issuer 数据库） |
| `draft-liu-agent-operation-authorization-02`（阿里+Cisco） | `agent_operation_proposal` / `agent_operation_authorization` / `evidence` / `context` | 我们的 `evidence` 段与它的 `evidence` claim 同构；我们的 `authorization` 段对应它的 authorization token | 它的 evidence claim 是"引用"，我们补**重算与失效判定**（ttl、digest、撤销） |
| `draft-mishra-oauth-agent-grants-02`（DAAP） | resource-bound、sender-constrained token、token exchange 衰减 | `authorization.scope` 收敛后写入；衰减链保留在 `authorization` 的审计字段 | 衰减链的**可离线回溯** |
| `draft-klrc-aiagent-auth-01` | 复用 WIMSE + OAuth，明确"静态 API key 是 antipattern" | 我们完全同意；`identity.key_fp` 即短期凭证公钥指纹 | 凭证过期后，**证据仍然可验**（这是他们不处理的） |
| Web Bot Auth（IETF WG） | 请求级签名（Cloudflare/GoDaddy/Google/AWS 已支持） | 我们**不替换**它的签名；`evidence` 段与之并存，签名通过 ≠ 内容可信 | 签名有效与内容可信的**分离** |

---

## 2. 与支付/商务标准的映射

| 标准 | 所有权 | 映射 | 边界 |
|---|---|---|---|
| **Visa TAP** | Visa | `evaluation.domain = "commerce"`，TAP 的 registry 状态可作为一条 evaluation | 我们**不做**支付认证，只登记其结论摘要 |
| **Mastercard Agent Pay** | Mastercard | 同上；agent registry 结果作为 evaluation 的一条 | 域内 registry 不能当跨域撤销源 |
| **Verifiable Intent**（Mastercard + Google，2026-03 开源） | 联合 | 其"用户身份+指令+交易结果"三要素 ↔ 我们的 `identity` + `authorization` + `evidence` | VI 的**选择性披露**我们保留，不强制全量暴露 |
| **Google AP2** | Google | `authorization.scope` 可映射 Intent/Cart Mandate 的摘要 | 未见生产级跨域撤销，仍是空白 |
| **ARS**（Quantifying Trust 提出） | 社区 | 结算层标准，与我们的验证层正交 | 不重叠、不竞争 |

---

## 3. 三条不越界声明

1. **签名有效 ≠ 授权有效**：`identity.sig` 通过只证明"这个键签了这条断言"，不证明"它被允许做这件事"。授权永远在 `authorization` 段单独判定。
2. **评测通过 ≠ 安全**：`evaluation.score` 只描述**在某个语料、某个规则版本下的表现**，不构成认证，不映射为权限。
3. **注册 ≠ 现实身份**：`entity_id` 是密码学标识，不是法人、不是自然人、不代表任何资质。

---

## 4. 我们相对这些标准的增量（唯一值得说的部分）

| 增量 | 现有标准是否覆盖 |
|---|---|
| 公开一致性向量（30 条，语言中立） | **否**——草案通常只写要求，不出可执行向量 |
| 撤销 feed 的 `serial` 单调 + `next_expected_by` + 只增不删 | **否**——支付网络是域内 registry，无跨域 feed 语义 |
| 快照过期的 fail-closed（V-17） | **否**——多数实现把"查不到"当"没撤销" |
| 离线永验（不依赖 issuer 在线） | **否**——XAA/AAuth 仍需要 issuer 端点 |
| 规范化攻击面成文（重复键/NFC/NaN/大整数/数字词法） | **否**——散落在各实现的安全公告里，没有统一向量 |

---

## 5. 使用方式

实现者只需做两件事：
1. 跑 `repro_kit/`（`python run.py` 或 `node run.mjs`），得到 30/30 才算符合本规范；
2. 按下表把已有 claim 填进 bundle，**不需要改自己的令牌格式**。

```jsonc
// 最小可用 bundle（只填你已有的）
{
  "bundle_version": "gtp/1",
  "identity":  { "entity_id": "<你的 agent.id>", "key_fp": "<你的签名密钥指纹>", ... },
  "evaluation":{ "score": ..., "rule_version": ..., "engine_version": ..., "corpus_version": ..., ... },
  "authorization": { "scope": [...], "expires_at": ... },
  "revocation": { "serial": ..., "revoked": [...], "sig": ... }
}
```
