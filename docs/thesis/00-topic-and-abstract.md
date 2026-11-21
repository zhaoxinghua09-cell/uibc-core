> 学位论文稿 · 湖北师范大学 070120 信息计算与智能系统 · 同等学力申硕
> 本目录为论文正文草稿，不是项目对外材料；措辞与数据口径以论文体例为准。
> 排版母本为校规版 DOCX，本文件仅作版本管理与协作使用。

# 论文选题、摘要与章节骨架（送审稿）

学科：070120　信息计算与智能系统　　学位类型：同等学力硕士　　学校代码：10513　　编制日期：2026 年 11 月 19 日

## 一、题目

拟定题目：面向智能体行为证据的离线可验证封装方法研究

副标题（可省）：以开源判定器 uibc-core 的构造与实测为例

题目共 19 字，未超过学校规定 25 字上限，且符合“准确概括核心内容、可检索”的要求。题目中三个限定词各有对应：

- “智能体行为证据”——研究对象，不是泛指的日志或审计记录；

- “离线可验证”——方法特征，判定不依赖在线服务、不依赖对方系统；

- “封装”——落点是包的构造与格式，而非仅讨论判定原则。

备选题目（供答辩委员会取舍，均 25 字以内）：

- 《智能体行为证据链的离线封装与判定方法研究》

- 《智能体行为证据的可验证封装格式及其判定器实现》

## 二、中文摘要

智能体的行为记录一经产生，事后核查却常无据可依：记录由被核查方自行保存，格式各行其是，判定依赖在线服务，第三方既无法复算，也无法判断“这次判定究竟看住了什么”。本文把这一问题归结为证据边界的缺失，并提出一种把边界显式化、可在离线状态判定的封装方法。

方法上，本文不追求“判断智能体是否正确”，而把判定收敛到可复算的层面：以固定的包布局与内容哈希确定被判定对象，以 Merkle 树包含证明与树规模确定某条记录在当时的集合位置，以 Ed25519 签名与 JSON 规范化序列化确定内容未被替换，以时间戳与链头外部观察确定包的时序位置；由此给出三值裁决——在观察到的证据边界内未检出违规、检出具体违规、无法判定，并拒绝把“无法判定”折叠为“通过”。判定项计 20 项，按依据分为草案明文规定、思想来源、本文自定三类，其中 6 项为本文自定的加固项，正文逐项注明其无条款可引，不作条款化表述。

实现与实证方面，本文构造了判定器并给出独立第二实现，两者就同一批语料交叉比对；以 37 个攻击用例检验判定表，35 个使至少一项判定项失败，未被任何攻击触达的判定项为零；对单次记录写入的热路径实测中位延迟 1.225 毫秒、p99 2.156 毫秒，该口径含写盘与索引重写，不与仅计校验的数字比较。为检验方法本身能否被外部复核，本文另选一份他人公开的对照实现，在其语料上执行一次单字段改动，记录其对照驱动是否停下并归因到该字段，结果为退出码非零且三层报出；该实验只用于检验对方声明的可证伪性，不构成任何优劣判断。

结论部分明确本文的边界：判定结论限于观察到的证据边界，既不主张智能体本身正确、安全或明智，也不主张所记录输入真实完整，亦不主张任何现实结果随之发生；第三方独立见证为零、在线端点未部署、链尾收据不能仅由包内材料判定，均作为局限列出。

上述工作为智能体行为的事后核查提供了一个可离线复算、可被第三方重跑、并在证据不足时明确拒绝作答的最小判据集。

## 三、关键词

智能体行为证据；离线验证；证据边界；Merkle 树；可验证封装

## 四、Abstract

An agent's behaviour record is produced once and audited later, often with nothing to audit against: the record is kept by the party under scrutiny, its format is local to that party, the verdict depends on an online service, and a third party can neither recompute it nor tell what the verdict actually covered. This thesis frames the problem as a missing evidence boundary and proposes a packaging method that makes the boundary explicit and judges it offline.

The method does not attempt to decide whether an agent was correct. It narrows judgement to what can be recomputed: a fixed package layout and content digests fix the object under judgement; a Merkle inclusion proof and tree size fix where a record sat in the set at that time; an Ed25519 signature over a canonicalised serialisation fixes that the content was not substituted; a timestamp and an externally observed chain head fix the package's position in time. The verdict is three-valued: no violation detected within the observed evidence boundary, a specific violation detected, or not determinable. Indeterminate is never collapsed into a pass. Twenty checks are given, classified by basis into textually mandated, derived from an idea, and self-imposed by this thesis; the six self-imposed ones are marked as having no clause to cite.

A verifier and an independent second implementation were built and cross-compared on the same corpus. Of 37 attack cases, 35 make at least one check fail and no check is left unreached. On the write hot path, median latency is 1.225 ms and p99 is 2.156 ms, a figure that includes writing to disk and rewriting the index and is therefore not comparable with digest-only measurements. To test whether the method itself survives external scrutiny, one public third-party implementation was taken and a single field in its corpus was changed; its comparison driver exited non-zero and reported the change at three separate layers. That experiment tests the falsifiability of their published claim, not any ranking between verifiers.

The conclusion states the boundary: a verdict covers only the observed evidence boundary, and claims nothing about whether the agent was correct, safe or wise, whether the recorded inputs were true or complete, or whether any real-world outcome followed. Zero independent third-party witnesses, no deployed online endpoint, and the inability to judge the receipt tail from package-internal material alone are listed as limitations.

