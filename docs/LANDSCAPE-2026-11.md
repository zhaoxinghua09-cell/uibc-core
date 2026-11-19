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
