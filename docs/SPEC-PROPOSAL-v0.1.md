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
