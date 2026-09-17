# uibc-core

UIBC Core 参考实现 v0.1.0 **[PROPOSAL]** —— Agent 生命周期证据包与验证器。

理念（LGD）：**有籍 · 有证 · 有门禁** → Registry（身份注册）/ Evidence（内容哈希证据）/ Gates（生命周期状态机 + 验证门禁）。

> ⚠️ 状态：PROPOSAL，非正式标准。验证结果是**限定范围的证明**（scoped proof）：
> PASS 仅表示"在观测到的证据边界内未发现违规"，不声称绝对可信。

## 5 分钟 Quickstart

```bash
pip install -e .

# 1. 建包
uibc init demo.uibc

# 2. 注册 agent（有籍）
uibc register demo.uibc --agent-id my-agent-001 --owner alice

# 3. 生命周期事件（门禁状态机管理）
uibc event demo.uibc --type ACTIVATE

# 4. 附加证据（有证：自动记录 SHA-256）
uibc evidence demo.uibc --type ACTION --file report.txt --note "agent action log"

# 5. 封包（计算 Evidence Root 写入 manifest）
uibc submit demo.uibc

# 6. 验证（门禁）：exit 0 = PASS
uibc verify demo.uibc
```

## 验证什么（v0.1 检查项）

| 检查 | 内容 |
|------|------|
| S1 | 包结构完整（manifest / identity / lifecycle / evidence index） |
| S2 | identity 与 manifest 的 agent_id 一致 |
| S3 | 生命周期状态机（REGISTER 开头、previous_event 链、REVOKE/RETIRE 终态、非法转移报 lifecycle state violation） |
| S4 | 证据文件 SHA-256 逐一重算比对（防篡改核心） |
| S5 | Evidence Root 重算比对 manifest |

## 报告纪律（总档案 §16/§17）

每份验证报告必须包含：`scope`（范围）、`limitations`（局限）、`checked`（查了什么）、`not_checked`（没查什么）。
v0.1 明确不查：密码学签名、外部时间戳锚定、行为评估、记忆忠实性/连续性。

## 已知边界（诚实清单）

- 签名字段存在但 v0.1 未实现签名验证（规范未定稿前不强制算法）
- Evidence Root 算法为临时版（sorted hashes 的 SHA-256），待 canonical serialization 定稿后升级为 Merkle 树
- 时间戳未做外部锚定（生产用 OTS/Rekor，见行动计划）

## 对应规范

- 《XLGD/LGD/UIBC 历史讨论总档案 v0.1.0》§9-§26
- 《UIBC 工程实现摘录 v0.1.0》
- SPEC 提案：`docs/SPEC-PROPOSAL-v0.1.md`

## Golden Fixtures (archive SS30)

Benchmark as executable evidence — seven mutation categories, each a runnable
submission.uibc package:

```text
fixtures/
├── clean.uibc        PASS            baseline
├── tampered.uibc     FAIL  (S4)      evidence content rewritten
├── deleted.uibc      FAIL  (S4)      evidence file removed
├── duplicated.uibc   FAIL  (S5)      index entry duplicated, seal stale
├── reordered.uibc    FAIL  (S3)      lifecycle chain broken
├── migrated.uibc     FAIL  (S5)      partial migration, manifest not re-sealed
└── malicious.uibc    PASS*           full self-consistent forgery — UNDETECTED
                                     by v0.1 (no signatures yet); the standing
                                     motivating case for v0.2 Ed25519
```

Regenerate + re-verify: `python fixtures/generate_fixtures.py` (writes
`fixtures/EXPECTED.md` with expected-vs-observed per archive SS31 fields).
