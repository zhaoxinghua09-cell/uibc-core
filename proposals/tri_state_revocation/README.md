# Tri-state revocation — local prototype

状态：**本地原型，未并入任何公开仓**。用途：把此前被检索推翻的“三态撤销”主张，先做成语义清晰、可复跑的最小实现，等评审后再考虑合入。

## 为什么需要第三态

通常的撤销判断只有两态：在名单里 = revoked，不在 = not revoked。问题在于“不在名单”可能来自三种完全不同的情况：名单没拿到、名单过期、名单签名坏了。把这三类都当成 not revoked，就是典型的 silent failure。第三态 `undetermined` 的作用是把“不知道”与“没撤销”分开。

## 判定规则

输入：撤销快照 `Feed{issued_at, entries, signature_ok}`、主体 ID、评估时刻 `t`、最大新鲜度 `max_age`。

| 条件 | 结果 |
|---|---|
| 无快照 / 签名无效 / `t < issued_at`（时钟偏移）/ `t - issued_at > max_age` | `undetermined` |
| 快照新鲜且无该主体条目 | `not_revoked_at_t` |
| 有该主体条目且 `revoked_at <= t` | `revoked_at_t` |
| 有该主体条目但 `revoked_at > t` | `undetermined` |

## 复跑

```bash
cd proposals/tri_state_revocation
python -m unittest -v test_tri_state     # 15/15 OK
python tri_state.py                      # 4 个演示用例 ALL PASS
```

红队用例（14 个对抗输入：naive 时间、非 datetime 条目、`entries=None`、负 `max_age`、边界等值）
在 PR 描述中逐条列出；修复前其中 5 个抛 `TypeError/AttributeError`，修复后 14/14 全部落 `undetermined`，不抛异常。

## 边界（必须写进任何引用处）

- 这是**分类器原型**，不处理签名验证本身（`signature_ok` 由调用方给出）。
- 没有接入任何真实撤销源；没有并发、持久化、时钟同步处理。
- 输入类型不合法（naive 时间、非 datetime、非映射、负 `max_age`）一律判 `undetermined`，不抛异常——这是 fail-closed 的一部分，但**时钟真伪仍需调用方保证**。
- 只有 15 个单元用例、14 个红队用例与 4 个演示用例，**不构成产品实现，也不构成外部验证**。
- 合入公开仓前需：命名对齐现有 API、增加反例向量、补 README 首屏窄声明、过 CI。
