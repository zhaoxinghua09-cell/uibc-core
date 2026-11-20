# SCC-1 的 15 条义务，逐条对我们 20 项检查（2026-11-20）

**先说清对方文件的身份**（避免我方把话说过头）：`draft-watts-scientific-constitutional-constraints-00` 以 individual draft 形式发布在 IETF 归档（2026-11-16，2027-05-20 到期），但正文第 1 节自己写着：

> "This -00 source is a private research candidate prepared for possible future author-controlled review. It has not been submitted to the IETF or adopted by any working group."

所以它是**归档里的个人草案**，不是任何 WG 的工作项。引用时必须带上这句，否则我方就成了"借权威"。

## 逐条对照

判定分三档：**有对应**（已有检查直接管这件事）、**同形**（检查管的是同一类错误，但对象不同）、**无落脚点**（我方格式里根本没有承载这件事的字段）。

| SCC | 义务（原文要点） | 我方状态 | 落在哪 |
|---|---|---|---|
| SCC-01 | 身份与证言有效但没有有效授权，不产生效果准入 | **无落脚点** | 我方格式记录"发生了什么"，不记录"是否准入"；没有 grant/admission 概念 |
| SCC-02 | 客户端自写的 `verification=pass` 不能导致 ALLOW | **同形** | 我方不接受自述结论：`unjudged` 与三值判词把"没查"与"通过"分开（S10/S11/S13 系列） |
| SCC-03 | 缺必需见证 → INDETERMINATE，而不是 ALLOW 或伪造的 FAIL | **有对应** | 三值判词 + `INCONCLUSIVE`（S6 无钥、S5 空索引、`unjudged` 非空） |
| SCC-04 | 为 sink A 签的请求被 sink B 拒绝，即使请求内所有 audience 字段都一致 | **无落脚点** | 我方 manifest 无 `sink_id`，包无法表达"这是给哪个 sink 的" |
| SCC-05 | 校验后被调用方改动，不能改变已提交字节或目的地 | **同形** | S4 证据内容哈希 + S12 标识严格性 + S11 严格序列化：提交的是被哈希过的字节 |
| SCC-06 | 重复 nonce 跨 worker 竞争不能在同一 sink 产生两次提交 | **无落脚点** | 无 nonce、无 sink、无提交序 |
| SCC-07 | 排队的旧 epoch 请求，不能在同一 sink 持久应用并确认更新的 cut 之后提交 | **无落脚点** | 无 epoch、无 cut、无 ack |
| SCC-08 | 未签名/过期/签名者错误的 root hop 不能被后代自证 | **同形** | S6 seal + S16 第三方时间戳 + S9 head 钉定；"hop"概念没有 |
| SCC-09 | 本地 cut 但没有必需的远端确认 → closure UNKNOWN | **无落脚点** | 无 closure 概念；我方只有包级判词 |
| SCC-10 | 未观测但 pin 正确、寻址正确的后代，应按当前 sink epoch 评价而非按错误 audience 拒绝 | **无落脚点** | 无 epoch/audience |
| SCC-11 | 重排或重放的 cut 不能把已推进的 sink epoch 回滚 | **无落脚点** | 无 epoch |
| SCC-12 | 收到的 fencing notice 与已确认的 applied cut 要报成不同证据类型 | **同形** | S4 的类型词表是封闭的，未知类型不明说就不算已查（这条是我方唯一真正实现"类型不许改写"的地方） |
| SCC-13 | clock-skew 导致的过期拒绝，不得改标为撤销 closure 的证明 | **同形** | S15 锚定事件解析 + S16 时间戳，但无"撤销/闭合"标签体系 |
| SCC-14 | 必需 sink 范围为空或未枚举的声明，不能靠空合取通过 | **有对应** | S5（空索引 → INCONCLUSIVE）+ V5（第二实现同样不把空集合判通过） |
| SCC-15 | 若某测试向量的预期本身有缺陷，该向量应隔离，而不是当作保证晋级的神谕 | **同形** | `conformance/oracle/expected.json` + `--emit` 回环复验（漂移即 exit 1）；但我方没有"隔离"状态，只有"改对" |

**计数**：有对应 2（SCC-03、SCC-14）；同形 6（02、05、08、12、13、15）；**无落脚点 7**（01、04、06、07、09、10、11）。

## 这 7 条说明的是什么

不是"我们漏了 7 项检查"，而是**我方格式里没有承载它们的字段**。具体缺 5 个东西：

| 缺什么 | 服务于哪几条 | 最小形态 |
|---|---|---|
| `sink_id`（接收方标识） | SCC-04、SCC-10 | manifest 里一个字段 + 准入侧比对 |
| `audience`（请求声明的受众） | SCC-04、SCC-10 | 与 `sink_id` 分开存，才测得出"字段全一致仍拒绝" |
| `epoch`（单调权威代数） | SCC-07、SCC-11 | 整数 + 单调性约束 |
| `nonce`（一次性消耗） | SCC-06 | 证据条目 + 消耗记录 |
| `cut_ack`（sink 签署的已应用确认） | SCC-07、SCC-09、SCC-11 | 独立证据类型 + 签名者身份 |

这五项一旦进格式，`verify()` 至少能多判 4–5 条；**但在没有真实 sink 的场景里，它们只能被"声明"而不能被"验证"**——这也正是 SCC-1 自己写的那句"single host、single research administration、非跨主机确认"。

## 因此可以对外说的

- 我方在"证据包本身是否被篡改"这一类（S1–S19）上，与 SCC-1 的前 6 条里的 SCC-02/05/08/12/13/15 **同形**，且有三值判词与 `unjudged` 这类"不许把没查说成通过"的机制；
- 我方在"准入、sink、epoch、cut、closure"这一整块（7 条）**没有落脚点**，这是格式缺口，不是检查遗漏；
- 两条"有对应"（SCC-03、SCC-14）是我方现成的可讲点，但**不能**说成"我们实现了 SCC-1"——SCC-1 的定义域是准入与闭合，不是我方的证据完整性。

## 下一步（按成本）

1. **最小格式扩展**：给 manifest 加 `sink_id`/`audience`/`epoch`，作为**可选字段**；缺省不改变既有语料的任何判词（当时 28 例，现 30 例）（这是能保住现有数字的唯一做法）。
2. 为 SCC-04 造两例（同 audience 不同 sink → 必须拒），跑通参考实现与第二实现。
3. SCC-07 需要"提交序"概念，成本最高，放最后。
