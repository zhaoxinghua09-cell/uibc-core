# 身份互操作映射（Identity Interoperability Mapping）

2026-11-24。对应战略支柱 1 / P0「完成身份互操作映射」。
规则：**每一格要么有实现与测试，要么写"未实现"和一个具体补法。** 没有第三种状态。
本表不主张任何一家已被"兼容"或"对接"。

字段顺序沿用互操作提案 Workstream 1 的九项：标识格式、解析机制、验证要求、信任依赖、密钥轮换、撤销、过期、不支持的操作、失败条件。

---

## 1. DID（W3C 方法注册表）

| 字段 | 现状 |
|---|---|
| 标识格式 | 8 种已接受：`did:key`、`did:web`、`did:cn`、`did:ioa`、`did:cndid`、`did:ctid`、`did:oan`、`did:cndomain`。六种中国注册体系的 ABNF 强制校验（`uibc_core/did_cn.py`） |
| 解析机制 | `did:key` 离线；`did:web` HTTPS；`did:cn` 走 `GET {base}/did/resolve/<did>`；`ioa`/`cndid` 走 `operation:"read"` 信封；`cndomain` 走 HTTPS 发布。**端点必须调用方给，无默认 URL** |
| 验证要求 | Ed25519 公钥提取（`document_ed25519_key`）；`did:ctid`（SM2/SDK）与 `did:oan`（无 read API）**只校验不解析**，理由写入 `SPECS` |
| 信任依赖 | `did:web` 依赖域名 + TLS；六法依赖各自注册中心；`did:key` 无外部依赖 |
| 密钥轮换 | 不支持——文档只取当前状态，无历史。属"不做"而非遗漏（见 `PARITY-MATRIX`） |
| 撤销 | 不做分发；只能靠调用方重新解析后比对 |
| 过期 | 不适用（DID 本身无有效期）；凭证级过期在 §3 |
| 不支持的操作 | `did:wba`（有公开规范、resolver 分支未写）；其余 274 种注册方法 |
| 失败条件 | 语法不符 → `IdentifierError`；无端点 → `RegistryEndpointRequired`；文档 id 不符 → `DIDCNError`；网络失败 → 原样抛出 |

**测试**：`tests/test_did_cn.py` 41 条、`tests/test_did.py` 15 条。

---

## 2. PKI / X.509

| 字段 | 现状 |
|---|---|
| 标识格式 | 未接。计划形态：Subject DN / SAN / SPKI 指纹 |
| 解析机制 | 未接。计划：链构建 + 信任锚 |
| 验证要求 | 未接 |
| 信任依赖 | 未接 |
| 密钥轮换 / 撤销 / 过期 | 未接（这三项恰是 X.509 最成熟的部分，也是我们最缺的证据面） |
| 不支持的操作 | 全部 |
| 失败条件 | 无 |
| 补法 | 支柱 1 / P1「定义 adapter 接口」：`IdentityAdapter.resolve()` → 统一 `evidence` 列表；先用 `cryptography` 的 X.509 解析做只读 adapter（不建链） |

---

## 3. Verifiable Credentials（W3C VC 2.0 / SD-JWT VC）

| 字段 | 现状 |
|---|---|
| 标识格式 | 未接凭证本身；仅在证据元数据里预留 `issuer` / `subject` / `expires_at` 字段 |
| 解析机制 | 未接 |
| 验证要求 | 未接（Data Integrity / JOSE 两套证明都未实现） |
| 信任依赖 | 未接 |
| 过期 | 字段级支持（`expires_at`），无自动判定 |
| 撤销 | 未接（StatusList / 撤销位图均未实现） |
| 补法 | 先做"只读映射"：把 VC 的 `credentialSubject.id` 与 `issuer` 映射到七态结果的 `subject` / `evidence[].issuer`，不实现密码学校验——这仍然让一个 VC 持有者能拿到可比的判定形状 |

---

## 4. DNS-based identity

