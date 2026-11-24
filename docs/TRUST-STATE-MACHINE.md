# 信任状态机：七态之间的合法移动

2026-11-24。对应战略 P1-2。代码：`uibc_core/trust_state.py`；机器表：`docs/TRUST-STATE-TRANSITIONS.json`（由 `transitions_document()` 生成，测试逐字节比对）。

`interop_result` 说一个判定**是什么**，这一页说同一个主体再被判一次时，**什么移动是合法的**。两件事分开，是因为前者管形状，后者管历史。

## 两条硬规则

1. **没有证据，什么都不许升到 `VERIFIED`**，包括一分钟前刚被 `REVOKED` 的。后者还要额外一个 `reinstated=True`——撤销的解除是治理动作，不是再跑一次的结果。
2. **坏消息不需要许可**。`VERIFIED` 随时可以掉到 `INVALID` / `REVOKED` / `EXPIRED` / `INCONCLUSIVE`；反方向才逐条检查。**沉默永远不是升档。**

## 符号

`·` 原地不动（无新主张）｜`ok` 无需证据即可｜`E` 需至少一条证据｜`E+R` 需证据 + `reinstated=True`｜`-` 合规实现**不得**发出

| 从 \ 到 | VERIFI | INVALI | REVOKE | EXPIRE | INCONC | UNSUPP | UNRESO |
|---|---|---|---|---|---|---|---|
| **VERIFI** | · | ok | ok | ok | ok | - | - |
| **INVALI** | - | · | - | - | - | - | - |
| **REVOKE** | E+R | ok | · | ok | - | - | - |
| **EXPIRE** | E | ok | ok | · | - | - | - |
| **INCONC** | E | ok | ok | ok | · | ok | ok |
| **UNSUPP** | E | - | - | - | ok | · | ok |
| **UNRESO** | E | ok | - | - | ok | ok | · |

补注：`REVOKED`、`EXPIRED` 作为**新**状态时必须写明原因（原地不动不需要）。

## 为什么这几格是 `-`

| 移动 | 为什么禁止 | 说给谁听 |
|---|---|---|
| `INVALID → VERIFIED` | 一个已经判出违规的陈旧包，重跑一万次也还是那个包。"通过"只能属于**新**制品，不属于旧对象 | 想靠重试把红变绿的人 |
| `VERIFIED → UNSUPPORTED` | 不会做是能力事实，不是判定结果。判过了再说"我们没实现"是自相矛盾 | 想用 `UNSUPPORTED` 擦掉已判结果的人 |
| `REVOKED → INCONCLUSIVE` | 撤销是已知的坏消息，不许退回"判不了" | 想让撤销悄悄失效的人 |
| `UNSUPPORTED → INVALID` | 读不懂不等于读出了违规 | 想把"不认识"升级成"你有罪"的人 |

## 这份表管什么、不管什么

**管**：合规实现能发出哪些序列。两台实现可以对同一主体给出不同判定，但只要历史合法，分歧就是**结论分歧**而不是**过程违规**——互操作里最贵的那类争吵（"你到底有没有按规矩走"）因此可以先被排除掉。

**不管**：

- **谁对**。判定对错要靠证据与复跑，不靠转移表。
- **新鲜度**。`EXPIRED → VERIFIED` 需要证据，但"这份证据是不是刚取的"要接收方自己判，本模块不看时钟。
- **时长**。没有超时概念：`VERIFIED` 不会自己变 `INCONCLUSIVE`，要靠重新判。
- **第三方**。这张表是我们自己的实现契约；外部实现可以不遵守，那时 `COMPATIBILITY.md` 里该出现第二行，而不是我们改表迎合。

## 复跑

```
python3 -m pytest -q tests/test_trust_state.py     # 9 条
python3 -c "from uibc_core import trust_state as ts; print(ts.transitions_document()['rows'][:2])"
```

测试钉住 49 格与磁盘 JSON 逐字节一致；改一格必须同时改表，否则红。
