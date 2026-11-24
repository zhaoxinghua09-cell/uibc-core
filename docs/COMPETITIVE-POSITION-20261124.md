# UIBC 竞争位置（2026-11-24 取证版）

> **这不是单一同侪的比较。** 逐项、带复跑命令的同侪对比在 [`COMPETITORS.md`](COMPETITORS.md)（测量日 2026-11-18），机器事实在 [`COMPETITOR-FACTS.json`](COMPETITOR-FACTS.json)。本文件只补它没覆盖的**更大范围**：身份层、授权层、收据格式层、国家基础设施层的十个参与者。
> 两者冲突时，**以带复跑命令的那份为准**；本文件只是把"我们站哪"说清楚。

规则：每一格必须能指到一个可点的来源；指不到就写"未核实"。**不允许把"我们没想到"写成"别人没有"。**

对标维度（8 个）：

- **D1** 身份层是否已有规范/产品（谁定义"这个 agent 是谁"）
- **D2** 判定结果是否多值（不止 permit/deny 两态）
- **D3** 证据前置是否**强制**（无证据不得判"通过"）
- **D4** 判定标签是否防事后篡改（改了能否被发现）
- **D5** 是否有跨身份体系的统一验证器（不绑定某一家身份）
- **D6** 是否有可复跑向量与量化一致率
- **D7** 是否有非作者本人的独立实现
- **D8** 是否有组织级采纳/认证计划

---

## 一、逐家对标

| 对手 | D1 | D2 | D3 | D4 | D5 | D6 | D7 | D8 |
|---|---|---|---|---|---|---|---|---|
| **Microsoft Entra Agent ID**（GA，2026-11-17 更新） | 有，企业级一等身份 + 生命周期 + 条件访问 | 无：授权结果是策略判定（允许/阻止） | 不适用（策略授权，非证据判定） | 审计日志平台侧 | 只覆盖自家租户 | 无公开向量 | 不适用 | 有（Graph/许可/A365） |
| **DIF KYA-OS**（CONFORMANCE 1.2.0，三条阶梯 Core/Entity Card/AAP） | 有：DID+VC+委托，绑定 MCP | 部分：L1/L2/L3 + **AAP-0…AAP-4 审计保证档** | 部分：缺件即降级、fail-closed | 未规定 | 绑定 DID（不认 OIDC 之外的体系） | 有 per-requirement 测试条目 | 未公开外部实现数 | 有（DIF 工作组 + 徽章） |
| **ANP 1.2**（did:wba + WNS + P1–P9） | 有：did:wba / did:web | 无：认证通过/不通过 | 不适用 | 有（DID 文档 + 签名，但针对身份不是判定） | 只在自己的 DID 方法族 | 有 SDK 多语言（Python/Go/Rust/TS/Java/Dart） | 有（多语言 SDK） | 有（开放协议栈） |
| **SCITT / RFC 9943 + agent profiles**（noa-01、emirdag-01、thaha-00、bailey-00、mih capsule、munoz permit） | 不定义身份（借用外部） | 部分：profile 里"recorded verdict"字段，但**不规定取值语义** | 不规定 | 强：COSE 签名 + 注册 receipt + 哈希链 | 是（任何身份都行） | 无强制向量 | 多作者并存 | 有（IETF WG，RFC 9943 已发布） |
| **OpenID AuthZEN 1.0**（2026-11-06）+ AARP/COAZ | 不定义（SARC 输入） | 两态：`decision: true/false`；"deny 不是 4xx" | 不适用 | 无 | 是（transport/identity 无关） | 有官方符合性套件（6 个 plan） | 有（多家 PDP 实现） | **强：官方认证计划** |
| **GLEIF vLEI + AMC**（2026-09 论文，2026-10-29 博文） | 强：法人身份 + 角色凭证 | 无：验证 organizational identity 的通过/不通过 | 不适用（AMC 仍是提案） | 走 KERI 链 | 只认 vLEI 体系 | 无公开向量 | 生态内 Issuer 多家 | 强（治理框架 + 全球 LEI） |
| **GLEIF 自述的缺口**（2026-10-29 原文） | —— | —— | —— | —— | —— | —— | —— | 明写"mandate、其边界、执行控制仍须另行建立" |
| **中国信通院智能体标识与身份网络**（2026-10 开放接入；武汉中心 2026-11-19 试运行） | 强：标识注册 + 解析核验 + 能力发现，兼容多 DID 方法 | 未公开状态取值 | 未公开 | 区块链存证（星火·链网） | 兼容多方法，但接入其网络 | 未公开 | 未公开 | 强：北京/厦门/重庆/武汉四节点 |
| **ARIA Protocol**（两轴信任等级 L0–L3） | 有：人+实体双轴，等级重算不读值 | 部分：等级而非判定状态 | 部分：失效即降级 | 有（登记签名绑定 DID） | 自有体系 | 有"该信/不该信"清单 | 未核实 | 未核实 |
| **bailey-00（Agent Session Receipt）** | 不定义 | 部分：bounded verifier | 部分：显式 head commitment 防截断/整体回滚 | 有 | 是 | 无 | 未核实 | IETF 个人稿 |