| 字段 | 现状 |
|---|---|
| 标识格式 | `did:web` 隐式依赖 DNS；ANP 的 WNS handle（`alice.example.com`）未接 |
| 解析机制 | 仅通过 `did:web` 间接使用 HTTPS，无 DNS TXT / DNSSEC 读取 |
| 验证要求 | 无 |
| 信任依赖 | 域名注册 + TLS |
| 补法 | 与 X.509 adapter 同批：DNSSEC 属于"信任依赖"而非"标识"，先记录依赖，不实现 |

---

## 5. 智能体身份框架（Entra Agent ID / ANP did:wba / DIF KYA-OS）

| 字段 | 现状 |
|---|---|
| 标识格式 | 未接任一家 SDK。三家都可用 DID 或 OIDC 表达，因此**接口上是同一个 adapter 位** |
| 解析机制 | 未接 |
| 验证要求 | 未接 |
| 信任依赖 | 各自租户/域名/账本 |
| 轮换 / 撤销 | 未接；KYA-OS L2 明确要求"凭证化委托 + 撤销" |
| 补法 | 先做 KYA-OS L2/L3 对齐矩阵（支柱 1 的 P1 项），因为它已经把要求写成三级符合性，最容易逐条对账 |

---

## 6. 透明度系统（SCITT / OTS / Rekor / Nostr）

| 字段 | 现状 |
|---|---|
| 标识格式 | 摘要（`sha256:<hex>`）；SCITT 用 Signed Statement + Receipt |
| 解析机制 | OTS 日历 3 个已实现；Nostr relay 已实现（BIP-340/NIP-01，零依赖，经官方向量互验）；Rekor 有真实条目 1 条 |
| 验证要求 | 摘要必须与包内字节相等；时间戳按 RFC 3161 校验（Node 实现独立复核） |
| 信任依赖 | 日历/relay/Rekor 各自的运营方；**我们不运营透明度服务** |
| 轮换 / 撤销 | 不适用 |
| 过期 | 时间戳无过期，但新鲜度由调用方判 |
| 失败条件 | 摘要不符 → FAIL；端点不可达 → `HOLD`（不回落 `ALLOW`） |
| 缺口 | 无第二个独立见证方联署（`KNOWN-LIMITS` #4）；SCITT 要求的"独立托管方"我们不是 |

---

## 7. 信任框架（EUDI ARF / GLEIF vLEI / NIST 十诫 / CoSAI）

| 框架 | 可映射的点 | 现状 |
|---|---|---|
| EUDI ARF | "representation attestation"（代表他人行事）↔ 我们的委托字段 + 七态 | **仅语义对照**，无 crosswalk 文件 |
| GLEIF vLEI | 法人身份 + 角色凭证 + KERI 的委托链 ↔ `identity.owner` + 七态 `REVOKED` | **仅语义对照** |
| NIST 十诫 | 第 2 条权限衰减、第 6 条 mandate、第 7 条策略与推理分离 | **第 7 条已实现**（判据在代码里，不在模型里）；第 2/6 条仅部分 |
| CoSAI WS4 | "agent 是一等身份 + 静态/动态/委托三类 claim" | **字段形状可对齐**，未做映射表 |

**共同缺口**：四个框架都还没有一份"UIBC 字段 ↔ 该框架字段"的正式 crosswalk。这是 P1 的活，且是**纯文档工作**，不需要任何外部许可。

---

## 汇总：可对着看的六个数字

| 维度 | 有实现 | 未实现 |
|---|---|---|
| 身份体系 | 1（DID，8 方法） | 5（PKI、VC、DNS、agent 框架、信任框架 crosswalk） |
| adapter 接口 | 0 | 1（待定义） |
| 密码学校验路径 | 2（Ed25519、SHA-256/RFC 6962） | 3（SM2、X.509 链、SD-JWT） |
| 撤销处理 | 1（屏障 + 自证覆盖层） | 3（分发、StatusList、第三方确认） |

**这张表的用途不是好看，是给 P1 排序**：五个未实现里，X.509 只读 adapter 与 VC 只读映射的代价最低、对"异质身份"的说服力最高，应当先做。
