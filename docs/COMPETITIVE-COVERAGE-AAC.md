# 对照：他们 40 类向量，我们独立复算了 1 类，并且在那一类里发现我们缺一条

2026-11-19 ｜ 数据源：`action-state-group/agent-action-capsule` 的 `vectors/`（clone 后 40 个目录）

---

## 先给结论

| 项 | 数字 |
|---|---|
| 对手公开向量目录 | 40 |
| 我们能**只用标准库**独立复算的 | **2**（`json-nesting`、`history-frame-v0`） |
| 我们跑出的第一版独立复算 | **4/9 分歧，全部是我们缺 128 层上限** |
| 把我们缺的那条补上之后 | **9/9 一致，rc=0** |
| `history-frame-v0` 的 22 项绑定判定 | **22/22 一致，0 分歧（一次就对，无需补任何东西）** |

也就是说：不是"我们更强"，是**在他们写成规范、四种语言共享的这一条上，我们原来是缺的**。补上之后才一致。

本页不主张任何「首个」地位：同一批向量上已有 IETF BMWG/BPM 评测基准草案、AACP 认证、AAIF 与 OpenReview《Skills as Verifiable Artifacts》等在推进，我们只是把「自己能复算多少」如实写下来。

## 为什么 40 类里只有 1 类能算

他们的验证栈是 **MMR（cll）+ COSE + ed25519**；我们的栈是 **RFC 6962 Merkle + 自建 20 项检查**。两套东西的向量，多数在语义上不可比：拿我们的 RFC 6962 代码去折叠一棵 MMR 树，出来的差异说明不了任何一方的对错。

逐类实测的技术栈标记（脚本对每个目录扫 JSON 文本得）：

| 类别 | 标记 | 可否独立复算 |
|---|---|---|
| `json-nesting` | 无（纯 JSON 文本） | **可以** |
| `history-frame-v0` | 无（JSON 值 + SHA-256） | **可以**（`tools/crosscheck_aac_history_frame.py`） |
| `cbor-nesting` / `cbor-request-model` | 无 | 需 CBOR 解析器，未做 |
| `checkpoint-consistency` / `cll-material` / `bundle` | MMR | 算法不同，不可比 |
| `cross-language` / `minimum-necessary` / `producer-envelope` / `settlement` / `evidence-request` | COSE + ed25519 | 需 COSE 库，本机无 |
| 其余 25 类（`capsule`、`judge`、`judgment`、`interop-profile-*` 等） | ed25519 或无标记 | 多为签名/注册表/文本层，不属算术可比范围 |

完整目录清单见 `tools/crosscheck_aac_json_nesting.py` 的同目录报告与本节表格。

## 我们缺的那一条是什么

他们的 `spec/interop-profile-v1.md` §5.2 与 capsule draft 的 Conventions 一节写明：**JSON 的深度上限是 128 层**（`[]` 算 1 层，`[[]]` 算 2 层），深于此视为畸形输入；四种语言（Go / Python / TS / Rust）共享这一条（#498）。

我们原来**没有这只上限**。跑他们的 9 个 case，4 个负例（`neg-arrays-past-limit` 等，均为 129 层）我们全都接受了：

```
neg-arrays-past-limit      depth=129  accept=False  we_accepted=True   <-- DISAGREES
neg-objects-past-limit     depth=129  accept=False  we_accepted=True   <-- DISAGREES
neg-mixed-past-limit       depth=129  accept=False  we_accepted=True   <-- DISAGREES
neg-after-escaped-backslash depth=129 accept=False  we_accepted=True   <-- DISAGREES
cases: 9  mismatches: 4
```

## 补法

`uibc_core/canonical.py`：

- `MAX_NESTING_DEPTH = 128`
- `nesting_depth(obj)`：标量 0、`[]` 1、`[[]]` 2
- `check_nesting(obj, limit=128)`：超限抛 `ValueError: nesting depth N exceeds the limit of 128`
- `canonicalize()` 入口先调用它

复跑：

