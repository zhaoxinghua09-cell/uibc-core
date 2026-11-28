# 第 5 章 实证：可直接引用的表格

**生成方式**：`python3 tools/build_thesis_tables.py`。表中每个数字都来自同仓库脚本的 JSON 输出，读者可用表下注明的命令重跑；本文件不手工维护数字。

## 表 5-1　检查项及其依据分类

| 编号 | 检查内容 | 依据类别 | 依据文本 |
|---|---|---|---|
| S0 | 异常时也必须给出判定，不得崩溃（本项目自定） | 无 | — |
| S1 | 包文件布局（声明的文件都在、无多出文件）为本项目自定；草案规定的是回执载荷字段，不是包的文件布局 | 无 | — |
| S2 | 主体标识 | 草案明文规定 | draft-noa-scitt-ai-agent-receipt-00 |
| S3 | 状态机自定；事件类型集合参照该草案 | 思想来源（非直接规定） | draft-maintainer-1f916-agent-record-01 |
| S4 | 内容哈希为通用做法；符号链接围栏为本项目自定的安全加固 | 无 | — |
| S5 | Merkle 根的思想；本包的根构造自定 | 思想来源（非直接规定） | RFC 6962 |
| S6 | Ed25519 签名；「签名须覆盖当前内容」的组合检查自定 | 思想来源（非直接规定） | RFC 8032 |
| S7 | 索引元数据未可改由内容哈希看不到、需单独摘要，为本项目自定；草案中没有对应条款 | 无 | — |
| S8 | checkpoint 概念；整状态提交自定 | 思想来源（非直接规定） | draft-maintainer-1f916-agent-record-01 |
| S9 | 链头需在外部被观察；pin 机制自定 | 思想来源（非直接规定） | draft-bailey-scitt-agent-session-receipt |
| S10 | 证明闭包六成分 | 草案明文规定 | draft-sharif-agent-audit-trail-03 §13.6 |
| S11 | JCS 严格序列化；重复成员名拒收为加固 | 思想来源（非直接规定） | RFC 8785 |
| S12 | 时间戳与标识符按不可能值拒收（本项目自定） | 无 | — |
| S13 | 包含证明的构造；本包证明格式自定 | 思想来源（非直接规定） | RFC 6962 |
| S14 | 严格 base64：不得缺填充、不得混入杂字符 | 思想来源（非直接规定） | RFC 4648 §4 |
| S15 | 锚定事件解析与根重算（本项目自定） | 无 | — |
| S16 | 时间戳协议本体；「须覆盖本包链头」的判定自定 | 草案明文规定 | RFC 3161 |
| S17 | 收据与摘要 | 草案明文规定 | draft-marques-asqav-compliance-receipts-01 |
| S18 | 摘要须可解析 | 草案明文规定 | draft-marques-asqav-compliance-receipts-01 §4.2.4 |
| S19 | 新鲜度只能由外部状态判定，签名不蕴含时间顺序；高水位记忆机制为本项目自定。机制并不新：draft-chang-delta1-settlement-00 §7.2/§12.4 已要求序号单调、拒绝重放；draft-maintainer-1f916-agent-record 用 checkpoint 加见证方；RFC 9162 的 STH 管的是日志侧。本项目做的是把这条放进离线验包器，作为可选的验证器侧状态，并给出三值裁决口径 | 思想来源（非直接规定） | draft-bailey-scitt-agent-session-receipt |
| S20 | 媒体类型本就是注册表里的闭集词表，类型/子类型有固定语法；但「包内必须声明、且只能声明闭集内的一类」是自定约束，载体（JCS 载荷里的 media_type 字段）也不是哪份草案规定的。来源最近的是 OCI Image Spec 对 mediaType 的必填与枚举，本项目只是把同一思路移到离线验包器，用 12 类闭集判定越界 | 思想来源（非直接规定） | RFC 2045 §5.1 / RFC 6838（媒体类型注册表） |

