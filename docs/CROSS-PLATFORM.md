# 跨平台实测：Windows 上真的跑了一遍

`2026-11-18`｜Python 3.13.18 / win32（DESKTOP-IGJBTUB，Windows 11 桌面）

---

## 之前写的是"Windows 分支未实跑"

`docs/CONCURRENCY.md` 里有一句诚实的边界：`msvcrt.locking` 的代码路径在库里，但所有实测都在 Linux 上，不能算"已验证"。

这次补上：把仓库打成包，传到**这台真实的 Windows 桌面**上解压、跑。

## 结果

| 项目 | 结果 |
|---|---|
| 解释器 | Python **3.13.18**，`sys.platform=win32` |
| 锁分支判定 | `fcntl: False`，**`msvcrt: True`** ← 确实走的是 Windows 分支 |
| `test_concurrency_and_build` | **2 tests OK**（8 线程 200/200，`register` 回填 manifest） |
| `test_outsider_audit` | **6 tests OK**（11 条攻击全抓，2 条对照不误判） |

也就是说：**并发不丢证据这件事，在 Windows 上成立**，不是只在 Linux 上成立。`msvcrt.locking` 那条路径不再只是"代码在库里"。

## 顺带抓到一个 Windows 特有的问题

跑测试时日志里出现：

```
ResourceWarning: unclosed file <_io.BufferedReader name='...\evidence\index.json'>
  raw = open(path, "rb").read()
```

`verify.py` 里有**两处裸 `open().read()`**（S11 严格序列化读原始字节、S13 Merkle 叶哈希）。在 Linux 上这没后果——Linux 允许删除已打开的文件。**在 Windows 上不是**：未关闭的句柄会占住文件，后续删除或替换可能失败。

已改成 `with open(...)`。这个修复在 Linux 上无法证明其价值（Linux 容忍这种行为），它的意义只存在于 Windows——**这也是为什么必须真的在 Windows 上跑一遍，而不是推断"应该没问题"**。

## 同时也暴露了我打包的不完整

第一次只打了 `uibc_core/adapters/tests/fixtures/tools`，Windows 上全量跑出 22 ERROR + 4 FAIL，追下去全是缺 `benchmark/corpus/base`、`docs/conformance/vectors.json` 这类路径——**测试跑到一半找不到夹具**，不是产品缺陷。

所以第一次只声称跑过那两套。

## 补跑：完整包全量

把 `benchmark/`、`docs/`、`pyproject.toml` 和根目录文件全部打进包（843 个文件、1.0 MB），在 Windows 上重跑：

```
Ran 393 tests in 48.234s

OK (skipped=15)
```

**Windows 全量 393 项通过。** Linux 是 `skipped=14`，差的那 1 项是：

```
test_evidence_symlink_outside_the_package_fails_s4
  skipped 'this platform does not allow creating symlinks'
```

Windows 默认不给普通用户创建符号链接的特权，所以 S4 那一格被跳过了——**不是失败，但是也没被测到**。

## 用 junction 把那格补上

Windows 有另一种目录链接：**junction（目录联接）**，普通用户就能创建，不需要开发者模式。

做法：复制干净包，把 `evidence/files` 整个移动到包外，再用 `cmd /c mklink /J` 在原来的位置建一个目录联接指向它——文件字节完全相同，只有"它其实在包外"这一点不同。

结果：

| 检查 | 结果 |
|---|---|
| junction 创建 | 成功（exit 0，无特权） |
| `os.path.islink()` | **False** ← 它看不见 junction |
| `os.path.realpath()` | 正确解析到包外 |
| **S4** | **FAIL**：`2 entries checked; evidence file 'files/action-log.txt' resolves outside the evidence root` |

这一格值得单独记下来：**如果 S4 用 `islink()` 来判断，Windows 上的 junction 会完全绕过它**。它没绕过，是因为 S4 判的是 `realpath` 是否落在证据根之内——判"最终落在哪"，而不是"看起来像不像链接"。

`islink() == False` 而 `realpath()` 指向包外，这个组合就是为什么"判解析结果"比"判链接类型"更可靠。

## 现在的边界表

| 项 | 状态 |
|---|---|
| Linux 全量 393 项 | **OK (skipped=14)** |
| Windows 并发 + 审计（8 项） | **OK**，msvcrt 分支已实走 |
| Windows 全量 393 项 | **OK (skipped=15)**，完整包实测 |
| Windows S4 目录联接（junction）逃逸 | **已测**，S4 FAIL 抓住（`islink=False` 仍被抓） |
| macOS | **未跑** |
| 跨进程（同一机器） | 已测，200/200 |
| 跨机器 / 网络挂载 | 未测，且 flock 在部分 NFS 上不生效 |
