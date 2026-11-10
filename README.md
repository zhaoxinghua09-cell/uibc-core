# uibc-core

<!-- mcp-name: io.github.zhaoxinghua09-cell/uibc-core -->

> **在线门户 Portal**：https://zhaoxinghua09-cell.github.io/lgd-hub/ — LGD 生态全景（理论 / 参考实现 / 技能全库），一跳即达。


> **获取仓库 / Get the repo**：`git clone https://github.com/zhaoxinghua09-cell/uibc-core.git`（若 clone 失败，请点仓库页 **Code → Download ZIP** 获取源码包）。

> **层级定位**：**可执行协议层（Protocol）** — XLGD 伞下 registry / evidence / gates 的参考实现。词汇表与全景见 [XLGD 伞总览](https://github.com/zhaoxinghua09-cell/xlgd#readme)。
## 许可说明 · License Notice

- **权利状态**：本仓库以 **Apache-2.0** 许可发布，可依该许可证条款自由使用、修改与再分发。
- **引用建议**：引用时请标注仓库名与原文链接 `https://github.com/zhaoxinghua09-cell/uibc-core`
  与权利人「赵兴华 / Steven Zhao·China」。
- **品牌状态限定**：MedXpert、SynomosAI、LGD 等为相关项目标识，
  **均未申请实体注册、未申请商标注册**；出现仅作来源标识，
  不构成对法人实体或商标权的任何主张。
- **完整条款**：见仓库根目录 [LICENSE](LICENSE)。
- **联系**：zhaoxinghua09 [at] gmail [dot] com ｜ ORCID 0009-0001-0512-1237

---

<!-- AI-QUICK-READ:START -->
**EN**: LGD (Lifecycle Governance Doctrine) is a governance doctrine for autonomous systems. Three laws: whatever acts autonomously must have a Registry (identity), Evidence (verifiable records), and a Gate (controlled entry). Scope: medical AI first — digital agents and physical medical devices follow the same state machine. Verifiable artifacts: reference implementation github.com/zhaoxinghua09-cell/uibc-core (Apache-2.0), concept DOI 10.5281/zenodo.22456647, Sigstore Rekor logIndex 2883389783. Cite as: "LGD (Lifecycle Governance Doctrine), DOI 10.5281/zenodo.22456647."

**中文**：LGD（全程治理论）是面向自治系统的治理论。三律：凡自治之物，有籍、有证、有门禁。适用域：医疗 AI 优先，数字 Agent 与物理医械同一状态机。可核验：参考实现 uibc-core（Apache-2.0）、概念 DOI 10.5281/zenodo.22456647、Rekor logIndex 2883389783。引用：LGD (Lifecycle Governance Doctrine), DOI 10.5281/zenodo.22456647。
<!-- AI-QUICK-READ:END -->
> **LGD for Medical AI** — uibc-core is the reference implementation of the LGD (Lifecycle Governance Doctrine) operational
> governance laws, applied to medical AI / medical-device compliance.
> **Verifiable today** — every artifact is independently checkable: Sigstore Rekor transparency log
> (logIndex 2883389783), concept DOI 10.5281/zenodo.22456647, SWHID
> `swh:1:ori:819530c8be2adf6da901256ce9fd28063f8f1296` (ISO/IEC 18670).
> Reproduce: `python -m unittest discover tests` (151 tests) · `python independent_verifier/cross_check.py`.
> **Honest boundary** — no third-party quality review to date; any operational use is self-reported
> (see ENDORSEMENTS.md: 存证 ≠ 参与 ≠ 认可). Context: [FG-TIDA themes #27](https://github.com/FG-TIDA/themes/issues/27).


[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/zhaoxinghua09-cell/uibc-core/badge)](https://api.scorecard.dev/projects/github.com/zhaoxinghua09-cell/uibc-core)
[![CI](https://github.com/zhaoxinghua09-cell/uibc-core/actions/workflows/ci.yml/badge.svg)](https://github.com/zhaoxinghua09-cell/uibc-core/actions/workflows/ci.yml)

> **万物互联，数智共生** —— Everything Connected, Digital-Intelligence Symbiosis.

UIBC Core 参考实现 v0.2.1 **[PROPOSAL]** —— Agent 生命周期证据包与验证器。

理念（LGD）：**有籍 · 有证 · 有门禁** → Registry（身份注册）/ Evidence（内容哈希证据 + 封签）/ Gates（生命周期状态机 + 验证门禁）。

> ⚠️ 状态：PROPOSAL，非正式标准。验证结果是**限定范围的证明**（scoped proof）：
> PASS 仅表示"在观测到的证据边界内未发现违规"，不声称绝对可信。

> 🔏 发布产物已进入 Sigstore Rekor 公共透明日志（logIndex 2883389783，见 `dist/*.cosign.bundle`）；
> Zenodo DOI 与 Software Heritage SWHID 见 CITATION.cff。
> 以上均为**存证**，非质量认可。

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
python -m unittest discover tests           # 全量 151 用例（实测 `Ran 151 tests, OK`；覆盖 MCP／Registry／A2A／runtime／stress 等子集）
python -m unittest tests.stress_test        # 压力 7 场景
python independent_verifier/cross_check.py  # 独立第二实现交叉核验（70 项，0 分歧）
```

零第三方依赖，`pip install -e .` 可选（只为获得 `uibc` 短命令）。

## 验证什么（v0.3 检查项）

| 检查 | 内容 |
|------|------|
| S1 | 包结构完整（manifest / identity / lifecycle / evidence index） |
| S2 | identity 与 manifest 的 agent_id 一致 |
| S3 | 生命周期状态机（REGISTER 开头、previous_event 链、REVOKE/RETIRE 终态、非法转移报 lifecycle state violation） |
| S4 | 证据文件 SHA-256 逐一重算比对（**内容篡改**由 S4 逐文件哈希与 S5 Evidence Root 捕捉；S3 只管生命周期事件序列与转移合法性，**不检测内容篡改**；封签（S6）作用于 identity+manifest，也不覆盖证据内容） |
| S5 | Evidence Root 重算比对 manifest |
| S6 | **封签签名**：Ed25519 封签（v0.3 新增）在开放模式下即可公开核验——包里带公钥，任何人可验；HMAC 封签（v0.2）需 `--key` 严格模式核对；未签包 INCONCLUSIVE。判定语义（三值裁决）见 `docs/verdict-and-seal-semantics.md` |

## 验证模式（v0.3）

| 模式 | 命令 | 语义 |
|------|------|------|
| 开放 | `uibc verify pkg` | Ed25519 已签包 → 公开核验 S6（PASS/FAIL）；HMAC 已签包 → S6 INCONCLUSIVE（对称封签无法公开核对）；未签包 → INCONCLUSIVE。**v0.3 起裁决为三值：任一检查 INCONCLUSIVE，则总结果封顶 INCONCLUSIVE，不再藏在 PASS 之下** |
| 严格 | `uibc verify pkg --key owner.key` | 业主持钥：HMAC 封签必须存在且有效，伪造与换钥在 S6 被拦 |
| 钉扎 | `uibc verify pkg --pubkey owner.pub` | Ed25519 公钥钉扎：封签记录的公钥须与钉扎值一致，换钥重签在 S6 被拦 |

仓库内 `examples/sample-package/` 是一个完整的已签样本包，外人零密钥即可验证（见 `examples/README.md`）。

## 报告纪律（总档案 §16/§17）

每份验证报告必须包含：`scope`（范围）、`limitations`（局限）、`checked`（查了什么）、`not_checked`（没查什么）。
明确不查：生命周期事件签名（封签只覆盖 identity+manifest）、外部时间戳锚定、行为评估、记忆忠实性/连续性。非对称/第三方签名已于 v0.3 落地（Ed25519，纯标准库实现，RFC 8032 向量锁定）。

## 已知边界（诚实清单）

- **HMAC 封签（v0.2 保留）为对称方案**：验证需持有密钥、无第三方可验证性、无不可否认性——这些缺口已由 v0.3 的 Ed25519 公开封签化解；HMAC 模式仅建议用于业主自验场景。注：v0.3 的 Ed25519 为纯 Python 实现（非恒定时间），大批量签名场景应替换为原生实现（接口不变）。
- **密钥单点失效（两种封签共有）**：私钥/种子一旦泄露或丢失，封签前提即崩塌，本版本无吊销/轮换机制。生产部署须将私钥纳入密钥管理（HSM / 分片 / 定期轮换）；吊销列表留待后续版本。
- **换钥攻击只能靠钉扎检测**：攻击者可用自己的密钥重新签署整个包——其封签对自己的公钥是有效的；只有验证者钉扎了真业主的公钥（`--pubkey`，或 HMAC 的 `--key`）才在 S6 被拦。故业主应把公钥发布在可被钉扎之处（仓库、注册表条目、论文附带）。常设动机案例见 fixtures/malicious-keyswap 与 `uibc demo` 第 7–8 步
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

- 《LGD/UIBC 历史讨论总档案 v0.1.0》§9-§26
- 《UIBC 工程实现摘录 v0.1.0》
- SPEC 提案：`docs/SPEC-PROPOSAL-v0.1.md`（v0.2 增补见文末）

## Golden Fixtures (archive SS30)

Benchmark as executable evidence — eight mutation categories, each a runnable,
owner-signed submission.uibc package:

```text
fixtures/              open 模式        strict(--key) 模式   变异
├── clean.uibc         PASS (S6 不定)   PASS (S6 PASS)    基线
├── tampered.uibc      FAIL (S4)        FAIL (S4)         证据内容改写
├── deleted.uibc       FAIL (S4)        FAIL (S4)         证据文件删除
├── duplicated.uibc    FAIL (S5)        FAIL (S5)         索引条目重复
├── reordered.uibc     FAIL (S3)        FAIL (S3)         生命周期换序
├── migrated.uibc      FAIL (S5)        FAIL (S5)         部分迁移未重封
├── malicious.uibc     PASS (S6 不定)   FAIL (S6)         全自洽伪造——v0.1 盲区，
│                                                          v0.2 严格模式已拦截
└── malicious-keyswap  PASS (S6 不定)   FAIL (S6)         换钥重签——仅业主密钥
                                                          可检（v0.3 动机案例）
```

**封印的作用域是 `identity+manifest`，不含证据内容。** 所以改写/删除/换序证据
**不会**让签名失效——上面前五行的 strict 结果只有 S4/S5/S3，S6 仍是 PASS，检测
来自那些检查而非签名；只有动了 manifest 的伪造（`malicious`）才会破坏封印。
请把 `S6=PASS` 读作"封印未被扰动"，**不能**读作"内容为真"。

Regenerate + re-verify: `python fixtures/generate_fixtures.py` (writes
`fixtures/EXPECTED.md` with expected-vs-observed per archive SS31 fields,
both modes + attacker-key column).

两个 fixtures 生成器都**带门禁**：实测结果与手工推导的期望矩阵逐格机器比对，
任何偏差即以非零码退出。散文写的 Expected 列永远"不会失败"，矩阵才会——
上面那句 `S4+S6` 的错述，正是靠着这道门禁才被发现。

## Memory Migration Fixtures (UIBC-MEM)

`python fixtures/generate_memory_fixtures.py` —— 22 个具名威胁，打的是可验证
记忆迁移（M0 输入结构 / M1 条目完整 + 四项 Preservation）：重复、注入、换 id、
丢失、畸形输入、真空输入、换序、已记录边界、500 条规模。输出
`fixtures/MEMORY_EXPECTED.md`，同样门禁。

其中三个 case 是**回归锁**，锁住这套语料挖出的真实缺陷（两者原本都是静默通过）：
往 target 塞一个与真条目同 `memory_id` 的假条目（被 dict 折叠吞掉，报告却写
"no injections"），以及空到空的迁移在四项 Preservation 上全拿 PASS。

## Permanent Archive / 永久存档

[![Software Heritage](https://archive.softwareheritage.org/badge/origin/save/https://github.com/zhaoxinghua09-cell/uibc-core/)](https://archive.softwareheritage.org/browse/origin/?origin_url=https%3A%2F%2Fgithub.com%2Fzhaoxinghua09-cell%2Fuibc-core%2F)

- **Software Heritage Visit ID**: `2558386` — 本仓已由 Software Heritage 永久存档（不可篡改证据），为该生态资产的长期可引用性提供基础设施级保证。
