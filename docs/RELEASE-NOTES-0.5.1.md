# RELEASE NOTES · 0.5.1（提案，未发布）

> 状态：**本地已实现并通过全量测试（1247 passed / 26 skipped / 87 subtests）**，尚未推送、未发布 PyPI。
> 版本号建议 `0.5.1`（行为修正，非新特性；但对下游是破坏性变更，见下）。

## 修正

### 1. 三值结论：不再把"没查"报成"通过"（P1-1，安全相关）

- 旧：`verified = ... and sig_ok is not False` —— 缺 `cryptography` 或缺日志公钥时 `sig_ok=None`，
  于是 inclusion proof 一过，整份收据就是 `verified=True`、`exit 0`。
- 新：新增 `conclusion ∈ {verified, failed, inconclusive}`；`verified=True` **只**在签名真的验过时成立。
- 退出码：`0` verified / `1` failed / `3` inconclusive（见表 `docs/EXIT-CODES.md`）。
- 实测（同一份 `rekor_entry_2883389783.json`）：
  | 环境 | 旧 | 新 |
  |---|---|---|
  | 无 `cryptography`（`.venv_nocrypto`） | `verified=True, exit=0` | `verified=false, conclusion=inconclusive, exit=3` |
  | 有 `cryptography` 50.0.2 | `verified=True, exit=0` | `verified=true, exit=0`（不变） |

### 2. 测试契约随之修正

`tests/test_verify_rekor_inclusion.py` 中三处断言原先写死 `verified is True`（等于把 fail-open 固化进契约），
现改为断言 `conclusion == "inconclusive"` + `verified is False` + `_exit_for(out) == 3`。

### 3. 新增文档

- `docs/EXIT-CODES.md`：统一退出码契约（含"0 只能出现在真正执行过检查时"硬规则）
- `docs/SPEC-MUST-INDEX.md`：20 行含 MUST 的自动索引，其中 16 条编号为条款，4 条标为引用/评论
- `docs/BUS_FACTOR.md`：六维全 1 的现状 + 接手 1 天路径 + 30 天补漏清单
- `docs/LICENSE-DECISION.md`：代码 Apache-2.0 / 文本 CC BY 4.0 / 向量 CC0 的分层建议

## 对下游的影响（必须写进发布公告）

任何把 `exit 0` 当绿灯的流水线，升级后会从"静默通过"变成"明确阻塞（exit 3）"。这是**有意为之**：
原来的绿灯是假的。迁移方式：判定 `conclusion` 字段，或把 `exit 3` 映射为"人工复核"而不是"失败重试"。

## 未做（需单独批准）

- 未改 `CHANGELOG.md`（该文件是长文，合并方式需定）
- 未推送、未打 tag、未发布 PyPI
- 未处理 `benchmark/adapter.py` 等其余 4 处类似的 `verified=True` 语义（需逐一评估，不在本次范围）
