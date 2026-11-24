# 验证语义冻结（Semantics Freeze）

冻结日期：**2026-11-24**。对应战略 P0「冻结验证语义」。
冻结不是宣布完成，而是**宣布"再改就要付出可见代价"**：下面两个哈希被测试钉住，语义一变，测试立刻红。

```
states-sha256: 5a458ca1765e7f4b6d813ac47c623f0e8f1b0b34800595acdd788322871e56cd
schema-sha256: a46b3319e5f66665addfb1e2e5584e88c94211dd3deded07b3fffe738c6b11da
```

（`states-sha256` = `sha256("|".join(STATES))`；`schema-sha256` = `sha256(json.dumps(states_document(), sort_keys=True, separators=(",",":")))`。校验器：`tests/test_semantics_freeze.py`。）

## 一、被冻结的四件事

| # | 对象 | 冻结内容 | 依据 |
|---|---|---|---|
| F1 | 七态词表 | `VERIFIED / INVALID / REVOKED / EXPIRED / INCONCLUSIVE / UNSUPPORTED / UNRESOLVED`，集合与顺序不可增减 | `uibc_core/interop_result.py` 的 `STATES` |
| F2 | 结果文档结构 | `state / subject / evidence / detail` 为必填；`evidence[]` 必带 `id / type / issuer / digest`；`digest` 形如 `sha256:<hex>` | `schemas/verification-result.schema.json` |
| F3 | 证据前置条件 | `VERIFIED` 必须 ≥1 条证据；`REVOKED`/`EXPIRED` 必须写明原因；无"静默降级" | schema 的 `allOf[0]` 与 `result()` 的抛错分支 |
| F4 | `PASS` 的定义 | "在观察边界内未发现违规"，不是"安全"；全仓唯一原句 | `claims-register` A5 的 grep 门 |

## 二、允许改的（不触动哈希）

- 错误消息的措辞、`detail` 文本、文档、示例；
- 新增可选字段（如 `risk_context`）——但必须同时更新 schema 与 `states_document()`，此时 `schema-sha256` 会变；
- adapter 的具体实现、DID 方法的扩展（新增方法不改变七态语义）。

## 三、必须付出代价才能改的

| 变更 | 需要什么 |
|---|---|
| 增删一个状态，或改任一状态的**含义** | 线路格式升版（`SPEC_VERSION`），`CHANGELOG` 记 `BREAKING`，所有已封签包的 `spec_id()` 语境失效须公开说明 |
| 放宽 `VERIFIED` 的证据要求 | 不允许。若确需放宽，只能新增一个**更弱**的状态（例如 `VERIFIED-UNANCHORED`），而不是把 `VERIFIED` 稀释 |
| 改 `PASS` 的定义 | 不允许软化；只能新增判据并把旧定义保留为"更弱的一档" |

## 四、冻结的上限（这页不承诺什么）

- 冻结的是**我们自己的**语义，不是事实上的行业标准。外部实现可以不同意——不同意时，`COMPATIBILITY.md` 该出现第二行，而不是我们改语义去迎合。
- 冻结不覆盖检查集 S1–S19 的内部判据（那是更大的一次冻结，且现在有 3 项没有直接向量：S9/S16/S19）。
- 冻结不阻止撤回：如果发现某状态定义本身站不住，撤对比固守更诚实，代价是公开一次 `BREAKING`。

## 五、怎么验这一页是活的

```
python -m pytest -q tests/test_semantics_freeze.py     # 语义一变即红
python -m pytest -q tests/test_interop_result.py       # 14 条行为测试
```
