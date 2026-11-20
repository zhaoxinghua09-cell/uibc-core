# 竞品状态：2026-11-18 实拉

上一次横向测评（PR #89）用的是几天前抓的数据，已经过时。这一页是**今天重新拉取的**，每行带出处。只看能核验的事实，不写形容词。

## 三个主要对手，今天的状态

| 项目 | 版本 | 最近一次发布/推送 | 出处 |
|---|---|---|---|
| Agent Action Capsule (AAC) | **0.17.0** | **2026-11-18 05:02Z**（当天仍在推） | `api.github.com/repos/action-state-group/agent-action-capsule` |
| capsule-emit（其 Rust/生产侧） | 0.0.13 | 2026-11-17 12:59Z | 同上，`capsule-emit` |
| aer1-pydantic（AER-1 官方 SDK） | 0.1.17 | 2026-10-19 | `pypi.org/pypi/aer1-pydantic/json` |
| arc-protocol | 1.1.4 | 2026-04-03 | `pypi.org/pypi/arc-protocol/json` |

AER-1 与 ARC 自上次抓取以来**没有更新**；AAC 今天还在动，而且它有两个实现（Python 0.17.0 + Rust 0.0.13）。

## AAC 的第三方互操作登记：13 家

`agent-action-capsule/INTEROP.md`（今天抓的原件）列出 13 个独立对手方，其中 **10 家标 `ran & verified`，且每家链到公开记录**：

| 对手方 | 公开记录 |
|---|---|
| EMILIA Protocol (Schrock) | PR #40，3 次独立计算同一摘要 `8cf0c36e…` |
| Songbo Bu | 向量复现 + 其 I-D 已上 datatracker（`draft-bu-agentproto-security-principal-binding`） |
| Tyche Institute (Sokolov) | TPM quote 复验，第三方行 0→1 |
| Microsoft / CCF (Chamayou) | 双 TS，`scitt-ccf-ledger` PR #424 |
| NANDA / MIT | 跨登记处 deal-room 上线，`verify.actionstate.ai` |
| GlyphZero (Rampalli) | 双向跑通，`cross-org-delegation-registry` issue #3 |
| APS (Pidlisnyi) | 双向 6/6 + 24/24 |
| A2A boundary-seal (Tyche) | `a2a-tck` 100% MUST |
| GAR / SOOS | 封签+验证，leaf 166，`anchor.agentactioncapsule.org` |
| Continuum / COSA | 32/32 复现（产物待出） |

另有 VSO、libp2p/VTO 标 `agreed — scheduled`，PermitReceipt 标 `HOLD`。

他们的 `IMPLEMENTATIONS.md` 还记了两件"进了别人仓库"的事：

- `ietf-wg-scitt/examples` **PR #3** 合并（2026-06-26）——测试向量进了 IETF WG 的共享 examples 仓。
- `projnanda/nandatown` **PR #197 / #200** 合并（2026-07-15，由对方维护者合并，+2049 行）——他们的库进了 MIT NANDA 的主线。

## 对照我们自己

| 维度 | 我们 | AAC |
|---|---|---|
| 外部独立第三方（有公开记录） | **0** | **10 确认 + 3 在途** |
| 提交进别人的仓库 | 0 | 2 处（IETF SCITT examples、NANDA） |
| 公开可访问的在线验证入口 | 无 | `verify.actionstate.ai` |
| 规范文本 | 本地 I-D 形状草稿，未提交 | 已投 datatracker 的 -03 + 本仓 spec |
| 实现数（语言） | 1（Python） | 2（Python + Rust） |
| 版本节奏 | 0.3.3 | 0.17.0，且当天仍推 |
| 检查项数量 | 19（S1–S19） | 未逐项计数（`verify.py` 839 行，检查 1–8 分组） |
| 红队：每条检查都有专门攻击 | 有（11+2 / 6 / 8 / 4） | 未见公开的逐检查攻击清单 |

**结论：在"外部见证"与"实现广度"上是数量级落后，不是"单点更深、面上更窄"这么客气。** 唯一能说"更深"的一列是逐检查红队覆盖——而这一列他们可能也做了，只是没公开。

## 这一轮新增的一个硬证据

