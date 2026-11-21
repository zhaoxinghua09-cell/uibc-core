# 我们在哪：2026-11 的竞品现状

写这份文档的原因不是宣传，是因为"我们比他们强"这个说法在 2026-11 的公开材料面前站不住，而继续加自测数量不会改变它。以下每条都可以点开核对。

## 一、最近的同题项目做到了什么

**Agent Action Capsule（Action State Group）** —— 与我们同题，且已经在生态里：

| 维度 | 他们 | 我们 |
|---|---|---|
| 标准文本 | `draft-mih-scitt-agent-action-capsule-05`，2026-09-26，Standards Track，IETF SCITT 组个人提交 | 无草案，只有仓库内规格 |
| 底座 | 直接建在 RFC 9943（SCITT）上，COSE_Sign1 签名 + Transparency Service 注册回执 | 自建 `uibc-anchor/0.1`，未接 SCITT |
| 互操作公开记录 | IETF 126（2026-07-24）hackathon/interop：两实现字节与摘要一致；一条 statement 注册到两个不同 TS（CCF dev node + RFC 9162 log），两份回执各自独立验过 | 双实现一致（我们自己测的，未对外展示） |
| 分发 | PyPI 两个包（`agent-action-capsule` 0.0.2 / `capsule-emit` 0.1.0） | PyPI `uibc-core` 0.4.0 |
| 接入面 | MCP / LangChain / CrewAI / Hermes 适配器 | 无框架适配器 |
| 衍生文本 | `draft-mih-agent-disclosure-envelope-00`（选择性披露）、`draft-rampalli-scitt-capsule-provenance-binding`（授权绑定，第三方作者） | 无 |

来源：`https://datatracker.ietf.org/doc/html/draft-mih-scitt-agent-action-capsule`、`https://agentactioncapsule.org/`、`https://pypi.org/project/agent-action-capsule/0.0.2/`、`https://www.ietf.org/archive/id/draft-mih-agent-disclosure-envelope-00.html`。

**结论要说得直白：在"被外部采纳"这个维度上，我们不是领先，是落后。** 他们有一个草案、一次公开互操作报告、一条第三方作者的衍生草案；我们有零。这不是形容词问题，是数数问题。

## 二、我们确实不同、且他们公开材料里没做的

| 我们的做法 | 他们公开材料中的对应物 |
|---|---|
| 19 项检查逐项生成"只违反该项"的样本，19/19 全部非零（`docs/FALSIFIABILITY.md`） | 未见逐检查项的可证伪矩阵 |
| 36 个一致性包在 Python / JavaScript 双实现上判决一致，且拒绝必须指名检查项 | 双实现字节一致（仅在 IETF 126 报告中） |
| 锚与包分处两通道，跨通道重组后仍能判 | 稀见（their trust 由 TS 回执承担） |
| 发布件三源对齐（pin / 索引 / 真实下载字节） | 未见同等严格的三源对齐 |
| 外到内的顺序：先有第三方见证核验，再谈采纳（`tools/check_witnesses.py`） | 由 TS 承担见证 |

这些是真的差异，但请注意它们全部是**自证**：证明"我们的验证器确实在验证"，不证明"别人认可我们"。自证可以写进论文的方法章，不能用来宣称领先。

## 三、三条能真正改变"采纳=0"的路线（按性价比排序）

**R1 接入而非另立：把锚映射成 SCITT statement。**
我们已经有 Rekor 条目（`logIndex 2883389783`），Rekor 是可公开验证的日志。把 `anchor.json` 的 Canonical 摘要包成 COSE_Sign1 payload 注册，就能被 SCITT 生态的 verifier 看见——不是让他们改用我们，是让我们出现在他们已有的视野里。成本：一个映射脚本 + 一次注册。**这是唯一"零成本借生态"的动作。**

**R2 把可证伪矩阵作为贡献交出去（性价比最高）。**
我们手上有一套 19 项逐项可证伪的矩阵，这是对任何 SCITT 实现都有增益的东西，而他们没有公开同类资产。把它整理成"对 SCITT profile 的 conformance 测试套件"并投稿（IETF interop 报告或直接给他们的仓库开 PR），对方没有理由拒绝——因为拒绝了就说明其检查不可证伪。**这是唯一有可能在数周内把"采纳"从 0 变成 1 的动作，且不要求我们先变强。**

