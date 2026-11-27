# ROLES

写明谁有权做什么，避免"谁都能改"与"只有一个人能改"同时成立。

## 角色

| 角色 | 现任 | 职权 | 限制 |
|---|---|---|---|
| Maintainer（维护者） | Xinghua Zhao (@zhaoxinghua09-cell) | 合并代码、开分支、提名版本候选 | 不得单独合并规范实质变更 |
| Specification Editor（规范编辑） | Xinghua Zhao | 提交规范文本 PR | 不得自行宣告"通过" |
| Reviewer（审阅者） | 空缺（外部自愿者，≥1 人时本条生效） | 对 PR 出书面意见 | 不得代替 Maintainer 合并 |
| Release Approver（发布批准） | Xinghua Zhao | 批准 tag 与 release 正文 | 不得批准自己参与判定的被评件 |
| Backup Maintainer（备份维护者） | 待指定 | Maintainer 90 天无活动时自动接管合并权 | 接管须在 GOVERNANCE.md 留一条记录 |

## 单一维护者的处置（现状，不粉饰）

当前一个自然人持有全部职权。这是事实，必须写出来：

1. 每 90 天在 `GOVERNANCE.md` 增补一条"维护者在岗"记录：日期 + 最近一次合并的 commit。
2. 连续 90 天无合并动作，Backup Maintainer 自动取得合并权，无需另行投票。
3. 未指定 Backup 之前，本条记为 **UNMET**，对外不得声称 "bus factor > 1" 或"多维护者治理"。

## 批准权（谁说了算）

- **代码合并**：Maintainer。
- **规范实质变更**（改判定语义 / 增必填字段 / 收紧 PASS 条件）：Maintainer + 至少 1 名 Reviewer 书面同意；Reviewer 空缺时，PR 内必须附"语料 diff + 受影响实现清单"（`GOVERNANCE.md` §4），并由 Maintainer 在 PR 正文写明"单人批准（无审阅者）"。
- **发布**：Release Approver。发版正文必须含 `VERSIONING.md` §3 的七个字段，缺一不发；发版同时写 `anchors/pins/uibc-release-<tag>.json`。
- **对外表述**：任何"通过测试 / 合规 / 认证"表述须经 Maintainer 复核，且不得出现 "certified" 或"官方"（`GOVERNANCE.md` §3）。
- **判定独立性**：判定人不得同时是收费复核服务的收款方（见 `APPEALS.md` §4）。

## 变更本文件

本文件变更走 ADR（`docs/adr/`），与 `GOVERNANCE.md` §2 同一规则。
