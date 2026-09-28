# LGD-MedAI 问题应对手册（Problem–Response Handbook）

> 版本 v1.0 · 2026 年 9 月 28 日 · 发布于 uibc-core 仓库 · 上游真源：内部设计提案（版本从略）
> 性质：对外速查件，面向人类读者与 AI 检索（RAG / llms.txt / AI Index）；机制细节零披露，只陈述「问题 → LGD 怎么应对」与公开可核验物。

## 0. 权属宣告（统一块 · 整体复制不得删改）

```
© 2026 赵兴华 / Steven Zhao·China (ORCID 0009-0001-0512-1237). All rights reserved.
理论署名 (attribution) : LGD（Lifecycle Governance Doctrine / 全程治理论）— SynomosAI initiative
名称状态 (name status)  : "SynomosAI" / "MedXpert" — 未申请实体注册、未申请商标注册
                        (not a registered legal entity; no trademark registered)
生产参考部署 (production reference, self-reported) : MedXpert
                    ← 非认证、非背书、非监管认可（not a certification or endorsement）
代码许可 (code license) : uibc-core = Apache-2.0 (see repo LICENSE)
                    本文本与理论表述不在 Apache-2.0 覆盖范围内
引用格式 (cite as)      : uibc-core/CITATION.cff · concept DOI 10.5281/zenodo.22821834
首次公开锚 (first public): 2026-09-17 13:31:45 UTC (commit cb6f11b)
                    外锚 (external anchor): Sigstore Rekor logIndex 2883389783
```

> **G0 对外授权闸**：常设在位 —— 此后任何对外动作（新文件、新渠道、引用扩散）一律待 Steven 授权，本行即为该闸声明。
> **本次发布授权**：Steven 2026 年 9 月 28 日已授权「全面执行、不要停」（聊天记录在案）；机器闸 22/22 通过、著作权官推送前终审通过后执行本仓库发布。

---

## 1. LGD 是什么

**LGD（Lifecycle Governance Doctrine，全程治理论）**是面向自治实体全生命周期的治理状态机理论：以五要素 Registry（有籍）、Evidence（有证）、Gate（有门禁）、Authority（授权）、Lifecycle（生命周期）刻画自治实体从创建、运行、变更到退役的治理状态与状态转移。

三律一句话：**「凡自治之物，有籍 · 有证 · 有门禁」**——凡自治实体必登记入册，凡行动必留可验证证据，凡状态转移必过门禁谓词。

## 2. 十七类医疗 AI 问题 → LGD 应对全景

> 口径：LGD 不主张任一单项机制原创；增量集中于「组合成可操作状态机 + 数字 Agent 与物理医械统一抽象 + 高优维度 Extension 延伸」。先例状态沿用调研判定：✅已有 / ⚠️部分 / ⭕未发现。

| A# | 问题 | LGD 怎么应对 | 先例状态 |
|---|---|---|---|
| A-01 | 幻影发现（模型报告未见发现） | 无证据即拦截（Gate）+ 像素级溯源（Evidence），统一适用影像 Agent 与物理器械告警 | ⚠️部分 |
| A-02 | 假阴性漏诊 | 最低召回阈值门禁 + RESUMED 周期重估，数字诊断与物理器械共享重评状态机 | ✅已有 |
| A-03 | 数据/人群漂移 | 生命周期持续监测态 + 漂移证据入链，统一表达避免法域口径碎片化 | ✅已有 |
| A-04 | 黑箱不可解释 | 每次转换附依据、拒无依据转换，解释性为状态机内建约束 | ⚠️部分 |
| A-05 | 偏见与公平 | 子群登记 + 子群性能门禁谓词纳入统一生命周期，跨法域一致 | ⚠️部分 |
| A-06 | 训练数据代表性 | 数据籍登记 + 代表性证据，统一 Registry 补足跨域追溯链 | ✅已有 |
| A-07 | 人机责任归属 | 能力≠权限、分别授权分别留证；云部署三方 Authority 切片 | ⚠️部分 |
| A-08 | PMCF 难开展 | 监测态强制回采为生命周期必经态，跨法域范式一致 | ✅已有 |
| A-09 | 召回/变更滞后 | PCCP 式预批谓词纳入生命周期抽象，与物理器械变更同态 | ✅已有 |
| A-10 | 网安/提示注入 | 门禁对不可信输入的拒绝谓词，与物理器械访问控制同抽象 | ⚠️部分 |
| A-11 | 跨域多模态验证 | 各模态组件共享 R/E/G，`multimodal_consistency_gate` 桥接一致性 | ⚠️部分 |
| A-12 | 监管碎片化 | 各国要求表达为同一抽象的参数化实例（统一收敛） | ⭕未发现（统一收敛） |
| A-13 | 罕见病小样本 | 小样本显式门禁分支 + 人类复核强制门，统一于生命周期重估 | ⚠️部分 |
| A-14 | 标签噪声 | `label_noise_estimator` 纳入 Evidence 前置门禁 | ⚠️部分 |
| A-15 | 部署后性能衰减 | 跌破谓词自动降级 + `AUTO_RETRAIN_GATE` 防静默漂移 | ✅已有 |
| A-16 | 审计链断裂 | 统一 Registry 串成模型/数据/审批/部署单一可审计链 | ✅已有 |
| A-17 | 供应商锁定 | 权重/管线/证据以开放可验证格式登记，迁移不丢证据链（非核心主张） | ⭕未发现 |