**R3 提交 IETF individual draft。**
需要英文文本、引用规范、作者与联络方式，成本最高。且 R1/R2 未做成之前提交，大概率被当作又一份无人实现的提案——**这正是我们批评别人的地方**，不能自己犯。

## 四、明确不建议做的

- 继续加测试数量、加检查项。**边际收益已接近零**：内部严格度不是稀缺资源，外部采纳才是。
- 在任何材料里写"全面超越竞品"。当前事实是 0 对 1（草案数），写这句话会被一次点击推翻。
- 用学位论文承担营销功能。论文可以写"可证伪性设计"与"双实现交叉验证"，这两段是真本事；写"领先"会把真本事一起拖下水。

## 五、零采纳是可测的，不是可写的

```
$ python3 tools/check_adoption.py
bucket                    found  what
another repository            0
another codebase              0
a standards body              0
a neighbouring spec           0
VERDICT: ZERO ADOPTION - no party outside this account has taken up the format
```

四个桶分别问：别人的仓库、别人的代码、标准组织、最近的同题规格。任一桶非零时脚本退出码变 1，逼人来看——**"零"从此是一个可被推翻的测量结果，而不是一句自我描述。**

## 六、2026-11-19 复核：竞争维度变了，而"零采纳"有第三方佐证

上一版把结论写成"我们落后"。这句仍然成立，但不够准确：复核之后必须分成两个维度看，否则会得出错误的行动方向。

**as of 2026-11-19T04:14:10Z**（`python3 tools/check_citations.py` → 49 条外链，43 条本机直达；下列三条 IETF 链接均 200，arXiv 页本机 503 但正文已取回）。

### 6.1 规格与生态：差距被拉大了，不是缩小了

| 新证据 | 事实 |
|---|---|
| `draft-mih-scitt-agent-action-capsule-05`（2026-09-26，Standards Track，Expires 2027-03-30，61 页） | 一次性请求 **7 个 IANA registry**（registry group "Agent Action Capsule Parameters"，Specification Required），并写明 `Interim registry of record: REGISTRY.md`，Change controller 为 Action State Group, Inc.；正文含 Cross-Profile Comparability 与一条可机器核对的 vector `urn:action-state:aac-aep-scitt:digest-binding:2026-07-02` |
| `draft-pidlisnyi-aps-04`（2026-09-28，Informational，Agent Passport System） | 定义了 passport / 单调委托 / 签名行动记录 / verifier outcomes / **profiles** / MCP 绑定，并把要求切成 **APS Core 与 Candidate**，还写"哪些要求有 exact conformance-vector coverage"；组织下 **17 个仓库**、TypeScript/Python/MCP/Go 包、两个托管服务、npm `agent-passport-system-mcp` 6.0.0 |
| `draft-munoz-scitt-permit-profile-01`（2026-07-19，Informational，Keel API, Inc.，31 页） | 另一个独立作者的**执行前授权** profile，含 Implementation Status 段、IANA 请求、Appendix B 开列待解问题 |
| 相邻文本（同一批引用链里可见） | `draft-emirdag-scitt-ai-agent-execution-00`、`draft-kamimura-scitt-refusal-events-03`、`draft-klrc-aiagent-auth`、`draft-veridom-omp`、`draft-sato-soos-gar-08`、`draft-noa-scitt-ai-agent-receipt` 等 |

一句话：这条赛道上已经有**多家公司、多作者、多轮草案、注册表请求、四种语言的实现、两个托管服务**。以"规格完备度"和"生态规模"为尺子，我们落后不止一个身位，且这个差距**不会因为再加自测而缩小**。

### 6.2 采纳：全领域都是零，有第三方论文自己写的

`arXiv:2606.04193`（Juan Figuera，2026-06-02，22 页，cs.CR，"Notarized Agents: Receiver-Attested Confidential Receipts for AI Agent Actions"）在第 8 节把这件事写成了原话：

> **Adoption-incentive problem.** Sello is only useful if services adopt it; **in 2026, that adoption is zero.**

