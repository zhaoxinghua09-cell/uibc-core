# 检查项参考手册（`tools/build_checks_reference.py` 生成）

20 项检查各自回答一个问题。**最后两列是给评审看的**：有没有外部规范说要这么做，以及失败时它说什么。

| 检查 | 名称 | 回答的问题 | 依据类别 | 依据说明 | 源码行 |
|---|---|---|---|---|---|
| S0 | verifier robustness | 包根本无法处理时，验证器是崩溃还是给出判定？ | 无 | 异常时也必须给出判定，不得崩溃（本项目自定） | 1243 |
| S1 | package structure | 声明的每个文件都在，且没有多出不该有的文件？ | 草案明文规定 | 回执包的结构与成员（draft-noa-scitt-ai-agent-receipt-00） | 386 |
| S2 | identity consistency | 包自称的 agent 身份与生命周期事件里的一致？ | 草案明文规定 | 主体标识（draft-noa-scitt-ai-agent-receipt-00） | 519 |
| S3 | lifecycle state machine + semantics | 生命周期事件序列合法（类型、顺序、时间），不是伪造的转场？ | 思想来源（非直接规定） | 状态机自定；事件类型集合参照该草案（draft-maintainer-1f916-agent-record-01） | 537 |
| S4 | evidence integrity | 每个证据文件的字节未被改动，且没有指向证据目录之外的符号链接？ | 无 | 内容哈希为通用做法；符号链接围栏为本项目自定的安全加固 | 580 |
| S5 | evidence root | 所有证据的根承诺与清单声明一致（含整条尾部被删除）？ | 思想来源（非直接规定） | Merkle 根的思想；本包的根构造自定（RFC 6962） | 1017 |
| S6 | seal signature | 封条签名有效，且签名覆盖的是当前这份内容？ | 思想来源（非直接规定） | Ed25519 签名；「签名须覆盖当前内容」的组合检查自定（RFC 8032） | 1038 |
| S7 | evidence index metadata | 索引自身的元数据（类型、备注）未被改写（内容哈希看不到这层）？ | 草案明文规定 | 被审计对象的元数据（draft-sharif-agent-audit-trail-03） | 869 |
| S8 | package checkpoint head | 整包状态与封存的检查点一致（能看见被截短的日志）？ | 思想来源（非直接规定） | checkpoint 概念；整状态提交自定（draft-maintainer-1f916-agent-record-01） | 926 |
| S9 | head pinned out-of-band | 包与外部钉住的链头一致（能看见回滚到旧的自洽包）？ | 思想来源（非直接规定） | 链头需在外部被观察；pin 机制自定（draft-bailey-scitt-agent-session-receipt） | 949 |
| S10 | attestation closure declared | 六个证明闭包成分都被声明并给了摘要（只声明，不验内容）？ | 草案明文规定 | 证明闭包六成分（draft-sharif-agent-audit-trail-03 §13.6） | 898 |
| S11 | strict serialization | 序列化严格（重复成员名、非 ECMAScript 数值都会被拒）？ | 思想来源（非直接规定） | JCS 严格序列化；重复成员名拒收为加固（RFC 8785） | 335 |
| S12 | timestamp and identifier strictness | 时间戳与标识符严格（例如 2 月 30 日这样的日期不可能通过）？ | 无 | 时间戳与标识符按不可能值拒收（本项目自定） | 628 |
| S13 | merkle inclusion proofs | merkle 包含证明可复算，且证明与被证明项对应？ | 思想来源（非直接规定） | 包含证明的构造；本包证明格式自定（RFC 6962） | 687 |
| S14 | strict base64 | base64 严格（缺填充、混入杂字符都不接受）？ | 思想来源（非直接规定） | 严格 base64：不得缺填充、不得混入杂字符（RFC 4648 §4） | 724 |
| S15 | anchor event resolution | 锚定事件可解析，锚覆盖的根可由包内内容重算出来？ | 无 | 锚定事件解析与根重算（本项目自定） | 750 |
| S16 | external timestamp (RFC 3161) | 存在真实的第三方时间戳（RFC 3161），且它覆盖的是本包的链头？ | 草案明文规定 | 时间戳协议本体；「须覆盖本包链头」的判定自定（RFC 3161） | 766 |
| S17 | linear receipt chain | 收据链线性、无分叉、无伪造的创世前驱？ | 草案明文规定 | 收据与摘要（draft-marques-asqav-compliance-receipts-01） | 833 |
| S18 | policy artefact resolution | 策略产物存在，且其摘要与收据引用的摘要一致？ | 草案明文规定 | 摘要须可解析（draft-marques-asqav-compliance-receipts-01 §4.2.4） | 854 |
| S19 | freshness state | 包比这个验证器上次接受的那份更新（而不是一个更旧但签名合法的包）？ | 思想来源（非直接规定） | 新鲜度只能由外部状态判定，签名不蕴含时间顺序；高水位记忆机制为本项目自定（draft-bailey-scitt-agent-session-receipt） | 981 |

## 关于「外部依据」这一列

草案明文规定 7 项；思想来源 9 项；完全自定 4 项（S0, S4, S12, S15）。

三类的区别不是措辞，是责任：第一类写「按某草案要求」，第二类只能写「借鉴某处思想」，第三类必须写「本项目自定」。**混写会被抓住。**

这不是缺陷，但**必须照实写**：论文里不能说「依据国际标准规定」——只能说「参照若干 IETF 草案，其余为本项目自定」。评审一旦发现把自定项说成标准项，整篇的可信度都会受影响。

## 每项失败时它说什么（源码原话，可用于复现时的比对）

- **S5**：skipped: evidence missing or S4 failed
- **S6**：Ed25519 seal records no valid public_key
- **S7**：evidence/index.json metadata does not match
- **S8**：state does not match the sealed checkpoint_head
- **S9**：package checkpoint does not match the pinned
- **S10**：closure is incomplete or malformed:
- **S15**：verifier lacks asn1crypto; a token in the package
- **S16**：verifier lacks asn1crypto; a token in the package
- **S17**：evidence/index.json metadata does not match
- **S18**：evidence/index.json metadata does not match
- **S19**：no agent_id or freshness_head.subject: a
