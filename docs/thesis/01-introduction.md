> 学位论文稿 · 湖北师范大学 070120 信息计算与智能系统 · 同等学力申硕
> 本目录为论文正文草稿，不是项目对外材料；措辞与数据口径以论文体例为准。
> 排版母本为校规版 DOCX，本文件仅作版本管理与协作使用。

# 1　绪论

## 1.1　研究背景与问题的提出

过去两年，能够自主调用工具、读写文件、发起网络请求的智能体从演示走向日常使用。伴随这一变化，一个原本属于审计领域的问题被推到前台：一次智能体行为发生后，如果当事人、监管方或协作者事后对“它当时究竟做了什么”产生争议，凭什么材料来核查？

现实中的做法有三种，且各有缺口。其一是自留日志。日志由被核查一方自行保存，格式自行约定，读写权限也在同一方手中；一旦发生争议，记录的可信度与被核查方本身的可信度绑定，这在结构上无法解决。其二是平台回执。由平台在服务端记录并出具结果，核查须向其申请、依赖其在线服务与存续，第三方不能独立复算，也无法判断回执覆盖了哪些检查、遗漏了哪些。其三是自建留痕。把操作记录写入区块链或可信存储，锚定确实成立，但代价是把核查能力绑定在一条链、一个网络和一套运维之上，离线场景、内网场景与跨组织场景均不适用。

三种做法的共同盲点不在“有没有记录”，而在“记录的边界有没有被说清”。一份记录可以完备地证明某条动作发生过，同时完全无法证明它在整批记录中的位置、无法证明它出现时集合有多大、无法证明后来没有新增、也无法证明记录与索引是否被整体替换。这些问题不是记录质量问题，而是判定结构问题：判定者不知道自己的判断覆盖了多大的证据范围。

本文把这一缺失称为证据边界（evidence boundary）的缺失，并把它作为核心问题：能否构造一种封装，使证据边界在包内即被确定、使判定可在完全离线的状态下完成、使“证据不足以判断”成为一个独立的、必须显式给出的结论，而不是被折叠为“通过”或“拒绝”？

这一问题与本学科的关系是直接的。它要求的不是某种业务规则的制定，而是一组可计算的判定：摘要如何取、树如何构造、证明如何验证、规范化如何消除序列化差异、裁决如何在三值之间落定、以及在计算资源受限时判定路径如何保持确定的复杂度。这些都是信息计算层面的问题，其结果须以可重复的方式给出，而非以论述方式给出。

## 1.2　国内外研究现状

本节按三条线梳理：标准侧（规范文本）、学术侧（论文提出的方法）与实现侧（已发布的开源与商业实现）。三条线的梳理标准一致：是否给出可离线复核的判定、是否明确证据边界的范围、是否把“不可判定”作为独立结论、是否提供可失败的判定表。以下评述仅依据各文献题名与其摘要所述内容，不对未读到的细节作推断。

### 1.2.1　标准侧：从透明日志到智能体回执

可验证记录的技术底座来自透明日志。RFC 6962 定义了证书透明日志的 Merkle 树构造、包含证明与一致性证明的交换格式；RFC 9162 给出其第二版，明确了树规模的表示与证明验证的边界条件。这两份文本确立了本文沿用的一条原则：判定者只需持有树头与一条证明路径，即可在不获取全量数据的前提下确认某条记录属于某个确定的集合，且该集合在某一时刻的规模是可核的。

时间维度的锚定由 RFC 3161 提供。其时间戳令牌把“某份摘要在某时刻已存在”这一事实交由第三方签署，本文用它来确定包的时序位置，并据此区分“包内时间”与“外部观察时间”——前者可被构造者改写，后者不能。签名与序列化分别由 RFC 8032（Ed25519）与 RFC 8785（JSON 规范化）规定，编码由 RFC 4648 规定。这三份文本的价值在于消除歧义：同一份内容在不同实现中必须产生同一摘要，否则跨实现复算在第一步就会失败。