它还对自己提出的四条属性做了同类对比（Signet、AgentROA、Agent Passport System、`draft-farley-acta`、agentreceipts.ai、Pipelock、Attested Intelligence、SCITT），结论是"没有哪个现存系统同时具备这四条"。

这条证据改变了"零采纳"的含义：**它不是我们的耻辱，是这类格式在 2026 年的共同天花板**。因此把"采纳率"当作竞争指标是不成立的——**在这个指标上没有任何人领先，包括写了 61 页草案的人**。

### 6.3 于是我们唯一站得住的差异，恰好是他们公开材料里没有的

| 我们的做法 | 复核后仍然成立的判断 |
|---|---|
| 19 项检查逐项"只违反该项"的样本，19/19 非零 | 未在 -05 / APS-04 / munoz-01 中见到同类的逐项可证伪矩阵 |
| 36 包双实现判决一致，且**拒绝必须指名检查项** | 他们的 Implementation Status 只报"覆盖到哪"，不报"拒绝时能否定位" |
| `check_adoption.py` 四桶全零、非零即退出码 1 | **没有见到任何一方把"我们未被采纳"做成一条会失败的检查**；这是最便宜、也最不容易被反驳的一条差异 |
| `docs/PAPER-EVIDENCE.md` 每条主张带"不能支持什么" | 未见同等写法 |

### 6.4 结论（替换上一版单句结论）

- 在**规格与生态**上：落后，且差距在扩大。任何"全面超越"的表述都会被上面四条事实推翻。
- 在**采纳**上：全领域为零，无可比性，谁说自己领先谁就需要出示证据。
- 在**可证伪性**上：我们有一条别人没公开做的动作——把"零采纳"写成会失败的检查，并把"拒绝必须指名检查项"写进契约。这条可以写进论文的方法章，**但不能写成"领先"**，只能写成"我们采用了一种别人未采用的可证伪做法"。

## 七、2026-11-19 第三次复核：两处自我修正

这一节存在的唯一理由是**上两版有两句话被今天的材料推翻了**。修正写在这里，不删旧文——删掉会让人以为我们从没错过。

### 7.1 修正一：不能说"对手没有第三方执行"

上一版隐含的对照是"我们有外部节点，他们未见"。查证结果相反。

- 来源：IETF SCITT 邮件列表，2026-07-14，
  `https://mailarchive.ietf.org/arch/msg/scitt/RBzdNmy9QOfgzMgmmWekmyHv81s/`
- 原话（verbatim）："An independent party has run the full vector suite against the published package and **reproduced 32/32**."

同一线程（2026-06-23、2026-07-01）还有：Python 与 Go 两实现跑同一套 vectors "with zero divergences"；`583 passed, 9 skipped`（-02 上）；PyPI/rustion 侧另有 Rust 与 TypeScript 兄弟实现；公开 anchor 实例 `http://anchor.agentactioncapsule.org`。

**所以"第三方执行"不是我们的独占项。** 我们与它的差别只剩下面 7.3 那一条。

### 7.2 修正二："任何组织采纳 = 0"要说准

- 来源：OpenChain，2026-07-17，
  `https://openchainproject.org/conformance/2026/07/17/agent-passport-system-joins-the-openchain-community-of-conformance`
- 事实：Agent Passport System 进入 **OpenChain Community of Conformance**，就 ISO/IEC 5230:2020 与 ISO/IEC 18974:2023 作自我认证。

精确说法是：**"有组织的用户采纳该协议"仍然为 0；但"外部组织公开发布过与它的合规记录"不是 0**。这两件事不同，我此前把后者也说成了 0，那是错的。

另：APS 另有独立仓 `aps-conformance-suite`（跨实现 golden/negative fixtures），Python SDK 声称与 TS 做 byte-identical canonical JSON 对比，跨语言签名互验。

### 7.3 收窄后仍站得住的一条

对照两份材料，我们仍有**一件别人没公开做过的事**：

- 他们：独立方复现 = **全部通过**（32/32），两/四语言 = **零分歧**。
- 我们：外部节点在异体机上**跑出了 2 处分歧**（S4、S5），随后**把那条分歧做成一条会失败的检查**（`tools/external_node_regression.py`，`run_all_evidence` 第 9 项）。

