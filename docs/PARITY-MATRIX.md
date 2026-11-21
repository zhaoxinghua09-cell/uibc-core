# 竞品对齐矩阵（"任何一项都不能弱于他们"的可执行版本）

> 结论先说：**"每一项都不弱"做不到，硬说就是撒谎。** 能做的是——每条维度都给出
> 现状、差距、以及"补到什么程度算对齐"。目前 **11 项对齐（其中两项不再声称领先），3 项结构受限，
> 3 项明确不做，另有 6 维我们没有对应物**（见 §4，2026-11-20 补齐后新增）。

## 1. 对齐表

| # | 维度 | 谁有 | 我们 | 判定 | 依据 |
|---|---|---|---|---|---|
| 1 | 可携带包 + 离线验证 | AIVS、AAT、raskar-00 | 有（manifest/identity/lifecycle/evidence/seal） | **对齐** | S1–S5、S7 |
| 2 | 免依赖自验（stdlib only） | **AIVS 独有的杀手特性** | **今日补齐**：`independent_verifier/iverify.py` 仅用 stdlib，覆盖 V1–V9，语料 21/21 一致 | **对齐（接近）** | `benchmark/adapter.py` 21/21 |
| 3 | 篡改可见的哈希链 | AAT、NHE、GAR、capsule | 有（事件链 + 封签 + 三档基准） | **领先**（有公开可复算基准） | `benchmark/` 未解释接受 0 |
| 4 | 截断/回滚检测 | bailey（head commitment）、1F916（checkpoint） | 有（S8 自洽 / S9 带外钉扎） | **对齐** | M20/M21 |
| 5 | 计算闭包（权重/分词器/模板/引擎/解码/数值环境） | **AAT-03 的 Attestation Closure** | **今日新增 S10**：声明六项即 PASS，缺项即 FAIL；**不声称验证内容** | **声明层对齐，证明层不做** | `tests/test_v11_closure.py` |
| 6 | 被拒调用留痕 | COGITATOR phantom entry | 有（`uibc_core/phantom.py`，改/删/缺口全能抓） | **对齐** | 6 条单测 + 门禁 5 条 |
| 7 | 策略摘要绑定 | COGITATOR policy digest、GAR `cap_profile_hash` | 有（`policy_hash`，逐字复用 noa/GAR 字段） | **对齐** | S2 校验 |
| 8 | 多档证据分级 | EP-AEC-02 五档 | 三值 + 映射工具（6/6 期望达成） | **对齐（粗化）** | `tools/uibc_to_epaec.py` |
| 9 | 执行前拦截 | APort/OAP、CCS、MCP 网关群 | 有 PoC（ALLOW/HOLD/DENY，判据 `PASS+anchored`） | **功能对齐** | 5/5 |
| 10 | 结果词表（八值 disposition） | capsule / bilateral-attestation | 未定义，但决定**直接复用** | 对齐（定义层） | `docs/TERMINOLOGY.md` |
| 11 | 性能 | CCS 亚毫秒/次调用 | **两个口径都测**：**1.22 ms/次调用**（median，300 次，含索引重写与写盘；p95 1.93 ms）＋ 23 ms/包（median，50 次） | **同量级（1 ms vs 亚毫秒），不宣称领先** | `tools/latency_per_call.py`、`tools/out/latency.json` |
| 12 | 独立见证人联署 | 1F916、Sello | **无** | **弱（结构受限）** | 需第三方，自己不能发给自己 |
| 13 | 透明日志 / 外部锚 | 1F916、RFC 9162、AAC 自建 SCITT TS | **两个后端已实现**：OTS 日历（3 个）+ Nostr relay（BIP-340/NIP-01），零依赖，密码学经官方向量与 libsecp256k1/pynostr 互验；**真实提交 0 次** | **实现对齐，记录为 0** | `tools/anchor_chain_head.py`、`tools/nostr_anchor.py` |
| 14 | 生产部署 | 1F916 称已在产 | 无真实部署；**并发写入正确性已修**（8 线程 200/200，锁 + 原子写；`docs/CONCURRENCY.md`） | **弱（事实差距）；并发不在其中** | `tests/test_concurrency_and_build.py` |
| 15 | 集成广度（IDE/CLI/框架/MCP/CI） | APort 已接 Claude Code/Cursor/Goose/Codex/Gemini CLI | CLI + MCP server + A2A 适配器 + 框架钩子（三形状零依赖）＋ **真 LangChain 栈内实测**：`BaseCallbackHandler` 子类，langchain-core 1.8.2 跑通 6 项 | **对齐（框架已实测；IDE 插件仍缺）** | `adapters/frameworks/langchain_callback.py`、`docs/LIVE-INTEGRATION.md` |
| 16 | 单一评分/排名 | GAR、ERC-8004、ATEP | 明确不做 | **不做** | 两家都禁止压成单分 |
| 17 | 决策结果（ALLOW/DENY/ESCALATE/SUSPEND） | GAR-08 | 明确不做（正交维） | **不做** | 我们答"验不验得清" |
| 18 | 行为/合规判断 | 无人提供（监管自己判） | 明确不做 | **不做** | 越过即失效 |

## 2. 今天实际补上的三项（不是计划，已落地）

1. **第二实现补到同水平**：`iverify.py` 新增 `undeclared_root_files` / `index_metadata_digest` /
   `lifecycle_head` / `checkpoint_head`，对应 V7/V8/V9。语料比对 **18/21 → 21/21**。
   这一步同时解决两件事：语料暴露的实现漂移，以及 AIVS 的"免依赖自验"（该实现全程只用 stdlib）。
