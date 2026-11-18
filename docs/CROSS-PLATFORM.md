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

所以本文只声称跑过这两套（并发与审计），**不声称 Windows 上全量 393 项都通过**——那需要完整包在 Windows 上重跑一次，本轮没做。

## 现在的边界表

| 项 | 状态 |
|---|---|
| Linux 全量 393 项 | **OK (skipped=14)** |
| Windows 并发 + 审计（8 项） | **OK**，msvcrt 分支已实走 |
| Windows 全量 393 项 | **未跑**（缺完整夹具，未声称） |
| macOS | **未跑** |
| 跨进程（同一机器） | 已测，200/200 |
| 跨机器 / 网络挂载 | 未测，且 flock 在部分 NFS 上不生效 |
