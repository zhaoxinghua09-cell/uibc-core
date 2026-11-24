# DID 对接全景（2026-11）

这份文件回答一句话：**"是不是都能对接了？"** 答：**不能全接，也不需要全接；但被生态真正使用的那些，我们已经覆盖到 11 种，剩下的是分层排期而不是"接不上"。**

本页只写能核对的东西：每一条"已接"对应代码与测试；每一条"未接"写清理由与补法。数字与外部事实均标注出处，不靠记忆。

---

## 1. 现在的真实能力（代码 + 实测）

| 方法 | 解析通道 | 现在能给出的最强判定 | 依据 |
|---|---|---|---|
| `did:key` | 离线，标识即公钥（仅 ed25519-pub） | `VERIFIED`（公钥字节可复算，文档摘要钉入 evidence） | `uibc_core/did.py::did_key_document`；`tests/test_did.py` |
| `did:jwk` | 离线，`base64url(JWK)` 解码即文档 | `VERIFIED`（JWK `OKP/Ed25519`）；其它键型 `INCONCLUSIVE`（文档解得开、键取不出） | `did.py::did_jwk_document`；`tests/test_did_jwk.py`（15 条） |
| `did:web` | HTTPS，域名绑定 | `VERIFIED`（强制 https、强制 `document.id == did`、禁降级 302、限体积） | `did.py::resolve`；`tests/test_did.py` |
| `did:cn` | 注册中心，**端点必须调用方给** | `UNRESOLVED`（无端点）/ `VERIFIED`（给了端点且文档 id 对上） | `did_cn.py`；`tests/test_did_cn.py`（41 条） |
| `did:ioa` | 注册中心（`operation:"read"` 信封） | 同上；另可离线推导文档（`derivable_document`） | 同上 |
| `did:cndid` | 注册中心（`operation:"read"` 信封） | 同上 | 同上 |
| `did:cndomain` | HTTPS 发布（`.cn` 域 + 可选对象段） | 同上 | 同上 |
| `did:peer` | **离线**：文档由标识本身推导（numalgo 0/2），无端点、无注册中心 | `VERIFIED`（numalgo 0 与 did:key 同键；numalgo 2 按 A/E/V/I/D 建关系）；numalgo 1/3/4 为 `UNRESOLVED`（文档不在标识里，需要对方给长形态） | `did_peer.py`；`tests/test_did_peer.py`（24 条） |
| `did:bid` | 星火·链网 BIF：`read` 走 HTTP GET，端点必须调用方给 | `UNRESOLVED` / `VERIFIED`；另识别 `did:bid:byol` 这一规范明列的例外 | `did_cn.py::_check_bid`；`tests/test_did_bid.py`（14 条） |
| `did:ctid` | **只校验不解析**（文档由厂商 SDK 用 SM2 签发，无公开 read API） | `INVALID`（写法不符）/ 合法则 `UNRESOLVED`，并说明"通道未发布" | 同上 |
| `did:oan` | **只校验不解析**（规范未定义 HTTP read API） | 同上 | 同上 |

实测探针（2026-11-24，本机）：

```
did:key:z6MkpTHR8VNsBxYAA…  VERIFIED      （离线自描述）
did:web:example.com        UNRESOLVED    （推出了 URL，404）
did:cn:11.318.12345        UNRESOLVED    （合法，缺端点）
did:jwk:eyJrdHkiOiJFQyJ9   INCONCLUSIVE  （EC 键：文档解得开，ed25519 提取器读不出）
did:peer:0z6MkpTHR8…      VERIFIED      （离线，文档由标识推导）
did:webvh:… / did:pkh:… /  UNSUPPORTED   （有公开发布规则但我们未写分支）
did:ethr:… / did:wba:…
```

**顺带修掉一个真缺陷（本次调研最有价值的产出）**：信通院线上平台发的是
`did:cn:agent:<base58>`（`agent.idfactory.cn` 注册的智能体全是这个形状，它不在已发布 ABNF
`2DIGIT.3*5DIGIT.1*128DIGIT` 里）。适配器把 `validate()` 的拒绝当成了 `INVALID`——等于告诉一个
**分配正确**的智能体"你的标识写错了"。已改为 `UNRESOLVED` 并保留标签（形态可识别 ≠ 分配已确认），
回归测试 `test_live_did_cn_agent_form_is_unresolved_not_invalid` 钉住。这是本仓第二次犯
"错误信息坍缩"的同类毛病，第一次是 `RegistryEndpointRequired`。

---

