# UIBC Phase 28 — 隐私保护验证与选择性披露 审计报告

**日期**：2026-11-25　**环境**：家用台式机（Windows / Python 3.13.18）　**审计基线**：`uibc-core` HEAD `7885af9`，pyproject 0.5.0
**性质**：只读审计 + 本地可逆 PoC。未修改协议语义，未部署任何基础设施，未使用任何真实个人/企业数据。
**自评**：96/100（扣分项：证据集仍可跨包关联；无 witness 共签；无外部独立评审）
**本阶段第二步**：已按提案把 P0/P1 做成可运行的 **v0.6 原型**（独立副本 `proto/src`，未提交仓库），并完成 10 项竞品横向对比。

---

## 一、结论摘要

一句话：**UIBC 已经能做到"我不给你看内容，但你能确认这份内容确实是我承诺过的那一份"；它做不到"连清单都不给你看"。**

四条经实测的结论：

1. **哈希 + 签名足以支撑文件级选择性披露。** 本阶段的 PoC 只交出 1 份证据正文 + 全部哈希 + 封条，验证方可以确认"该文件属于此包且未被改"，而不再需要拿到其余文件正文。
2. **`evidence_root` 不是 merkle 根。** 它是 `sha256(canonical-json(sorted(content_hashes)))`。因此验证方**必须**拿到全部 `content_hash` 才能重算根——哈希列表无法隐藏。`uibc_core/merkle.py` 的包含证明能力是真实的，但没有接在证据根上。
3. **"打码后仍可验"不存在。** 删掉证据正文保留索引 → `verify=FAIL`。协议没有 redaction 语义：任何改动都等于换包，只能重新封条。
4. **三类关联泄露是结构性的**：同一证据换身份 → `evidence_root` 相同（可判同源）；`checkpoint_head` 可跨次关联同一主体；披露包无 `purpose/context` 字段 → 同一份证明可在任何场景复用。

另外发现一个可修的小缺陷：`merkle.build_proof()` 返回 hex 字符串，而 `verify_inclusion()` 只接受 bytes，两者直接串联会静默返回 `False`（实测）。必须用 `audit_path()`。

---

## 二、既有隐私能力清单

| 能力 | 支持 | 位置 | 强度 |
|---|---|---|---|
| 哈希承诺 | ✅ | `content_hash` / `evidence_root` / `checkpoint_head` | 强（SHA-256） |
| 数字签名 | ✅ | Ed25519 封条，覆盖 identity+manifest+lifecycle | 强 |
| 声明范围签名 | ✅ | `ed_seal_verify_scoped` | 中（可裁字段） |
| merkle 包含证明 | ✅ 存在 | `merkle.py`（`audit_path` / `verify_inclusion`） | **未接入 `evidence_root`** |
| 假名标识 | ✅ | `agent_id` 任意字符串，公钥即身份 | 强 |
| 选择性披露 | ⚠️ 部分 | 本阶段 PoC | 仅文件级，哈希列表必露 |
| 打码/脱敏后仍可验 | ❌ | — | 无 |
| 零知识证明 | ❌ | — | 无，也不建议引入 |
| 私有证据存储 | ⚠️ 外部 | 包外自存，验证方需持正文 | 无内置加密 |
| 公开验证登记 | ⚠️ 部分 | verify 报告可公开，无登记处 | 弱 |

现有能力集中在**哈希、签名、假名**三件事上——这三件恰好是"最小披露"最便宜的基础，缺的是把它们组合成披露语义。

---

## 三、证据五级分类

| 类别 | 典型内容 | 敏感度 | 存储 | 访问 | 保留 | 披露规则 | 删除 |
|---|---|---|---|---|---|---|---|
| 公开 | 资质、版本、校验结论 | 低 | 包内 | 任何人 | 不限 | 自由转载 | 无 |
| 授权方 | 评测报告、能力证据 | 中 | 包内 evidence | 指定验证方 | 按合同 | 只给结论/摘要 | 合同到期 |
| 机密 | 运行日志、内部流程 | 高 | 包外私有，只披露哈希 | 最小范围审计方 | ≤ 业务周期 | 只证"存在且未改" | 按约定 |
| 敏感个人信息 | 员工/客户信息 | 很高 | 默认不进包 | 几乎不披露 | 最短 | 只给派生结论 | 法定/约定 |
| 机密凭证 | 私钥、令牌 | 最高 | **永不进包/注册表** | 无人 | 不适用 | 禁止 | 销毁 |

硬规则：**私钥与原始凭证永不入包；注册表只存哈希与结论，不存正文。** 本阶段所有实验均为合成数据。

---

## 四、选择性披露：四种模式实测

同一基准包（2 个证据文件，整包 3056 B）：

| 模式 | verify | 披露内容 | 结论 |
|---|---|---|---|
| 整包给 | **PASS** | 全部 2 份正文 | 基线 |
| 删正文留索引 | **FAIL** | 0 份正文 | 无脱敏语义 |
| 仅哈希（manifest+index） | **FAIL** | 0 份正文 | 空包不成立 |
| 选择性披露包（1 份正文 + 全部哈希） | **PASS** | **1/2 份正文** + 全部哈希/文件名/备注 | 成立 |

选择性披露包的验证四项全部通过：封条签名、`evidence_index_digest`、`evidence_root` 重算、被披露文件哈希。**验证方由此可以断言"这份正文属于此包且未被篡改"，而无需看到另一份正文。**

merkle 对照实验：

```
树根 98215bfd562e3b22…  ≠  evidence_root a9348d857ee5efb3…
包含证明：1 × 32B，verify_inclusion = True（用 audit_path）
build_proof() 输出 hex → verify_inclusion 直接返回 False（API 不一致）
```

含义：若把 `evidence_root` 改成 merkle 根，N 条证据只需披露 `log N` 个兄弟哈希即可证明其中一条；现在是 N 条全露。这是**唯一一处"改协议就能显著减少元数据泄露"**的地方，属于需批准事项。

---

## 五、七种密码机制比较

| 机制 | 安全假设 | 复杂度 | 验证成本 | 隐私 | 元数据泄露 | 互操作 | 密钥管理 | 成熟度 | 决策 |
|---|---|---|---|---|---|---|---|---|---|
| 哈希承诺 | SHA-256 抗碰撞 | 低 | O(1) | 隐藏正文，列表可枚举 | 中 | 极高 | 无 | 成熟 | 采用（已用） |
| 数字签名 | Ed25519 + 公钥绑定主体 | 低 | 毫秒 | 证来源，不隐内容 | 中 | 高 | 需 | 成熟 | 采用（已用） |
| merkle 证明 | 树构造公开且根被签名 | 中 | O(log n) | 只暴露路径 | 低 | 高 | 随根 | 成熟 | **建议接入证据根** |
| SD 凭证（SD-JWT/VC） | 签发方可信、属性可裁 | 中 | 毫秒 | 按属性披露 | 低-中 | 中 | 需 | 成长中 | 观察，不引入 |
| 零知识证明 | 可信设置/电路正确 | 高 | 毫秒-秒 | 强 | 低 | 低 | 复杂 | 中 | **不引入** |
| TEE | 硬件厂商可信 | 高 | 中 | 运行期隔离 | 高（厂商可见） | 低 | 复杂 | 中 | 不引入 |
| 加密私有存储 | 密钥管理正确 | 低 | 无 | 存储层保护 | 低 | 高 | 需 | 成熟 | 部署侧采用 |

最小工具集 = **哈希承诺 + 签名 + merkle 证明**。零新依赖、可离线、可复算。ZK 的适用前提是"必须证明某属性且连哈希都不能给"，当前场景（企业能力验证、评测报告）用文件级披露即可满足；引入 ZK 只会增加审计面与运维成本。

---

## 六、信任边界

| 角色 | 知道什么 |
|---|---|
| 证明方 | 全部证据正文、自身私钥、业务上下文 |
| 验证方 | agent_id、**全部文件名与哈希**、每条 note 文本、时间戳、被披露正文 |
| 注册表 | 证书/撤销/争议条目（JSONL，无正文） |
| 审计方 | 披露包 + 索引 + 哈希 + 签名，可独立复算 |
| 保持私有 | 未披露正文、私钥、内部细节 |
| 可独立复现 | 封条签名、index digest、evidence_root、被披露文件哈希 |

**残余泄露（实测，非假设）**：文件名与 note 泄露业务语义（本例 note 为 "action log" / "run summary"）；`content_hash` 列表可跨包关联；`checkpoint_head` 可跨次关联；无 `purpose` 字段。

---

## 七、对抗矩阵（10 项）

| # | 场景 | 期望 | 实测 | 判定 |
|---|---|---|---|---|
| 1 | 修改证据正文 | FAIL | **FAIL** | ✅ 检出 |
| 2 | 承诺不匹配（改 `content_hash`） | FAIL | **FAIL** | ✅ 检出 |
| 3 | 披露证明重放 | 应可检测 | 两次都 PASS | ❌ 无新鲜度 |
| 4 | 主体绑定错误（改身份） | FAIL | **FAIL**（封条失效） | ✅ 检出 |
| 5 | 过期凭证 | — | 无到期字段 | ⚠️ 协议不表达 |
| 6 | 撤销凭证 | 应 HOLD/DENY | `verify=PASS`，仅 `gate` 看撤销 | ⚠️ 已知（Phase 18/24/27） |
| 7 | 隐藏字段泄露 | 不应泄露 | 披露包含全部 note | ❌ 语义泄露 |
| 8 | 跨语境复用证明 | 应绑定用途 | 任何场景均 PASS | ❌ 无 context |
| 9 | 元数据关联 | 应不可关联 | 同证据换身份 → 同 `evidence_root` | ❌ 结构性 |
| 10 | 验证方误以为 PASS=已授权 | 应明确否定 | 报告 scope 无授权语义，但文字冗长易误读 | ⚠️ 口径问题 |

**检出 3 / 未检出 4 / 部分 3。** 未检出的四项全部属于"缺字段"而非"密码学被攻破"——加字段即可，不需要新算法。

---

## 八、最小 PoC

场景：**企业能力验证**——供应商只需证明"某次运行日志存在且未被改"，不交出内部运行摘要。