近两年，IETF 的 SCITT 工作组把上述构件组合到“供给链与智能体”的语境中，形成了一批草案。与本文直接相关者包括智能体回执（draft-noa-scitt-ai-agent-receipt）、智能体记录（draft-maintainer-1f916-agent-record）、智能体审计轨迹（draft-sharif-agent-audit-trail）、合规回执（draft-marques-asqav-compliance-receipts）、会话回执（draft-bailey-scitt-agent-session-receipt）、动作胶囊（draft-mih-scitt-agent-action-capsule）、披露信封（draft-mih-agent-disclosure-envelope）、执行证据（draft-emirdag-scitt-ai-agent-execution）、拒绝事件（draft-kamimura-scitt-refusal-events）、许可档案（draft-munoz-scitt-permit-profile）、通用动作记录（draft-sato-soos-gar）等。这批文本的共同取向是把“回执”作为可互操作的对象，用统一的封装承接签发、传输与验证。

标准侧的成熟之处在于构件齐备、术语统一；其尚未收敛之处在于两点。其一，多数文本把验证的完成条件寄托于在线服务或既有信任基础设施，离线可验证虽被提及，但少有文本逐项规定“无网络时判定者手里必须有哪几样东西”。其二，回执类文本普遍以“是否合规”为判定结果，二值取向明显，对“材料不足、无法判定”这一状态的处理多置于实现层，未见统一的裁决语义。

### 1.2.2　学术侧：三类方法与各自的边界

学术界的进路大致可分为三类。

第一类是锚定型，把记录写入链上或可验证存储，以不可篡改性保证可信。White 等（2019）提出面向机器人的不可变黑盒记录方法，以区块链承接日志的不可篡改性；Wright（2025）提出以ECDH 密钥化的 Merkle 链构造智能体不可变记忆；Bindschaedler 等（2026）提出为长周期工具型智能体提供带链上锚定的防篡改审计轨迹。这类方法的优点是把“事后无法抵赖”做实，其边界在于判定能力与链的可得性绑定：核查方必须能访问该链及其历史状态，离线、内网与跨组织的核查场景因此受限；同时，链上锚定解决的是“未被改写”，并不回答“记录覆盖了哪些检查项”。

第二类是回放型，通过复算执行过程来确认结果。Vispute 与 Kadam（2026）提出面向自主智能体的推理溯源，把状态检查点与执行轨迹之外的推理过程结构化；Chong 等（2025）提出以确定性可复现性支撑大模型的不对称可验证；Ghosh（2026）提出对意图—推理—动作三层做防篡改审计。这类方法的优点是把“过程是否发生”做得更细，其边界在于复现条件：执行环境、模型版本、随机源与外部依赖必须一致，跨实现、跨版本、跨供应商时复算难以成立，而这恰是争议最常见的场合。

第三类是证明型，以零知识证明或密码学承诺直接证明某属性。Bhutto（2026）提出以内容寻址承接多智能体协作的可问责性；Raman 等（2019）提出面向多方协作的可信计算与可验证模拟；另有业界白皮书讨论面向智能体治理的零知识证明链（2026）。这类方法的优点是把证明强度推到很高，其边界在于成本与可解释性：证明生成耗时与验证者需掌握的构件复杂度，都与“现场快速核查”相矛盾；更重要的是，强证明回答的是“某属性成立”，仍不回答“本次判定覆盖了哪些证据”。

中文文献方面，严宇萍等（2026）在《计算》上系统梳理了群体智能与 AI 智能体的可信问题，把威胁、对策与展望归入统一框架，指出当前对策在“责任可追溯”与“跨主体互认”之间存在张力。该综述为本文的问题设定提供了中文语境的支撑：可信问题并不止于模型对齐，而是延伸到行为发生之后的证据与责任环节。

综观三类方法，其共同特征是把判定强度作为主要追求，而较少把判定边界作为独立对象处理。由此产生两个具体空白：其一，缺少“仅凭包内材料即可完成判定”的完整判据集；其二，缺少把“不可判定”与“通过”“拒绝”并列的裁决模型。这两个空白构成了本文的切入位置。

### 1.2.3　实现侧：已发布实现的形态

已发布实现大致有两类形态。一类以 SDK 或包的形式提供记录与验证，安装后即可在本地运行，但验证范围通常围绕单一记录，树级一致性、索引元数据与锚定的交叉验证需自行补齐。另一类以服务形式提供，验证在服务端完成，客户端只获得结论，其便利性与“离线自证”的目标相反。两类形态都没有公开一组“可被攻击的判定表”，即：列出所有判定项、逐项说明依据，并用一组攻击用例检验每个判定项是否真的会被触发。缺少这张表，外部无法判断某次通过究竟是“检查通过”还是“检查未被执行”。

这一判断可由一次直接观察支持：在若干公开实现中，验证输出的粒度为整体通过或整体失败，失败时不指明是哪一层、哪一项、哪个字段导致失败。此类输出在排障上可用，在举证上不可用。