**诚实边界注**：A-12 与 A-17 为 ⭕未发现项，是 LGD 最可能形成差异的方向，但须后续一手文献复核，本文档不作「创新」定论。A-13/A-14/A-11 本质是算法与数据工程问题，LGD 治理的是「处理过程须有证据」，不发明算法、不替代 ML 方法本身。

## 3. 真实差异（四线调研互相印证）

以下差异点截至 2026 年 9 月，由四条独立调研线（民间/社区/学者线、行业/标准/政府间线、历史外部评估批次线、既有医疗 AI 监管域线）在其各自覆盖范围内互相印证；本文档不作任何序数性占位表述。

- **V2 · 跨域实体级状态机：当前最干净的差异真空。** 在四线调研全量条目中，未发现任何一家把软件 Agent 与物理医械纳入同一实体级 Registry/Evidence/Gate/Lifecycle 状态机。相邻工作（AEP/AADP 等 Agent 治理草案与论文）均明确限于 software agents / AI systems；监管实践中 FDA 占设备侧、各类 Agent 框架占数字侧，中间桥接无人做。
- **V3 · 资格重估非单调：收窄后仍可主张。** 「可逆挂起 + 非单调重评」思想已在 AEP/AADP 的动作/会话级出现先声；LGD 的主张收窄为「实体级 PAUSED→RESUMED 转移义务 + eligibility 可降级变量的一等状态转移」的形式化语义，仅在此语义层保留差异点。
- **V1 · 域无关统一抽象：被挤压未失守。** 统一策略架构类工作挤压「统一/授权/证据」各面叙事；LGD 剩余差异在于把上述各面合并为同一套实体级状态机 + 证据门 + 资格重估的统一理论，并强调跨域实例化，而非主张「统一策略」。

## 4. 为什么适配医疗 AI

### 4.1 五 KPI（诚实版）

| KPI | 达成逻辑 |
|---|---|
| 接入快 | 不新增任何审批环节：把 FDA/EU/NMPA/PMDA 等既有监管要求重新表述为同一套状态机实例，在既有注册/变更流程上叠加治理状态机 |
| 边际成本低 | 一套状态机实现、多法域参数化实例：五要素一次实现，各国差异表达为门禁谓词参数，避免逐法域维护独立治理栈 |
| 覆盖范围广 | 数字 Agent 与物理医械同一抽象：SaMD/LLM 诊断、植入物/设备、组合产品、多模态 Agent 纳入同一实体级状态机 |
| 承载既有监管 | 治理层在监管之上而非替代：每法域为同一抽象的谓词参数实例，可承载既有要求、异构要求并存不冲突（如美 PCCP 预批变更与欧 NB 重认证同机并行） |
| 模块化可增减 | 五要素为可组合原子原语，三层冻结纪律（CoreSpec/Extension/Experimental）约束概念增删；法域谓词集按需启用，安全门强制保留 |

### 4.2 九法域 × 五要素强制映射点

> 此表为既有监管要求向 LGD 五要素的重新表述。LGD 未进入任何法规文本，不主张法规地位。

| 法域 | 有籍 Registry | 有证 Evidence | 门禁 Gate / 授权 Authority | 生命周期 Lifecycle |
|---|---|---|---|---|
| FDA（美） | 设备列名/主记录/PMA | GMLP 训练验证证据 | PMA 批准/PCCP 变更门；上市授权≠模型可改 | TPLC + 部署后监测草案 |
| EU MDR + AI Act | EUDAMED/UDI | 技术文档/CER/PMCF | NB 发证/CE/AI Act 评估；CE≠绕过 AI Act | PMCF/警戒闭环 |
| NMPA（中） | 注册证/UDI/生产许可 | 算法资料/数据溯源/CER | 注册审评/GMP 核查；注册证≠算法自改 | 指导原则全生命周期 + 2025/107 GMP |
| PMDA（日） | 国内登记/制造贩卖许可 | 审评性能证据 | PMDA 批准/PACMP；许可≠模型自改 | PACMP 变更治理 |
| MHRA（英） | UK 版注册 | AI 专项文档 | UKCA/符合性评估 | GMLP 映射（UK MDR 202x 改革仍处咨询未落地） |
| TGA（澳） | ARTG | AI 专项证据 | 准入；卫生监管授权 | 变更/再验证（UDI 强制自 2026 年 7 月起） |
| ANVISA（巴西） | Cadastro/Registro | 技术文档 AI 证据 | 卫生监管授权 | PMS（无独立 AI 规则，靠 RDC 657/2022 SaMD 框架 + LGPD 承载） |
| HC（加） | Licence | AI 证据 | 符合性；授权 | GMLP 映射（MLMD 指南终版 2025 年 2 月） |
| IMDRF | SaMD 定义/分类 | N41 临床 + N23 QMS | N12 风险分级门（协调层） | ML GMLP 全周期 |