## 2. 生态有多大：注册表 ≠ 需要接

- W3C DID Extensions 注册表是本生态的方法总表，2026-11 版条目已过 **270** 个（第三方统计口径：
  275 个，其中 272 注册、3 弃用，2026-11-05）。<https://www.w3.org/TR/2026/NOTE-did-extensions-methods-20261117/>
- W3C 自己的 rubric 只对极少数方法做过评级（`did:web` 记 A、`did:ion` 记 B 这类），因为注册表
  **只登记不背书**。<https://www.w3.org/TR/2026/NOTE-did-rubric-20260916/>
- DIF Universal Resolver 是"广度标杆"：driver 上百个，含 `did:webvh` 2.8.0、`did:cndid` 1.0.0、
  `did:pkh`、`did:ion`、`did:indy`、`did:web`。<https://github.com/decentralized-identity/universal-resolver>
- 真正被生产使用的，业内公认不到 15 个（`did:web`、`did:webvh`、`did:key`、`did:jwk`、`did:peer`、
  `did:ion`、`did:ethr`、`did:indy`、`did:cheqd`、`did:plc`、`did:pkh`，中国侧 `did:cn`/`did:bid` 等）。
  <https://startwithidentity.com/guides/decentralized-identity/did-methods-compared/>

结论：**追 270 个是错策略**（其中大量是单链、单项目、无实现可对照）；正确策略是"高频 15 个 + 声明边界"。

---

## 3. 主流方法矩阵：能不能接、怎么接、值不值

| 方法 | 我们现状 | 技术可接性 | 成本 | 优先级 |
|---|---|---|---|---|
| `did:webvh` | 未接 | 可接：HTTPS + 逐条校验 JSONL 日志（entryHash 链、`versionId`、预轮换承诺、见证人阈值），且 `did:webvh:…` 可退化为 `did:web` | 中（~2–3 天，含全套负例） | **P0**（`did:web` 的生产升级版，DIF v1.0，可作为"可验证历史"卖点）<https://identity.foundation/didwebvh/v1.0/> |
| `did:bid` | **已接（本次）** | 星火·链网 BIF；ABNF 两形状（主链 `ef…` / 子链 `AC01:…`）+ `byol` 例外；`read` 走 GET，端点由调用方给 | 已完成（1 天） | — |
| `did:jwk` | **已接（本次）** | 离线、无网络、私钥成员拒绝、4096 字节上限 | 已完成 | — |
| `did:pkh` | 未接 | 可接：CAIP-10 账户 → 多链地址；纯离线可推导文档形状，链上归属需外部查询 | 低（离线形状 0.5 天；链上成员性另算） | P1 |
| `did:peer` | 未接 | 可接：点对点、设计上不可公开解析；只能校验 `numalgo`/`transform` 与文档形状 | 低（1 天，且必须明确"不可解析"是设计而非缺陷） | P1（DIDComm 生态入口） |
| `did:wba` | 未接 | 可接：有公开规范（HTTPS 域名 + 路径结构），条法与 `did:web` 同族 | 低（0.5–1 天） | P1（国内智能体互联、ANP 侧） |
| `did:ion` | 未接 | 可接：Sidetree，需 IPFS + Bitcoin 锚定；只读解析可以走公开节点，但"跑得起来"依赖外部服务 | 中–高 | P2（北美企业侧） |
| `did:ethr` | 未接 | 可接：ERC-1056 注册表读调用；需 RPC | 中 | P2 |
| `did:indy` / `did:cheqd` | 未接 | 可接：账本读 + 各自 ledger 依赖 | 中 | P2 |
| `did:plc` | 未接 | 可接：`plc.directory` 纯 HTTP，代价极低 | 低（0.5 天） | P2（但生态与我们业务不重叠） |
| `did:ccp` / `did:tdid` / `did:ldid` / `did:kdid` / `did:iid` / `did:vtid` | 未接 | 部分是国内联盟链（Baidu Quorum / 腾讯 FISCO / 长安链 / 微众 FISCO / 浪潮 / 见康）；多数**无公开解析端点**，只可校验语法 | 低（每法 0.5 天，且大概率停在 identifier_only） | P3（按客户点名再接） |
| 其余 ~250 种 | 不接 | 大量为单项目/单链，缺参考实现 | — | 不做，走 §5 的 driver 规范 |

---

## 4. 中国体系：两个必须分清的东西