```
pos-arrays-at-limit        depth=128  accept=True   we_accepted=True   ok
neg-arrays-past-limit      depth=129  accept=False  we_accepted=False  ok
pos-objects-at-limit       depth=128  accept=True   we_accepted=True   ok
neg-objects-past-limit     depth=129  accept=False  we_accepted=False  ok
pos-mixed-at-limit         depth=128  accept=True   we_accepted=True   ok
neg-mixed-past-limit       depth=129  accept=False  we_accepted=False  ok
pos-brackets-in-string     depth=1    accept=True   we_accepted=True   ok
pos-after-escaped-backslash depth=128 accept=True   we_accepted=True   ok
neg-after-escaped-backslash depth=129 accept=False  we_accepted=False  ok
cases: 9  mismatches: 0
VERDICT: WE MATCH THEIR NESTING CONTRACT
```

## 这条限制的连带影响（如实记）

新加的上限改变了 `conformance` 对抗样本的诊断结果，`docs/THESIS-CH5-TABLES.md` 由 `tools/build_thesis_tables.py` 重新生成后，表 5-4 的两个数字从 `0 / 0` 变为 `4 / 14`（对方 `4 / 5`）。原因：原先被接受的深层输入现在被拒，可报的原因因此变多。文档由脚本现读生成，不是手改的。

## 这一段在论文里怎么写

> "对照该实现公开的 9 个嵌套用例，本实现原接受其中 4 个超出其规范上限（128 层）的负例；补入该上限后 9 个全部符合。该上限并非本实现原有设计，而是对照时发现并补齐的。"

**必须写"补齐的"，不能写"我们本来就有"。**

## 第二类：`history-frame-v0`，一次就对

11 个 case，22 项绑定判定（`table_binding` / `pack_binding`）：

```
properties: 22  disagreements: 0
VERDICT: OUR JCS REPRODUCES THEIR BINDING VERDICTS
```

这一类的摘要算法与我们完全一致：我们对他们给的 JSON 值做 RFC 8785 规范化后取 SHA-256，得到的值与他们在 `listed` 里登记的一致；五个负例（`pack-digest-mismatch`、`table-digest-mismatch`、`pack-for-another-instance`、`pack-translated-in-place`、`pack-carries-checked-string`）也按预期不一致。

注意范围：这只验证**绑定**（摘要是对的那份），不验证他们的计数规则（那是他们的主题）。


## 已排除的候选，与排除的理由

探查过、判断**不做**的类，理由写在这里，免得下次重复试：

| 类 | 为什么不做 |
|---|---|
| `standard-history-v0`（3 个文件共 69 个 case） | 考的是**计数规则**（`in_window`、`outcomes` 分类、优先级），不是摘要绑定。要复算就得完整实现 SH §5–§11 的优先级语义——那等于照抄对方的规范，不构成独立验证；读漏一条，产出的"分歧"还是我们的错。所以不碰。 |
| `cbor-nesting` / `cbor-request-model` | 需 CBOR 解码器。本机无 `cbor2`；手写最小解码器的风险大于它能给的证据。 |
| `checkpoint-consistency` / `cll-material` / `bundle` | MMR（`cll`）树。与 RFC 6962 是两套算法族，折叠结果的差异不可归因。 |
| `cross-language` / `minimum-necessary` / `producer-envelope` / `settlement` / `evidence-request` / `anchor-witness-v1` | COSE + ed25519，需 COSE 库；本机无。 |
| `capsule`（239 文件）、`judge`、`judgment`、`interop`、`profiles`、`registry-conformance`、`viewer-core-text`、`evidence-dataset`、`evidence-result`、`disclosure-envelope`、`adapters`、`deal-reconcile-v0`、`controller-binding-v0`、`coverage-declaration-v0`、`personal-history-*`、`inference-service-history-*`、`interop-profile-*` | 注册表 / 文本 / 策略层，或依赖签名。不在算术可比范围。 |

**结论：2/40 是"只用标准库可独立复算"的上限，不是偷懒。** 把 40 类都跑一遍需要先实现 MMR、COSE、CBOR 三套东西，那时跑出来的数字已不能叫"独立复算"。

## 边界

- 这只覆盖 40 类中的 2 类，占 5%。
- 其余 39 类的差异属算法族不同，不构成本实现的强弱证据。
- 对手的 `INTEROP.md` 仍不列本仓库；跑通一类向量不改这一点。
