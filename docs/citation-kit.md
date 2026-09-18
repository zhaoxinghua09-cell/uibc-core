# Citation Kit — 怎么规范引用 UIBC 与 uibc-core

> 目的：**不给引用格式，别人想引也无从下手。** 本件是「被引用」的前提条件。
> 状态：v0（2026-09-18）｜ 配套：`CITATION.cff`（仓库根）· `CITATION.bib`（仓库根）
> 依据：v2.1 §三 机制 11「citation kit + 复现徽章」（对标 AML / ACM Artifact Evaluation）

---

## 1. 三种引用场景（先选对入口）

| 你用了什么 | 引用哪个条目 | BibTeX key |
|---|---|---|
| 工具链 / 规范 / 验证器 | uibc-core 软件 | `uibc_core_2026` |
| 赛事本身（命题、赛制、赛道体系） | UIBC 赛事 | `uibc_competition_2026` |
| 某个具体成绩 / 榜单快照 | 榜单快照（须填日期+契约版本） | `uibc_s1_leaderboard_2026` |

**榜单快照的强制填写项**：引用任何成绩，**必须**同时给出 `snapshot <date>` 与 `contract <version>`。原因：我们的评测契约是**版本化**的，换数据集/换管线/换评分规则都会升版本号——不写版本号的成绩引用是无效引用。

---

## 2. 作者与署名口径（引用时请照抄）

| 项 | 值 |
|---|---|
| 作者 | Zhao, Xinghua（Steven Zhao） |
| ORCID | https://orcid.org/0009-0001-0512-1237 |
| 归属 | **独立研究者个人项目**（personal agent-governance project） |
| 赛事本体署名 | `SynomosAI Governance Line` |
| 理论主张署名 | `Zhao, X.` + ORCID |

> ⚠️ **不写公司/机构**。本项目**不是注册法人实体**，引用时请勿表述为 organization / corporation / university。写 `"Independent researcher"` 或 `"personal project"` 即可。

---

## 3. 一键生成（不用手抄）

```bash
# GitHub 会自动读 CITATION.cff，仓库页右侧出现 "Cite this repository"
# 本地生成 APA / BibTeX / RIS：
cd uibc-core
pip install cffconvert            # 可选
cffconvert -f bibtex -o my.bib
cffconvert -f apalike -o my.txt
```

---

## 4. 复现徽章（三级 · 对标 ACM Artifact Evaluation）

论文 / 作品若引用了我们的结果，可按下表在 artifact 里标注徽章。**徽章由引用方自评，我们不认证**。

| 徽章 | 含义 | 判定条件 |
|---|---|---|
| 🟡 **Artifacts Available** | 可用 | 代码/数据已放到**长期可访问**的公开位置（有稳定 URL，非临时网盘） |
| 🟠 **Artifacts Evaluated** | 已审 | 第三方按仓库 README 步骤**成功跑通**，记录了环境与耗时 |
| 🟢 **Results Reproduced** | 已复现 | 第三方独立复现出**同一结论**（不要求逐位一致，要求结论一致并有证据记录） |

**用法（论文里怎么写）**：

```latex
This work uses \cite{uibc_core_2026}. Our artifact carries the
\textbf{Results Reproduced} badge: an independent party re-ran
\texttt{python -m unittest discover tests} and
\texttt{python independent\_verifier/cross\_check.py} on <date>
and obtained the same verdicts (see \S\,Reproduction).
```

---

## 5. 我们自己要做到的（否则没资格要别人引）

- [x] `CITATION.cff` 在仓库根（GitHub 自动识别）
- [x] `CITATION.bib` 提供三种场景
- [x] 测试一条命令可跑（零安装依赖）
- [x] Zenodo DOI 存证（v0.2.1 软件包：版本 DOI + 概念 DOI）→ 见 §7
- [x] 双实现交叉核验可作为"结论一致"的证据
- [ ] 榜单快照 DOI 存证（**待建** — 见 v2.1 机制 11）
- [ ] 每站榜单发布时同步给 `snapshot_date + contract_version`（**待建**）

---

## 6. 诚实边界（写给自己看）

1. 徽章是**引用方自评**，我们不做认证机构——避免任何"我们给别人发认证"的越界表述。
2. `CITATION.cff` 里的 `preferred-citation` 指向一篇**尚未发表**的竞赛论文；在它正式发布前，请引 `uibc_core_2026`。
3. 本 kit 不构成对外正式发布物；对外投放（官网 / Zenodo / arXiv）需 Steven 逐次点头。**（2026-09-18 更新：Zenodo 软件包 v0.2.1 经 Steven 明确授权已发布，DOI 见 §7；其余渠道仍须逐次点头。）**

