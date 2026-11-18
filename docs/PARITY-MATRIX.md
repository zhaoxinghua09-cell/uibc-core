# 竞品对齐矩阵（"任何一项都不能弱于他们"的可执行版本）

> 结论先说：**"每一项都不弱"做不到，硬说就是撒谎。** 能做的是——每条维度都给出
> 现状、差距、以及"补到什么程度算对齐"。目前 **11 项已对齐或领先，3 项结构受限，3 项明确不做**。

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
| 内嵌自验脚本 | AIVS 把验证脚本放进包里，我们还要求 clone 仓库 | 把 `iverify.py` 打成单文件塞进包 `verify/`（半天，兼容性无损） |

## 4. 一句话口径（对外只能说这些）

> 在**包形态、免依赖自验、篡改可见、截断/回滚检测、被拒留痕、分级映射**六项上，我们与现有草案对齐；
> 在**公开可复算基准**一项上领先（别人没有可复跑的漏判语料）。
> 我们**没有**见证人、**没有**生产部署、**没有**集成生态——这三项不宣称，也不靠措辞掩盖。
