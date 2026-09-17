# uibc-core

UIBC Core 参考实现 v0.2.1 **[PROPOSAL]** —— Agent 生命周期证据包与验证器。

理念（LGD）：**有籍 · 有证 · 有门禁** → Registry（身份注册）/ Evidence（内容哈希证据 + 封签）/ Gates（生命周期状态机 + 验证门禁）。

> ⚠️ 状态：PROPOSAL，非正式标准。验证结果是**限定范围的证明**（scoped proof）：
> PASS 仅表示"在观测到的证据边界内未发现违规"，不声称绝对可信。

## 5 分钟 Quickstart

**30 秒先看效果（无需任何准备）：**

```bash
python -m uibc_core.cli demo   # 一键演示：建包→签封→验证 PASS→篡改→FAIL 捉获
```

```bash
pip install -e .

# 0. 生成封签密钥（可选，v0.2 推荐）
uibc keygen --out owner.key        # 密钥自己保管，绝不放进包里

# 1. 建包
uibc init demo.uibc

# 2. 注册 agent（有籍）
uibc register demo.uibc --agent-id my-agent-001 --owner alice

# 3. 生命周期事件（门禁状态机管理）
uibc event demo.uibc --type ACTIVATE

# 4. 附加证据（有证：自动记录 SHA-256）
uibc evidence demo.uibc --type ACTION --file report.txt --note "agent action log"

# 5. 封包 + 签署（计算 Evidence Root 并写 HMAC 封签）
uibc submit demo.uibc --key owner.key

# 6. 验证（门禁）：exit 0 = PASS
uibc verify demo.uibc --key owner.key   # 严格模式：伪造/换钥包在 S6 被拦
uibc verify demo.uibc                   # 开放模式：仅完整性检查
```

## 运行测试（外人复现三件套）

```bash
python -m unittest discover tests           # 全量 115 用例（含 11 MCP＋9 Registry＋15 A2A＋9 runtime
python -m unittest tests.stress_test        # 压力 7 场景
python independent_verifier/cross_check.py  # 独立第二实现交叉核验（70 项，0 分歧）
```

零第三方依赖，`pip install -e .` 可选（只为获得 `uibc` 短命令）。

## 验证什么（v0.2 检查项）

| 检查 | 内容 |
|------|------|
| S1 | 包结构完整（manifest / identity / lifecycle / evidence index） |
| S2 | identity 与 manifest 的 agent_id 一致 |
| S3 | 生命周期状态机（REGISTER 开头、previous_event 链、REVOKE/RETIRE 终态、非法转移报 lifecycle state violation） |
| S4 | 证据文件 SHA-256 逐一重算比对（防篡改核心） |
| S5 | Evidence Root 重算比对 manifest |
| S6 | **封签签名**（v0.2 新增）：`--key` 严格模式下，未签/伪造/换钥的包 FAIL；开放模式下已签包报 INCONCLUSIVE、未签包 SKIP |

## 两种验证模式

| 模式 | 命令 | 语义 |
|------|------|------|
| 开放 | `uibc verify pkg` | v0.1 兼容：只查完整性（S1-S5），封签存在但无法核对 → INCONCLUSIVE |
| 严格 | `uibc verify pkg --key owner.key` | 业主持钥：封签必须存在且有效，伪造与换钥在 S6 被拦 |

## 报告纪律（总档案 §16/§17）

每份验证报告必须包含：`scope`（范围）、`limitations`（局限）、`checked`（查了什么）、`not_checked`（没查什么）。
v0.2 明确不查：非对称/第三方签名（Ed25519，v0.3 目标）、生命周期事件签名、外部时间戳锚定、行为评估、记忆忠实性/连续性。

## 已知边界（诚实清单）

- **封签为对称 HMAC-SHA256（v0.2 临时方案，纯标准库零依赖）**：验证需持有密钥；第三方可验证需 Ed25519（v0.3 目标，待 `cryptography` 依赖决策）
- **换钥攻击只能靠链外钉扎检测**：攻击者可用自己的密钥重新签署整个包——用业主密钥 `--key` 验证即 FAIL（key mismatch），不持业主密钥则无法察觉。这是 v0.3（Ed25519 + 公钥注册表）的常设动机案例（见 fixtures/malicious-keyswap）
- Evidence Root 算法为临时版（sorted hashes 的 SHA-256），待 canonical serialization 定稿后升级为 Merkle 树
- 时间戳未做外部锚定（生产用 OTS/Rekor，见行动计划）

## 生态组件（Ecosystem）

| 组件 | 位置 | 说明 |
|------|------|------|
| MCP server（只读） | `mcp_server/` | 7 个工具，stdio JSON-RPC |
| Registry 服务（只读） | `registry_server/` | 三大登记处 HTTP 查询；静态查询页 `registry/index.html` |
| A2A 适配器 | `adapters/a2a/` | JSON-RPC 2.0 over HTTP：`card` / `uibc/verify` / `uibc/gate` / `uibc/inspect` |
| 示范应用（完整生命周期） | `examples/showcase.py` | 一个 agent 的可验证生命周期；实录 `examples/SHOWCASE.md` |
| 失败语料 | `failure_corpus/` | 真实失败 F-001~F-006（根因/教训） |
| 赛事包 | `contest/` | 章程/赛题/评审/提交规范/内测实录 |
| AI 发现 | `llms.txt` + `ai/` | 机器可读入口 |
| Runtime hooks | `uibc_core/runtime.py` | 一行式 `record_action` / `seal` / `event` / `snapshot` |
| 英文文档 | `README.en.md` | English documentation |

## 对应规范

- 《XLGD/LGD/UIBC 历史讨论总档案 v0.1.0》§9-§26
- 《UIBC 工程实现摘录 v0.1.0》
- SPEC 提案：`docs/SPEC-PROPOSAL-v0.1.md`（v0.2 增补见文末）

## Golden Fixtures (archive SS30)

Benchmark as executable evidence — eight mutation categories, each a runnable,
owner-signed submission.uibc package:

```text
fixtures/              open 模式        strict(--key) 模式
├── clean.uibc         PASS (S6 INCONCLUSIVE)   PASS (S6 PASS)   基线
├── tampered.uibc      FAIL (S4)        FAIL (S4+S6)     证据内容改写
├── deleted.uibc       FAIL (S4)        FAIL (S4+S6)     证据文件删除
├── duplicated.uibc    FAIL (S5)        FAIL (S5+S6)     索引条目重复
├── reordered.uibc     FAIL (S3)        FAIL (S3+S6)     生命周期换序
├── migrated.uibc      FAIL (S5)        FAIL (S5+S6)     部分迁移未重封
├── malicious.uibc     PASS (S6 不定)   FAIL (S6)        全自洽伪造——v0.1 盲区，
│                                                        v0.2 严格模式已拦截
└── malicious-keyswap  PASS (S6 不定)   FAIL (S6)        换钥重签——仅业主密钥
                                                         可检（v0.3 动机案例）
```

Regenerate + re-verify: `python fixtures/generate_fixtures.py` (writes
`fixtures/EXPECTED.md` with expected-vs-observed per archive SS31 fields,
both modes + attacker-key column).
