# NOTICE — 权属与许可分层

Copyright (c) 2026 Xinghua Zhao (Steven Zhao) · ORCID 0009-0001-0512-1237

许可按**路径**分层，**以文件为准，不以叙述为准**：

| 内容 | 路径 | 许可 |
|---|---|---|
| 代码与脚本 | `**/*.py`、`tools/**`、`adapters/**`、`conformance/*.py` | **Apache-2.0**（见 `LICENSE`） |
| 规范文本与方法论文本 | `spec/**`、`docs/**`、`paper/**`、根目录 `*.md` | **CC BY 4.0**（见 `LICENSE-TEXT`） |
| 数据与夹具 | `conformance/**/*.json`、`fixtures/**` | **CC BY 4.0**（随文本） |
| 品牌名称与标识 | 全仓 | **不随任何许可授予**（见 `TRADEMARK.md`） |

本仓库**不再声明"保留所有权利"**。若某文件未落入上表任一路径，视为 Apache-2.0，并欢迎开 issue 指出。

许可变更的门槛写死在 `GOVERNANCE.md §1`（已发布版本不变、新版本 30 天公示 + 全贡献者书面同意）。

---

## 品牌与名称状态

- MedXpert、SynomosAI、LGD 为相关项目标识，**均未申请实体注册、未申请商标注册**；其出现仅作来源标识，不构成对法人实体或商标权的声明。
- 内容基于公开官方信息整理，不构成法规意见或注册代理服务；关键数据以监管机构最新发布为准。

---

## 权属宣告统一块（照《LGD 对外表述规范》v1.2 §3.2 · 整体复制，不得删改）

```
© 2026 Xinghua Zhao (Steven Zhao) · ORCID 0009-0001-0512-1237
理论署名 (attribution) : LGD（Lifecycle Governance Doctrine / 全程治理论）— SynomosAI initiative
名称状态 (name status)  : "SynomosAI" / "MedXpert" — 未申请实体注册、未申请商标注册
                        (not a registered legal entity; no trademark registered)
生产参考部署 (production reference, self-reported) : MedXpert
                    ← 非认证、非背书、非监管认可（not a certification or endorsement）
代码许可 (code license) : uibc-core = Apache-2.0 (see LICENSE)
文本许可 (text license) : spec/docs/paper/root *.md = CC BY 4.0 (see LICENSE-TEXT)
商标 (trademark)        : 不随许可授予 (see TRADEMARK.md)
引用格式 (cite as)      : uibc-core/CITATION.cff · concept DOI 10.5281/zenodo.22456647
首次公开锚 (first public): 2026-09-17 13:31:45 UTC (commit cb6f11b)
                    外锚 (external anchor): Sigstore Rekor logIndex 2883389783
```

> 统一块中的 DOI 与 commit 是首次公开时的历史记录，**不随每次发版重写**；当前版本号以 `pyproject.toml` 与 Zenodo 版本 DOI 为准。
