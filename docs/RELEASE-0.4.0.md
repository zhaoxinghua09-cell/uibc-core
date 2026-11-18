# 0.4.0 发布说明（可直接用于 GitHub Release 与 PyPI description）

## 一句话

**这是让十八项检查真正能被拿到的版本。** 之前发布的两份（Zenodo `0.2.1`、PyPI `0.3.3`）在同一个包上只报六项。

## 与 0.3.3 的差别（实测，不是估计）

| | `0.3.3` | `0.4.0` |
|---|---|---|
| 同一个全特性包，报出 | S1–S6（6 项） | S1–S18（17 项；S9 需外部 pin） |
| 审计器 / 套件 / 端点 / AAC 导出 | 无 | 有 |
| 测试 | — | 446 项，其中 16 项因环境缺依赖跳过 |

复算：

```
python3 tools/check_release_parity.py     # 三个渠道并排
python3 tools/preflight_release.py        # 安装后的包能报几项
```

## 装完先跑这个

```
pip install uibc-core==0.4.0
python -c "from uibc_core.verify import verify; \
r=verify('fixtures/clean.uibc'); \
print(r['result'], [c['id'] for c in r['checks']])"
```

出厂包是未签名的，正确结果是 `INCONCLUSIVE` 并列出已跑到的检查——**不是** `PASS`。

## 这是破坏性变更

本项目自定的规则：**任何改变「哪个包得到哪个判定」的改动都是破坏性变更**。多十二项检查必然改变判定，因此 0.4.0 是次版本跳跃，不是补丁。

## 仍未解决（照实写）

- **外部第三方独立验证：0。** 所有证据都由本项目自己产出。
- 端点仅绑定 `127.0.0.1`，未部署。
- 链尾收据正文被改，包内无物可发现（`V11_KNOWN_GAPS`）。
- macOS 未实测。

## 归档建议（给 Zenodo 的元数据草稿）

- **Title**：uibc-core 0.4.0: verifiable evidence packages for autonomous AI agents (eighteen checks)
- **Version**：0.4.0
- **Publication date**：2026-11-18
- **Related identifiers**：`isNewVersionOf 10.5281/zenodo.22821835`（0.2.1 那一条）
- **Keywords**：与 `CITATION.cff` 现有列表一致
- **Description**：以本文件前两节为底，删掉"发布说明"字样

> 归档前请先确认：仓库当前**没有任何 tag**，`0.2.1` 无法从 git 重建。这次请一并打 `v0.4.0`，让归档快照与 tag 一一对应。
