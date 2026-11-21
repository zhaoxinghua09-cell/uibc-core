# 与 SCITT 的一份逐字段对照（2026-11-20）

**结论先说**：我们不兼容 SCITT。`docs/SCITT-CROSSWALK.json` 用 18 行对照把差在哪写到字段级：
**3 行相同 / 8 行部分 / 6 行缺失 / 1 行是我们多做**。容器不是 COSE_Sign1，没注册进任何 Transparency Service，
也没有 CBOR。任何一个"SCITT-compatible"式的说法，都会让 `tools/check_scitt_crosswalk.py` 退出码 1。

## 对照的是哪份文本

`docs/spec-sources/draft-noa-scitt-ai-agent-receipt-00.txt`（`SCITT AI-Agent Action Receipts`，individual draft，-00），
读的是仓内这份 504 行的原件，不是记忆。读了 §3（载荷结构）、§4（COSE Signed Statement 配置）、§5（哈希链与完整性）、
§6（身份绑定）、§9（**policy-replay 明确排除在本版范围之外**）。该草案是个人提交，不是已被采纳的标准——不把它写成标准，也不把我们写成它的实现。

## 三行相同（不是巧合，是同一个构造）

| 他们的 | 我们的 |
|---|---|
| `chain.hash` = `sha256(JCS(去掉 chain.hash 与 sig.value))` | 签名与摘要都覆盖 **JCS(去掉 `signature` 的整行)**：`tools/anchor_release_digests.py` 的 `signed_bytes`、`tools/check_config_change.py` 的同一规则 |
| 哈希链只证明"在呈现的链内不可改、不可截尾"，**不证明 equivocation**；要证明那件事需要注册进透明服务 | `docs/LAB-PROTOCOL.md` 原话：bundle 只能证明之后无法改口，不能证明运行发生过 |
| 没有身份清单时，attribution 只在密钥层面成立，且**必须向依赖方明示这一限制** | `docs/DELEGATION.md`：不带外给出公钥时打印 `identity unbound`，不假装绑定了身份 |

第三行尤其值得记：**"必须明示限制"这条规则，他们写在草案里，我们写在校验器里。** 两边都是把"没证明的东西"变成可见的句子，
而不是让它悄悄通过。

## 六行缺失（写明代价，不写成待办）

| 他们的字段 | 我们为什么没有 |
|---|---|
| `scope.tenant` / `scope.chain` | 没有租户、没有每发行方链头；这需要一个有归属的发行方，而回执属于跑它的那个人 |
| `agent.model` | 回执侧观察不到模型；填了也只是 runner 的声明，权威性与 `run_by` 一样为零 |
| `agent.principal`（HUMAN/SERVICE/POLICY/SANDBOX_SIM） | 我们不分类"谁在行动"，`run_by` 是无枚举的自由文本 |
| `action.paramsHash` | 我们确实有"只绑摘要、不放原文"的做法，但绑的是**语料**（`manifest_sha256`），不是行动参数；两者结构同源，不能互相顶替 |
| `action.reversible` / `rollbackRef` | 验证是副作用自由的，没有可回滚的东西；加上就是一个没有值可填的列 |
| 注册进 Transparency Service | 我们锚的是 RFC 3161 TSA（以及客户端存在时的 OTS）。**时间戳证明某时刻已有这些字节；它不证明某个日志接受了它们。** 把 TSA 叫透明服务，是本文档拒绝做的那一步 |

## 八行部分相同

`spec` 标识（角色同、字符串不同，读 `noa.receipt/0.1` 的人不会找到我们）；`id`（我们靠文件摘要寻址，回执内没有 id）；
`ts`（`when_utc` 同形）；`agent.id`（`run_by` 是自由文本，草案自己也称其 `agent.id` 为 signer-asserted）；
`action.id/canonical/riskClass`（我们的"行动"是一致性案例，有 id 与攻击类，但没有风险类，因为一个案例不是一次高风险行动）；
`governance.*`（逐案 verdict 与规则名有，随运行附带的批准没有，只有一份独立委派记录）；
`chain.seq/prevHash`（构造同源，但对象不同：我们的链在**变更台账**上，不在回执流上；回执彼此靠语料摘要相连，不靠 seq）；
COSEv1 容器与 `alg = -19`（拒绝其它算法的规则相同，容器不同，且没有 CBOR 互操作）。

## 一行我们多做

草案 §9 把 policy-replay **明确排除**在本版范围之外。我们的产品恰恰是逐案重放：294 个案例、三种对照、退出码契约。
这是对照表里唯一我们超出的行——但它的意义是"这份草案还没做这件事"，不是"我们比它强"。

## 检查器拒什么

- 源文档不在仓库里 → 拒绝（"对着没人能读的文本做的对照，是记忆不是比较"）；
- `container.interoperable` 不是 `false`；
- `flags.registered_in_transparency_service` / `emits_cose_sign1` / `claims_scitt_conformance` 任一不是 `false`；
- 标为 `partial` 却没写 `note`，标为 `absent` 却没写 `cost`（没有代价的缺失读起来像临时状态）；
- 整表没有任何一行 `have`（那就该写一句话，而不是摆 18 行）；
- 扫描 README 与三份关键文档，出现 `scitt-compatible` / `scitt compliant` / `conforms to scitt` 等短语 → **OVERCLAIM**，退出码 1。

## 实测

```
$ python tools/check_scitt_crosswalk.py
counts: have=3, partial=8, absent=6, ours_only=1
ACCEPTABLE — 18 rows against the vendored draft, no conformance claim in the scanned documents   exit 0
```

把 `flagged.claims_scitt_conformance` 改为 true，或在 README 写一句 "SCITT-compatible"，立即 `NOT ACCEPTABLE`、退出码 1 或 3。

## 仍然没有的

- **没有 COSE/CBOR 编解码路径**：不接 CBOR，就没有互操作，`interoperable: false` 是字面事实。
- **没有任何透明服务**：没有运营方、没有日志、没有注册策略。
- **没有提交给 SCITT 的 IETF 线程**（该做的就是用户账号的动作，不是我能代做的）。