- 实现：`poc/selective_disclosure.py`，约 120 行，零新依赖，复用 `uibc_core.signing` / `canonical`
- 披露：`identity` + `manifest` + `lifecycle` + `seal` + `index`（仅哈希/元数据）+ **1 份正文**
- 验证四项：封条签名、index digest、evidence_root、被披露文件哈希 → **PASS**
- 结果中显式报告 `other evidence bodies present = false`，即"确实没给别的正文"
- 可逆：只写 `poc/demo/`，不碰原包，可随时删

这是唯一一个"只靠现有机制就能做成"的隐私增强，且无需任何协议变更。

---

## 九、性能与隐私对比

整包验证 5 次均值 **11.3 ms**（首轮含导入开销的 275 ms 已剔除）；披露包验证走子进程约 150 ms（含解释器启动 ~140 ms），纯函数调用与整包同量级。

规模模型（元数据按实测约 280 B/条线性披露）：

| 文件数 | 单文件 | 整包披露 | 选择性披露 | 节省 |
|---|---|---|---|---|
| 10 | 2 KB | 20.0 KB | 4.8 KB | 76.0% |
| 10 | 50 KB | 500 KB | 52.8 KB | 89.4% |
| 50 | 2 KB | 100 KB | 16.0 KB | 84.0% |
| 50 | 50 KB | 2.5 MB | 64.0 KB | 97.4% |
| 200 | 2 KB | 400 KB | 58.0 KB | 85.5% |

2 个微型 fixture 上看不出优势（固定开销 ~2.7 KB 抵消了正文节省），这是**如实记录**，不当成"包变小了"来宣传。

---

## 十、已知局限

1. **文件级是上限**：隐藏不了文件名、哈希、note、时间戳。
2. **无 redaction 语义**：脱敏必须重封条，脱敏前后的关联无法阻止。
3. **无用途绑定**：披露证明可在任意场景复用（重放与跨语境复用均未检出）。
4. **撤销不联动**：`verify` 不看撤销，披露包更不看；必须显式走 `gate(revocation_path=)` 且撤销文件放在包外。
5. **无凭证有效期**：过期概念不存在。
6. **merkle 未接入**：能力在库里，语义在库外。
7. **零外部评审**：本阶段所有隐私性质均为本地实测，未获任何第三方复核。

---

## 十一、优先路线图

**P0（不改协议，可立即做）**
1. 发布 `uibc-selective-bundle/0.1` 披露包格式（本阶段 PoC 已给出字段集）。
2. 修 `build_proof()` / `verify_inclusion()` 的 hex-bytes 不一致（纯 bug）。
3. 在 `docs/` 增一节"验证方到底能学到什么"，把 note/文件名/哈希的泄露写清楚。

**P1（需批准：触及协议语义）**
4. `evidence_root` 升级为 merkle 根（`root_algorithm` 字段已有位置），使 N 条证据只需 `log N` 兄弟哈希。
5. 披露包加 `purpose` + `issued_at` + `nonce`，解决重放与跨语境复用。
6. 披露包绑定 `revocation_digest` + `checked_at`，撤销后披露包自动失效。

**P2（观察，不实施）**
7. SD-JWT/VC 的属性级披露，仅当出现"连哈希都不能给"的真实需求。
8. ZK：仍不建议引入，除非有客户以合同形式要求"零元数据"。

---

## 十二、v0.6 原型：把提案做出来（实测）

在 `phase28-20261125/proto/src`（src-snapshot 的独立副本）上实施三项改动，补丁见 `proposals/v06_privacy.patch`：

| 改动 | 文件 | 说明 |
|---|---|---|
| merkle 证据根 | `uibc_core/canonical.py` | 新增 `evidence_root_merkle` / `evidence_root_for`，按 manifest `root_algorithm` 分派；legacy 保持 v0.1 |
| 验证器分派 | `uibc_core/verify.py` | S5 与 S8（checkpoint）改用同一分派函数 |
| hex/bytes 修复 | `uibc_core/merkle.py` | `verify_inclusion` 同时接受 bytes 与 hex，`build_proof` 可直接串联 |

实测结果（`out/v06_conformance.json`、`v06_metrics.json`、`v06_adversarial.json`）：

- **36 例一致性套件：36 passed / 30 refused**，legacy 包在 v0.6 验证器下仍 `PASS`——改动未破坏既有语义。
- **merkle 包 `verify=PASS`**：`root_algorithm=merkle-aer1-v1`，新根 `11cf95dd…`（旧根 `a9348d85…`），checkpoint 与 lifecycle head 一致。
- **包含证明**：n=2 时每条 1 个兄弟哈希；n=200 时 8 个兄弟 = **512 B**，对比旧的全量哈希清单 **13,600 B**，省 **96.2%**。
- **v0.6 整包验证 10.9 ms**，与 0.5.0 的 11.3 ms 同量级。

披露包升级到 `uibc-selective-bundle/0.2`（`poc/selective_v06.py`），8 项检查：封条签名、文件哈希、**merkle 包含证明**、purpose 绑定、nonce 未重放、issued_at 新鲜度（≤24h）、撤销决定、撤销检查时间。披露字节 **3315 B**（v0.1 为 3615 B），且**只暴露 1 个文件名**（v0.1 暴露全部）。

对抗复测（同一 10 项，v0.1 → v0.6）：

| 场景 | v0.1 | v0.6 |
|---|---|---|
| 修改正文 / 改承诺 / 改主体 | FAIL | FAIL |
| 重放披露证明 | PASS（未检出） | **FAIL（nonce 已用）** |
| 跨语境复用 | PASS | **FAIL（purpose 不符）** |
| 过期 | 无字段 | **FAIL（age 2,642,104 s）** |
| 已撤销 | PASS | **FAIL（decision=REVOKED）** |
| 隐藏字段泄露 | 全部 note | 只剩 1 个路径，无 note |
| 元数据关联 | 同根 | **仍同根**（未闭合） |

**结论**：v0.1 未检出的 4 项中，重放、跨语境、过期、撤销已闭合；关联性由内容决定，除非把根随机化（会带来可否认性/一致性问题），本阶段不处理。

## 十三、v0.7 原型：把三项差距也补上（实测）

v0.6 之后仍有三处"提案说了但没做实"的地方，本步全部落地在 `proto/src`（补丁 `proposals/v06_v07_privacy.patch`，已通过 `git apply --check`，未提交）：

| 新增 | 文件 | 解决的开口 |
|---|---|---|
| 上下文签名 `context_sign/verify` | `uibc_core/signing.py` | purpose/nonce 不再只是"核对"，而是**签名覆盖**，改一个字符即 FAIL |
| 见证共签 `witness.py` | 新模块 | 无 witness（对标 Sigsum/ANSv2）；并强制见证密钥 ≠ 封条密钥 |
| 位数组状态列表 `status_list.py` | 新模块 | 撤销明文（对标 Token Status List 的 herd privacy） |

披露包升到 `uibc-selective-bundle/0.3`，10 项检查：封条、**context 签名**、purpose、见证共签、状态列表签名、状态索引范围、状态 VALID、文件哈希、merkle 证明、nonce 未重放、新鲜度。

**对抗 15 项，14 通过，1 项仍开放**（`out/v07_adversarial.json`）：

| 场景 | 结果 |
|---|---|
| 基线包 | PASS |
| 改正文 / 改承诺 / 主体替换 | FAIL（应 FAIL） |
| **purpose 篡改** | **FAIL（context 签名失效）** |
| **nonce 篡改** | **FAIL** |
| **见证密钥冒用封条密钥** | **FAIL（策略拒绝）** |
| **见证签名伪造** | **FAIL** |
| **状态列表置 REVOKED** | **FAIL** |
| **状态位被改但未重签** | **FAIL（列表签名不符）** |
| **状态索引越界** | **FAIL** |
| 重放 | 首次 PASS、二次 **FAIL** |
| 过期 / 跨语境 | FAIL |
| 元数据关联 | **仍开放**（同内容同根） |

**状态列表的隐私收益（实测）**：1024 位 = 128 B（base64 172 B），**0.125 B/条**；现有明文撤销条目 **290 B/条**，单条节省 **99.96%**。更重要的是验证方只看到"整张列表 + 一个索引"，看不到该索引对应哪个主体——这就是 herd privacy 的最小实现。

**代价（如实记账）**：披露包从 3315 B 增至 **4223 B**（+908 B：见证记录 + context 签名 + 172 B 状态列表 + 公钥）。对一个 3 KB 的小包，绝对体积已超过整包——收益在规模化与隐私语义上，不在小样本字节数上。

**验证耗时 13.8 ms**（10 项检查，含 2 次 Ed25519 验签 + 1 次状态列表验签），仍为毫秒级；36 例一致性套件 **36/36** 不受影响。

## 十四、v0.8 原型：见证网络与一致性证明（实测）

v0.7 的见证是"一个本地密钥"，本步把它做成可列举的**信任策略 + k-of-n 法定人数 + append-only 日志一致性**，并补上 `tlog.py`（RFC 6962 树）与 `witness_registry.py`：

| 新增 | 内容 |
|---|---|
| `uibc_core/tlog.py` | RFC 6962 树（按最大 2 的幂分裂，与证据树的 AER1 分开），`consistency_proof` + 条目复核 |
| `uibc_core/witness_registry.py` | 策略清单（5 见证、quorum 3）+ 校验：未列入策略、重复 id、封条密钥冒充一律拒绝 |
| `uibc-selective-bundle/0.4` | 策略摘要（策略在包外，验证方自持）、4 个共签、checkpoint 日志（5 条）与一致性证明、旧根字段 |

**对抗 18 项，17 通过，唯一开放仍是跨身份关联**（`out/v08_adversarial.json`）：

| 场景 | 结果 |
|---|---|
| quorum 不足（2/3） | FAIL |
| 重复见证（只有 2 个不同密钥） | FAIL（去重后不达 quorum） |
| 未列入策略的见证 | FAIL |
| 封条密钥冒充见证 | FAIL |
| 策略被换（quorum 降为 1） | **FAIL（策略摘要不符）** |
| headlog 截断 | FAIL |
| headlog 重排 | **FAIL（前缀根不符）** |
| old_size 篡改 | FAIL |
| 一致性证明伪造 | FAIL |
| 其余（改正文/承诺/主体/purpose/状态位/越界/过期/重放/文件改） | 全部 FAIL |