**格子里最要紧的三件事**

1. **D2 我们不再是唯一**：KYA-OS 有三级 + 审计保证档，ARIA 有 L0–L3，SCITT profile 有 recorded verdict。多值这件事，2026 年下半年已被普遍接受。
2. **D4 我们仍罕见**：判定标签**自我复查**——`is_verified()` 不信任标签，回读证据再判。逐家看，没有第二家把"标签可能被事后改写"当成必须处理的问题。
3. **D8 我们全空**：AuthZEN 有认证计划、KYA-OS 有徽章、vLEI 有治理框架、信通院有四地节点。我们 0。

---

## 二、我们真正独有的（三条，都能用命令证）

| # | 优势 | 与谁不同 | 复跑命令 |
|---|---|---|---|
| A1 | **失败即分化**：`UNSUPPORTED`（不会做）与 `UNRESOLVED`（做不了）分开，不允许合流成"不通过" | 所有对手要么两态（AuthZEN），要么用等级下压（KYA-OS/ARIA）。两者都会把"我们没实现"说成"你不合格" | `pytest tests/test_interop_result.py -q`（14 条含映射不扁平化） |
| A2 | **无证据不得判通过，且以抛异常实现**，不是文档建议 | SCITT 明文把"判定能否复现"列为非目标；KYA-OS 降级是规范建议；我们是运行期硬拒 | `pytest tests/test_semantics_freeze.py -q`（`evidence=[]` 直接 `ResultError`） |
| A3 | **重放结果必须经公开语料与量化界**：36 条合规定向向量、21 类突变、α/β 错误率带上界 | 对手都尚未公开"接受率/漏判率"数字 | `python tools/check_vector_package.py`、`python tools/mutation_benchmark.py` |

一句话定位：**别人在造身份、造授权接口、造收据格式；我们做的是"拿到这些东西之后，怎么判、判成什么、凭什么信这个判"。** GLEIF 2026-10-29 的原话正好给了这块地的地契——"vLEI 提供组织基础，但 mandate、其边界与执行控制必须另行建立"。

---

## 三、我们已被追平或落后（诚实清单）