## 五、关键词（英文）

agent behaviour evidence; offline verification; evidence boundary; Merkle tree; verifiable packaging

## 六、章节骨架

### 第 1 章　绪论

研究背景与问题（智能体行为的事后核查缺口）→ 研究现状与文献综述（标准侧、产品侧、学术侧三条线）→ 本文研究目标与内容 → 研究方法与技术路线 → 论文结构安排。本章须独立成章，文献综述不得少于 3000 字，且须指出既有工作未覆盖之处，不作“首创”表述。

### 第 2 章　相关工作与标准依据

透明日志（RFC 6962、RFC 9162）、时间戳协议（RFC 3161）、签名与规范化序列化（RFC 8032、RFC 8785、RFC 4648）→ SCITT 系列草案与智能体回执类草案的条款梳理 → 同类实现的对比口径（按能力而非按厂商声称）。本章所有条款须能直达原文，仓库内已入库 5 份草案原文与 RFC 3161 原文。

### 第 3 章　证据边界的建模与封装格式

证据边界的定义（能判定什么、不能判定什么）→ 包布局与内容哈希 → 索引元数据与树构造 → 链头与锚定 → 三值裁决的形式化。本章为方法主体，自定项须逐条注明无条款可引。

### 第 4 章　判定器的构造与实现

20 项判定项及其依据分类 → 攻击—判定发生矩阵的设计 → 独立第二实现与交叉比对 → 严格性选择（如拒绝闰秒、严格 base64）作为策略而非正确性主张单独说明。

### 第 5 章　实证

表 5-1 至表 5-6（由脚本生成，数字可重跑）→ 表 5-7 与 5.x 节（外部材料上的复核）→ 本章须写明两类证据来源不同、不得混用。

### 第 6 章　结论与局限

核心结论 → 局限（第三方见证为零、无在线端点、链尾不可包内判定、单机单操作者）→ 后续工作。

## 七、参考文献种子（已核实，可直接著录）

学校规定要求不少于 30 篇、按著者-出版年制、先中文后外文。以下为已核实且可直达的条目，按 GB/T 7714—2015 著录；标“待补”者为尚需补齐的真实文献，不得以推测条目充数。

中文部分（含国家标准）

- 全国信息与文献标准化技术委员会. 2015. 信息与文献　参考文献著录规则: GB/T 7714—2015[S]. 北京: 中国标准出版社.

- 全国信息与文献标准化技术委员会. 2006. 学位论文编写规则: GB/T 7713.1—2006[S]. 北京: 中国标准出版社.

- 国家技术监督局. 1993. 量和单位: GB 3100～3102—93[S]. 北京: 中国标准出版社.

外文部分（标准与草案，均已在仓库内入库原文或经直达核验）

- IETF. 2001. Internet X.509 Public Key Infrastructure Time-Stamp Protocol (TSP): RFC 3161[S].

- IETF. 2008. The Base16, Base32, and Base64 Data Encodings: RFC 4648[S].

- IETF. 2013. Certificate Transparency: RFC 6962[S].

- IETF. 2017. Ed25519: EdDSA Edwards-curve Digital Signature Algorithm: RFC 8032[S].

- IETF. 2019. JSON Canonicalization Scheme (JCS): RFC 8785[S].

- IETF. 2021. Certificate Transparency Version 2.0: RFC 9162[S].

- IETF. 2026. draft-noa-scitt-ai-agent-receipt-00[S/OL].

- IETF. 2026. draft-maintainer-1f916-agent-record-01[S/OL].

- IETF. 2026. draft-sharif-agent-audit-trail-03[S/OL].

- IETF. 2026. draft-marques-asqav-compliance-receipts-01[S/OL].

- IETF. 2026. draft-bailey-scitt-agent-session-receipt[S/OL].

- IETF. 2026. draft-mih-scitt-agent-action-capsule-05[S/OL].

- IETF. 2026. draft-mih-agent-disclosure-envelope-00[S/OL].

- IETF. 2026. draft-pidlisnyi-aps-04[S/OL].

- IETF. 2026. draft-munoz-scitt-permit-profile-01[S/OL].

- IETF. 2026. draft-emirdag-scitt-ai-agent-execution-00[S/OL].

- IETF. 2026. draft-kamimura-scitt-refusal-events-03[S/OL].

- IETF. 2026. draft-sato-soos-gar-08[S/OL].

- IETF. 2026. draft-sergeev-wexp-core-02[S/OL].

待补（须逐篇核实出版页后方可著录，现有条目约 22，距 30 篇尚缺 8 篇）

- 智能体审计与可验证计算方向的期刊或会议论文，须从万方、维普或相应学科数据库按题录核实；

- 透明日志与 Merkle 证明在教学或工程实践中的中文文献；

- 笔记：任何一条若不能取得出版页或原文，则不入表，宁缺勿造。

## 八、提交前须确认的三件事

- 题目最终取舍（三选一），一经确定，摘要与各章标题须同步；

- 副标题是否保留——保留便于答辩委员会定位，但封面字数须复核；

- 参考文献制式：本研究属自然科学类，章节编号用 1 / 1.1 / 1.1.1 体例，但参考文献仍按学校规定的著者-出版年制，不改为顺序编码制。
