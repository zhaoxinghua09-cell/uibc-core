# Install

Verified 2026-11-17. Package name `uibc-core`, version 0.3.3, no runtime dependencies beyond the standard library.

## Support matrix

| OS | Python | Status |
|---|---|---|
Windows 11 + PowerShell 7 | 3.13.12 | verified (demo + verify executed) |
Linux / macOS | ≥ 3.10 | expected, **not** executed in this verification |

Python 3.10 is the declared floor (`requires-python = ">=3.10"`). Nothing above it is tested by us yet — treat 3.13 as verified and 3.10–3.12 as declared.

## Path A — no install (recommended for a first look)

```bash
git clone https://github.com/zhaoxinghua09-cell/uibc-core.git
cd uibc-core
export PYTHONPATH="$PWD"
python -m uibc_core.cli demo
```

Nothing is written outside a temporary directory, and no network call is made.

## Path B — editable install (for development)

```bash
pip install -e .
uibc --help
```

Installs three console scripts: `uibc`, `uibc-mcp`, `uibc-core`.

## Path C — from PyPI

```bash
pip install uibc-core
```

Availability verified on 2026-11-17 with `pip download uibc-core --no-deps` (download succeeded). We have not exercised a full fresh-environment install in this verification; if it fails on your platform, Path A always works.

## Offline operation

The tool performs no network I/O: keys are generated locally, seals are verified locally, and `verify` accepts a package directory plus an optional pinned public key. If any command attempts a network call, that is a defect — report it.

## Uninstall

```bash
pip uninstall uibc-core
```

Path A leaves nothing to uninstall; delete the checkout.

## Common failures

| Symptom | Cause | Fix |
|---|---|---|
`ImportError: attempted relative import with no known parent package` | Ran `python uibc_core/cli.py` directly | Use `python -m uibc_core.cli`, or the `uibc` script |
`verify` exits non-zero but the report looks fine | Exit code collapses FAIL and INCONCLUSIVE | Read the report; INCONCLUSIVE means a check could not be resolved |
Step 7 of `demo` prints PASS with a foreign key | Expected — an unpinned seal verifies against itself | Pin the owner's `.pub` (`--pubkey`) |
`PASS` where you expected `FAIL` | You are verifying a forged package without `--pubkey` | Add the pinned public key |

---

# 安装

2026-11-17 实测。包名 `uibc-core`，版本 0.3.3，除标准库外无运行时依赖。

## 支持矩阵

| 系统 | Python | 状态 |
|---|---|---|
Windows 11 + PowerShell 7 | 3.13.12 | **已实测**（demo 与 verify 均跑通） |
Linux / macOS | ≥ 3.10 | 预期可用，**本次未实测** |

## 路径 A — 不安装（首次试用推荐）

```powershell
git clone https://github.com/zhaoxinghua09-cell/uibc-core.git
cd uibc-core
$env:PYTHONPATH = (Get-Location)
python -m uibc_core.cli demo
```

除临时目录外不写任何位置，不发起网络请求。

## 路径 B — 可编辑安装（开发用）

```bash
pip install -e .
uibc --help
```

装三个命令：`uibc`、`uibc-mcp`、`uibc-core`。

## 路径 C — 从 PyPI 安装

```bash
pip install uibc-core
```

2026-11-17 用 `pip download uibc-core --no-deps` 核实可获取（下载成功）。本次**未**在全新环境中完整走一遍安装；若你的平台失败，路径 A 始终可用。

## 离线运行

工具不做任何网络 I/O：钥匙本地生成、封签本地验证、`verify` 只需包目录与可选的钉住公钥。若任何命令尝试联网，即为缺陷，请报 issue。

## 卸载

```bash
pip uninstall uibc-core
```

路径 A 无需卸载，删目录即可。

## 常见失败

| 症状 | 原因 | 处置 |
|---|---|---|
`attempted relative import with no known parent package` | 直接跑了 `python uibc_core/cli.py` | 改用 `python -m uibc_core.cli` 或 `uibc` |
`verify` 非 0 退出但报告看起来正常 | 退出码把 FAIL 与 INCONCLUSIVE 合并了 | 读报告；INCONCLUSIVE 表示某项检查未能解决 |
demo 第 7 步用外来钥匙仍 PASS | 符合预期：未钉住的封签对自己有效 | 用 `--pubkey` 钉住所有者公钥 |
期待 `FAIL` 却得到 `PASS` | 验证伪造包时没加 `--pubkey` | 加上钉住公钥 |