注：依据类别按「草案或 RFC 明文规定」「思想来源」「本项目自定」三分；标为本项目自定的四项，其 citation 字段为空字符串，论文中不得补写条款号。
数据来源：`python3 -c "from uibc_core import basis; basis.for_check('S1')"`。

## 表 5-2　依据分布

| 依据类别 | 项数 |
|---|---|
| 草案明文规定 | 5 |
| 思想来源（非直接规定） | 10 |
| 无 | 6 |
| 合计 | 21 |

数据来源：`python3 -c "from uibc_core import basis; print(basis.counts())"`。

## 表 5-3　攻击—检查发生矩阵摘要

| 指标 | 值 |
|---|---|
| 受测攻击数 | 37 |
| 使至少一项检查 FAIL 的攻击数 | 35 |
| 仅使一项检查 FAIL 的攻击数 | 32 |
| 未被任何攻击触达的检查 | 无 |
| 参与矩阵的检查项 | 19（不含 S0） |

注：S0 是异常兜底，不属于可被单独触发的检查项，故不进入矩阵；因此此处为 18 项，而表 5-5 的仓库渠道报 19 项（含 S0）。
同时触发多项检查的攻击（耦合项，已在正文注明）：

| 攻击 | 触发的检查 |
|---|---|
| impossible calendar date | S12、S3 |
| deregister an entry, keep the file | S12、S5 |
| rewrite index metadata, content untouched | S7、S8 |

数据来源：`python3 tools/check_matrix.py --json`；逐格矩阵见 `docs/CHECK-MATRIX.md`。

## 表 5-4　同等攻击下两实现的诊断输出比较

| 项 | 本实现 | agent-action-capsule 0.17.0 |
|---|---|---|
| 双方均可表达的破坏类别 | 0 | 0 |
| 报出的具体原因条数 | 0 | 0 |
| 原因可定位到具体文件 | 可以 | 否（定位到缺失字段） |
| 每条原因附依据条款 | 结构化字段 + `uibc explain` | 句内联条款号 |

注：条数差异源于粒度不同，不表示判定能力优劣；对方的单条原因覆盖整个 capsule，本实现的单条原因指向单个文件。
数据来源：`python3 tools/compare_diagnostics.py --json`。

## 表 5-5　同一版本在三处发布渠道的检查覆盖

| 渠道 | 版本 | 报出的检查项数 | 检查项 |
|---|---|---|---|
| archive (DOI) | 0.2.1 | 6 | S1、S2、S3、S4、S5、S6 |
| package (pip) | 0.3.3 | 6 | S1、S2、S3、S4、S5、S6 |
| repository | 0.5.5（未发布） | 21 | S0、S1、S2、S3、S4、S5、S6、S7、S8、S9、S10、S11、S12、S13、S14、S15、S16、S17、S18、S19、S20 |

注：差异源于发布未随仓库推进，非代码差异。
数据来源：`python3 tools/check_release_parity.py --json`。

## 表 5-6　集成实测（单次工具调用热路径）

| 指标 | 值 |
|---|---|
| 计量单位 | 一次 `record()`（含索引重写与证据文件写盘） |
| 中位延迟 | 1.225 ms |
| p99 | 2.156 ms |

注：该口径含写盘与索引重写，与只计校验的亚毫秒数字不可直接比较；正文按同量级表述，不宣称优势。
数据来源：`python3 tools/latency_per_call.py --json`；口径说明见 `docs/LIVE-INTEGRATION.md`。

## 未纳入本章的项（避免超范围陈述）

- 外部第三方独立见证：本实现为 0；对方公开材料记录 13 家第三方实现。
- 在线验证端点：本实现仅有本地端点，未部署。
- macOS 平台与网络挂载场景未测。
- 链尾收据正文不可由包内材料判定（见 `docs/CHECK-MATRIX.md` 中 `(not caught)` 一行）。


