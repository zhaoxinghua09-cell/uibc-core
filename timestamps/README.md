# timestamps/ — 时间锚留档（**已停用** · Historical archive）

> ⛔ **本目录不得作为"已验证存证"对外引用。**
>
> 2026-09-26 复核判定：本目录留存的时间戳证明文件**不构成有效的 OpenTimestamps 时间锚**
> （四判据：无 OTS magic、不内嵌工件摘要、日历回执不可复算、无第三方独立验证），
> 因此**已停止作为存证对外引用**。
>
> `.ots` 证明文件**不构成有效锚**，仅保留供审计复核；据其声称"时间证明"或不早于某区块时间的
> 存在性**属无效主张**。

## 本仓**有效**存证锚（可独立复算）

| 锚 | 值 | 复核方式 |
|---|---|---|
| Sigstore Rekor 透明日志 | `logIndex 2883389783` | `dist/uibc-core-0.2.1.zip.cosign.bundle` + `cosign verify-blob` |
| Zenodo DOI | 概念 `10.5281/zenodo.22821834` | 见 `CITATION.cff`；`https://doi.org/10.5281/zenodo.22821834` |
| Software Heritage | 见 `CITATION.cff` 的 `identifiers` | SWHID 格式标准见 ISO/IEC 18670 |

## 留档文件（均**不构成有效锚**，不得引用为证据）

- `uibc-core-0.2.1.zip.sha256` — v0.2.1 发布件的 SHA256 校验值（值见文件本体）
- `uibc-core-0.2.1.zip.ots` — 已停用的时间戳证明文件，**不构成有效锚**，仅审计留档

> 原"本目录可复算时间证明"的表述（含证明文件升级为区块见证、第三方无需信任本方即可核验等说法）
> **已撤回**；原始文本保留于 git 历史，以便复核撤回范围。