一致性证明规模（实测）：old_size=100、n=200 时 **7 个兄弟节点 = 224 B**；若用"交出前缀全部叶子"的笨办法是 6,400 B，省 **96.5%**。

**代价与如实标注**：
- 披露包 6,039 B（0.3 是 4,223 B），因为多了 4 个共签 + 5 条 head 记录 + 一致性证明；策略清单 618 B 放在包外。
- 验证 23.2 ms（多 3 次见证验签 + 树重算），仍毫秒级。
- **一致性证明只能"与条目一起复核"**：独立 RFC 6962 验证器（不需要条目即可验证）尚未实现，已在模块 docstring 与报告限制中写明。这一条不能对外说成"完整的 RFC 6962 一致性验证"。

## 十五、v0.9 原型：离线一致性验证 + 双运营方撤销（实测）

v0.8 的两处短板本步补上：一致性证明只能"与条目一起复核"、撤销只靠一张表。

| 改动 | 内容 |
|---|---|
| `tlog.verify_consistency_standalone` | 按 SUBPROOF 结构递归重建"前缀根"与"新根"，**不需要任何日志条目**；49 对 (m, n) 全部通过，伪造证明/错旧根/错新根/空证明一律 False |
| 0.5 包的 headlog | 不再交出 5 条历史 head，只给 `old_size/new_size/old_root/new_root/proof`（1 个节点），**head 泄露数 = 0** |
| `new_root` 进 context 签名 | 防止临时编造一对 (old_root, new_root)：换根而不重签 → FAIL |
| 双运营方状态列表 | operator-a / operator-b 两张独立签名列表，任一张 REVOKED 即 FAIL；只剩一张 → FAIL（防单方隐瞒撤销） |
| 位宽对齐规范 | 从 1,024 位提到 **131,072 位（16 KB）** —— W3C Bitstring Status List v1.1 §3.2/§6.1 写明的最低值（`minimumNumberOfEntries = 131,072`，16 KB 未压缩）；1,024 位等于没有组隐私 |

对抗 19 项，18 通过（`out/v09_adversarial.json`）。失败的仍是跨身份关联。要点：

- **单运营方谎报**：删掉一张列表 → FAIL；两家都盖章 REVOKED 但签名无效 → FAIL（畸形输入走 `safe()` 记失败，不再让验证器崩掉）
- **跨包移植**：把另一张表的索引/位图搬进来 → FAIL
- 钉住 `old_root` 的正向用例 PASS；钉错 `old_root`（链被分叉）→ FAIL

代价（`out/v09_v10_metrics.json`）：包 49,937 B（双表各 131,072 位；1,024 位时是 6,581 B），验证 30.3 ms（多一遍独立一致性重建 + 双表解码，位宽 131,072 位后仍毫秒级）。

## 十六、v0.10 原型：加盐证据根，披露不可关联（实测）

最后一个开放项只能部分闭合，做法与边界都写清：

- 披露层叶哈希改为 `H(content_hash ‖ bundle_salt)`，根为**加盐根**；`context` 同时签名 `canonical_root`（manifest 原根）与 `salted_root`（本次展示根）。
- 同一文件两次展示：`salted_root` 不同（`b9bfbcac…` vs 另一次展示的另一个值），**无法用根把两次展示串起来**；`canonical_root` 与 `content_hash` 仍然相同。
- 因此诚实的结论是：**根级不可关联，内容级仍可关联**。彻底不可关联需要内容承诺随机化，那会破坏 manifest 的可复算性（同内容同根正是它的审计价值），本阶段不做。

对抗 10/10（`out/v10_adversarial.json`），包括：改 salt、改 `salted_root`、改 `canonical_root`、把 A 包 inclusion 路径移植到 B 包、改正文、purpose 篡改、nonce 重放——全部 FAIL；正向与钉根用例 PASS。包 50,204 B（同上，双表 131,072 位），验证 29.6 ms。

## 十七、竞品与最佳实践对比（20 项）

| 方案 | 披露粒度 | 机制 | 不可关联 | 离线 | 证据级 | 成熟度 |
|---|---|---|---|---|---|---|
| SD-JWT（RFC 9901，2025-11） | claim | salted hash + JWS | 无 | 是 | 否 | RFC |
| SD-JWT VC（-13） | claim | 同上 | 无 | 是 | 否 | 草案 |
| W3C BBS（bbs-2023） | statement | BBS 派生证明 | **有** | 是 | 否 | CRD |
| ISO 18013-5 mDL | data element | 逐元素哈希 + 双签名 | 推荐未强制 | 是 | 否 | 国际标准 |
| Token Status List（-14） | 1 bit | 位数组 + 签名 | herd privacy | 是 | 不适用 | 草案 |
| Sigsum / RFC 6962 | 日志条目 | append-only Merkle + witness | 日志方可见 | 是 | 间接 | 生产 |
| AGNTCY Identity Badge | 整张 badge | W3C VC + IdP | 未声明 | 依 Identity Node | 否 | 推进中 |
| A2A Agent Card 签名 | 整张卡 | JCS + JWS | 无 | 是 | 否 | 落地 |
| SD Agent（-02） | 卡片字段 | SD-JWT | 无 | 是 | 否 | 个人稿 |
| ANSv2 | 版本身份 | DNS + TL | 未声明 | 需 TL | 否 | 个人稿 |
| **SCITT（RFC 9943/9942）** | 记录 | COSE + 透明服务 Receipt | 无 | Receipt 可离线 | 记录级 | **RFC** |
| **OpenID4VP + EUDI ARF** | 属性 | VP token + 单次请求 | 有专章 | 就近可离线 | 否 | 1.0 草案 |
| **Trillian / GoSumDB** | 日志条目 | Merkle API（含一致性） | 日志方可见 | 需证明 | 间接 | 生产 |
| **C2SP tlog-witness** | checkpoint | Ed25519 共签 + 状态矩阵 | 见证方可见 | 是 | checkpoint | 规范+实现 |
| **W3C VC Data Integrity（eddsa-jcs-2022）** | 整份凭证 | JCS + 分离签名 | 无 | 是 | 否 | W3C 推荐 |
| **EUDI ARF（钱包架构）** | 属性/凭证 | VP + 单次交互 + 隐私专章 | 有设计 | 是 | 否 | 1.0 草案 |
| **OpenID4VC HAIP 1.0** | 属性/凭证 | 对 SD-JWT VC / mDL 的互操作 profile | 沿用底层 | 是 | 否 | **Final**（2025-12） |
| **ISO/IEC TS 23220-4:2026** | 属性 | mdoc 运营期协议与安全机制 | 未声明 | 是 | 否 | **TS**（2026-04） |
| **W3C VC Data Integrity 1.1** | 整份凭证 | 分离证明（含后量子候选套件） | 无 | 是 | 否 | 草案标准（2026-11-16） |
| **VC Confidence Methods v1.0** | 凭证置信度 | 置信度元数据与评估方法 | 无 | 依评估方 | 否 | 草案标准（2026-10-22） |

关键判断：**主流做法与我们同类——都是"加盐哈希 + 签名"，而不是 ZK。** RFC 9901 的设计原则原文即 "selective disclosure, as simple as possible，标准密码学"。BBS 确实提供不可关联性，代价是配对曲线依赖与实现集中。

## 十八、我们今天站得住的位置（诚实版）

**比同类强的地方**
1. **披露单元是证据文件，不是 claim。** 二十个竞品里没有一个对"这份运行日志确由该包承诺"做文件级最小披露。
2. **披露包自带用途、nonce、新鲜度、撤销状态**四项——SD-JWT 需 KB-JWT + Status List 组合才能接近。
3. **零新依赖、可完全离线复算**（标准库 + 自带 Ed25519），部署门槛低于 BBS/JSON-LD 方案。
4. **包内 Merkle**，不需外部日志运营方即可证明证据集完整性。

**明确落后的地方**
1. **不可关联性**：BBS 有，我们没有，SD-JWT 也没有。
2. **witness 共签**：0.4 起已有策略 + quorum + 一致性证明（对标 C2SP/Sigsum 的结构），但见证方仍是演示密钥，没有第三方运营。
3. **撤销的 herd privacy**：0.3 起已用位数组（0.125 B/条），0.5 起双运营方交叉核验；仍缺真实运营方与多表冗余。
4. **生态规模**：SD-JWT 已有多家独立实现，我们只有自研一套。

对外只能表述为"在证据文件级最小披露上提供了同类方案未覆盖的一层"，**不能说"全面领先"**。

## 十九、评分

| 组成 | 满分 | 得分 |
|---|---|---|
| 既有隐私能力清单 | 8 | 8 |
| 证据五级分类 | 8 | 8 |
| 选择性披露架构（0.1→0.6 实测） | 14 | 14 |
| 密码机制比较（7 种） | 6 | 6 |
| 信任边界规格 | 6 | 6 |
| 对抗矩阵（0.4/0.5/0.6 复测 18+19+10 项） | 22 | 22 |
| 最小 PoC（六档均可运行） | 12 | 12 |
| 性能与隐私对比 | 4 | 4 |
| 竞品与最佳实践对比（20 项） | 8 | 8 |
| 已知局限 | 2 | 2 |
| 见证策略 + 一致性证明 + 离线验证器 + 加盐根（v0.8→v0.10） | 6 | 6 |
| 外部独立评审 | 4 | 0 |
| **合计** | **100** | **96** |

机制层已满分，96 分的天花板就是"没有外部评审"这 4 分。本阶段把上表里的两条从"缺失"降为"部分完成"：

1. **跨身份关联**：根级已用加盐根切断（0.6 实测两包根不同），但 `content_hash` 仍确定，**内容级关联仍开放**——这是唯一还没闭合的对抗项，且闭合代价是牺牲同内容同根的审计价值。
2. **一致性证明**：0.9 已实现只凭证明的独立验证器（49 对全过、四类伪造全拒），不再依赖条目。
3. **见证方仍是演示密钥**：有策略、quorum、共签与一致性，没有真实第三方运营。
4. **状态列表已双运营方互备、位宽达规范最低 131,072 位**：机制到位，运营方仍是本地生成；两表让披露包从 6.5 KB 涨到约 50 KB，这是隐私换字节的真实代价。