| 项 | 谁领先 | 差多少 | 补法 |
|---|---|---|---|
| 审计保证分级 | KYA-OS 已有 AAP-0…AAP-4 | 我们无对应档位 | 把现有 17 条可复跑断言自评成一档（AAP 风格），先有"能被别人对账的档" |
| 防截断/防整体回滚的显式 head 承诺 | bailey-00 已写入规范 | 我们 S9 判据存在但**无直接向量** | P0 缺口台账第一条 |
| 多语言实现 | ANP 有 6 语言 SDK | 我们 1（Python）+ Node 第二实现（同作者，不算独立） | 需真正外部实现——见下一份文档 |
| 符合性认证通道 | AuthZEN 有官方 6 计划 | 我们只有自建套件 | 先做到"外人 30 秒能跑完并交回 receipt" |
| 采纳与部署 | 全线（Entra GA、vLEI 生态、信通院四节点） | 我们 0 | 不可替代：需要一个真实使用方 |
| **外部执行记录** | 对手靠真实部署；我们靠邀请 | 我们有 **2 条**邀请型外部执行（`docs/EXTERNAL-NODES.md`）：001 为同工作组通信方（第三方执行、非第三方利益），002 的 `independent` 字段被本人要求加注为**不构成独立评估证据**。**无关复现 0** | 见 `docs/AUDIT-ASSURANCE-LADDER.md`：自评 AIA-2，AIA-3 需一次主动到访或一次无利害运行 |
| 审计保证阶梯 | KYA-OS 已有 AAP-0…AAP-4 | 已补自评版 `AIA-0…AIA-4`（2026-11-24） | 但**发证权不在我们手里**，自评不等于合规 |
| **生态渗透（对最接近的同侪）** | `agent-action-capsule` 有 **13 个第三方实现**（10 跑通并验证、2 同意、1 HOLD）、已落进 `ietf-wg-scitt/examples` PR #3 与 `projnanda/nandatown` PR #197/#200、且有在线验证器 `verify.actionstate.ai` | 我们同样是 **0**（README 第一屏的数字就是 2 个外部节点） | 见 `COMPETITOR-FACTS.json`（2026-11-18）；这一格我们**明显落后**，不辩解 |

---

## 四、结论（三句）

1. 身份与授权的赛道已经拥挤，且由大厂与国家基础设施主导——**在那里竞争没有胜算**。
2. 判定与证据层仍空着：GLEIF 自己点出、SCITT 明文列为非目标、AuthZEN 只给布尔、KYA-OS 只到"档位"。**我们占的正是这块**。
3. 但"占着"不等于"站住"：我们缺的不是论述，是**别人亲手跑过一次**。四项计分里三项为 0，这是唯一真正的门槛。

---

## 五、来源（日期均为发布日）

- Entra Agent ID 能力与生命周期：learn.microsoft.com `entra/agent-id/whats-new-agent-id`（2026-11-17）与 Ignite 公告（2026-11-17）
- KYA-OS 三级 + 三条阶梯 + AAP：`kya-os.org/mcp/introduction`、`decentralized-identity/kya-os-mcp` 的 `CONFORMANCE.md`（Version 1.2.0, Stable）
- ANP 1.2 文档集与多语言 SDK：`agent-network-protocol.com/docs/anp-getting-started-guide`、`anp/README.cn.md`
- SCITT：RFC 9943（2026-06）；`draft-noa-scitt-ai-agent-receipt-01`（2026-08-14，Standards Track，"policy-replay 列为本次范围外"）；`draft-emirdag-scitt-ai-agent-execution-01`（2026-10-12）；`draft-thaha-scitt-agent-execution-evidence-00`（2026-10）；`draft-bailey-scitt-agent-session-receipt-00`（2026-10-25，head commitment 防截断与回滚）
- AuthZEN 1.0（2026-11-06 发布）、AARP/COAZ 工作组稿（2026-06-15）、符合性测试计划（2026-10-08）
- GLEIF：`When Machines Act, Trust Must Be Verifiable`（2026-10-29）、`Agentic AI in Payments` 论文（2026-09）、AMC 提案自述"仍是提案"
- 信通院：开放接入公告（2026-10）、武汉中心试运行（2026-11-20 报道）、"互认而非接入"与星火·链网 5 个 DID 方法（中国日报 2026-09-29）
- ARIA Protocol 信任等级文档（`aria.bar/docs/trust-levels`）

标"未核实"的格子：ARIA 的外部实现数量与治理、bailey-00 的实现情况、信通院的状态码取值——**这些没查到，不等于没有。**
