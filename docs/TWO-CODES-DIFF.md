# 两套码的差异表：OID 身份码 vs `did:cn`

2026-11-24。目的：**把两条标准化路线的差异逐条钉死**，每行标注依据强度。这张表是"能不能说'同时支持两套'"的唯一依据。

依据类型：**标准**（GB/Z 185.2—2026 原文）· **规范**（`did:cn` 官方 README）· **实测**（我直接请求过平台/API）· **未见**（查过没有公开文本）。

---

## 1. 十项对照

| 维度 | OID 身份码（GB/Z 185.2—2026） | `did:cn`（CN DID Method Specification） | 依据 |
|---|---|---|---|
| 编码体系 | 分层 OID，遵循 GB/T 26231；`1.2.156.3088.版本.服务方.请求方.序列号` | `did:cn:<issuer>.<industry>.<enterprise>`，如 `did:cn:88.100.1` | 标准 5.1–5.2；规范 2.1 |
| 字符集 | 每段 `0-9`/`A-Z`，字母不区分大小写，`.` 分隔 | 前缀固定的**十进制数字**段（`2DIGIT.3*5DIGIT.1*128DIGIT`） | 标准 5.1；规范 ABNF |
| 谁能分配 | **身份注册服务方**（组织，码由主管部门分配）；一码一智能体 | 企业向**授权发行方**申请工业互联网标识，然后自行生成 DID 并上链 | 标准 5.4 / 6(d)；规范 3.1 |
| 根标识管理者 | 国家OID注册中心（`1.2.156`、`2.16.156` 中国根） | 国家区块链注册中心（DID Document 上链，返回交易哈希） | 标准 5.2 + CNOID 公开说明；规范 3.1 |
| 注册/创建入口 | 由服务方受理，**无公开在线入口文本** | `POST /did/register`，DID Document 直接上链 | 标准 6；规范 3.1（示例） |
| 解析入口 | **标准未定义解析接口**（只写"作为解析起点"，没给协议） | `GET /did/resolve/<did>`，返回 `application/did+json` | 标准 5.2；规范 3.2 |
| 服务端点在不在标识文档里 | 标准全文没有"文档"这个概念 | **规范里在**（示例含 `service` 与 `serviceEndpoint`），可与 Update 追加 | 规范 3.3 / 4 |
| 撤销 / 停用 | 标准只要求服务方管理序列号，**未定义撤销语义**（撤销后旧凭证是否仍有效无文本） | **规范有** `PUT /did/deactivate`，状态置 `deactivated` 并上链 | 标准 6；规范 3.4 |
| 撤销的**查询**通道 | 未见 | **规范未给**（deactivate 是写操作；读只有 resolve） | 规范 3.2 vs 3.4，**未见**状态查询 |
| 校验和 / 完整性 | 标准**无**校验字段 | 规范**无**校验字段；两者都靠签名 | 标准 5.1–5.6；规范 2–4 |

---

## 2. 三条必须写出来的不一致（都是实测/原文，不是推断）

1. **线上 `did:cn` 不符合自己的 ABNF。** 规范 ABNF 是 `2DIGIT.3*5DIGIT.1*128DIGIT`，但 `agent.idfactory.cn` 在册的智能体标识全部是 `did:cn:agent:<base58>`（例如 `did:cn:agent:sfKvhQocnYJJME4zGDdRqvWtes21Mi9c`）。**规范与实现各说各话**，而且这个 live 形式在任何公开文本里都没有 ABNF。
   - 我方处理：`validate()` 继续按规范 ABNF 拒绝它；新增 `validate_live_agent_id()` 单独识别并标注 `published_abnf: False`。两条都不许升 `VERIFIED`。
2. **`service` 的归属在两条轨上相反。** `did:cn` 规范把 `service` 放在 DID Document 里；而国标身份码根本没有"文档"概念，服务端点只能靠平台私有接口（`resolve-verify` 的 `data`）。所以"从标识找到 agent"这件事，两条轨的答案结构不同。
3. **撤销的两种不同成熟度。** `did:cn` 有写操作（deactivate）但没有**状态查询**；国标身份码连撤销语义都没写。**两边都答不了"撤销后之前签发的凭证是否仍然有效"** —— 这正是我们给信通院必问的第一条。

---

## 3. 三条"能说/不能说"

**能说**
- 我们**同时实现了两条路线上的读取能力**：OID 身份码的形状校验（GB/Z 185.2 5.1–5.6 逐条）+ `did:cn` 的规范 ABNF 校验与线上形式识别。
- 我们说清了**两套码在结构、分配、解析、撤销上的差异**，并且每条都标了依据。
- 我们不给任何一方当"认证"：两套码的最高判定都是 `INCONCLUSIVE`（除非拿到签发方的证据）。

**不能说**
- 不能说"两套码已互通"——**双向映射规则至今没有任何公开文本**，谁声称有都得给出处。
- 不能说"已接入国标身份码"——签发权在身份注册服务方。
- 不能说"平台已验签"——`vcVerificationStatus` 恒为 `SKIPPED`（实测）。

---

## 4. 这张表能换来的东西

- 对外只需一页就能回答"你们到底支持哪套"——不必每次重新解释两套标准；
- 把"支持两条路线"从形容词降为**可核对的十行**；
- 让"互通"这个声称变成**有缺口的声称**：缺口就是第 1 节第 8–9 行，任何人都能核。

---

## 5. 来源

- 标准全文（含 5.1–5.6、6、附录 A/B/C）：`https://amr.guiyang.gov.cn/zwgk/zfxxgk/fdzdgknr/fggw/fggz_5772383/202607/P020260707417736330678.pdf`
- `did:cn` 规范（README 6,536 字节，v1.0.0，2025-03-20）：`https://github.com/caict-4iot-dev/CN-DID-Method-Specification`
- 线上形式实测：`https://agent.idfactory.cn`（页面列出的在册智能体均为 `did:cn:agent:sf…`）
- 平台接口实测：`https://iaisp.teleinfo.cn` 的 `GET /api/public/ioa/agents`（77 条，仅 `did`+`name`）、`POST /api/public/ioa/did/resolve-verify`
- 本仓实现：`uibc_core/agent_identity_code.py`、`uibc_core/did_cn.py`（`validate` 与 `validate_live_agent_id`）
