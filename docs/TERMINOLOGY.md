# Terminology alignment · 术语与上游对齐

本文件存在的唯一目的：让评审方一眼看清**哪些词是我们的、哪些是复用的、哪些我们明确不做**。
凡此处未列出的词，一律视为本仓库自用表述，不得引作标准术语。

## 0. 一句话

我们不主张新形态；我们主张的是**裁决纪律**：在观测到的证据边界内，把"验过了 / 验不过 / 验不清"
分开处理，且永不把"验不清"洗成"通过"。承载它的位置是**多条异源记录组成一个案子后的确定性判定**。

## 1. 同名或上下位关系

| uibc 用词 | 上游用词（出处） | 关系 | 强度差异 |
|---|---|---|---|
| 证据包 package（manifest + identity + lifecycle + evidence/index + seal） | Package Digest（`draft-raskar-scitt-agent-provenance-00`）；AIVS bundle（`draft-stone-aivs-01`） | 同形态 | **AIVS 更省事**：其自验脚本只需 Python3 标准库；我们的 COSE 路径需 pycose / cbor2 |
| 证据根 evidence_root | Package Digest / Merkle root（RFC 6962） | 同类 | 我们是"排序后内容哈希再做 sha256"的**单层根**，无 Merkle 树、无包含证明 |
| `checkpoint_head`（S8 自洽 / S9 带外钉扎） | RFC 6962 STH；`draft-maintainer-1f916-agent-record-01` 的 5 分钟 checkpoint | 同类不同强度 | 我们是"生命周期 head + 证据根 + 索引元数据 + 条数"的单哈希；无一致性证明、无见证人联署 |
| 三值裁决 PASS / FAIL / INCONCLUSIVE | EP-AEC 现行 `-08` 的 `SATISFIED / UNSATISFIED`（`-02` 的五档词汇在 `-08` 中已 0 次出现） | **不同问题** | `-08` 分离"验证/接受"并用 bounded reason codes 细分失败，三值不能再称"粗化投影" |
| （不输出）决策 | GAR-08 `governance_decision` = ALLOW / DENY / ESCALATE / SUSPEND | **正交两维** | GAR 答"放不放行"，我们答"验不验得清"。两者不可互相替代 |
| （不输出）结果 | capsule / bilateral-attestation 的八值词表 `executed / blocked / denied / timeout / errored / deferred / expired / escalated` | 复用而不自造 | 若将来需要记录结果，直接抄这八值 |
| `trust_level` = anchored / unanchored / unattested | 1F916 `witnessed`（独立见证人联署） | **真子集** | `witnessed ⊃ anchored ⊃ unanchored`；我们没有见证人，故**永不得**声称 witnessed |
| 生命周期状态机（REGISTERED / ACTIVATED / SUSPENDED / REVOKED / RETIRED 等 5 态） | 无直接对应 | 独立 | 与 EP-AEC 的**证据组合判定**不是同一对象，勿混 |
| `principal_type`、`sequence_number`、`policy_hash` | noa-01 逐字枚举；GAR-08 `cap_profile_hash` | **逐字复用** | 一字段同时满足两家，改一个字母都要重编文档 |
| 门禁 ALLOW / HOLD / DENY | APort OAP 的 pre-action authorization；COGITATOR 的 phantom entry | 同目的 | 我们唯一可辩护处：判据是"**PASS + anchored 才放行**" |
| 证据边界 evidence boundary | AAT-03 的 **Attestation Closure**（闭包外任一组件 = 伪造通道） | **弱化版** | 我们只覆盖包内文件；AAT 覆盖到权重/分词器/模板/引擎/数值环境 |

## 2. 明确不做

1. 不自建 `uibc://` URI scheme —— 没有注册机构，自称 scheme 只会制造无效引用。
2. 不自造生命周期事件名 —— 复用 GAR 的 ALE 六类。
3. 不复刻 OTel 命名空间 —— 复用 `soos.*`，仅追加 `uibc.verdict` 与 `uibc.rule_id`。
4. 不做单一评分 / 排名 —— GAR 与 ERC-8004 都禁止把多维信号压成一个分数。
5. 不声称"任何人可离线验证" —— 准确说法是"装好依赖即可离线验证"（比 AIVS 差一步）。

## 3. 我们的空位（对外主句的出处）

`draft-mih-agent-accountability-conformance-00` 摘要指出：`draft-kuehlewind-audit-architecture-00`
列出 WI-1…WI-11，**没有一项覆盖 composition verification** —— 即"由不同方、不同 profile 产出、
被组合成一个案子的多条记录，审计方如何确定性且可测试地判定其自洽并得出结论"。

uibc 的位置就是这一项：**多个证据包 → 一次裁决**，并且裁决是三值 fail-closed 的。

## 4. 版本与不可变标识

- `SPEC_VERSION = "uibc-core/0.3.0-proposal"`：字面常量，不依赖已安装的 dist 元数据（干净 clone 亦同）。
- `SPEC_ID = "<SPEC_VERSION>@<sha256 前 12 位>"`：对本包全部 `.py` 内容按文件排序取摘要，
  使"版本号相同、字节不同"无法冒充。查看：`python -c "import uibc_core as u; print(u.spec_id())"`。