即：**他们证明了"能跑通"；我们多了一条"跑不通时会被记住、并且会一直盯着"。** 这不是"更强"，是**另一种做法**——把外部发现当资产而不是当成绩。

### 7.4 结论（第三版）

可以对外说的，只有这一句：

> On specification maturity, ecosystem access and production readiness, published work from other authors is ahead. On one axis this repository differs: an outside operator found two disagreements here, and those two rows are now a check that fails if they come back. Elsewhere the same kind of independence exists — another draft reports an independent party reproducing 32/32 — so this is a difference in what is done with a finding, not a monopoly on outside execution.

中文：**规格、生态、生产就绪三项我们在后；唯一不同是"外部发现被留成一条会失败的检查"，这在别人那里未见公开对应做法。第三方执行本身已不是我们独占。**

## 八、2026-11-19 第四次复核：外部记录不是一个量级

上一节（§7）刚把"对手没有第三方执行"收回，但收得还不够。查了对手仓库的登记册之后，真实差距是**数量级**，不是"各有一次"。

### 8.1 他们的登记册

`https://github.com/action-state-group/agent-action-capsule/blob/main/INTEROP.md`
标题 `AAC Interop Registry`，状态标注 `IETF 126, Vienna, Jul 18–22 2026`，并写了一句话：

> "A name is not evidence; a digest is — every `ran` row links a public record."

其 `Independent parties` 表列出 **9 个独立方**，状态都是 `ran & verified`，每行带公开记录链接：

| 独立方 | 做了什么 | 公开记录 |
|---|---|---|
| EMILIA Protocol (Schrock) | 3 次独立计算 | PR #40 |
| Songbo Bu | vector 复现 · -03 已投 | datatracker 上的独立 draft |
| Tyche Institute (Sokolov) | TPM quote 复验 · **第三方行 0→1** | aep-pcr16-vector release · eatf/verification |
| Microsoft / CCF (Chamayou) | 双 TS、两份 receipt 均 ok | scitt-ccf-ledger PR #424 |
| NANDA / MIT | 跨注册表 deal-room **LIVE** | verify.actionstate.ai |
| GlyphZero | 双向均跑通 | cross-org-delegation-registry #3 |
| APS (Pidlisnyi) | 双向 cross-run 6/6 + 24/24 | audit-bof-preparation #9 |
| A2A boundary-seal | a2a-tck 100% MUST | capsule-emit #29 |
| GAR / SOOS | seal + verify，leaf 166 | anchor.agentactioncapsule.org |

### 8.2 我们的对应数字

| | 他们 | 我们 |
|---|---|---|
| 独立方公开记录 | **9**（每行带链接） | **1**（`docs/external-review/EXTERNAL-NODE-001.md`） |
| 对方是否把我们写进其记录 | — | **没有**（`INTEROP.md` 里没有本仓库） |

**这是本文件里最不利的一行。** 它说明：我们的问题从来不是"自测不够多"，而是**没有进入任何一份别人维护的记录**。

### 8.3 由此得到一个不必再绕的结论

他们的机制值得照抄，而且它比任何自测更硬：**"名字不是证据，摘要才是"**——一行 `ran` 必须挂一个公开记录链接。

我们的 1 行确实挂了记录（外部节点的回执 + 我们复算它的工具）。但**1 行与 9 行不在一个量级**，且我们的 1 行还是自己写的，不是别人写的。

要改变这一点，只有一条路：**让别人在他们的记录里写我们**。那需要一次对外动作（向他们开一个带回执的 PR/issue，或向 SCITT 投实现报告），**这需要授权，我停在门口**。

### 8.4 结论（第四版）

> On specification, ecosystem and the count of independent public records, other work is ahead by roughly an order of magnitude — nine independent parties with linked records against our one. The one thing this repository does differently is what it did with a finding: a disagreement found by an outside operator became a check that fails if it returns. That is a difference in handling, not a claim of superiority.

中文：**在独立公开记录的条数上，我们是 1，他们是 9；这个差距不是一个量级。我们唯一不同的做法，是把外部发现留成会失败的检查。**