### 1.2.4　现有研究的缺口

将三条线合并比较，可归纳出四点缺口：

（1）离线判定的完整性未被制度化。多数设计假定核查方能够访问在线服务或链上状态，对完全离线（无网络、无对方系统、仅持有一个包）时判定者手里必须有什么、能判断到什么程度，缺少明确规定。

（2）证据边界未作为独立对象被构造。记录格式通常只描述“一条记录长什么样”，不描述“这一批记录在何时有多大、某条记录在其中第几位、此后是否新增”，判定者因此无法陈述自己的判断覆盖范围。

（3）裁决语义多为二值。合规或不合规、通过或不通过的两分法，把材料不足、签名者未知、锚定缺失等情形压缩进“不通过”，其后果是真实风险与形式不合规无法区分，长期看会诱导实现方以降低检查项的方式规避失败。

（4）缺少可失败的判定表。判定项的依据来源、覆盖关系与相互耦合未见系统披露，外部无法复核“每一项是否真被检查”，也无法判断某一攻击是否只被一项检查拦住。

本文以四点缺口为立论依据，不求在判定强度上超过已有工作，而求在判定边界的明确性、离线可完成性与裁决语义的完整性上有所补充。

## 1.3　研究目标与研究内容

研究目标是构造一套面向智能体行为证据的离线可验证封装方法，使证据边界在包内即被确定，并使判定在无网络条件下可完成、可复算、可被第三方重跑，且在证据不足时明确拒绝作答。具体内容包括四项。

（1）证据边界的建模。给出包内必须携带的边界要素：内容摘要、索引元数据、树规模、链头与外部观察时间，并说明每一要素排除哪一类歧义。

（2）封装格式的构造。确定包布局、字段语义、规范化序列化规则与签名覆盖范围，使不同实现就同一份内容产生同一摘要。

（3）判定器的构造与判定表的给出。形成 20 项判定项，按依据分为草案明文规定、思想来源与本文自定三类，自定项逐条注明无条款可引；以 37 个攻击用例检验判定项的可触发性与耦合关系。

（4）实证。包括内部测量（判定表、攻击矩阵、覆盖、延迟）与外部复核（在他人公开材料上检验一条可证伪的声明），并明确两类证据来源不同，不得混用。

## 1.4　研究方法与技术路线

方法上采取“可复算优先”的取向：凡写进论文的数字，必须由仓库内脚本生成，并在表下注明命令；凡引用他人材料，必须给出可直达的来源；凡本文自定的加固项，必须注明其无条款可引。技术路线分五步。

第一步，条款梳理。取 SCITT 系列草案与相关 RFC 原文入库，逐条摘出与判定相关的明文规定，形成“条款—判定项”的映射，映射不成立者不强行归入。

第二步，边界建模与格式构造。以内容摘要定对象、以树与证明定位置、以签名与规范化定完整性、以时间戳与链头定时序，四者合成一个可在离线状态判定的边界。

第三步，判定器与第二实现。构造主判定器，另以独立路径实现第二判定器，两者对同一批语料交叉比对，以此代替单实现的自我验证。

第四步，攻击矩阵。设计 37 个攻击用例，逐一运行，记录其触发的判定项，观察是否存在未被任何攻击触达的判定项，以及是否存在只被单一判定项拦住的攻击。

第五步，外部复核。选取一份他人公开的对照实现，在其语料上执行一次单字段改动，观察其驱动是否停下并把失败指向该字段。此步只检验对方声明的可证伪性，不作优劣判断。

上述五步的产出均以可执行脚本与文本记录的形式留档，使读者可在不看本文结论的情况下自行复算并得出相同或相反的结果。

## 1.5　论文结构安排

全文共六章。第 1 章为绪论，交代问题、现状与路线。第 2 章梳理相关工作与标准依据，把本文引用的条款逐条落到原文位置。第 3 章给出证据边界的建模与封装格式，为方法主体。第 4 章给出判定器的构造与实现，含 20 项判定项的依据分类与攻击矩阵设计。第 5 章为实证，含内部测量与外部复核两部分，并说明两类证据的适用边界。第 6 章给出结论与局限，逐项列出本文不能主张的内容。

## 参考文献（第一批，著者-出版年制）

以下 30 条均经核实：标准与草案类可在 IETF 与 RFC Editor 站点直达，学术类可在其发布页直达。凡未能取得发布页者一律不入表。

