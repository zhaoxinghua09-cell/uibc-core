# EXIT-CODES · 退出码与结论对照表（v0.5.1 提案）

> 背景：工具族此前各自定义退出码（LGD-Eval 用 2 表示"对象不成立"，uibc 校验器在缺依赖时用 0 表示"通过"）。
> 同一个生态里两个工具对"没验成"给出相反的退出码，下游无法自动化处理。
> 本表是**统一契约**，两个实现都必须遵守；违反本表的实现不得声称符合本规范。

## 一、四个结论，六个退出码

| 退出码 | 结论 | 含义 | 是否可自动化放行 |
|---|---|---|---|
| `0` | **VERIFIED** | 声明的检查项全部真正执行且全部通过 | 是（仅在声明范围内） |
| `1` | **FAILED** | 至少一项检查确实不通过（含伪造签名、折叠不符） | 否 |
| `2` | **INVALID_INPUT** | 对象不成立：路径不存在、缺 SKILL.md/收据结构、参数矛盾 | 否（重跑无意义，需换输入） |
| `3` | **INCONCLUSIVE** | 无法判定：缺依赖、缺公钥、证据不足、无可执行面 | 否（**必须人看**） |
| `4` | **EXPIRED** | 结论已过期（超出 `valid_until`） | 否 |
| `5` | **REVOKED** | 结论已被撤销 | 否 |
| `6` | **ERROR** | 工具自身异常（未捕获异常、内部不一致） | 否（视为工具缺陷） |

**唯一硬规则**：`0` 只能出现在"检查真的执行过"的情况下。
"没查"（依赖缺失、公钥缺失、目标无内容）必须是 `3`，绝不允许 `0`。

## 二、机器可读块（stdout 末行或 `--json` 字段）

```json
{"conclusion": "verified|failed|invalid_input|inconclusive|expired|revoked|error",
 "exit": 0,
 "reason": "短句，给下游日志用",
 "coverage": {"checked": ["S1", "..."], "not_checked": ["..."]},
 "engine_version": "0.5.1"}
```

## 三、两个实现的落点

| 实现 | 位置 | 当前状态 |
|---|---|---|
| `tools/verify_rekor_inclusion.py` | `conclusion` + `_exit_for()` | 已改为三值（0/1/3），实测通过 |
| `ls/scripts/evaluate.py`（LGD-Eval） | `sys.exit(2)` for INVALID_SUBJECT / no_executable_surface | 已改（2），评分不因"没内容"给出分数 |

## 四、兼容性说明（必须随发布写进 CHANGELOG）

- 旧行为：缺 `cryptography` 时 `verified=True, exit=0`；
- 新行为：`verified=False, conclusion="inconclusive", exit=3`；
- **这是对下游的破坏性变更**：任何把 `exit 0` 当绿灯的流水线，会在升级后从"静默通过"变成"明确阻塞"。这是有意为之。
- 迁移建议：下游改为判定 `conclusion` 字段而非退出码；若必须用退出码，把 `3` 当"人工复核"，不要当失败重试。

## 五、测试要求

| 用例 | 期望 |
|---|---|
| 有公钥 + 签名合法 | 0 / verified |
| 伪造签名 | 1 / failed |
| 折叠不符 | 1 / failed |
| 无公钥 | 3 / inconclusive |
| 缺 `cryptography` | 3 / inconclusive |
| 路径不存在 | 2 / invalid_input |
| 空目录（LGD-Eval） | 2 / invalid_subject |
| 只有文档无可执行面 | 3 / inconclusive |
