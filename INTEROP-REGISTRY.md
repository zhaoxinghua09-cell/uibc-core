# 互操作登记表

形态参照 `action-state-group/agent-action-capsule` 的 `INTEROP.md`：把"谁跑了什么、结论是什么、证据在哪"写成一张表，而不是散在若干文档里。

**独立性一栏必须诚实。** 同一作者、同一台机器、同一份语料，都不算独立第三方。

| 参与方 | 独立性 | 做了什么 | 结果 | 证据 |
|---|---|---|---|---|
| 发布方实现（`zambo` 的 `base/conformance.py`） | 对方代码，但同源规范 | 判我们产出的 9 份 AER-1 0.4 收据 | 9/9 PASS | [PR #86](https://github.com/zhaoxinghua09-cell/uibc-core/pull/86)、`docs/AER1-EMIT-RESULT.md` |
| 我们（本仓库） | — | 判外来 21 份 `valid/` 与 36 份 `invalid/` | 21 ACCEPTED / 36 REJECTED | [PR #88](https://github.com/zhaoxinghua09-cell/uibc-core/pull/88)、`docs/AER1-VERIFY-EXTERNAL.md` |
| 我们（本仓库） | — | 复现公开语料 143 个向量 | 143/143 | [PR #85](https://github.com/zhaoxinghua09-cell/uibc-core/pull/85)、`docs/AER1-REPLAY-FULL.md` |
| 我们（本仓库） | — | 八种篡改 × 双实现对照 | 7 种双方一致拒绝，1 处分歧已公开 | `docs/AER1-EMIT-RESULT.md` |
| 异协议产物（Agent Action Capsule / SCITT，28 份 JSON） | 协议不同 | 冒名测试：能否被误认成 AER-1 | 0 误接受 | `docs/COMPETITIVE-VERIFIABILITY.md` |
| **真实独立第三方** | — | — | **0（缺口）** | 见下 |

## 缺口

`docs/OUTSIDER-RUN.md` 是给第三人的执行说明。它现在**没有交付给任何真人**，所以上表最后一行为 0。

对照：AAC 的 `INTEROP.md` 已登记 EMILIA Protocol（三家独立计算）与 GlyphZero（双向 `ran & verified`）。这是当前唯一一处我们明确落后、且无法靠写代码补上的一格。

## 维护规则

- 只登记**跑过**的事；"计划""将支持""已兼容"不进表。
- 每条必须带可点击证据（PR 号 / 文档路径 / 复跑命令）。
- 独立性一栏不得填"第三方"除非对方是不同组织、不同代码库、不同机器。