严宇萍, 谢雨晗, 俞恒杰, 金耀初. 2026. 面向可信的群体智能与AI智能体：威胁、对策与展望[J]. 计算. DOI:10.11991/cccf.202603009.

全国信息与文献标准化技术委员会. 2015. 信息与文献　参考文献著录规则: GB/T 7714—2015[S]. 北京: 中国标准出版社.

全国信息与文献标准化技术委员会. 2006. 学位论文编写规则: GB/T 7713.1—2006[S]. 北京: 中国标准出版社.

国家技术监督局. 1993. 量和单位: GB 3100～3102—93[S]. 北京: 中国标准出版社.

IETF. 2001. Internet X.509 Public Key Infrastructure Time-Stamp Protocol (TSP): RFC 3161[S].

IETF. 2008. The Base16, Base32, and Base64 Data Encodings: RFC 4648[S].

IETF. 2013. Certificate Transparency: RFC 6962[S].

IETF. 2017. Ed25519: EdDSA Edwards-curve Digital Signature Algorithm: RFC 8032[S].

IETF. 2019. JSON Canonicalization Scheme (JCS): RFC 8785[S].

IETF. 2021. Certificate Transparency Version 2.0: RFC 9162[S].

IETF. 2026. draft-noa-scitt-ai-agent-receipt-00[S/OL].

IETF. 2026. draft-maintainer-1f916-agent-record-01[S/OL].

IETF. 2026. draft-sharif-agent-audit-trail-03[S/OL].

IETF. 2026. draft-marques-asqav-compliance-receipts-01[S/OL].

IETF. 2026. draft-bailey-scitt-agent-session-receipt[S/OL].

IETF. 2026. draft-mih-scitt-agent-action-capsule-05[S/OL].

IETF. 2026. draft-mih-agent-disclosure-envelope-00[S/OL].

IETF. 2026. draft-pidlisnyi-aps-04[S/OL].

IETF. 2026. draft-munoz-scitt-permit-profile-01[S/OL].

IETF. 2026. draft-emirdag-scitt-ai-agent-execution-00[S/OL].

IETF. 2026. draft-kamimura-scitt-refusal-events-03[S/OL].

IETF. 2026. draft-sato-soos-gar-08[S/OL].

IETF. 2026. draft-sergeev-wexp-core-02[S/OL].

White R, Caiazza G, Cortesi A, et al. 2019. Black Block Recorder: Immutable Black Box Logging for Robots via Blockchain[J]. IEEE Robotics and Automation Letters, 4(4).

Raman R K, Vaculin R, Hind M, et al. 2019. A Scalable Blockchain Approach for Trusted Computation and Verifiable Simulation in Multi-Party Collaborations[C]//IEEE International Conference on Blockchain.

Wright C S. 2025. On Immutable Memory Systems for Artificial Agents: A Blockchain-Indexed Automata-Theoretic Framework Using ECDH-Keyed Merkle Chains[EB/OL]. arXiv:2506.13246.

Chong Z K, Ohsaki H, Ng B. 2025. Tractable Asymmetric Verification for Large Language Models via Deterministic Replicability[EB/OL]. arXiv:2509.11068.

Vispute N, Kadam A. 2026. Reasoning Provenance for Autonomous AI Agents: Structured Behavioral Analytics Beyond State Checkpoints and Execution Traces[EB/OL]. arXiv:2603.21692.

Ghosh B. 2026. Tracekit: Tamper-Evident Intent–Reasoning–Action Auditing for AI Agents[EB/OL]. arXiv:2609.35659.

Bindschaedler L, Botha Q, Siebenbrunner C. 2026. Agent Flight Recorder: Tamper-Evident Audit Trails with On-Chain Anchoring for Long-Horizon Tool-Using Agents[EB/OL]. arXiv:2609.01931.

Bhutto A M. 2026. LATTICE: Ledgered Agent Traces for Transparent, Inspectable Collaborative Execution — Content-Addressed Accountability for Multi-Agent AI Systems[EB/OL].

Zhang J. 2026. Right to History: A Sovereignty Kernel for Verifiable AI Agent Execution[EB/OL]. arXiv:2602.20214.

Narajala V S, Bhatt M, Habler I, et al. 2025. MAIF: Enforcing AI Trust and Provenance with an Artifact-Centric Agentic Paradigm[EB/OL]. arXiv:2511.15097.