1. **CAICT 智能体标识与身份网络**（2026-07 四部门文件后启动，北京/厦门试运行）：技术路线是
   "区块链 + DID + 超级智能体"，明确"兼容符合 W3C 规范的多种 DID 方法，适配 A2A、ANP 等主流互联协议"，
   并通过 DID SDK 接受企业自有/行业既有 DID 接入。
   <http://m.toutiao.com/group/7698229243691532809/>
   → 这对我们是**结构性利好**：我们已覆盖 `did:cn`（含线上 `agent:` 形态）、`did:ioa`、`did:cndid`、
   `did:cndomain` 与 `did:bid`，A2A 适配器与 MCP server 也在仓内；缺口只剩 `did:wba`（有公开规范、分支未写）。
2. **星火·链网 BID**（`did:bid`）：信通院体系里另一条独立主线，许可公有链 + BID 标识解析
   <https://bif-doc.readthedocs.io/zh_CN/1.0.0/business/digital_id.html>
   → 与 `did:cn` 不是同一个东西，不要混为一谈。**已接**（`did:bid` 主链/子链两形状 + `byol` 例外，`read` 走 GET，端点由调用方给）。
→ 另记一处**规范间冲突**：BID 的 ABNF 允许 `acsn ":" 0*1(suffix)` 这种空后缀形态（如 `did:bid:AC01:`），但 DID Core 的 `method-specific-id` 必须以 idchar 结尾，两者不能同时满足。我们按 DID Core 拒绝，并在测试里写明这条冲突，不装作看不见。

---

## 5. 策略：三档 + 一条 driver 规范

| 档 | 含义 | 做法 |
|---|---|---|
| A 已接 | 有代码、有测试、有实跑 | 保持；每加一个方法必须同步 `matrix()` 与本文 |
| B 可接未接 | 公开规范齐全，纯软件工作 | 按 §3 优先级排期；每个 ~1–3 天，含 5 类负例（语法/端点缺失/文档 id 不符/降级/超限） |
| C 不接 | 通道私有、无参考实现、或价值不重叠 | **明确写进"不支持清单"**，而不是假装支持；调用方点名时按客户场景单独立项 |

**driver 规范（对标 DIF Universal Resolver 的 driver 思路）**：若要覆盖 B/C 档的长尾，不写进主包，
而是允许外部按 `resolve(did, endpoint=…, fetcher=…)` 契约注册一个 driver（一个函数 + 一份
`SUPPORTED_METHODS` 声明 + 一组负例）。主包保持"零依赖、可审计"，广度靠插件。这样"能接 270 个"
和"我只主张我验过的"可以同时成立。

---

## 6. 与竞品的真实差距（别自欺）

| 维度 | DIF Universal Resolver / Godiddy | 我们 | 判 |
|---|---|---|---|
| 方法广度 | 100+ driver，含长尾 | 9 种 + 三档策略 | 我们**明显落后**，且短期不该追 |
| 判定语义 | 返回 DID Resolution Result，错误码粗 | 五态 + 两条红线（不判 REVOKED/EXPIRED；不把"缺端点"说成"标识错"） | 我们**更严**，这是可辩护的差异点 |
| 可复算 | 结果即解析结果 | 文档 sha256 钉进 evidence，bench 有 ATTEST 哈希清单 | 我们**更强**（"结论能被外人复算"） |
| 中国侧 | 有 `did:cndid` driver，无 `did:cn` 线上形态处理 | 6 种中国方法 + 线上 `agent:` 形态单独识别 | 我们**更细** |
| 平台差异 | 以 Docker 为主 | 纯标准库，Windows/Linux 同一条命令 | 我们更适合"外人 clone 就跑" |

一句话：**广度认输，语义与可复算不认输**；广度用插件补，语义用测试钉。

---

## 7. 下一步（按此顺序，每一步都有验收口径）

1. `did:webvh`（P0，2–3 天）：日志链校验 + 预轮换 + 见证人阈值 + `did:web` 退化 → 验收：官方 v1.0 的 3 个实现给出的样例日志能判对（含被篡改一条的负例）。
3. `did:wba`（P1，1 天）：HTTPS 域名 + 路径结构 → 验收：与 `did:web` 共用取文档通道，超限/降级负例复用。
4. `did:pkh` / `did:peer`（P1，各 1 天）：只做形状与"不可解析"的诚实表态。
5. 写 `docs/DRIVER-CONTRACT.md`：外部 driver 注册契约 + 负例清单（把"广度"变成接口，而不是承诺）。

> 本页任何一行都不主张"已兼容某家"。已接 = 有代码有测试；未接 = 写明补法。