### 4.3 高优维度（Extension 层）

- **G-02 · LocalAdaptor 本地化接入**：数据驻留（PIPL/GDPR）、本地语言标签、本地临床实践等内容级本地需求不在 LGD 治理抽象范围内。LocalAdaptor 提供标准化挂载接口，使本地「血肉」接入统一「骨架」而非另起炉灶；本地扩展不可覆盖 Core 安全门，证据库与 Registry 可本地实例化，跨境仅同步指纹。
- **G-03 · 技术 ML 治理桥接四算子**：罕见病小样本、标签噪声、多模态验证本质是算法/数据工程问题，LGD 不发明算法，只在治理层要求过程证据——`low_sample_declaration` + `human_review_gate`（小样本显式声明与人类复核熔断）、`label_noise_estimator`（噪声率超阈拦截训练产物入 ACTIVATE）、`multimodal_consistency_gate`（跨模态证据一致性门）。
- **G-04 · `AUTO_RETRAIN_GATE` 持续学习门**：自动再训练若不治理将静默漂移。该 Extension 转换要求任何权重更新必须过 CHANGE_GATE + RESUMED，禁止静默再训练，未过门即 PAUSE；映射 FDA PCCP「预定义变更」精神与 NIST AI RMF 的 monitor & re-assess。
- **G-16 · `hosting_authority_separation` 云部署责任分离**：SaaS 医疗 AI 中模型方/托管方/运营方责任归属常不清。该 Extension 令三方各持独立 Authority 切片、各留证据，责任事件按切片追溯，任一切片缺失即 PAUSE；基于「分别授权分别留证」既有原则扩展，映射云责任共担模型既有实践。

## 5. 诚实边界（发布前必读）

1. **不替代监管审批**：Gate(ACTIVATE) ≠ 上市许可；架构符合性 ≠ 监管认可；LGD 未进入任何法规文本，不主张法规地位。
2. **技术 ML 问题归 ML**：A-11/A-13/A-14 本质是算法与数据工程问题，LGD 只治理「处理过程须有证据」，不声称发明新 ML 方法。
3. **V3 主张已收窄**：可逆挂起/非单调重评思想已有动作/会话级先声；LGD 仅保留「实体级 PAUSED→RESUMED 转移义务 + eligibility 可降级变量」的形式化语义差异。
4. **模块化不可关安全门**：ACTIVATE/PAUSE/RESUMED/RECALL 在任何法域实例中强制启用，属 CoreSpec 不可裁剪项；「减」只关闭非必要辅助谓词集。
5. **本地内容需求走 LocalAdaptor 不越权**：数据主权/本地语言/本地临床实践由本地基础设施与合规团队承载，本地接口不覆盖 Core 安全门。
6. **不笼统称适用于全球**：英国 UK MDR 202x 改革仍处咨询未落地；ANVISA 无独立 AI 规则（靠 RDC 657/2022 + LGPD 承载）；对外按「已核实九法域一手源 / 部分法域改革未落地」分层口径表述。
7. **高优维度均为 Extension 层**：G-02/G-03/G-04/G-16 全部在 Extension 层实现，不新增 Core 概念。
8. **标准参与通道优先**：AIP/CESI/ITU FG-TIDA 等标准席位是 V2/V3 主张的合法出口，优先走标准参与而非单篇论文硬主张。

## 6. 公开可核验物与接入

- **参考实现**：github.com/zhaoxinghua09-cell/uibc-core（Apache-2.0，见仓库 LICENSE；理论文本不在 Apache-2.0 覆盖范围内）
- **概念 DOI**：10.5281/zenodo.22821834（Zenodo concept DOI）
- **外部时间锚**：Sigstore Rekor logIndex 2883389783
- **首次公开锚**：commit cb6f11b
- **引用格式**：uibc-core/CITATION.cff
- **LocalAdaptor 三接口**：
  - `evidence_store_local`——证据库可本地实例化，满足数据驻留要求，治理链仍统一；
  - `predicate_extension_local`——法域谓词集可本地扩展（如本地语言标签证据门），但不可覆盖 Core 安全门；
  - `registry_local_mirror`——Registry 本地镜像，跨境仅同步指纹/哈希，不同步原始数据。
