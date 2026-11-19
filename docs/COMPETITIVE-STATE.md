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

**仍然落后的一半（写清）**：他们的 `.sig` / `.sig.ots` / `.sig.tsr` 已经挂在已发布的 release 上；
本轮我们把同样的三件做成了可执行路径（`tools/anchor_release_digests.py`：Ed25519 签名 + FreeTSA 令牌 + OTS，
工作流在打 tag 时签名并尝试锚定，缺密钥时挂 `UNSIGNED.txt` 而不是假装签了），**但尚未在任何一个已发布的 release 上实际生效**——
下一个 tag 才会验证这条链。当前状态应读作"已实现、本地实测通过、发布侧未验证"，不是"已经对齐"。