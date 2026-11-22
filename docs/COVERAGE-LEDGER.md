# 统一覆盖账本（`docs/coverage-ledger.json`）

一句话：**把"我们没测什么"写成一串可以被 diff、被 CI 拦的字段，而不是一段散文。**

`FIELD-COVERAGE.md` 与 `KNOWN-LIMITS.md` 已经写得很诚实，但它们是 markdown 散文。散文有三个弱点：改了一行看不出影响、两个地方会各写一套数字、外部无法机械比对。这份账本把它们与 `coverage/` 下的逐检查账本合成一份 JSON，并把**所有数字从源材料解析后重算比对**。

## 怎么用

```bash
python tools/build_coverage_ledger.py --build   # 重新生成 docs/coverage-ledger.json
python tools/build_coverage_ledger.py --check   # 只校验（CI / 提交前）
```

当前实测（`--build` 与 `--check` 两次一致，rc=0）：

```
OK cdl checks=20 exercised=19 untested=1 exempt=0 not_public=0 disclosure=0.95
   fields=36/59 known_limits=8 peers=3
   peer_disclosure={self:0.95, aac:0.6667, eqr:0.5714, asqav:0.5714}
```

## 五条硬规则（任一不满足即 exit 1）

1. `schema` 固定为 `coverage-ledger/1`，`checks` 不得为空，`id` 不得重复。
2. 状态只能是 `EXERCISED / UNTESTED / EXEMPT / NOT_PUBLIC`；**`UNTESTED` 必须带 `owner` 与 `review_by`，`EXEMPT` 必须带 `reason`** —— 不允许留一个没有责任人的坑。
3. 字段覆盖必须自洽：`probed = moved + silent`，且三个数从 `FIELD-COVERAGE.md` 现解析。
4. `known_limits` 不少于 8 条，每条必须有处置。
5. 对手账本必须三家齐全；`summary` 的每个数字都用明细**重算**比对（手改 summary 会被抓）。

## 口径，别混用

| 口径 | 算式 | 当前值 |
|---|---|---|
| `disclosure_ratio` | `exercised / total` | **0.95**（19/20） |
| `named_gap_ratio`（CDP-1 原文口径） | 缺口是否全部具名 | **1.0**（20/20） |

两个数不能混着说成"披露率 100%"。

## 已知的边界

- 这份账本描述的是**验证覆盖**（我们测了什么、没测什么），不是**锚定等级**（证据有多硬）。后者是另一件事，不要互相替代。
- `coverage/peers/*.cdp.json` 里的对手条目是**按公开材料判定**，不是对手自述，也不是我们代他们声明。
- 生成时间戳每次 `--build` 都会变。若要让 diff 干净，CI 里只跑 `--check`（不重写文件）。

## CI 接线（未做，留作下一步）

仓库 CI 目前由 `actions.lock` 与 release-integrity 一类门禁管理，新增工作流会牵扯可复用 workflow 的 pin。因此本 PR **没有**加 workflow 文件，只在文档里写明一行命令：

```yaml
- run: python tools/build_coverage_ledger.py --check
```

把这行接到现有 `ci.yml` 的合适 job 里，是后续独立一步，需要与维护 CI 的线协调。
