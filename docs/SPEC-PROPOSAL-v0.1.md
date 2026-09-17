# UIBC Core Specification — PROPOSAL v0.1（草案）

> 状态：PROPOSED（对应总档案 §35 Protocol 标尺 P0-P1）。本文档是工程摘录的最小可执行子集，
> 不是正式规范。变更遵循 SemVer + 向后兼容原则（行动计划·协议发布规范）。

## 1. 范围

定义 submission.uibc 包的最小结构、生命周期状态机规则、证据哈希完整性检查、
Evidence Root 计算，以及验证报告的最低披露要求（scope/limitations/checked/not_checked）。

## 2. 包结构（总档案 §22）

```
submission.uibc/
├── manifest.json      封包清单（agent_id、evidence_root、status）
├── identity.json      身份（agent_id/owner/version/status）—— Agent identity ≠ cryptographic key
├── lifecycle.json     事件链（REGISTER 起始，previous_event 链式）
└── evidence/
    ├── index.json     证据索引（type/path/content_hash）
    └── files/         证据文件本体
```

## 3. Canonical Serialization（§13，未决项）

v0.1 采用临时方案：sorted-keys / compact / UTF-8 JSON。
**升级路径**：正式规范必须迁移到 RFC 8785 (JCS) 后才能定稿签名与 Merkle 结构。
在此之前，所有 hash 均视为临时值，算法标识随报告输出。

## 4. Evidence Root（v0.1 临时算法）

```
evidence_root = SHA-256( canonical_json( sorted( [content_hash_1...content_hash_n] ) ) )
```

## 5. 生命周期状态机（§11）

规则 L1-L7 见 `uibc_core/lifecycle.py` 文档字符串。非法转移 = lifecycle state violation。

## 6. 验证结果（§16/§17）

- 结果集：PASS / FAIL / INCONCLUSIVE
- 报告必须披露：scope、limitations、checked、not_checked
- PASS 的语义："No violation was detected within the observed evidence boundary."

## 7. 明确不做（Non-goals，§26）

不证明：哲学身份、意识、universal trustworthiness；不替代法律/监管；不做行为评估。

---

# v0.2 增补：封签签名（Seal Signature）[PROPOSAL]

> 状态：PROPOSAL（对应总档案 §10/B5 签名决策、§19 Certificate 纪律）。
> 本节为 uibc-core v0.2.0 实现所依据的工作规范，非正式标准。

## 1. 决策记录

| 项 | 决定 | 依据 |
|----|------|------|
| v0.2 签名算法 | HMAC-SHA256（对称） | 纯标准库零依赖；关闭 v0.1 malicious 盲区（攻击者无钥不可重算封签） |
| v0.3 目标算法 | Ed25519（非对称） | 第三方可验证；待 `cryptography` 依赖决策后切换 |
| 签名对象 | canonical({"identity":…, "manifest":…}) | 与证据哈希同一套临时 canonical JSON（RFC 8785 前不视为已批准） |
| 封签存放 | `signatures/seal.json` | carrier 与 semantics 分离（§22） |
| 生命周期事件签名 | 未批准，`event.signature` 保持 None | 规范未定稿前不强制算法（§10） |

## 2. seal.json 结构

```json
{
  "schema": "uibc-core/0.2.0-proposal",
  "algorithm": "HMAC-SHA256",
  "key_id": "<sha256(key) hex —— 单向摘要，可公开>",
  "signed": "identity+manifest",
  "signature": "<base64 HMAC>",
  "created_at": "<UTC>"
}
```

## 3. 验证语义（S6）

- **开放模式**（无钥）：封签存在 → INCONCLUSIVE；不存在 → SKIP（v0.1 兼容）。
- **严格模式**（`--key`）：封签缺失 → FAIL；algorithm 未知 → FAIL；
  key_id ≠ sha256(所给钥) → FAIL（**换钥在此被检出**）；HMAC 不符 → FAIL；
  全部通过 → PASS。

## 4. 已知边界（继承 §17 纪律，逐条声明）

1. 对称签名：验证者必须持钥 → 本版不提供第三方验证。
2. 换钥攻击：攻击者可整体重签 → 仅业主密钥（链外钉扎）可检；
   fixtures/malicious-keyswap 为常设动机案例。
3. Ed25519 + 公钥注册表 = v0.3 目标。
4. 本节不构成 §19 意义上的 Certificate；Certificate 签发体系另行立项。
