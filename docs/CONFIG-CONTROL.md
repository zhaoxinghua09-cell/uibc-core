# Change control: who proposed it, who decided, and what moved

A conformance suite is only usable by a party that trusts neither the producer nor the
implementer. Such a party cannot evaluate bytes without knowing what happens when those
bytes change. Three of our peers wrote that down; this page records what we took from
them, what we mechanised, and what we still do not have.

## What the peers state (read in full, 2026-11-20)

| 仓库 | 改动是怎么被决定的 | 一句话里最硬的那条 |
|---|---|---|
| `probityai/agent-evidence-vectors` | 单一维护者，公开约束自己；每条提案落入**四种处置的闭集**：`adopted` / `adopted-in-part` / `declined` / `open`；`declined` 是有理由的决定，`open` 必须写明"什么能把它关掉"；部分采纳必须在行里写残差；台账 **append-only**；被拒的异议也公开 | "A record of only the agreeable objections is worse than none." |
| `emiliaprotocol/emilia-protocol` | 任何人可提；规范行为的改动**必须在规格文本、参考验证器、一致性向量三处同时落地，或都不落地**；向量是"是否一致的运行定义" | "together, or not at all." |
| `tyche-institute/eatf-verifier` | 一段话：由一个人维护、属开放研究软件而非标准机构 | 没有可机械化的规则 |

我们此前的 `CODEOWNERS` 只有一行 `* @zhaoxinghua09-cell`——它约束"谁点了合并按钮"，
不约束"改了什么、谁批的、批的理由、批完之后语料是否跟着动"。这正是这一维的缺口。

## 我们机械化的五条

`tools/check_config_change.py` 读一条 `uibc-change-v0` 记录，按五类拒：

| 拒绝 | 来源 | 它挡住什么 |
|---|---|---|
| 提案人与决定人是同一方 | 我们自己 | 变更自我批准，那等于没有第二个读者 |
| `disposition` 不在闭集里 | probityai | 用形容词代替决定 |
| `declined` 无理由 / `adopted-in-part` 无残差 / `open` 无"什么能关掉它" | probityai | 把缺口藏在状态词后面 |
| 标为规范变更却缺 `spec` / `verifier` / `corpus` 任一条腿 | emilia | 只改一处就宣称行为没变 |
| 行内容的摘要与 `id` 不符、或台账链断开 | 我们自己 | 事后编辑历史行 |

另有两条轻的：模式标为"非规范"时必须写理由（否则"非规范"是免罪符）；决定时间不得早于
提案时间、也不得晚于一年（迟到的同意仍是同意，但一年后的"同意"是失踪）。

"silence is not agreement" 落成什么：`decision.by` 与 `decision.at` 都是必填，**没有"七天无人反对"这种写法**。
想用沉默通过，记录就通不过。

## 实测，2026-11-20

四条记录串成一份台账（全规范变更 → 部分采纳带残差 → 拒绝带理由 → open 带结束条件）：

```
$ python tools/check_config_change.py ledger.json --decider-key <hex>
bfa79bbab17d — 'adopted' by Maintainer, decided by Decider at 2026-11-20T01:00:00Z, normative True, legs corpus, spec, verifier
eac66789dd19 — 'adopted-in-part' by Maintainer, decided by Decider at 2026-11-20T03:00:00Z, normative True, legs corpus, spec, verifier
228731323239 — 'declined' by Outsider, decided by Decider at 2026-11-20T05:00:00Z, normative False, legs none
af2b1588e474 — 'open' by Outsider, decided by Maintainer at 2026-11-20T07:00:00Z, normative False, legs none
ACCEPTABLE — 4 row(s), chain intact, dispositions from the closed set
```

删掉第一行的 `verifier` 腿后重跑，一次给出三条理由 —— 缺腿、行被事后编辑、签名不成立：

```
NOT ACCEPTABLE
 - row 1: normative change is missing the verifier leg; it lands in all three or not at all
 - row 1: the id is 'bfa79bb…' but the body hashes to cc496e10…; this row was edited after it was recorded
 - row 1: the Ed25519 signature does not verify over the canonical record
```

第三条是这回真实踩到的坑：第一版在签名与验签两侧用了不同的字节（签名时没有 `signature`
字段，验签时有了），于是**每条正常记录都报签名不通过**；测试立刻暴露，改成两侧共用
`signed_bytes()`（行去掉 `signature`）后 17 例全绿。一个验签器如果从来没被自己跑过，
它和一句口号没有区别。

## 仍然没有的（写成缺，不写成待办）

- **台账是空表。** 仓库里没有一条 `uibc-change-v0` 记录；空集表示"还没有被记录的配置变更"，
  不表示"变更受控"。第一次真实使用就是下一次改 `docs/` 里的口径。
- **没有分支保护的可核证据。** `CODEOWNERS` 与 GitHub 的 required review 是平台设置，
  不在字节里；外人无法从仓库证明它们开着。
- **没有撤销已落地变更的机制。** 撤销只能作为一条新记录（`disposition: declined` 指向旧 id），
  旧记录仍在台账里，这是设计（append-only），但也意味着"撤回"永远是一条新行而不是删除。
- **阈值授权仍无。** 一条记录一个签名；与 `docs/DELEGATION.md` 是同一个缺口。