2. **S10 闭包声明**（对齐 AAT-03）：六项组件各自必须给出 sha256，缺一项判 FAIL；
   但**绝不声称**这些摘要对应真实运行环境——这正是 AAT 承认只能靠 attested environment 解决的部分。
3. **延迟实测**：23 ms/包（median），把"离线验证很慢"的猜测换成数字，并明确不与 CCS 的
   "亚毫秒/次调用"混比（单位不同）。

## 3. 仍然弱、且现在补不了的

| 维度 | 为什么补不了 | 唯一解法 |
|---|---|---|
| 见证人 / 透明日志 | 自己给自己联署等于没联署 | 找到第一个真实的外部见证方（第二家机构或公开日志） |
| 生产部署 | 事实，不是文档 | 真实用户跑起来并留下可查记录 |
| 集成广度 | 适配器代码能写，**被生态采纳不能自封** | 已给出可跑的形状适配器（`adapters/frameworks`，7 项测试）；剩下的是分发与上游采纳，仍属运营问题 |
| 内嵌自验脚本 | ~~AIVS 把验证脚本放进包里，我们还要求 clone 仓库~~ → **2026-11-20 已补**：`uibc submit --embed-verifier <script>` 把单文件验证器放进 `verify/uibc_verify.py`，`manifest.embedded_verifier` 记 path + sha256，S1 校验 hash（改了就叫 FAIL，不是"没覆盖"） | `tools/build_standalone_verifier.py` 从 `iverify.py` 现场生成该单文件；实测：无仓无 pip 直接跑 → INCONCLUSIVE/exit 2（未签名包的正确结论），签发包装进 → PASS/anchored，篡改嵌入脚本 → S1 FAIL。**仍与 AIVS 对齐、不领先**：他们先有，我们只是补上 |

## 4. 覆盖补齐与主张下调（2026-11-20）

上表的 18 维只覆盖了当时读到的 4–5 份草案。读 `draft-templeman-scitt-measurement-capsule-00`
与 `draft-schrock-ep-authorization-receipts-13` 的引用网之后，同域草案至少 **16 份**，
其中三份的版本号（-13 / -10 / -09）比我们的发布号（0.4.1）成熟得多。补齐后有三条主张必须往下调：

| 原主张 | 事实 | 处置 |
|---|---|---|
| 「三值裁决是我们的特色」 | `draft-schrock-ep-authorization-receipts-13`（**Standards Track**）变更记录写明 "three-state verification result"；`templeman` 把 "could not be checked" 设为一等结果；arXiv 2610.07675 用 PASS/REVIEW/BLOCK | **撤回特色表述**，只说"我们与这三家同构" |
| 「字节钉扎 + 外部锚是我们独有的做法」 | 对手同样钉 commit / tree oid / 工具链 / 语料 sha256（`conformance/external/rust-cleanroom-jdieselny.v1.json`） | **降为"做法同源"**，不再列为差异点 |
| 「免依赖离线自验」 | 是 `draft-stone-aivs-01` 的主打卖点，且其验证脚本就在包内 | **保持"对齐但不领先"** |

覆盖率补齐后新增的对照（只写有据可查的部分）：

| 草案 | 最新版 | 与我们重叠的 | 我们没有的 |
|---|---|---|---|
| `schrock-ep-authorization-receipts` | -13 | 执行前绑定、三值结果、离线验证需外部选择的信任输入（等价于我们的 anchored/unanchored） | **外部净室实现 + 353 例敌意语料**；Standards Track 身份 |
| `schrock-ep-bounded-capability-receipts` | -01 | 能力边界与支出控制 | 该维度我们完全没有 |
| `schrock-ep-quorum` | -03 | 审批人集合 | 多方法定人数（quorum）我们没有 |
| `nelson-agent-delegation-receipts` | -10 | 代理授权链 | 委派语义我们只有 TRANSFER/DELEGATE 事件，无回执格式 |
| `marques-asqav-compliance-receipts` | -09 | 决策回执携带 policy digest | 合规配置层（映射到具体法规条款）我们没有 |
| `sahu-agent-action-receipts` | -00 | 签名哈希链动作回执 | 无（形态同层） |
| `dogru-cedulon-decision-profile` | -03 | 决策与效果对账 | 功效追踪层我们没有 |
| `mih-sokolov-scitt-payload-binding` | -05 | 规范化声明（JCS/CBOR 绑定） | 我们的 `root_algorithm` 仍标 provisional，对方已单独成文 |
| `hopley-x402-compliance-receipt` | -02 | 分类筛查结果 | 支付场景适配我们没有 |
| `noa-scitt-ai-agent-receipt` | -01 | SCITT 承载 | 我们只在检查依据里引用它，未做 SCITT 侧适配 |

**净结论**：18 维里有 6 维「我们根本没有对应物」（quorum、委派回执、合规配置层、功效追踪、支付适配、SCITT 侧适配）。
把它们写成"不做"是诚实的，写成"不弱于"是撒谎。上一句"每一项都不弱于他们做不到"，在这张补齐后的表面前
比写它的时候更成立。

## 5. 一句话口径（对外只能说这些）

> 在**包形态、篡改可见、截断/回滚检测、被拒留痕、分级映射、免依赖自验**六项上，我们与现有草案对齐（不领先）；
> 三值裁决与三家同构，字节钉扎与对手做法同源，**两者都不再作为差异点**；
> 仍然只属我们的只有三条流程证据：**公开可复算的漏判语料、跨版本迁移向量、版本下限机制**——
> 且限定为"据本人检索未发现公开等价物"。
> 我们**没有**见证人、**没有**生产部署、**没有**集成生态、**没有**外部实现（记录数 0），
> 并在六维上**没有对应物**。这些不宣称，也不靠措辞掩盖。

