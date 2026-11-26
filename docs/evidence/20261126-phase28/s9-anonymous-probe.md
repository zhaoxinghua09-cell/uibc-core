# S9 我方 GitHub 物件 · 匿名全量实测（2026-11-26，家机）

> 目的：把 `_141` 派给 Muse 的八项判据里**可以客观化**的部分，我方先匿名跑一遍，给出"任何人跑结果一样"的事实。
> 边界：**我方匿名跑 ≠ 外人主导跑**。本件能把 S9 从"未过"推到"客观项已自证"，不能替代 Muse 回执。

## 现场事实（全部可复跑，不带任何凭据）

| 项 | 结果 |
|---|---|
| main 头 | `87bf268f4e42a536f34c99efcd7bc9ffffa4d8cf`（匿名 `git ls-remote refs/heads/main`） |
| 仓库可见性 | 匿名可读；API `private=false`，`full_name=zhaoxinghua09-cell/uibc-core` |
| 双通道 | 8 个物件 × 2 条通道（`raw.githubusercontent.com/{sha}/…` 与 `cdn.jsdelivr.net/gh/…@{sha}/…`）**全部 200 且字节一致**（sha256 相等） |
| raw 稳定性 | 首轮 8 个里 4 个 `curl: (56) Recv failure: Connection was reset`，**重试第 1 次即 200**；记"可用但不稳"，不记不可达 |
| 干净 clone | 匿名（`-c credential.helper=`）`clone --depth 1`，**42 s，2,460 文件，rc=0**，HEAD=`87bf268f` |
| 一条命令 | `python tools/outsider_rerun.py --check` → **rc=0**，输出 `OUTSIDER OK: receipt matches this disk (2456 files, 033a0d0aee76, content f4ceea43f8bd), 4 steps passed`，13 s |
| CI 矩阵 | 匿名读 `/commits/{sha}/check-runs`：**25 项，24 success / 1 skipped / 0 failure** |
| CI 覆盖面 | `test (3.10) (3.11) (3.12) (3.13)`、`test-macos`、`test-with-extras`、`windows-clone-bytes`、`windows-probes`、`build-and-attest`、`codeql`、`Scorecard`、`zizmor`、`sdist-self-check`、`second-implementation`、`crosswalk-gate` 等 |
| 匿名读回 PR | `#503 merged=true, merge_commit=939cc2e`；`#525 merged=true, merge_commit=c11e2ad` |
| PR reviewer | `pulls/503/reviews = 0`、`issues/503/comments = 0`（管理员 squash，**无 reviewer 批准**） |
| release | 现有 5 个，最新 `v0.5.5`；**本轮没有 Phase 28 的 release 或 tag** |

## 八项判据逐条

| # | 判据 | 判定 | 依据 |
|---|---|---|---|
| 1 | 匿名 `git ls-remote` 判公私 | **过** | 匿名成功返回 main sha |
| 2 | 双通道命中该版本独有标记、禁用 `@main` | **过** | 8/8 均用 commit sha，raw 与 jsdelivr 字节一致 |
| 3 | 干净 clone 一条命令 rc=0 且逐字节相同 | **过** | 匿名 clone + `--check` rc=0，"receipt matches this disk" |
| 4 | CI 写到平台 × Python 版本矩阵 | **过** | 4 个 Python 版本 + macOS + extras + Windows 专项 |
| 5 | 评论 / issue 匿名读回 | **过（内容为 0）** | 可读；内容 0 条，属事实而非缺陷 |
| 6 | 每个物件 `checked` 分母 | **过** | 8 物件 × 2 通道 = 16 次，16/16 一致 |
| 7 | **由外人主导执行并出回执** | **未过** | 本件是我方代跑；`_140`/`_141` 的回执未到 |
| 8 | 回执形态过 `check_muse_return.py` | **N/A** | 无回执可校验 |

**结论：`S9 = 部分过（客观六项已自证，缺"外人主导"这一项）。`** 不许写成 S9 过。

## 顺带校准出的两条不利事实（要一起引用）

1. **PR #503/#525 均无 reviewer**：`reviews=0`、`comments=0`，合并是管理员直接 squash。这写进 S8 的"对手视角"和"流程视角"两张图里，不藏。
2. **没有发 release / tag**：最新 release 停在 `v0.5.5`。所以"release note 已补齐"指的是 `CHANGELOG.md` 进了 main，**不是**打了一个 release。

## 与旧记录的数字差异（必须替换）

| 项 | 旧记录（11-26 早） | 现场（`87bf268`） |
|---|---|---|
| 文件数 | 2453 | **2456** |
| tree | `7ecf1f4096ad` | **`033a0d0aee76`** |
| content | `300ee671e019` | **`f4ceea43f8bd`** |
| 收据体积 | 305 KB | **2,097 B**（`files_manifest` 指向 `docs/OUTSIDER-FILES.txt`，2456 条） |
| CI | 24 success / 1 skipped | **25 项：24 / 1 / 0** |

引用旧数字的地方（报告 29.3、收尾卡、自检）以本件为准。

## 复跑命令

```powershell
$git='C:\Users\Administrator\.local\bin\git.cmd'
& $git -c credential.helper= ls-remote https://github.com/zhaoxinghua09-cell/uibc-core.git refs/heads/main
& $git -c credential.helper= clone --depth 1 https://github.com/zhaoxinghua09-cell/uibc-core.git D:\tmp\s9_clone
cd D:\tmp\s9_clone ; python tools/outsider_rerun.py --check
```