---

## 7. Zenodo DOI 存证（v0.2.1 软件包 · 2026-09-18 发布）

uibc-core v0.2.1 的**固化发布包**已在 Zenodo 存证，得到一个**版本 DOI** 与一个**概念 DOI**。两者用途不同，引用时按需取用。

| 类型 | DOI | 解析地址 | 用途 |
|---|---|---|---|
| **版本 DOI**（本版） | `10.5281/zenodo.22821835` | https://doi.org/10.5281/zenodo.22821835 | **可重复性**：精确指向 v0.2.1 这一份 artifact。引用具体结果/复现时用它 |
| **概念 DOI**（全集） | `10.5281/zenodo.22821834` | https://doi.org/10.5281/zenodo.22821834 | **泛指"uibc-core 这个软件"**：始终解析到最新版本 |

**已存证的 artifact（本次唯一上传物，不含 git 源码树）**

| 项 | 值 |
|---|---|
| 文件名 | `uibc-core-0.2.1.zip` |
| SHA256 | `59cc1c917ff766af8f6528ceadfea522b8627a2c591e57334aa4afd2a07959f4` |
| MD5（Zenodo 侧核验） | `d8789c65a309e869977b0d74825a9b1e` |
| 大小 | 155,450 字节 |
| 记录页 | https://zenodo.org/records/22821835 |
| 元数据 | Open Access · Apache-2.0 · version 0.2.1 · publication_date 2026-09-18（注：初版记录曾误填 MIT，2026-09-18 已按专家核验通过 Zenodo API 修正为 Apache-2.0，与仓库 LICENSE 一致） |
| 关联标识 | `isSupplementTo` → https://github.com/zhaoxinghua09-cell/uibc-core |

**给引用者的建议**：正文写可点击的 `https://doi.org/...`；artifact 说明里**同时给出 SHA256**，第三方才能核验下载物与本文所述一致。

**BibTeX（Zenodo 条目）**

```bibtex
@misc{uibc_core_2026_zenodo,
  author       = {Zhao, Xinghua},
  title        = {uibc-core v0.2.1: verifiable evidence packages for
                  autonomous AI agents (PROPOSAL)},
  month        = sep,
  year         = 2026,
  publisher    = {Zenodo},
  version      = {0.2.1},
  doi          = {10.5281/zenodo.22821835},
  url          = {https://doi.org/10.5281/zenodo.22821835}
}
```

> ⚠️ 本件存档的是**固化发布包（zip）**，不是 git 源码树；源码以 GitHub 仓库为唯一真源（SSOT）。二者以上述 SHA256 对齐。

### 7.1 引用口径（SSOT — 多 DOI 并存的统一用法）

Zenodo 的机制是**一条记录天生两个 DOI**：概念 DOI（all versions）+ 每发布一个版本就多一个版本 DOI。这不是重复，无需合并、也无法删除。当前共 2 个号，全部有效：

| 场景 | 用哪个 | 原因 |
|---|---|---|
| **对外泛引**（知乎专栏、W3C/IETF 材料、社媒、简历、名片） | 概念 DOI `10.5281/zenodo.22821834` | 永指最新版，链接永不过期；发 v0.3/v1.0 后依然有效 |
| **学术精确引用 / 复现**（CITATION.cff、论文、issue 里的版本锚点） | 版本 DOI `10.5281/zenodo.22821835` + 注明 v0.2.1 | 精确钉住该 artifact；配合 SHA256 才可核验 |

**已落位的引用点一致性**：CITATION.cff（doi=版本 DOI + identifiers 概念 DOI ✅）、codemeta.json（citation 双条目：概念为主、版本为辅，2026-09-18 修正）、ENDORSEMENTS.md（概念 DOI 为主引用，2026-09-18 修正）。

**未来发布新版本的规则**：① 版本 DOI 会自动新增一个号，**无需宣传它**，只在 CHANGELOG 该版本条目下记录一行；② 概念 DOI 不变，对外一切引用**不跟随更新**；③ `citation-kit.md` 在表格中追加新版本 DOI 行即可，§7.1 的口径永不改。

---

*编制：2026-09-18 · 老二 🟡（代行 `uibc-race-ops` + `medxpert-standards-intel` 口径）*
