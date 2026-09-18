# 独立专家核验记录 — uibc-core 对外提交前

- **核验日期：** 2026-09-18
- **核验对象：** `uibc-core` v0.2.1 的对外材料包（引用元数据、许可与合规底座、SBOM、隐私与凭据）
- **触发原因：** 该材料包即将提交给 W3C 社区组、IETF、OpenSSF、Zenodo 与学术索引；作者的原则是**不允许任何未经交叉验证的断言**。

---

## 0. 诚实边界（先读这一节，再看结论）

1. **这是一次委托方自费组织的专家复核，不是认证机构背书。** 三路评审由本机 AI 专家角色执行 + 人工复核，**不构成** accredited third-party certification、不构成 W3C / ISO / OpenSSF 的任何认可。
2. **本记录只对"核验日当天可查的事实"负责。** 外部链接与政策会变；本记录中的每个结论都附了可复核证据（文件:行 或 URL），复核者可自行重跑。
3. **本记录不代表项目已被任何标准组织接受。** `uibc-core` 的状态仍是 **PROPOSAL**，不是标准。

---

## 1. 核验方法与三路分工

| 路 | 角色 | 关注面 | 授权范围 |
|---|---|---|---|
| A | 标准与合规审计 | 引用元数据、许可一致性、SPDX/CFF/CodeMeta 规范性、标准号真实性 | 只读 + 联网核验 |
| B | 标准情报与生态 | 背书/存证渠道的真伪、个人可参与性、门槛与时效 | 只读 + 联网核验 |
| C | 安全与隐私（red line） | 雇主信息、明文凭据、个人联系方式、商业敏感件 | 只读扫描 |

对上轮搜索得到的结论**一律要求一手源复核**，不接受二手转述；发现与既有说法冲突时以权威源为准并标注更正。

---

## 2. 路 A · 标准与合规核验结果

| # | 核验项 | 结论 | 证据 |
|---|---|---|---|
| 1 | Software Heritage 由 Inria 运营、与 UNESCO 合作 | PASS | softwareheritage.org FAQ；inria.fr/UNESCO 联合公告 |
| 2 | SWHID 已标准化为 **ISO/IEC 18670:2025**（2025-04-23 发布） | PASS | webstore.iec.ch/en/publication/107118；swhid.org 新闻 |
| 3 | CITATION.cff 的 SWHID 与归档 API 一致（独立复算） | PASS | `origin/search/uibc-core/` → snapshot `a901225…`；snapshot 的 main = revision `402ac6b…`（= 本地 HEAD）；独立重算 `sha1("https://github.com/zhaoxinghua09-cell/uibc-core")` = `819530c8…` |
| 4 | 版本 DOI `10.5281/zenodo.22821835` 与概念 DOI `…22821834` 可解析 | PASS | doi.org Handle API → 200；`https://doi.org/...` → 302 |
| 5 | CITATION.cff 符合 CFF 1.2.0 schema | PASS | 官方 1.2.0 schema 校验通过 |
| 6 | codemeta.json 符合 CodeMeta 2.0 术语 | PASS | 官方 context 定义逐字段核对 |
| 7 | .zenodo.json 与真实投放一致 | **FAIL → 已修** | 见 §4-2 |
| 8 | sbom.spdx.json 符合 SPDX 2.3 | **FAIL → 已修** | 见 §4-3 |
| 9 | 引用 `arXiv:2609.13637` 与 AML 仓库真实 | PASS（标题已修） | arXiv 侧标题/作者/日期核对；见 §4-1 |
| 10 | Apache-2.0 全链一致 | **FAIL(P0) → 已修** | 见 §3 |
| 11 | CHANGELOG 与 git 历史一致 | **FAIL → 已修** | 见 §4-4 |

### 被更正的两处「权威口径」（此前说法有误）

- **DID 1.1 尚未成为 W3C Recommendation**，当前是 Candidate Recommendation Snapshot（2026-03-05）；已成 Rec 的是 DID 1.0（2022-07-19）。
- **不存在名为 «computed vs asserted» / «AI Computed Provenance» 的 W3C 社区组**。与之最接近的是 **AI Content Disclosure CG**（2026-02-03 成立，对标 EU AI Act 第 50 条）；"computed ≠ asserted" 这类溯源问题更多落在 **C2PA / CAWG**，不在 W3C。

---

## 3. 唯一的 P0：被 DOI 固化的许可与仓库声明冲突

