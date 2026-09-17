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
- [x] 双实现交叉核验可作为"结论一致"的证据
- [ ] 榜单快照 DOI 存证（**待建** — 见 v2.1 机制 11）
- [ ] 每站榜单发布时同步给 `snapshot_date + contract_version`（**待建**）

---

## 6. 诚实边界（写给自己看）

1. 徽章是**引用方自评**，我们不做认证机构——避免任何"我们给别人发认证"的越界表述。
2. `CITATION.cff` 里的 `preferred-citation` 指向一篇**尚未发表**的竞赛论文；在它正式发布前，请引 `uibc_core_2026`。
3. 本 kit 不构成对外正式发布物；对外投放（官网 / Zenodo / arXiv）需 Steven 逐次点头。

---

*编制：2026-09-18 · 老二 🟡（代行 `uibc-race-ops` + `medxpert-standards-intel` 口径）*
