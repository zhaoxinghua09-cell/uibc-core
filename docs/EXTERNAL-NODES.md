# 外部验证节点登记表

> 这张表是 `README` 里 `external verification nodes` 那一行的**唯一出处**。README、`OUTSIDER-RUN.md`
> 和邮件正文里的数字都指向这里；要改数字，先改这张表，再让其他文档引用。
> 只有当**不在我们项目里的人**在自己机器上跑出结果并回传，这一行才加一。
> 我们承诺：失败的那次也记，原样记，不改写成"环境问题"，也不静默重跑到通过为止。

## 怎么登记

一次登记五列，不写评价，不写形容词：

| 日期 | 谁 | 平台 | 结果 | 回传文件 sha256 / 复算依据 |

- **谁**：可以是真名、可以是"anonymous runner #1"。对方不愿意被记录名字时，只写序号与平台（例如 `anonymous runner #1 · macOS 14`）。
- **结果**：原样抄 `external_node_check.py` 输出的一行判词（`CONSISTENT` / `INCONSISTENT`），以及测试的通过/失败/跳过数。不合并成一个"通过率"。
- **sha256**：对方回传的 `external_node_result.json` 的 sha256，这是唯一能证明"回传文件没被我们动过"的东西。
- **没有文件时**：只在报告里的数字能被我们**在指定 commit 上复算并逐项对上**时才记，且必须把复算依据（脚本名 + 复算结论）写在同一行。凑不上就不记。

## 记录

截至 2026-11-19 12:00 +0800，本表 **1 条**。

| 日期 | 谁 | 平台 | 结果 | 回传文件 sha256 / 复算依据 |
|---|---|---|---|---|
| 2026-11-19 | Wang Guigui（Correctover — AI Reliability） | Debian GNU/Linux 13 (trixie)，kernel 5.10.134，容器，uid 1001 无 sudo，无 `pip install` | 复算 `8a95747`：`Ran 605 tests` `OK`，`cross_check.py` **70 checks / 2 mismatches / AGREEMENT: FAIL - SPEC BUG**；随后自取修复分支 `refs/pull/169/head` 复跑：**70 checks / 0 mismatches / PASS** | 无文件回传（邮件正文）。复算依据：`tools/verify_external_node_report.py` 导出 `8a95747` 后同机复跑，`VERDICT: MATCHES THE RECEIPT (605 tests, 2 mismatches)` |

关于这一条的限制，写在这里而不是脚注：他是本项目同一 W3C 工作组的通信方，
**是第三方执行，不是第三方利益**——不是无利害审计者；而且是我们请来的，主动到访的节点比被邀请的更强。
一个节点是一个节点，不是一个样本。详见 [`external-review/EXTERNAL-NODE-001.md`](external-review/EXTERNAL-NODE-001.md)。

仍然为 0 的三条，继续保持可见：外部文档引用本仓库 **0**、任何团体采纳 **0**、
与本项目无关的人独立复现 **0**。

邀请方式见 [`OUTSIDER-RUN.md`](OUTSIDER-RUN.md)（三分钟，零安装），中文完整说明见
[`EXTERNAL-NODE-KIT.md`](EXTERNAL-NODE-KIT.md)。

## 我们不会做的三件事

1. 不把"我们自己换一台机器跑"算成外部节点。
2. 不把"对方说看起来没问题"算成外部节点——没回传文件、也没复算对上，就没有记录。
3. 不在表里加主观评价（"对方很满意""结果非常好"）。表只回答一个问题：谁、什么时候、跑出了什么。