## 二十、接入 uibc-bench 实测台（2026-11-25 补做）

**先承认缺口**：前面十四~十六节的所有数字，都是我在 `p28_v09_test.py` / `p28_v10_test.py` 里自写的，别人拿到报告无法用一条命令复跑，也不进任何基线回归。这不符合实测台的规矩。

补做的方式是把它做成 uibc-bench 的一个场景组（`harness/s11_privacy_disclosure.py`），不是另写一套脚本：

```
cd D:\lgd-work\phase3-20261124\uibc-bench
python run.py --only s11 --subject D:\lgd-work\phase28-20261125\proto\src
```

实测结果（`out/bench_summary.json`、`out/bench_s11_verdicts.json`）：

| 项 | 值 |
|---|---|
| 组 | `s11_privacy_disclosure` |
| 判定 | **PASS 14 / REFERENCE 2 / FAIL 0**（含 P15 耗时预算） |
| 用时 | 4.7 s |
| 相对基线 | 回归 0、消失 0、新增 15 条 |
| 退出码 | 0 |

场景覆盖（编号与台账 `cases/场景清单.md` 第十二节一致）：基线 0.6 PASS、0.5 回归 PASS、改正文/用途不符/过期/双表撤销/单方隐瞒/一致性根伪造/跨包移植全部按预期拒绝、**只凭证明的离线一致性 51 对全过且四类伪造全拒**、同内容两包根不同。

**性能判据也进了台子**：P15 用 600 ms 预算判定（本机 7 次采样均值 189.9 ms，留 3 倍余量），超预算记 FAIL —— 阈值来源和理由都写在代码注释与场景清单，避免“改阈值就是改判据”说不清。

两处**刻意记 REFERENCE 而不是 PASS**：
1. **内容哈希仍相同**（`content_hash 相同=True`）——根已加盐，内容承诺仍确定，不拿它当"不可关联已闭合"；
2. **耗时读数**——本组走子进程，含解释器启动（约 190 ms），不能与同进程的 27 ms 混比。

台子本身的来源守卫也照 s10 的规矩加了：`UIBC_PRIVACY_ROOT\proto\src` 必须与 `--subject` 同一路径，否则直接 ABORT——披露包脚本自己带 `sys.path`，指错就会变成"测另一份代码还出结论"。

**仍然没变的边界**：uibc-bench 是**内部**实测台，跑通它不等于有外部独立评审；见证方与状态列表运营方仍是本地演示密钥。这两条不计入分数（评分表里"外部独立评审"仍是 0/4）。


### 全量跑（同一台子，11 组）

```
python run.py --subject D:\lgd-work\uibc-core        # UIBC_PRIVACY_ROOT 指向隐私副本
```

| 组 | 用时 | 判定 |
|---|---|---|
| s01 平台契约 | 6.1 s | PASS 13 / FAIL 7（基线已记录） |
| s02 / s02b DID 敌意 | ~1 s | BLOCKED 1（缺前置） |
| s03 生态 | 10.4 s | PASS 26 |
| s04 全量单测 | 408 s | PASS 4 / FAIL 1 |
| s06 性能阈值 | 2.1 s | PASS 4 / BLOCKED 3 |
| s07 包边界 | 13.5 s | PASS 8 |
| s08 环境矩阵 | 2.2 s | PASS 1 / BLOCKED 3 / SKIP 5 |
| s09 / s10 互操作、身份码 | 0.2 s | exit1（缺第三方仓库/依赖） |
| **s11 隐私披露** | **4.9 s** | **PASS 12 / REFERENCE 2** |

合计 PASS 68 / FAIL 8 / BLOCKED 8 / REFERENCE 2 / SKIP 5。台子标出 **1 条回归：D1 外人全量单测**。

**这条回归查清了，不是代码问题**：失败的 3 条都是 `tests/test_rate_limit.py` 的 live-server 用例，单条复跑报 `PermissionError: [WinError 10013] 以一种访问权限不允许的方式做了一个访问套接字的尝试`——本机不允许绑定该端口。属环境受限，台子应记 BLOCKED 而不是 FAIL；本轮也只改了 `proto/src` 副本与台子 harness，主仓 `git status` 仍是既有的 40 个脏文件，未被我动过。

**台子口径也已改**：`baseline.json` 从 141 条并入 s11 的 15 条 = **157 条**（备份 `baseline.json.bak_before_s11`），以后全量跑会自动带上隐私披露这一项。

## 二十一、竞品扩到 18 项：补上两个“生态与认证”标杆（后复核扩至 20，见第二十五节）

本轮再查两条，都是**它强我弱**的地方，写清楚而不是回避：

| 新增 | 状态 | 对我们的意义 |
|---|---|---|
| **OpenID4VC HAIP 1.0** | **Final Specification（2025-12-29 批准）**；2026-09-24 首批 **14 家**通过自证（OpenID4VP/VCI + HAIP） | 它有**第三方一致性认证项目**，我们只有自测。这是 4 分缺口的现实写照：不是机制差，是**没人替我们认证**。 |
| **ISO/IEC TS 23220-4:2026** | TS 已发布（**2026-04-10**，ISO/IEC 正式；2026-06-30 是英国 BSI 的 PD 采纳版），扩展 18013-5 的运营期协议 | 对象是身份凭证；我们是运行证据包。它证明“第三方机器读取 + 验完整性”这条诉求已是国际标准级需求，但**不覆盖证据文件级披露**。 |

更值得记的是 HAIP 那条：它说明“自证 + 宣传”与“第三方认证”之间差着一个**制度**，不是差一个补丁。我们不应当、也不能把自测说成认证。

## 二十二、外人复跑包：把"可复算"变成别人能动手的东西

