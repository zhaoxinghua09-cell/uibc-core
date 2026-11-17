# PCCP ↔ uibc 字段对照（21 CFR 892.2055）

> 用途：把 FDA 已生效的 PCCP 条款要求，逐条对到 uibc 包里能承载的东西，并**明确标出对不上的部分**。
> 这不是合规章导意见，也不是申报模板；它是"我们的对象模型能证明到什么程度"的自我盘点。
> 任何人不得把"uibc 验证 PASS"读成"FDA 会接受"。

## 1. 法规锚点（先摆事实）

- 2022-12-29 由《FD&C Act》§515C 引入 PCCP：一项变更若**符合已获授权的 PCCP**，无需新的 510(k) 或 PMA 补充。
- 2026-06-17 FDA 以最终命令新增 **21 CFR 892.2055**——"放射学机器学习定量影像软件 + 预定变更控制计划"，
  这是**第一个把 PCCP 写进法规条文**的器械类型（此前只有指南与个案 clearance）。
  （来源：eCFR §892.2055；FDA 最终命令与 De Novo 记录；PCCP 指南已定稿，更宽的 AI 器械生命周期指南仍为草案。）

法规原文（特殊控制项，摘录）：

> "(2) As part of the design verification and validation activities, you must document the
> planned device modifications of the quantitative imaging software, and the associated
> methodology for the development, verification, and validation of modifications made
> consistent with the performance requirements in the plan."
>
> "(3) As part of the risk management activities, you must identify and assess the risks of
> the planned modification(s) and identify corresponding risk mitigations."
>
> "(4) Labeling must include: … (vii) Labeling related to the predetermined change control
> plan (PCCP), including: (A) A statement that the device has a PCCP; (B) A description of
> modification(s) implemented … including a summary of current performance, associated
> inputs, validation requirements, and related evidence; and (C) A version history, a
> description of how device modification(s) will be implemented, and a description of how
> users will be informed …"

## 2. 逐条对照：能承载 / 勉强承载 / 承载不了

| # | 法规要求 | uibc 现有承载 | 覆盖强度 | 说明 |
|---|---|---|---|---|
| 1 | **计划变更**及其描述 | 无专门对象。只能把每次变更记成一条 lifecycle 事件 + 一份证据 | **弱** | 我们记的是"已经发生的变更"，法规要的是"事先声明的可变更范围"。两者不可互替 |
| 2 | 变更的**验证/确认方法学** | `evidence` 条目（type=`EVAL`）+ `note`；`policy_hash` 绑定生效策略 | **弱** | 能证明"这份方法学文档存在且未被改"，不能证明"方法学本身合规" |
| 3 | 变更**风险评估与缓解** | 无对应类型（现有 EVIDENCE_TYPES 无 RISK） | **缺** | 需要新增 evidence type 或独立 `risk` 段落，且必须绑进 `evidence_root` |
| 4 | 标签声明"本器械有 PCCP" | 包不承载标签 | **缺** | 标签属申报文档层，不应塞进证据包；最多存标签的哈希并声明"标签版本" |
| 5 | 已实施变更的**当前性能/输入/验证要求/证据** | `manifest.agent_version` + evidence 条目 + 封签 | **中** | 性能数字是"被记录的事实"，不是"被验证的结论"——我们不做行为评价 |
| 6 | **版本历史** | lifecycle 事件序列 + `checkpoint_head`（生命周期 head ⊕ 证据根 ⊕ 索引元数据 ⊕ 条数）；`S8` 抓截断、`S9` 抓回滚 | **强** | **这是唯一真正对得上的地方**：法规要"版本历史"，我们给的是不可回滚、不可截断的版本链 |
| 7 | **用户告知方式** | 无 | **缺** | 属流程文件，不进包 |
| 8 | 变更"符合已授权 PCCP"（§515C 免新申报的前提） | 我们**只**证明记录自洽 | **明确不做** | 是否在授权范围内是合规判断，需人/监管方裁决；我们给的是"证据边界内的三项事实" |

## 3. 所以这块地怎么用（结论）

**能对上的只有第 6 条（版本历史）与第 5 条的一半。** 这已经足够形成差异化，因为它是整份法规里
**唯一"必须可追溯、否则无法自证"**的要求，而市面上的 agent 证据方案（AIVS 的会话包、AAT 的审计链、
APort 的授权决定）**都面向 agent 运行时，不面向器械生命周期**。

正确的产品动作是把第 6 条做到行业默认形状：

```
PCCP 变更 #N
  ├─ manifest.json        版本号、变更标识、policy_hash
  ├─ lifecycle.json       变更事件（谁、何时、何状态迁移）
  ├─ evidence/index.json  本次变更附带的验证/确认证据
  ├─ checkpoint_head      ← 关键：与 #N-1 的 head 形成链
  └─ signatures/seal.json 封签（anchored 才算数）
```

审阅方拿到第 N 个包，只要**手里有第 N-1 个包外记录的 head**，就能判两件事：
这条历史有没有被改写（S8），以及有没有人拿旧包顶替新包（S9）。这正是"版本历史"在监管语境里
真正需要的性质——不是"有个列表"，而是"**列表改不动**"。

## 4. 必须说清的边界（否则会被当成夸大）

1. **FDA 不会因为"包可自验"而接受**。申报材料是文档与数据，包只是让这些材料**可追溯、可复算**的组织方式。
2. **不做合规判断**。第 8 条明确不做：我们不判"是否符合已授权 PCCP"。
3. **不做性能评价**。第 5 条里的"当前性能"是记录下来的数字，不是我们验证出来的结论。
4. **不做见证**。没有独立见证人，所以历史"没被整体重写"这一点，只有在你保存了带外 head 时才成立
   （与 `--expect-head` 同一逻辑；`draft-ruvalcaba-nhe-audit-00` 对无钥链的边界写了同一句话）。
5. 本文件基于公开法规文本；如与官方最新文本冲突，以 eCFR 为准。

## 5. 下一步（把"弱"补成"中"所需的最小改动）

| 缺口 | 最小改动 | 是否影响既有包 |
|---|---|---|
| 计划变更（第 1 条） | `manifest.pccp = {plan_id, planned_changes[], plan_hash}`，仅当申报 PCCP 时存在 | 否（可选字段） |
| 风险与缓解（第 3 条） | 新增 evidence type `RISK`，纳入 `evidence_root` | 否（新增枚举值） |
| 标签版本（第 4 条） | `manifest.labeling = {version, sha256}` | 否 |
| 用户告知（第 7 条） | 记录为 evidence type `NOTICE` | 否 |

四条都是**可选字段**，加进去不会让旧包失效——这与本项目一贯的兼容策略一致（新增即向后兼容，
收紧校验才需要升版）。
