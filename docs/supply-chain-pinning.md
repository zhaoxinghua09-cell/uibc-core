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

本仓原先用 `gh-actions-lock` 维护 `.github/workflows/actions.lock`（lockfile version `v0.0.3`），共享 CI（`LGD-AI/lgd-ci` 可复用工作流，`verify-lockfile` 默认 `true`）在流水线里跑 `gh actions-lock --verify`。两套机制不兼容，实测三条证据：

1. `gh actions-lock --verify` 对 SHA 钉法报 `✗ Not pinned actions/checkout@<sha> ... used in workflow but not pinned in lockfile` —— 它按"字面 ref 与锁条目一一对应"比对，而锁条目只允许 `OWNER/REPO@REF`。
2. 在临时副本上把工作流改回 SHA 后运行 `gh actions-lock`（不带 `--verify`），工具把全部 `@<sha> # vX` **改写回 `@vX`**（`Pinned 0 actions`）——即该工具把 SHA 钉法视为需要"修复"的偏差，跑一次就是一次降级。
3. 锁文件不接受子路径键：手写 `'github/codeql-action/init@<sha>':` 报 `dependency key ... is not a valid pin (expected OWNER/REPO@REF)`；只用 `OWNER/REPO@<sha>` 又无法与 `codeql-action/init@<sha>`、`/analyze@<sha>` 两处 `uses:` 对齐。

## 处置

取更强的一侧：**保留 SHA 钉版，关闭锁文件校验**。

- `.github/workflows/lgd-ci.yml` 传 `verify-lockfile: false`（该输入由可复用工作流声明、默认 `true`，属调用方可配置项，不需要改上游仓）。
- `.github/workflows/actions.lock` 加 SUPERSEDED 注记后保留：它的 tag→commit 对照仍有参考价值，但不再被校验，也不再被信任。
- 钉版表落在本文件，任何人可用 `git ls-remote`/GitHub API 复算。

## 残余风险（如实记录）

- 关掉的是一条**已经在跑的**校验。SHA 钉版严格强于"tag + 锁文件记录"：tag 可被上游移动，锁文件的保护来自 diff 可见性，而 SHA 钉版直接消除可变引用；但本仓现在少了一道自动化比对，**新增工作流若忘了钉 SHA，没有门禁会拦**。这是本次处置的真实代价，已在此写明，不做美化。
- 该关闭只作用于本仓；其他仓若继续用 tag + 锁文件，仍会被共享 CI 校验。
- 上级是共享可复用工作流（`LGD-AI/lgd-ci`），若要根治，正解是在上游支持 `OWNER/REPO@SHA` 与子路径键，或把锁文件模型换成"钉 SHA 即合规"。本仓无法单方面改上游，故此处只做本仓范围的最小处置。