我们把自己的包导出成 format-4 Capsule，用**我们自己的 JCS** 算 `capsule_id`，再交给**他们的参考验证器**判：

```
$ /tmp/cmpv/bin/python tools/emit_aac_capsule.py --package fixtures/clean.uibc --verify
capsule_id: 453c97485d523b1ba7d34a0e254ba85a17fbb868f203c8cae44386515cc9adc1
their verifier: ok=True
```

以及反向：改掉 `action_id` 而不重算 id，他们的验证器必须拒（测试守着）。

这是"我们的产出被别人的实现接受"——比自测强，但仍**不等于**"别人验过我们的包"：跑的是他们的代码，不是他们的人。

## 要缩小的差距，只有一条是真的

数量上的追赶（多语言实现、更多集成）是工程量。**0 → 1 的第三方**不是工程量：需要一个人，用他的工具、他的时间，独立跑一次并把结果留在公开记录里。

`INTEROP.md` 里那 10 行之所以是 `ran & verified`，是因为每家都留了一条我们能点开的链接。我们也需要一条。

## 2026-11-20 实测：把对方的公开批次真的复算了一遍

此前记录的是"数据集拉不到"。镜像的 `/resolve/` 当天通了，于是拉下来连同事件文件一起复算。
这是**我们复算对方**，不是第三方复算我们——方向别记反。

| 项 | 实测 | 我们的对应物 |
|---|---|---|
| 文件哈希 | `events.jsonl` 8219 B，sha256 与 `batch.json` 声明**一致** | manifest 不记事件文件哈希，记每个证据文件的 `evidence_root`（S5） |
| 单条 id | 5/5 复现，规则 `sha256(JCS(事件去掉 event_id、anchors、signature))` | 单条证据由 `evidence/index.json` 的哈希覆盖（S4/S7） |
| 整批根 | **`batch.json` 没有 root 字段**；我能算 RFC 9162 与重复奇尾两法（`bfad9468…` / `e89e4a7f…`），但**无处可校** | `evidence_root` + `checkpoint_head` 在 manifest 里，S5/S8 复算、S9 可外部钉住 |
| 签名 / 锚定 | `signature_state: UNSIGNED`，5 条 `anchors` 全为 none（他们如实标注） | 可选 Ed25519 封签（S6）、锚定事件（S15）、未签名时只说 `unanchored` |
| 三值 | `state` 字段实打实在用：`CONSISTENT` 4 / `DIVERGENT` 1，并为 `negative_control` 记了期望与实得 | 同构（v1.3 已撤回"这是我们的特色"） |

**这一栏里唯一一条我方更严的地方**：整批根。少了它，逐条都自洽的一批文件可以被无损截断，而每一条仍然验得过。
他们是否在别处（master-spine 汇总、SCITT 锚）发布过根，我只读到这一份 `batch.json`，**因此这条结论只对这一份文件成立**。

**规则不是读他们代码得出的**：`build_evidence_index.py` 两条路都不通（镜像限流 / GitHub 404），改为对第一条事件穷举
"去掉 0/1/2 个成员"的 191 种组合，唯一命中后再校验其余四条。复算脚本在仓外的 `外部复算/`，记录见
`外部批次复算_Templeman公开批次_v1.0_20261120.md`。

顺带，这次外部数据逼出了我们复算工具两处缺陷（Merkle 的 k 写成 `<=` 导致 5 叶无限递归；重复奇尾函数只接受 hex 字符串）。
两处都因自测样例只有一个叶而不触发——1 叶通过不证明分叉正确。


## 2026-11-20 实测（回执通道）：这一栏**对方比我们成熟**，不是我们领先

我们刚给 conformance 归档配了"外人回执 → issue 表单 → 校验器"这条路（PR #270）。查同业时发现
`probityai/agent-evidence-vectors` 早有一套更完整的同类机制，且它正是我们跑过 288/288 的那套语料的作者。
逐项对照（文件一手读取，走 `gh api`）：

