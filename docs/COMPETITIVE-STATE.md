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