- **现象：** DOI 归档物元数据为 **MIT**，而仓库通篇声明 **Apache-2.0**（`pyproject.toml`、`LICENSE`、`NOTICE`、`codemeta.json`、`.zenodo.json`、`CITATION.cff` 六处）。
- **证据：** DataCite `rightsList` = MIT；`dist/deposit-v021.json`（`"license": {"id": "mit"}`）、`dist/deposit-response.json`、`dist/publish-response.json` 三处互证。
- **为何是 P0：** 「被引用托管物的许可 ≠ 被声明许可」会让任何第三方无法确权，也会在 W3C/IETF 的 IPR 审查与 Zenodo 版本一致性校验处被驳回。
- **处置：** 保留 Apache-2.0（含明确专利授权，更适合被标准生态采用），**修正 Zenodo 记录元数据**而非改动代码。
- **修后复核（权威源）：** DataCite `rightsList` = `Apache License 2.0`，`rightsIdentifier` = `apache-2.0`，scheme = SPDX；记录 state = `done`，submitted = `true`；**制品字节未变，仅元数据修正**。

---

## 4. P1 级问题与处置

### 4-1 引用元数据出现「未核验值」
- `CITATION.cff` 中曾写入一个**未经 API 复算**的 Software Heritage 标识符（`swh:1:ori:8f50d3f6…`）。复核时发现它与真实值不符（真实 origin = `swh:1:ori:819530c8…`）。
- 同文件引用的邻居基准论文标题为**改写而非原文引用**（真实标题 *Identity Is More Than Recall: A Benchmark for Persistent Identity in Deployed AI Agents*，"PAI-Bench" 是文内基准名）。
- **处置：** 两者均以真实值替换，并在描述中注明"已于 2026-09-18 对 arXiv 核验"。

### 4-2 `.zenodo.json` 与真实投放不一致
- 原文件缺 `publication_date`；含 Zenodo 元数据 schema 之外的自定义 `notes` 字段。
- **处置：** 补 `publication_date`；移除非 schema 字段（PROPOSAL 免责声明已在 description 内）；许可、标题、关联标识与记录对齐。

### 4-3 SBOM 三处 SPDX 违规
- 元素标识符含下划线（`SPDXRef-File-uibc_core-…`），不符 SPDX 标识符字符集；
- `hasExtractedLicensingInfos.licenseId = "Apache-2.0"` 违反 §10.1（该节仅用于**不在**清单内的许可，且须 `LicenseRef-` 前缀）；
- `licenseListVersion` 停留在 `3.22`（当前为 `3.29.0`）。
- **处置：** 生成器加 `spdx_id()` 归一化函数、删除该区块、版本号改为动态常量 `3.29.0`；新增断言校验 ID 唯一且字符集合法。重生成后 10 个 ID 全部合规。

### 4-4 CHANGELOG 与可复现链断裂
- CHANGELOG 声称 0.2.1「Triple-anchored: GitHub tag + OTS + Zenodo DOI」，但当时**只有 `v0.2.1-roadmap` 标签，没有 `v0.2.1` 发布标签**；且 LICENSE 等合规文件尚未入库，导致归档快照 `402ac6b` 内**不含许可文件**。
- **处置：** 合规文件入库 → 打 `v0.2.1` 标签 → 重新向 Software Heritage 提交 Save，使归档快照包含许可文件。

---

## 5. 路 C · 隐私与凭据红线

| 项 | 结果 |
|---|---|
| 明文凭据（`ghp_` / `github_pat_` / 私钥 / Bearer / PAT 形态） | **无命中**；Zenodo 回执（`dist/deposit-response.json`、`publish-response.json`、`upload-response.json`、`public-verify.json`、`deposit-v021.json`）仅含 DOI、记录 ID、bucket UUID，上传/下载链接不带凭据参数 |
| 个人联系方式 | 仅 `SECURITY.md` / `CODE_OF_CONDUCT.md` 中的**有意公开**的安全联系邮箱（无手机号、无证件号、无住址） |
| 商业敏感件（定价/营收/财务模型/渠道） | 公开仓库内**无** |
| 雇主/任职单位表述 | 曾命中 2 处，**已修**：`NOTICE` 的第三方公司名、`adapters/tencentdb-agent-memory/SPEC.md` 的"公司机"措辞 |

---

## 6. 路 B · 背书渠道核验（更正后的可用清单）