| 项 | 他们（`agent-evidence-vectors`） | 我们（#270 之后） |
|---|---|---|
| 提交入口 | `.github/ISSUE_TEMPLATE/independent-run.yml` | `.github/ISSUE_TEMPLATE/conformance-receipt.yml` |
| 公开台账 | `RUNS.md`，一行一次运行，**按提交者原话转录**、不四舍五入、不换算成别的语料的比例 | 无（本轮补 `docs/RUNS.md`，空表 + 规则） |
| 盲/定向 | 强制字段 blind / directed / part blind | **本轮才有**（补进表单） |
| 谁写的代码 | 强制字段 independent / second-party same code / author-produced | **本轮才有**（等同我们的"关系"字段，但他们的命名更贴事实） |
| 分歧处理 | `DISPOSITIONS.md`：每条异议一个永久条目，**在被异议者自己的框架里写**，拒掉的也记 | 无（本轮补 `docs/DISPOSITIONS.md`，空表 + 规则） |
| 结论口径 | "分歧比干净通过更有价值"；不做跨语料的比率换算 | 同向，但此前没有落成文件 |
| 实验协议 | 另有 `evidence-run.yml` + 公开 lab 协议（证据种类、保留字节清单、期望答案暴露申报、正/敌意/负对照） | `docs/LAB-PROTOCOL.md` + `tools/lab_manifest.py` / `tools/check_lab_bundle.py`（**本轮补**，见下） |

**结论（对我们不利的那一半）**：在"第三方运行如何被记录、异议如何被处置"这一维，他们有台账、有永久条目、
有盲/定向分离，我们此前只有一份自述。本轮补的是其中四件（RUNS / DISPOSITIONS / 两个强制字段 / lab 协议），
**但 lab 协议仍是缩小版**：他们按"证据种类"分类（保留字节完整、验证器行为、宿主 CI 依赖、观测效果、独立见证），
并带采纳声明与按 claim 的分母表；我们只有"一次运行、一个语料、一个问题"的四件套（字节清单、敌意对照必须不满分、
退出码、暴露申报）。**没有对应物的是他们那套证据种类分类与采纳/见证层**，如实记为缺口。

**这个对照还纠正了一个我自己的说法**：我在 #270 的 PR 描述里写"这个数字此前没有登记通道"，读起来像首创。
准确表述应是"我们此前没有，补上了一个更简单的版本；同业已有更完整的版本"。页面按后者写。

**不因此改口的地方**：他们的 RUNS 里跑的是"别人的验证器跑他们的语料"，我们的语料目前仍只有本机自测回执；
两边都不是"我方的外部节点"。计数口径不变。

### 本轮补的 lab 协议，实测到什么

`tools/lab_manifest.py` 直接吃运行目录：把里面 300 个文件逐个记 bytes + sha256 + media type，再单独记归档摘要、
命令、退出码、stdout 尾、三种对照结果、暴露申报与局限清单。`tools/check_lab_bundle.py` 重算这些字节并拒绝
四类断言——摘要对不上、敌意对照拿到满分（那说明语料没有区分力）、没有退出码、暴露申报空白。

**用我们 36/36 那次的真实运行目录做过一次**（含解包后的语料与 `receipt.json`）：
`ACCEPTABLE — 300 files digested, archive 711fa82c…, controls present, limits stated`。
**但这份 bundle 的 `roles.runner` 写的是作者本人**，因此它只能计入"作者产出"，不能计入外部节点——这是设计而非疏漏。
### 2026-11-20 实测（发版资产）：他们发的是"签过名的摘要 + 两个外部时间戳"，我们只发了 zip

读三家最近三个 release 的资产清单（`gh api repos/<r>/releases`）：

| 仓库 | 发版资产 |
|---|---|
| `probityai/agent-evidence-vectors` v0.37.1 | `CORPUS-DIGESTS.txt` + `.sig`（签名）+ `.sig.ots`（OpenTimestamps）+ `.sig.tsr`（RFC 3161） |
| `tyche-institute/eatf-verifier` v0.7.4 | `eatf-pqc-hybrid-lab-v0.7.4.zip` + `.sha256` + 一份 PDF |
| `emiliaprotocol/emilia-protocol` clean-room-kit-v1 | `emilia-clean-room-kit-v1.tar.gz` + `.manifest.json` |
| **我们** v0.4.0 | **只有 `uibc-conformance-0.4.0.zip`** |