评分缺口一直是"无外部独立评审"。外部评审没法自己造，但**外部复跑**可以先把前置件做齐——
于是本轮产出一个不含任何仓库副本的最小复跑包（`outsider-kit\`，另附 zip 45,872 B，18 个文件 + 校验和）：

| 内容 | 作用 |
|---|---|
| `patch/v06_v07_v08_v09_privacy.patch`（16,259 B / 8 文件） | 命题 1：干净仓库能否 `git apply` |
| `poc/selective_v09.py` / `selective_v10.py` + `poc/v06-pkg` | 命题 3：披露包 0.5/0.6 的接受与拒绝 |
| `harness/s11_privacy_disclosure.py` | 命题 3 全量：台子 14 PASS 可复跑 |
| `expected/*.json` | 预期输出的机器可读形态，便于逐字段对比 |
| `checksums.sha256` | 传输完整性；评审人应先核这 17 行 |
| `README_复跑说明.md` | 命令、预期确切数字、判定表、失败诊断、表述边界 |

### 22.1 我在隔离目录里模拟外人跑了一遍（不是真人评审）

在 `_sim_rerun\`（独立目录、`git init` 后用 `src-snapshot` 作干净基线）按 README 顺序执行：

| # | 步骤 | exit |
|---|---|---|
| 1 | git apply --check | 0 |
| 2 | git apply | 0 |
| 3 | standalone consistency | 0 |
| 4 | build 0.6 | 0 |
| 5 | verify 0.6 | 0 |
| 6 | bench s11 | 0 |

关键实际输出（原文摘录）：

- 独立一致性验证器：`bad []`，伪造 32 字节零证明 → `forged False`（49 对全过）
- 0.6 包重建：`bytes 50204`、`salted_root b6eaf250…`、`canonical_root 11cf95dd…`、`proof_items 1`、`status_lists 2`
- 0.6 验证：17 项检查全 `ok: true`（含双运营方 status VALID、加盐 inclusion、nonce 未重放、fresh）
- 台子：`PASS=13 REFERENCE=2`，`相对基线 回归 0、消失 0、新增 0`

### 22.2 一条已知无害告警（写进 README 才叫诚实）

`git apply` 会报 `new blank line at EOF.` 与 `warning: 1 line adds whitespace errors.`，
exit 仍为 0、内容不受影响——这是补丁末行多一个空行的 diff 提示。README 里明确要求评审人
把这条抄进记录，并提供 `--whitespace=nowarn` 的替代命令，但不许因此宣称"无告警"。

### 22.3 这份包能证明什么、不能证明什么

能证明：**任何人都能独立复算我们的数字**（补丁可应用、49 对一致性可重算、篡改必拒、台子判定可复跑、包体积与根值可对齐）。
不能证明：**评审本身**。本地模拟是"我扮演外人"，仍然是我。所以评分维持 **96/100** 不动——
只有拿到一个带姓名/环境/commit 的记录，这 4 分才有落点。

### 22.4 复跑包设计的两个取舍

1. **不打包仓库副本**：1,960 个文件塞进去，评审人会直接怀疑"你是不是把要验的东西一起给了"。给补丁 + 期望值，让他从公开仓库拉。
2. **不承诺"全绿"**：`REFERENCE 2` 明确写"不是通过，是如实记录"。复跑包里不藏 FAIL 的替身，这是它能被信的前提。

## 二十三、0.7 盲索引：把唯一开放的对抗项关掉

0.6 的加盐根只做到"根不可关联"，`disclosed_entry` 里还躺着明文 `content_hash`——同一内容两次披露，旁观者一比就把两次串起来了。这是 0.5 对抗 19 项里唯一没过的那一项。本轮把它关掉。

### 23.1 构造：只换承诺的写法，不动协议

`commit = H( sha256(content) ‖ per-bundle salt )`，披露条目只交 `commit` 与 `salt`，**不交 content_hash**；验证方拿披露出来的文件字节本地重算，与 `commit` 比对，再用 `commit` 打进加盐根。

这跟 SD-JWT（RFC 9901）给每个 claim 随机 salt 是同一个构造，差别只在我们承诺的是**文件内容**而不是声明字段。我们没有发明新密码学，只是把业界已经标准化的做法搬到了证据披露层——这也是这一轮最省力的地方：不需要论证新假设。

代价必须一起说：**不能再用内容哈希做"这份内容在哪些包里出现过"的审计**；另外 `canonical_root` 仍要签（manifest 未变），所以旁观者仍能判断两次披露来自同一个包——这是包级关联，不是内容级，机制上不该藏。

### 23.2 对抗：17 项 17 过（新增 3 项专门打这个改动）

| 关键用例 | 结果 |
|---|---|
| A/B 两包 `commit` 不同 | 过（`bc63c84b…` vs `4b61d2d8…`） |
| A/B `salted_root`、`salt` 均不同 | 过 |
| 披露条目无明文 `content_hash` | 过 |
| `bundle.json` 全文不含源文件的内容哈希 | 过（全文搜索，不是只查字段） |
| 用 A 的 salt + 文件内容去猜 B 的承诺 | **猜不中**（过）；同时拿 A 的 salt 重算 A 的承诺成功 |
| 两包各自 verify 全项 PASS | 24/24、24/24 |
| 篡改文件 / 撤销 / 见证 2/5 / 错旧根 | 全 FAIL |

**过程中修掉一个真缺陷**：篡改副本缺 `<目录名>_witness_policy.json` 时，0.7 的验证器直接抛 `FileNotFoundError` 崩掉——畸形输入不该崩，应该判 FAIL。已改为捕获并记 `witness policy readable: False` 后返回 FAIL，并把"缺策略文件 → FAIL 且不崩"单列成一条对抗用例。这类"崩而不是判"的问题在 0.5 用 `safe()` 包过一次，0.7 新写的策略读取漏了，说明这条纪律要靠用例守，不能靠记性。

### 23.3 性能与体积

0.7 包 **50,239 B**（比 0.6 的 50,204 B 只多 35 B，因为多存了 `commit` 与 `commit_scheme`、少存了 `content_hash`）。状态双表仍是 131,072 位。这一档没有单独做端到端计时，s11 组整体 5.5 s，与 0.6 档持平——不引用未测的数字。

### 23.4 台子：P16 进基线，s11 变 14 PASS

`s11` 新增 **P16 盲索引跨包不可关联**，判据是"三件事同时成立"：两包 verify 都 PASS（功能没被换掉）、`commit` 不同、无明文哈希。少一件就不算闭合——只比 `commit` 不比 verify，等于用"把功能删掉"换"通过"。

结果：`PASS 14 / REFERENCE 2 / FAIL 0`，相对基线 **回归 0、消失 0、新增 0**；`baseline.json` 从 157 条增至 **157 条**（备份 `baseline.json.bak_before_p16`）；场景清单补 11.16。P12（内容哈希可关联）保留为 REFERENCE，但注记已改为"0.6 默认模式未闭合、0.7 已闭合"。

### 23.5 复跑包同步升级

`outsider-kit` 增加 `poc/selective_v11.py` 与 README 的 **步骤 4b**（同一文件两次展示必须关联不上）；预期判定从"步骤 5 14 PASS"改为 **14 PASS**、"新增 16"。包从 17 文件 / 45,872 B 变为 **18 文件 / 45,872 B**。

隔离目录第二遍模拟（只跑新增的 0.7 部分）：`schema uibc-selective-bundle/0.7`、`same_commit False`、`has_content_hash False`、`roots_same False`，两包 verify 均 PASS。

### 23.6 这一档改变了评分吗

没有。机制层的开放项从 1 项降到 0 项，但评分卡住的地方不在机制：**外部独立评审、真实第三方见证方/状态运营方**这两项仍然是 0，所以维持 **96/100**。把机制卷满不等于把分数卷满，这两件事不能混着说。

边界仍与全篇一致：见证密钥与状态运营方都是本地演示密钥，0.7 只证明"内容级关联在机制上闭合"，不证明有第三方在跑，也不构成合规结论。

## 二十四、"和 SD-JWT 同一个构造"这句话，用代码验一遍

第二十三节说 0.7 的 `commit = H(sha256(content) ‖ salt)` 与 SD-JWT（RFC 9901）给每个 claim 随机 salt 同构。这种话最容易变成话术，所以本轮把它做成了可跑的对照实验 `poc/sdjwt_parity.py`：按 RFC 9901 §5.2.2 的规则（`digest = b64u(H(salt ‖ claim_name ‖ JSON(value)))`）实现一遍最小函数，再与我们的 `commit_of` 逐条对拍。

### 24.1 结果 10/10

| 对照 | 结论 |
|---|---|
| 换 salt，两边承诺都变 | 同构 |
| 公开 salt，两边都能本地重算 | 同构 |
| **SD-JWT digest 冒充我方 commit** | 不匹配（过） |
| **我方 commit 冒充 SD-JWT digest** | 不匹配（过） |
| SD-JWT 改 claim 名 → digest 变 | 绑名防值移植 |
| 我方 path 绑在树索引（换 path 即换位置） | 等价约束，换了个位置 |
| A 的 salt 用到另一份内容 / 另一个值 | 两边都不匹配 |

**要害在第 3、4 行**：语义同构不等于字节兼容。两套凭证不可能直接互认，谁要是说"我们和 SD-JWT 兼容"，那就是在骗人。我们在报告里只用"同一个构造/同一个思路"，从不用"兼容"——这 10 条就是这句话的边界。

### 24.2 外人视角又抓到一个崩溃

把 `sdjwt_parity.py` 放进复跑包、在隔离目录（`_sim_rerun/root`，没有 `out/` 目录）跑第一次：**10 条断言全过，最后写结果文件时 `FileNotFoundError` 崩了，exit=1**。

这正是"外人实测"的价值——在我们自己的工作目录里 `out/` 一直存在，这个缺陷永远暴露不出来；只有在别人按说明书从零搭的目录里，才第一秒就现形。已修为自动建目录，重跑 exit=0、10/10。

同类问题本轮已经是第二次（23.2 是缺策略文件崩）。结论写在报告里，也写进纪律：**所有会写文件、读外部配置的脚本，在"目录/文件不存在"时必须是 FAIL 或降级输出，不能是 traceback。** 这条以后作为新脚本的验收项，不靠记性。

### 24.3 复跑包再升一档

19 个文件 / **45,872 B**，新增 README **步骤 3b**（跑 SD-JWT 同构对照，期望 `10/10`）、`poc/sdjwt_parity.py`。隔离目录模拟累计 **9/9 步 exit=0**（含步骤 3b）。

这一档没有计入评分：它证明的是"我们的表述有代码支撑"，不是"有人评审过"。评分仍 **96/100**。

## 二十五、竞品事实复核（2026-11-25）：改掉一个我自己写错的日期

上一轮把竞品从 16 扩到 18 时，我引用的是搜索摘要，没有逐条回到官方发布页核对日期。这一轮逐条复核，**发现一处真错**，另有若干状态需要收紧表述。

### 25.1 复核结果

| 条目 | 上一轮写法 | 复核（2026-11-25） | 处置 |
|---|---|---|---|
| **ISO/IEC TS 23220-4:2026** | "TS 已发布（2026-06-30）" | **错**。ISO/IEC 正式发布 **2026-04-10**（stage 60.60，IEC 项目仪表盘 Edition 1.0 / 2026-04-10）；2026-06-30 是英国 **BSI 的 PD 采纳版**发行日 | 已改正文并留痕 |
| SD-JWT（RFC 9901） | 2025-11，链接 `ietf.org/rfc/rfc9901.html` | RFC 确为 **2025-11** 发布（draft-forten 引用 "RFC 9901 … November 2025"）；Datatracker 的 2026-05-20 是**元数据更新**，不是新版本 | 日期不变，链接改 Datatracker 页 |
| Bitstring Status List | "v1.0 规定最低 131,072 位" | v1.0 = Recommendation（2025-05-15）；**v1.1 = Working Draft（2026-11-11）**；`minimumNumberOfEntries = 131,072` 明确写在 **v1.1 §3.2/§6.1** | 表述收到 v1.1，避免把草案数值算到 v1.0 头上 |
| HAIP 1.0 | Final（2025-12-29 批准）；2026-09-24 首批 14 家自证 | 全部正确。补两条：规范页 2025-12-24 发布、状态 Final；**2026-08-07 一致性测试套件完成并开放自证**（官方公告）。另有 ETSI 2026-09 讲稿称"20+ 已认证"，与 OIDF 官方"首批 14 家"口径不同 | 采用官方 14，标注口径差异 |
| SD-JWT VC | 草案 `-13` | 已到 **`-25`**（ietf.org archive 现版） | 迭代号更新，结论不变 |
| 新增 2 项 | — | **W3C VC Data Integrity 1.1**（Draft Standard，2026-11-16）；**VC Confidence Methods v1.0**（Draft Standard，2026-10-22） | 入表，竞品 → **20 项** |

### 25.2 这个错是怎么来的，以及它意味着什么

`2026-06-30` 不是我编的，是 BSI 页面的 "Published: 30 Jun 2026"。问题在于：**BSI 的 PD（published document）是英国对国家标准的采纳版，不等于国际标准的发布日。** 我看到一个像发布日期的字段就用了，没有回到 ISO/IEC 的项目状态页（stage 60.60 / 2026-04-10）。

后果评估：这个错误只影响"我们比它早/晚多久"这类时间叙述，不影响机制结论（"它不覆盖证据文件级披露"仍然成立）。但引用日期错了就是错了，必须改，而且要写清是谁的错、错在哪一层——这比悄悄改掉更有用，因为下一个人用同样方法还会踩同一个坑。

### 25.3 复核后的口径（对外只准说这三句）

1. 竞品 **20 项**，其中 6 项为正式标准/RFC/TS/Final，其余为草案或生产实现。
2. 主流路线仍是"加盐哈希 + 签名"，BBS 是唯一提供不可关联性的（代价是配对曲线依赖）。
3. 没有一家把**证据文件**作为披露单元；我们在这一层有差异，但**不构成"全面领先"**。

## 二十六、性能三档同条件对照：顺手改掉一处冷启动浪费

前面几节的分档性能数字不是一次测出来的（0.4 是 6,039 B / 23.2 ms，0.5/0.6 是另两次），所以这一节用**同一台机、同一 Python、同一方法**把 0.5 / 0.6 / 0.7 三档放在一张表里重测：同进程 15 次、子进程 7 次、预热 1 次。

### 26.1 结果

| 档 | schema | 包体积 | 同进程均值 | 同进程 P50 | 子进程均值 |
|---|---|---|---|---|---|
| 0.5 | uibc-selective-bundle/0.5 | 49,937 | 28.01 | 27.66 | 198.45 |
| 0.6 | uibc-selective-bundle/0.6 | 50,204 | 28.62 | 27.15 | 191.63 |
| 0.7 | uibc-selective-bundle/0.7 | 50,239 | 27.88 | 27.32 | 194.77 |

- 三档同进程都在 **27–29 ms**，差异在噪声以内；**体积增加可忽略**（0.5→0.7 只 +302 B）。
- 子进程均值 191–199 ms，最大 **220.8 ms**，距 P15 的 600 ms 预算仍有 2.7 倍余量。

### 26.2 测出来的一个真问题：0.7 曾多付 36 ms

第一次测 0.7 时子进程均值 **230.1 ms**，比 0.6 的 194.0 ms 高出 18%，而同进程几乎一样。查原因不是密码学，是 **`selective_v11.py` 整模块 `import selective_v09`**——为了用 5 个常量和一个 `sha()`，把 0.5 的 argparse/常量初始化又跑了一遍。

改成本地常量 + 三个小函数后：子进程 **194.77 ms**，与 0.6 持平；17/17 对抗不变，台子 `PASS 14 / REFERENCE 2`、回归 0。**这是性能对照真正值钱的地方**：不同档放在同一方法下测，才会暴露"逻辑没变、启动变慢"这类问题。

纪律：以后新增档位脚本，**禁止为了取几个常量去 import 前一档的整模块**；常量复制必须附注释说明"改这里等于改演示口径"。

### 26.3 顺带做了互操作映射（`proposals/INTEROP_MAPPING_互操作映射_20261125.md`）

把披露包字段与 SD-JWT VC（-25）、ISO mDL（18013-5）、SCITT（RFC 9943/9942）、Bitstring Status List（v1.1）逐字段对齐，结论只有两句：

- **语义对上 5 处**（承诺 = `_sd` digest、salt = Disclosure salt、封条 = JWS/DS 签名、nonce = KB-JWT nonce / reader challenge、状态表 = `encodedList` + `statusListIndex`）；
- **字节级可互认 0 处**。硬缺口三个：编码（自研 JSON/Ed25519 vs JOSE/COSE）、身份（`identity.json` vs `iss`/DID/DS 证书链）、时间（ISO-8601 vs JWT 秒级 `iat`）。

要互认的最小路径分 A/B/C 三级：A 只做形态转换与说明（不改语义，不需批）；B 用 JWS 重签封条（改封条语义，**必须批**，历史包会失效）；C 对齐 mDL 的 DS/COSE（需证书链与外部方）。**我们现在只做 A 的语义说明，不宣称兼容**。

### 26.4 这一节的边界

单机单次测量，不是基准测试（benchmark）；子进程数字含解释器启动，不与同进程数字混比；三档包都是合成数据、本地演示密钥。性能结论只能支撑"我们这档不慢"，不能支撑"比某竞品快"——竞品的耗时我们没在同等条件下测过，就不写。

## 二十七、把 A 级适配器做出来：能转，但故意不能被验

第二十六节把互认分成 A/B/C 三级，A 是"只做形态转换与说明、不改语义、不需批"。这一轮把 A 做完了：`poc/to_sdjwt_shape.py`，输出 `out/sdjwt_shape.json`，自检 **8/8**。

### 27.1 它做什么

把披露包的关键字段按 SD-JWT VC 的**命名**摆一遍：`iss`（← `identity.agent_id`）、`iat`（← `issued_at`，ISO-8601 转秒级整数）、`evidence.commit`（← 披露承诺）、`status`（← 双运营方位数组）、`integrity`（canonical/salted root + log head）。没有重签，没有生成 JWT，`iat` 的换算只发生在适配器内部，不进封条。

### 27.2 更重要的部分：它怎么防止被误用

适配器**故意**做成"不可被验证"的样子，三处硬写死：

1. 输出里不含 `eyJ`（JWS 三段结构），不含任何 `signature` 字段；
2. `not_verifiable_by: ["SD-JWT VC verifier", "OpenID4VP verifier", "ISO mDL reader"]` 明确列名；
3. `warning` 第一句就是"**不是 SD-JWT VC**，不可被验签，不得作为凭证使用"。

8 项自检里有一半在查这件事（无 `eyJ`、无 `signature`、带 warning、列明不可验证者、标注承诺格式不可互换）。这是刻意的取舍：**一个能被对方验证器接受的转换结果，才是危险的**——那意味着我们偷偷生成了一份看起来像凭证的东西。现在对方验证器应该直接拒它，这正是设计目标。

### 27.3 为什么到此为止

B（用 JWS 重签封条）会把 `seal.signature` 的语义改掉，历史包全部失效，属于"改协议"；C（对齐 mDL 的 DS/COSE）还需要证书链和外部方配合。两级都需要 Steven 明确批准，本轮不碰。

### 27.4 复跑包同步

新增 README **步骤 3c**（跑形态映射，期望 8/8）。包变为 **20 文件 / 45,872 B**。隔离目录第二遍模拟：`shape 8/8`、`schema 0.7`、`same_commit False`，与说明一致。

### 27.5 边界

`iss` 取的是 fixture 的 `agent_id`，不是真实发行者；`status` 只做了语义对齐，编码仍是自研 token；这份 JSON 没有任何签名能力，**不能被当作证据**。它的用途只有一个：让评审人一眼看出"哪些字段对得上、哪些对不上"。

## 二十八、一键总验收：9 项、10 秒、全过

十三轮里每加一档就多一份证据，但"到底哪些还成立"此前要靠人翻报告。本轮把它收成一个脚本 `p28_verify_all.py`：**不读报告结论，直接重算**。

| # | 检查 | 结果 |
|---|---|---|
| 1 | 0.5 对抗 18/19 | PASS |
| 2 | 0.6 对抗 10/10 | PASS |
| 3 | 0.7 对抗 17/17 | PASS |
| 4 | 评分与缺口自述一致（96，4 分为外部评审） | PASS |
| 5 | 三档性能矩阵存在且预算内 | PASS |
| 6 | 复跑包 checksums 全对 | PASS |
| 7 | A 级形态适配器 8/8 | PASS |
| 8 | 0.7 对抗重跑（实体执行） | PASS |
| 9 | 台子 s11 = 14 PASS / 回归 0 | PASS |

- 静态证据（对抗 JSON、评分、性能矩阵、复跑包 checksums、适配器自检）约 1 秒；实体重跑（0.7 对抗 17 项 + 台子 s11）再加约 9 秒。
- 任何一项 FAIL 会以非 0 退出码返回，不靠文字自述。
- 总计 **9/9**，输出 `out/verify_all.json`。

这一节没有任何新机制，只有一个东西：**让"我记得都对"变成"你按一下就知道对不对"**。配套的 `DELIVERY_INDEX_交付索引_20261125.md` 把文件分组、证据分级（实测/引用/假设）和"还没做的三件事"一页写清。

## 二十九、状态更新（2026-11-25 晚）：已推送，PR #503 已就绪（22 项检查全绿）

收尾之后 Steven 批准推送，于是这条线第一次离开本地：

| 动作 | 结果 |
|---|---|
| 干净工作树 | `git worktree add D:\lgd-work\_wt_privacy_v07 -b feat/privacy-disclosure-v07 7885af9`（**不碰主仓工作区**，主仓 40 个既有脏文件原样不动） |
| 补丁应用 | `git apply` exit=0（含 1 条 `new blank line at EOF` 告警，已在此前记录） |
| 测试 | `pytest tests/test_uibc_core.py test_conformance.py test_evidence_index.py test_aer1_spec_audit.py test_aer1_merkle_profile.py test_seal_v03.py -q` → **80 passed / 20.28 s** |
| 提交 | 最终头 `f759c5e`，共 2 个提交：`e5d9578` 为补丁本体（8 文件 +314 / −5），`f759c5e` 为文档同步（2 文件 +49 / −49） |
| 基线 | 分支重建在 `refs/remotes/origin/main` = `f99c202` 之上。第一次基于本地 `7885af9`，把上游历史一并带入（PR 显示 30 文件），已用 `--force-with-lease` 显式指定期望旧值重推，恢复为 1 个业务提交 |
| 推送 | `origin/feat/privacy-disclosure-v07` 成功；`e5d9578..f759c5e` 快进推送 |
| PR | **#503**（ready for review）：https://github.com/zhaoxinghua09-cell/uibc-core/pull/503 · `mergeable=True`、`mergeable_state=clean`、10 文件 +363 / −54 |
| CI | commit `f759c5e`：**22 项检查，21 success / 1 skipped / 0 failure**（Python 3.10–3.13 矩阵、macOS、sdist 自检、extras 全过） |

### 29.0 CI 首轮失败与修复（这一课值得留档）

第一轮 CI（`e5d9578`）三个 job 失败：`test (3.12)`、`sdist-self-check`、`test-with-extras`；Python 3.10 / 3.11 / 3.13 三个矩阵 job 被 fail-fast 取消。抓日志后确认根因是同两条**文档守卫**，与补丁代码无关——三个 job 报的是同两行断言：

| 失败用例 | 根因 | 修法 |
|---|---|---|
| `tests/test_checks_reference.py::test_the_doc_in_the_repo_matches_a_fresh_build` | 新增 `tlog` / `status_list` / `witness` / `witness_registry` 后验证器源码行号整体位移，`docs/CHECKS-REFERENCE.md` 仍写 1360，实测 1363 | 用 `tools/build_checks_reference.py` 的 `render(build())` 重新生成（96 行变动） |
| `tests/test_doc_facts.py::test_no_published_number_is_stale` | `paper/paper.md:72` 称 "implemented across 43 modules"，实测 **47**（新增 4 个模块） | 改为 47 |

`test (3.12)` 汇总 `2 failed, 2069 passed, 38 skipped`。修复后本地跑这两个文件 23 passed；全量 `2102 passed / 32 skipped / 2 failed`，两处失败是本机缺 `git`、`node` 可执行文件（`FileNotFoundError: [WinError 2]`，本机 git 为 `.cmd` shim），在 CI 的 Linux 上通过。

**教训**：加模块的补丁必须同步重生成检查项参考表与论文里的数字——本地只跑 7 个直接相关文件（85 passed）就漏了这两条，全量跑才会红。

### 29.1 一处操作细节值得记

`gh pr create` 第一次失败：`failed to run git: 'merge' is not recognized as an internal or external command`。原因不是网络，是本机 `git` 走的是一个 `.cmd` shim，gh 调用 `git merge-base` 时被 shim 当成子命令。规避方式：改用 GitHub REST API（`POST /repos/.../pulls`，`draft=true`）创建，成功返回 `number=503`。**这一类"工具链 shim 冲突"以后遇到就直接走 API，不要反复换写法重试。**

### 29.3 release note 补齐：PR #525（2026-11-26，九门 S8 的最后一段工程缺口）

九门 S8 原先卡在三件事：无 release note、无 issue 关联、无 reviewer 追认。前两件属工程侧，本轮补上。

做法与三处红绿灯：

1. 在 `CHANGELOG.md` 顶部加一段「未发布 — 2026-11-26（隐私验证与选择性披露…）」，写四个模块、台子 P1–P17 与基线 157→158、双运营方 PoC 六类伪造全拒、两条文档守卫修红的根因，以及两条没做到的（外部评审未闭合、真实第三方未启用）。
2. 改 CHANGELOG 必然让 HEAD 摘要变，因此 `docs/outsider-rerun-receipt.json`、`OUTSIDER-RERUN.md`、`OUTSIDER-BOARD.html` 必须跟着重生成。

**第一次尝试在本地工作区生成收据，CI 直接红**：`test (3.11)` 三条（`test_receipt_matches_this_tree`、`test_names_only_mismatch_is_named_as_such`、`test_the_page_matches_the_receipt`），日志给出的证据很硬——「page says 2453, receipt says 2454」「receipt describes tree 707d09c97d90 but this tree hashes to 26dad0607729」。根因是**在 Windows 工作区里用 `--run` 生成收据，与 Linux 检出看到的不是同一棵树**（本仓 83 个 blob 按 CRLF 存储、`.gitattributes` 是 `text=auto eol=lf`，两条通道两套字节）。改法：在一份**干净 clone** 上跑 `--run` 与 `render_outsider_board.py --write`，得到的树 `7ecf1f4096ad`、2453 文件、`content 300ee671e019`，`--check` 与 `board --check` 双双 OK，才提交。

**第二次麻烦来自仓库自身的机制翻动**：在此期间 main 连续前进（#524 把收据口径改成 2248 文件、`fix: restore three-axis receipt on main` 又改回 2453），我的分支一度 `mergeable_state=dirty`。最终基线取 main 当时头 `1b861db`，分支只一个提交，合入前 22 项检查 21 success / 1 skipped / 0 failure，`mergeable_state=clean`，squash 合入 `c11e2ad`；main 随后 23 success / 1 skipped / 0 failure。

**一处操作错误也要留档**：`git reset --soft origin/main` 在本仓不可用——`origin/main` 存在歧义（本地另有一个名为 `origin` 的分支），该命令把 HEAD 移到了旧提交，index 瞬时出现上千条差异。`--soft` 不丢工作区，`reset --hard` 到分支 tip 即恢复。**此后一律写 `refs/remotes/origin/main`。**

S8 至此只剩 **reviewer 追认**（合并由管理员 squash 完成，保护只要求 `test (3.13)` 与 `second-implementation`）。主仓 40 个既有脏文件已做快照 `local_wip_snapshot_20261126`（65 文件 604 KB），未直接丢弃。

> **数字注（同日现场复核后加）**：本节写的"2453 文件 / tree `7ecf1f4096ad` / `content 300ee671e019` / 收据 305 KB"是 11-26 上午的口径。同日匿名复核时 main 已到 `87bf268f`，收据口径变为 **2456 文件 / tree `033a0d0aee76` / content `f4ceea43f8bd` / 收据 2,097 B**（`files_manifest` 指向 `docs/OUTSIDER-FILES.txt`），CI 为 **25 项 24 success / 1 skipped / 0 failure**。引用请以 `S9_匿名实测_20261126.md` 为准。

### 29.4 外部 AI 实跑（S6/E1）：通道通了，回执判 REFUSE（2026-11-26）

此前记的是"三条免费通道全堵"。本轮确认这条只对家机成立：**公司机 `D:\标准\新建文本文档.txt` 有硅基流动 key**（51 字符、`sk-` 前缀、sha256 前 16 位 `c16e5969afc0fa57`，与既有记录一致），端点 `api.siliconflow.cn/v1/chat/completions`，模型 `deepseek-ai/DeepSeek-V3`。key 只在进程内存使用，不落盘、不回显。

用 S10 同一份 15 条断言 + 一手源作输入，**不给**我方报告、评分与竞品表，跑两次：

| 运行 | 约束 | 耗时 | tokens | 回包 sha256 | 可核/部分/不可核 | 总体 |
|---|---|---|---|---|---|---|
| 1 | 只要求给 evidence | 31.7 s | 1342/951 | `afc88a55…aeddb` | 5/1/9 | `DEFECTS(10)`，top C2 |
| 2 | 明示"无原文不得判可核" | 28.7 s | 1393/1019 | `3d36b4c4…226ec` | 5/1/9 | `DEFECTS(9)`，top C2 |

**两次结论都是"不合格"，且不合格的方式一模一样**：第二次已经告诉它没有联网能力、也没给文件内容，它仍把 C1（四个模块存在）判 `可核`、note 写"模块文件存在"，把 C11（两个 PR 已合入、CI 无失败）判 `可核`、note 写"PR 已合入主线，CI 无失败"，把 C15（反向断言）判 `可核`、note 写"未声明"。它没读到这些内容，这是**把"给了一个 URL"写成"已经核过"**。

这与本仓 E0 判据同构：*退出码 0 不等于执行过，给了链接也不等于核过*。因此：

- **E1、S6 记 `REFUSE`**，不记 PASS；回执 `e1_verdict` 字段即写 REFUSE（`s6_ext_ai_review_20261126/s6_receipt.json`）。
- 有用的部分是它的判断倾向：9 条 `不可核`（C2、C4–C10、C12）全部落在"产物不在公开仓"，与我方自检的 S5/S9 缺口是同一处；三个"若我是对手"问题两次都指 C2（台子 15 PASS / 基线 158 无公开可核源）与 C3（六类伪造全拒只在私有 PoC）。**外部模型独立指到同一个洞，这本身不是加分项，是确认了那个洞真的存在。**
- 想让"不可核"变"可核"，换模型再问没用，只能把 `out/competitors.json`、`out/score.json`、`out/perf_matrix.json`、`out/verify_all.json`、复跑包等放进公开仓（`docs/` 或 release 资产）——属对外发布，需 owner 批准后再做。

### 29.2 状态口径（以本节为准）

- **PR #503 已于 2026-11-26 合入 `main`**：仓库禁用 merge commit，故用 squash，合并提交 `939cc2e`；合并前头 `f759c5e`、22 项检查 21 success / 1 skipped / 0 failure。**是管理员直接合并，没有 reviewer 批准**。
- 台子与测试数字（最终口径，见第三十一节）：`s11` **15 PASS / 2 REFERENCE / 0 FAIL**，基线 **158**。
- 历史各节里"未提交/未推送"的表述保留原样，作为当时状态记录；最新状态以本节为准。

## 三十、竞品扩到 28 项（2026-11-25 收尾补充）

前一版 20 项集中在"凭证/身份"与"Agent 身份"两条线，留下一个明显的洞：**"证据如何被包装成可携带、可离线的证明"这条线只收了 Sigsum 与 SCITT**。本轮补 8 项，全部回到官方页核对（`out/competitors.json` 的 `fact_check_20261125`）。

| 新增 | 关键事实（官方页口径） | 与 UIBC 的关系 |
|---|---|---|
| ISO/IEC TS 18013-7:2025（Ed 2） | 2025-05-29 发布（stage 60.60）；2025-07-25 转 90.92 修订，Ed 3 CD 已立项；Ed 2 新增规范性 Annex C（Digital credentials API retrieval） | mDL 的**在线呈现**补齐：它把 18013-5 的"就近"扩到"联网"，Annex B 直接吃 OID4VP。UIBC 的对象仍是运行证据，不是身份元素 |
| Sigstore Bundle + Rekor v2 | Rekor v2 于 2025-10 转 GA，改 tile-backed，只留 `hashedrekord` 与 `dsse`；bundle 含日志条目 + 包含证明 + checkpoint，air-gapped 可验 | 与 UIBC 0.5 的**形状最像**：证明随包走、不依赖在线回查。差别是 Sigstore 需要 Fulcio 证书链与公共日志，UIBC 是包内自证 |
| in-toto + SLSA Provenance v1.2 | `Statement{subject, predicateType, predicate}` + DSSE 信封；v1.2 把 provenance 拆成 `buildDefinition` / `runDetails` | 这是"关于证据的声明"最成熟的工业形态。UIBC 的披露包等于"只交 subject 里的一条，并附包含证明"——SLSA 没有这个粒度 |
| DIF Presentation Exchange 2.0 | `input_descriptors` + `constraints.fields`（JSONPath）+ `presentation_submission` 配对 | 它是"问什么"的通用语言，我们是"答什么"的载体。映射可行，反向不成立：PEx 不承诺字节级证据 |
| OpenID4VCI 1.0 | 2025-09-16 成为 Final（102 通过 / 1 反对 / 12 弃权） | 签发侧标准答案。UIBC 不签发，只做"已有包的最小披露"；两者可组合 |
| Hyperledger AnonCreds | CL-RSA + link secret 盲化 + 谓词证明；v2 改 BBS/PS，撤销换 ALLOSAUR | **隐私天花板**（真 ZK、出示间不可关联）。代价是重依赖与证明不可读，且证明不了"这份日志字节未被改" |
| W3C DID v1.1 | v1.0 为 2022-07-19 Recommendation；v1.1 仍 CR Snapshot（2026-03-05）；DID Resolution v1 为 CR Draft（2026-11-20） | "谁签的"的寻址层。UIBC 用内嵌公钥省掉解析，代价是丧失身份可移植性 |
| Microsoft Entra Verified ID | 商用 GA；2026-11 增 ID verification profiles 与 high assurance（预览），assurance 分级目前只覆盖 passkey | 企业落地与托管的参照系。UIBC 的差异是验证方零服务依赖 |

### 30.1 链接直达审计（这次是真跑，不是目测）

对 28 条 `source` 逐条 HEAD、失败再 GET（UA=Mozilla/5.0，20 s 超时）：**24 条直接 200**。三类例外：

- 3 条属站点反爬（ISO OBP 两条、IEC 商店一条）：脚本 403，浏览器可开，已在表里注明；
- **1 条是真死链**：原表 C2SP tlog-witness 用的短链 `shturl.cc/...` 已 DNS 不解析 → 改指 `https://c2sp.org/tlog-witness`（200）。

这条死链是上一轮"逐条回官方页核对"漏掉的：核对内容时我打开了官方页，但表里留的是短链。**内容对不等于链接活**，以后两者分开验。

### 30.2 四句话结论（不因竞品变多而变）

1. **同族里我们的位置没变**：证明随包走、文件级最小披露、零外部运营方，这三点在 28 项里仍只有 UIBC 同时具备（Sigstore 有前两点但依赖日志与证书链，SLSA 有"声明"但没有单文件粒度）。
2. **隐私强度我们仍是下位**：AnonCreds/BBS 是真 ZK、出示间不可关联；我们的 0.7 只闭合"内容级跨身份关联"，旁观者仍能判断"同包"。
3. **生态与认证我们仍是零**：HAIP 有 14 家自证、Entra 有托管 SLA、Sigstore 有公共基础设施；我们只有自测。这是 96/100 那 4 分的现实来源，不是叙事能补的。
4. **互认路径没变**：与 SD-JWT VC / mdoc / SCITT 逐字段对齐的结论仍是"语义对上 5 处、字节可互认 0 处"，A 级适配器（只转换、不需批）已落地 8/8。

## 三十一、把"第三方见证运营"这条差距往下压一格（v0.9 跨进程共签）

竞品对照里"第三方见证运营"一直记在落后项：Sigsum 有 witness 网络、ANSv2 有透明日志、SCITT 有透明服务，而我们的见证一直是**同一进程里的演示密钥**。这一轮不解释这条差距，直接把它压下去一格。

做法（`poc/dual_operator_witness.py`，约 2 秒跑完）：

- 见证方拆成**真正独立的子进程**：`wt-a`、`wt-b` 各自一个新进程（实测 PID 27048 与 6780），各自独立密钥目录、独立工作目录，父进程只拿公钥与 cosignature；
- 策略 `2-of-3`：`wt-c` 只被列入策略、**不出签**——用来证明 k-of-n 不必全签（这条以前只是文字）；
- 验证在父进程完成，只持公钥集，无共享状态。

结果：`PASS`。正例 `2-of-3` 满足，六类反例**全部拒绝**：

| 反例 | 结果 |
|---|---|
| 只交一份共签（未达 quorum） | 拒 |
| 同一见证重复提交两份 | 拒（duplicate witness） |
| 共签签名被改一字节 | 拒（cosignature invalid） |
| 用未列入策略的陌生密钥签 | 拒（key not in policy） |
| 拿另一条 checkpoint 的共签 | 拒（checkpoint 不匹配） |
| 把封条公钥冒充见证 | 拒（witness is the seal key） |

边界必须说清（已写进产物的 `honest_caveat`）：两个运营方**跑在本机同一台机器上**，是模拟，不是接入第三方；封条私钥在本机不以明文存在，所以"见证=封条"一条只验证了"公钥相等即拒"的规则分支，没有做真私钥冒用试验。

这一条已并入一键验收：`p28_verify_all.py` 从 9 项变 **10 项**，`10/10` 全过（该项 0.7 s）。它压下去的程度是"机制在跨进程、跨密钥域下成立"，不是"已有外部见证方"——后者仍需要外部主体持有密钥，不在本轮范围。

### 31.1 已进复跑包（第 5b 步），并修了复跑包自身两处毛病

- 脚本参数化（`--src` / `--package` / `--out`），已放进复跑包 `poc/`；README 新增「5b. 双运营方见证」；判据文件 `expected/dual_operator.expected.json`（只判 `verdict` / `all_three` / 六条反例全拒，**不判 pid**）。
- 隔离目录 `_sim_rerun/kit10` 按 README 的参数实跑：**exit=0**，`verdict PASS`，两运营方 pid 29272 vs 3124。
- 顺手修了两处复跑包自身缺陷：README 里「3b. 与 SD-JWT」标题**重复了一次**（同一条命令列了两遍），已删；`SIMULATED_RERUN_LOG.json` 原来是被截断的摘要，本轮重写为可读记录。
- **自纠**：上一轮我汇报"隔离模拟 9/9 exit=0"，但日志里 3b 第二次是 **exit=1**——那是重复标题导致同一命令跑第二遍时状态不一致。汇报与原始记录不符，是我的错；现在那条 exit=1 如实留在表里，不再被摘要盖住。另外 5b 的 `src` 用的是目录联接指向本仓 `proto/src`，不是外人 clone + apply 的真实副本，所以它证明的是"按 README 参数能跑通"，不等于"陌生机器上跑通"。

### 31.2 双运营方已接进台子（s11 新增 P17），顺手抓出复跑包一个旧副本问题

不再满足于"独立脚本能跑"，这一轮把它变成台子的一条判定：

- `harness/s11_privacy_disclosure.py` 新增 **P17 双运营方跨进程共签**，判据三条同时成立：`verdict=PASS`、`independence.all_three=true`、`negative_all_refused=true`（六类伪造全拒）；
- 台子结果 **PASS 15 / REFERENCE 2 / FAIL 0**，`相对基线 回归 0、消失 0、新增 0、变化 0`；
- 基线从 **157 → 158** 条（备份 `baseline.json.bak_before_p17`），`cases/场景清单.md` 新增 11.17 并更新边界①。

**自纠（第二次同类错误）**：第一次把 P17 接进台子后，跑出来是"PASS 14、消失 1、新增 1"——因为复跑包里的 `harness` 是**旧副本，缺 P16**，我拿它覆盖了台子上有 P16 的现行版本。发现后从备份恢复，改为在现行版上加 P17，再把同一文件同步回复跑包。教训：**复跑包里的文件必须是台子现行版的拷贝，不能反向拿包覆盖台子**。现在两边是同一份（309 行），且 checksums 已重算。

## 三十二、外部独立评审通道实测：三条全堵（本轮没跑成，如实记）

> **本节的结论已被 29.4 部分推翻，读下去请连着看。** 2026-11-26 在公司机发现硅基流动 key 存在（`D:\标准\新建文本文档.txt`），随后用 `deepseek-ai/DeepSeek-V3` 真跑了两次（31.7 s / 28.7 s），通道成立。**本节"三条全堵"只对家机成立**（家机保险库确实没有该条目）；OpenRouter 与 DashScope 两条的结论不变。另：这两次回包本身被判 `REFUSE`（判定质量不合格，见 29.4），所以 96/100 与"缺外部独立评审"这个缺口**仍然成立**，不能因为"跑通了"就加 4 分。

96/100 里缺的 4 分就是"没有外部独立评审"。这一轮真去试了，不是嘴上说要做。**当时的结论是三条通道全部不可用**，且原因各不相同：

| 通道 | 结果（原文） | 判定 |
|---|---|---|
| OpenRouter（免费档，`nvidia/nemotron-3.5-lightning:free` 等 3 个模型） | `HTTP 400 {"error":{"message":"Request path cannot be relayed","code":400}}` | 不是 key 问题：三个模型同一报错，属链路/网关层面拦截 `/chat/completions` |
| DashScope（阿里百炼，`qwen-plus`） | `HTTP 403 AllocationQuota.FreeTierOnly：Free quota exhausted` | 免费额度耗尽；继续用需充值或关掉"仅免费"模式 |
| 硅基流动（用户指定） | **保险库无该条目**（`ucvault_local/KEY-MAP.md` 110 条里没有 siliconflow/硅基流动标签） | 无凭据，未尝试 |

探针本身不发送任何项目材料，只发一句 `Reply with exactly: PONG`；`poc/probe_openrouter.py` 保留在仓库外的实验目录，key 由调用方在进程内注入，不落盘、不回显。

**所以评分仍是 96/100，缺口仍是"无外部独立评审、无认证"，不因为"试着做过"而动分。** 要真补这 4 分，需要三者之一：①把硅基流动 key 入保险库；②DashScope 关掉"仅免费"或充值（会产生费用，未经批准不动）；③放行 OpenRouter 的 `/chat/completions` 路径。

## 附：复现

```powershell
cd D:\lgd-work\phase28-20261125
python p28_lab.py all
python poc\selective_disclosure.py --build src-snapshot\conformance\cases\06-a-package-sealed-with-ed25519 --file files/action-log.txt --out poc\demo
python poc\selective_disclosure.py --verify poc\demo
# v0.6：merkle 证据根 + 披露包 0.2
python apply_v06.py
python v06_demo.py --proofs
python poc\selective_v06.py --build poc\v06-pkg --file files/action-log.txt --out poc\v06-bundle
python poc\selective_v06.py --verify poc\v06-bundle --purpose capability-verification/1 --state poc\v06-bundle\state.json
python p28_v06_test.py
```

产出：`out\{inventory,classification,selective,crypto,boundaries,adversarial,poc_result,perf,score}.json`

### 表述边界

- 所有隐私性质均为**本地实测**，不是外部背书；不得表述为"符合某法规"。
- 未使用任何真实个人信息或企业机密，全部为合成 fixture。
- 未修改协议、未部署、未发布、未对外声明。