| 渠道 | 个人可否 | 成本 | 关键门槛 | 结论 |
|---|---|---|---|---|
| **Sigstore cosign + Rekor** | ✅ | 免费 | 需 OIDC（keyless）或本地密钥；Windows 有官方二进制 | 真实，**当天可用** |
| **W3C 社区组（CG）** | ✅ | 免费 | 仅需 W3C 账号，**不需要会员资格**；产物**不等于 W3C 标准** | 真实 |
| 　·AI Content Disclosure CG | ✅ | 免费 | 2026-02-03 成立；对标 EU AI Act §50 | 真实，**最贴题** |
| 　·AI Agent Protocol CG | ✅ | 免费 | 范围含 agent 身份模型与 VC 信任 | 真实 |
| 　·Semantic Agent Communication CG | ⚠️ | 免费 | 2025-11-09 **提议**，启动状态未确证 | 存疑，勿视为已运行 |
| **IETF Internet-Draft** | ✅ | 免费 | 无需会员；**6 个月自动过期**，需周期重发 | 真实，但**不是永久背书** |
| **OpenSSF Best Practices Badge** | ✅ | 免费 | passing 67 / silver 55 / gold 23 条；**Gold 要求 ≥2 名无关联重要贡献者** | 真实，单人项目难达 Gold |
| **Zenodo** | ✅ | 免费 | 无评审；DOI 冻结版本 | 已用 |
| **TechRxiv** | ✅ | 免费 | IEEE 运营；无背书门槛 | 真实，**契合度高** |
| **Preprints.org** | ✅ | 免费 | MDPI；筛查 <24h | 真实，拿第二个 DOI 快 |
| **DIF** | ✅（附条件） | 免费 | 须签 Feedback Agreement；**若为某实体全职雇员/高管则不适用该通道** | 真实 |
| **arXiv（cs.SE/cs.CR）** | ✅（附条件） | 免费 | 首投**需域内既有作者背书**；2026-01-21 起机构邮箱不再单独算数 | 真实，门槛已提高 |
| **JOSS** | ✅ | 免费 | 需**公开 ≥6 个月**且活跃 + 真实研究使用证据 | 真实，**当前不合格**（会被 desk reject） |
| **ISO / IEC 直接提案** | ❌ | — | 必须经国家标准化机构（如 SAC/国标委）；立项需 ≥5 个 P 成员 | 个人通道封闭 |
| **Wikidata / Wikipedia** | ⚠️ | 免费 | 需独立可靠来源；**禁自我宣传** | 当前不可行 |
| **CNCF Sandbox** | ⚠️ | 免费 | 项目级可申请（非仅限组织），但须为云原生基础设施 | 契合度低 |

**按"抢首发性价比"排序的前三：** ① Sigstore cosign + Rekor（零成本、当天留痕）；② W3C AI Content Disclosure / AI Agent Protocol CG（免费挂名贡献，最贴题）；③ IETF Internet-Draft（具名 `draft-*` 记录，注意 6 个月续期）。备选：TechRxiv / Preprints.org 叠加 DOI 巩固时间戳。

---

## 7. 复核者如何自行重跑

```bash
# 1) SWHID 独立复算（应等于 CITATION.cff 中的 origin id）
printf 'https://github.com/zhaoxinghua09-cell/uibc-core' | sha1sum

# 2) 归档 API 交叉比对（origin → snapshot → revision）
curl --noproxy '*' "https://archive.softwareheritage.org/api/1/origin/search/uibc-core/?limit=5"
curl --noproxy '*' "https://archive.softwareheritage.org/api/1/snapshot/<snapshot-id>/"

# 3) DOI 许可现状（权威侧）
curl --noproxy '*' "https://api.datacite.org/dois/10.5281/zenodo.22821835"

# 4) SBOM 重新生成并自检（ID 唯一 + 字符集 + 清单版本）
python tools/gen-sbom.py && python -c "import json,sbom_check"  # 见 tools/gen-sbom.py 断言
```

> 本机提示：`zenodo.org` 存在 DNS 污染（解析到 `0.0.0.0`），但真实地址可达；用 `--resolve zenodo.org:443:<真实IP>` 或 DNS-over-HTTPS 取值即可。此现象与项目本身无关，仅影响复跑方式。

---

## 8. 结论

- **核验前状态：** 不可直接对外提交（1×P0 + 4×P1）。
- **核验后状态：** P0 与 4 项 P1 **全部处置完毕并已复核**（许可一致性在 DataCite 权威侧确认、SBOM 断言通过、引用改为真实值、归档链补齐）。
- **仍未解决的现实约束：** 项目公开史不足 6 个月（JOSS 暂不可投）、arXiv 需背书、OpenSSF Gold 需第二贡献者。这些是**时间与人力约束，不是合规缺陷**，应在对外表述中如实说明。