结论：**"发版挂摘要"是这三家的共同做法，其中一家还附签名与 OTS/TSA 两个外部时间戳**；我们此前连摘要文件都没挂。
本轮补的是这一层里我们做得到的：`tools/release_lab_bundle.py` 在发版时把三种对照实跑一遍，产出
`uibc-lab-bundle-<v>.json` + `receipt.json` + `CORPUS-DIGESTS.txt`，工作流在打 tag 时挂到 release。

**落后与追平的现状（2026-11-20 复核一次，按行写清）**：他们三件齐（`.sig` + `.sig.ots` + `.sig.tsr`）
挂在已发布的 release 上。我们的 `v0.4.1` release 现在也有三件中的两件：

| 件 | 他们 | 我们（`v0.4.1` release 实读） |
| --- | --- | --- |
| `CORPUS-DIGESTS.txt` | 有 | 有（287 B，`8b3818af…`） |
| RFC 3161 令牌 `.tsr` | 有 | **有**（`anchor_freetsa.tsr` 4,643 B，FreeTSA，匿名离线验 `verified: true` / `problems: []`） |
| OpenTimestamps `.ots` | 有（`.sig.ots`） | **无**（日历可达性不足 + 依赖此前未装，工作流已补装并改为三历法逐个回退；下一次运行为准） |
| 分离签名 `.sig` | 有 | **无**（缺 `UIBC_RELEASE_SEED_HEX`，挂 `UNSIGNED.txt`） |

所以当前状态读作"三件缺一，且缺的是签名"，不是"已经对齐"。缺哪件在 `ANCHORS.json` 上逐项写明，
不靠文档自述；`python tools/check_release_anchors.py` 一条命令即可复核我们已挂的那一件。

### 2026-11-20 实测（配置层）：他们写"改动怎么被决定"，我们只有一行 CODEOWNERS

读三家的 `GOVERNANCE.md`（`gh api` 逐份取全文）：

| 仓库 | 改动由谁决定 | 可机械化的那条规则 |
|---|---|---|
| `probityai/agent-evidence-vectors` | 单一维护者，公开绑住自己；提案落入**四种处置闭集**（`adopted` / `adopted-in-part` / `declined` / `open`），`declined` 必带理由，部分采纳必写残差，台账 append-only，被拒的异议也公开 | "**A record of only the agreeable objections is worse than none.**" |
| `emiliaprotocol/emilia-protocol` | 任何人可提；规范行为的改动**必须规格、参考验证器、一致性向量三处同时落地，或都不落地**；另有 policy-rollout 与 revoke 的服务端实现 | "**Specification, reference verifiers and conformance vectors together, or not at all.**" |
| `tyche-institute/eatf-verifier` | 一段话：个人维护、开放研究软件 | 无可机械化规则 |
| **我们** | `.github/CODEOWNERS` 一行 `* @zhaoxinghua09-cell` | 无 |

我们那一行只约束"谁点了合并按钮"，不约束"改了什么、谁批的、为什么、批完语料是否跟着动"。

本轮补的是可核的那一层：`tools/check_config_change.py` + `docs/CONFIG-CONTROL.md`，
五类拒（自我批准／处置不在闭集／拒绝无理由或部分采纳无残差／规范变更缺三腿之一／行被事后编辑或台账断链），
"silence is not agreement" 落成"决定人与时间都是必填"。实测四条记录串成台账通过，删一条腿后一次报三条理由。

**仍然落后**：台账是**空表**（仓库里没有任何 `uibc-change-v0` 记录）；分支保护与 required review 是平台设置，
不在字节里，外人无法从仓库证明；emilia 把 policy rollout 与 revoke 做成了服务端接口，我们只有文件级记录。
这三条都记为缺口，不计入对齐。

### 2026-11-20 实测（支付适配）：他们有 15 个案例判"金额是否超授权"，我们连"损失谁担"都没写过

一手读 `probityai/agent-evidence-vectors` 的 `corpora/vectors-agent-payment-mandate/`：`agent-payment-mandate/v1`，
**15 个案例、11 条规则、11 个变异体逐一被抓**；四样东西绑在一起（用户签的 mandate、agent 出示的凭证、实际扣款、串起它们的回执），
读者自己重算摘要而不是相信声称摘要的字段。其 README 自述两句边界："它证明扣款停留在用户授权之内；它不证明用户本意如此"，
"它不说争议中谁承担损失"。

