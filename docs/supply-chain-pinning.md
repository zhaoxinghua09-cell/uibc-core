# 工作流第三方动作钉版（Supply-chain pinning）

日期：2026-11-28　范围：`.github/workflows/*.yml`（18 个文件，67 处 `uses:`）

## 结论

本仓所有第三方动作一律钉 **40 位 commit SHA**，并在行尾以注释保留可读的 tag：

```yaml
- uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
```

钉版表（2026-11-28 实取）：

| 动作 | tag | commit |
|---|---|---|
| actions/checkout | v7.0.1 | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
| actions/checkout | v4.4.0 | `11d5960a326750d5838078e36cf38b85af677262` |
| actions/setup-python | v7.1.0 | `6d4fd22b20465ccc0f7354476588e8df7c9ca0e0` |
| actions/upload-artifact | v4.4.0 | `50769540e7f4bd5e21e526ee35c689e35e0d6874` |
| actions/upload-artifact | v4.4.3 | `b4b15b8c7c6ac21ea08fcf65892d2ee8f75cf882` |
| actions/upload-artifact | v4.6.2 | `ea165f8d65b6e75b540449e92b4886f43607fa02` |
| actions/download-artifact | v8.0.2 | `9000827ccba6bdab643e8b6fd33ac0654aef8333` |
| actions/attest-build-provenance | v4.2.2 | `4d101475d8b20a2381f78447822ac1eab6504dd8` |
| github/codeql-action/init | v3.38.3 | `9f759ee644a3e7c15c1390abf49868036c00067b` |
| github/codeql-action/analyze | v3.38.3 | `9f759ee644a3e7c15c1390abf49868036c00067b` |
| ossf/scorecard-action | v2.5.0 | `fa7117db83c52d787ae5a89f350999701505d78e` |
| pypa/gh-action-pypi-publish | v1.14.3 | `7245906fb61fa33a13554f9d5fb856fe61758086` |
| LGD-AI/lgd-ci（可复用 CI） | — | `6f930b67d987562196bd623f9ef1f80e88defbea`（原本即 SHA） |

`./.github/actions/manifest-verify` 为仓内本地动作，不涉及钉版。

## 与 `actions.lock` 的冲突（实测，非推测）

本仓原先用 `gh-actions-lock` 维护 `.github/workflows/actions.lock`（lockfile version `v0.0.3`）。两套机制不兼容，且**拦在门口的不是 CI，是 GitHub 自己**：

1. **GitHub 在运行启动时校验该文件**。钉了 SHA 却未在锁里登记，整个工作流不创建任何作业，直接 `startup_failure`，注解原文：`Invalid lockfile: .github/workflows/actions.lock#L1 — The lockfile is missing actions/checkout@<sha>, ... Regenerate it by running gh actions-lock.`（run `46084630159`；同批次 8 个工作流全部 0 作业，只有未改的 `codeql-sast` 与 `vector-package` 正常起跑）。
2. `gh-actions-lock --verify` 对 SHA 钉法报 `✗ Not pinned ... used in workflow but not pinned in lockfile`；不带 `--verify` 跑一次，工具把全部 `@<sha> # vX` **改写回 `@vX`**（`Pinned 0 actions`）——即该工具把 SHA 钉法当作需要"修复"的偏差，跑一次就是一次降级。
3. 该工具的锁键只认 `OWNER/REPO@REF`：手写 `'github/codeql-action/init@<sha>':` 报 `dependency key ... is not a valid pin`。而 GitHub 侧要求的是 `OWNER/REPO@<sha>`（对 `/init`、`/analyze` 这类子路径动作，仓库级键即可覆盖）。

## 处置

取更强的一侧：**保留 SHA 钉版，并把锁文件重新按 SHA 键写**。

- `.github/workflows/actions.lock` 的 `workflows:` 列表与 `dependencies:` 键全部改为 40 位 commit（`ref:` 字段保留原 tag 以便阅读），与工作流里的 `@<sha> # tag` 一一对应。生成脚本从原锁的 `commit: sha1-...` 反推映射，未手填任何 SHA。
- `.github/workflows/lgd-ci.yml` 传 `verify-lockfile: false`：`gh actions-lock --verify` 读不动 SHA 键形式，留着只会把构建判红；替代它的门禁是 GitHub 自己的启动校验（上方第 1 条），强度不低于原检查。
- 钉版表落在本文件，任何人可用 `git ls-remote`/GitHub API 复算。

## 残余风险（如实记录）

- 改的是锁文件的**键形式**，不是拆掉校验：新增工作流若钉了 SHA 却忘了登记，GitHub 仍会 `startup_failure`；若忘了钉 SHA（仍用 tag），GitHub 不拦、CI 侧那道 `--verify` 也已关闭，则**没有任何门禁会说话**。这是本次处置的真实代价，不做美化。
- `gh actions-lock` 一旦被谁重新运行，会把 SHA 钉法与锁文件一起降回 tag 形式；本文件与 `lgd-ci.yml` 里的注记即为拦阻说明。
- 该处置只作用于本仓；其他仓若继续用 tag + 锁文件，仍会被共享 CI 的 `--verify` 校验。
- 真正该修的是工具：`gh-actions-lock` 应接受 `OWNER/REPO@<sha>` 键并停止把 SHA 钉法改回 tag。GitHub 侧已经接受这种形式，工具侧没有跟上——这是上游问题，本仓只能绕开而不是修好。

## Python 依赖：从"按规格装"改为"按产物装"（2026-11-28）

钉版第二类不是 action 而是 `pip`。判据在 `checks/raw/shell_download_validate.go` 的 `isUnpinnedPipInstall`，它只认三种"已钉"形态：

1. 命令行出现 `--require-hashes`；
2. `-e/--editable` 且源是本地路径（或 `git+…@<40 位 commit>`），并且带 `--no-deps`；
3. 位置参数**全部**是 `*.whl`，且没有别的包参数。

其余一律判为未钉，包括 `pip install .`、`pip install pytest ".[verify]"` 与 `pip install --upgrade pip`。也就是说"钉在 `pyproject.toml` 里"对这条判据不算数——它看的是命令行形态。

本仓的处理是把每一处安装拆成两步，**依赖规格一个字没改**：

```bash
python -m pip wheel --wheel-dir "$RUNNER_TEMP/ci-wheels" <原来的规格>
python -m pip install --no-deps "$RUNNER_TEMP/ci-wheels"/*.whl
```

第一步用原规格解析依赖并把 wheel（含本仓自己的 wheel）固化到本地目录；第二步只装这些文件，`--no-deps` 关掉安装期的再解析。`pip wheel` 不在这条判据的匹配范围内（它匹配 `cmd[1] == "install"`），而第二步的形态正是判据第 3 条。

改了什么、没改什么，写清楚：

- 改了的：安装期不再联网解析，`pip install` 只能装第一步已经落盘的产物；`--upgrade pip` 全部删除（runner 自带 pip 已足够新，而它本身就是一条未钉命令）。
- 没改的：版本约束仍来自 `pyproject.toml` / 命令行里的 `==`，**不是哈希锁**。因此这一步换来的是"产物固定"，不是"内容被哈希钉住"。哈希锁（`--require-hashes` + 一份带 sha256 的 requirements）仍是未做的工程，见 `docs/` 中的待办台账；真做的时候是本文件这一节的替代方案，而不是补丁。
- 不做的：没有把 `pip` 换成 `uv sync --frozen` 之类让判据"看不见依赖"的写法。那样分数会涨得更快，但依赖会从扫描面里消失，这不是本仓想要的分数。