**我们这一维：没有对应物。** 本格式无 mandate、无金额、无商户、无币种，也没有清算链路。

本轮补的是把缺失写成**机器可读**的边界：`docs/SETTLEMENT-BOUNDARY.json` + `tools/settlement_boundary.py`，六问六答：
Q1 有人在这些确切字节上跑过吗（supported，依据 RECEIPT-FORMAT）；Q2 字节自某日起未改吗（partial——
签名与 TSA 已实现但**未在已发布 release 上跑过**）；Q3 跑的人被授权代表那方吗（partial——单签、无撤销登记处、
公钥不带外给出时只给 identity unbound）；Q4 扣款在限额内吗（not_ours，判它的语料在对方那边）；
Q5 损失谁承担（not_ours）；Q6 能否递给收单方当证据（not_ours）。

检查器拒三类：两个"我们是否处理支付／是否授权扣款"字段改成 true 即否决；`supported`/`partial` 指向不存在的文件即否决；
`partial` 不写限制即否决（没有限制的 partial 读起来就是 supported）。另扫描 README 与四份文档，出现"guarantees payment"
一类短语即判 **OVERCLAIM**，退出码 1——这条是为了防"改一个字段就把能绑字节读成能收款"。

**仍然落后**：没有 mandate 语料、没有清算/收单链路、没有法律意见；Q5/Q6 的回答除非有书面法律意见否则不变。三条都记为缺口。

### 2026-11-20 实测（SCITT 侧适配）：18 行字段对照，3 同 / 8 部分 / 6 缺 / 1 多做

读仓内原件 `docs/spec-sources/draft-noa-scitt-ai-agent-receipt-00.txt`（504 行，individual draft）的 §3 载荷、§4 COSE 配置、§5 哈希链、§6 身份绑定、§9 范围排除。

**三行是同一个构造，不是巧合**：他们的 `chain.hash` = `sha256(JCS(去掉 hash 与 sig.value))`，我们的签名与摘要也覆盖 JCS(去掉 `signature` 的整行)；
他们的哈希链自述"不证明 equivocation"，我们的 LAB-PROTOCOL 自述"只能证明之后无法改口"；
他们规定"没有身份清单时必须向依赖方明示限制"，我们把它落成校验器输出 `identity unbound`。

**六行缺失，逐条写明代价**：`scope.tenant`/`scope.chain`（无发行方归属）、`agent.model`（回执侧观察不到模型）、
`agent.principal`（不分类谁在行动）、`action.paramsHash`（我们绑语料不绑行动参数）、`action.reversible`/`rollbackRef`（验证无副作用可回滚）、
注册进透明服务（我们锚 TSA/OTS；**时间戳不证明某个日志接受了这些字节**，把 TSA 叫透明服务是本文档拒绝做的那一步）。

**八行部分相同**：`spec` 标识（角色同、字符串不同）、`id`（靠文件摘要寻址）、`ts`、`agent.id`（`run_by` 自由文本）、
`action` 三元组（案例 id 而非风险类）、`governance.*`（逐案 verdict 有、随运行批准无）、`chain.seq/prevHash`（链在变更台账不在回执流）、
COSE 容器与 alg 拒绝规则（规则同、容器不同、无 CBOR 互操作）。

**一行我们多做**：草案 §9 把 policy-replay 明确排除在本版之外，我们的产品就是逐案重放（294 案例、三种对照、退出码契约）。这是"草案还没做"，不是"我们更强"。

**检查器**：`tools/check_scitt_crosswalk.py` 拒五类——源文档不在仓库、容器声明互通、三个标志（是否注册透明服务／是否输出 COSE／是否宣称符合）任一为 true、
`partial` 无 note 或 `absent` 无 cost、整表无一行 `have`；另扫描 README 与三份文档，出现兼容性宣称短语即判 OVERCLAIM（退出码 1）。
实测：`counts: have=3, partial=8, absent=6, ours_only=1` → `ACCEPTABLE`，exit 0。

**仍然落后**：无 COSE/CBOR 路径、无任何透明服务（运营方／日志／注册策略皆无）、未向 SCITT 的 IETF 线程提交（那是用户账号动作）。三条记为缺口。
