# LGD Core Specification v0.2

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

> 本件为**理论文本**，保留所有权利，不在 Apache-2.0 覆盖范围内（见 `LICENSE`）。
> 状态：**v0.2 草案**；截至本草案，**未经任何第三方评审**；v0.1 已公开（2026-09-28 授权推送）。
> v0.1 → v0.2 为**向后兼容的文本澄清**：未增删任何字段，Manifest 格式不变，`lgd.version` 枚举保持 `"0.1"`（变更记录见 §5）。

---

## §1 术语

| 术语 | 定义 |
|---|---|
| LGD Manifest | 描述一个被治理对象（agent / skill / system）身份、证据与门禁的机读声明文件（YAML 或 JSON）。 |
| subject | 被治理对象。 |
| LGD-I 有籍 | 身份律：对象与其责任主体、声明版本须可声明（见 `THREE-LAWS.md`）。 |
| LGD-II 有证 | 证据律：声明所需的证据须存在且可指向来源与日期。 |
| LGD-III 有门禁 | 门禁律：治理门禁须存在，且审计须开启且不可篡改。 |
| 三律 | LGD-I / LGD-II / LGD-III 的合称。**三律并列，非递进**（硬规则 R41）；不设先后、不设权重、不互推。 |
| validator | 本目录 `VALIDATOR/validate_manifest.py`，按三律逐项校验 manifest。 |
| schema | 本目录 `MANIFEST.schema.json`，JSON Schema draft 2020-12，与 §2 字段一一对应。 |
| 合规等级 | §3 定义的机器可校验级别（v0.1 定义 L1、L2）。 |

## §2 LGD Manifest 格式

### §2.1 示例

```yaml
lgd:
  version: "0.1"

subject:
  type: agent
  id: agent.example.minimal

identity:            # LGD-I 有籍
  owner: example-owner
  version: "0.1.0"

evidence:            # LGD-II 有证
  required: false
  items: []

governance:          # LGD-III 有门禁
  gates:
    - authorization
    - audit

audit:               # LGD-III 有门禁
  logging: true
  immutable: true
```

### §2.2 字段表

| 字段 | 类型 | 必填 | 所属律 | 说明 |
|---|---|---|---|---|
| `lgd.version` | string，enum `["0.1"]` | 是 | — | 规范版本。 |
| `subject.type` | string（非空） | 是 | — | 对象类型（如 `agent` / `skill` / `system`）。 |
| `subject.id` | string（非空） | 是 | LGD-I | 对象标识符。 |
| `identity.owner` | string（非空） | 是 | LGD-I | 责任主体。 |
| `identity.version` | string（非空） | 是 | LGD-I | 该对象的声明版本。 |
| `evidence.required` | boolean | 是 | LGD-II | 是否强制证据。 |
| `evidence.items` | array | 当 `required=true` 时必填且非空 | LGD-II | 证据条目列表。 |
| `evidence.items[].source` | string（非空） | 有 items 时必填 | LGD-II | 证据来源。 |
| `evidence.items[].date` | string（非空） | 有 items 时必填 | LGD-II | 证据日期。 |
| `governance.gates[]` | string[]，enum `{authorization, safety, audit}`，≥1 项且不重复 | 是 | LGD-III | 门禁清单；**须含 `audit`**。 |
| `audit.logging` | boolean | 是 | LGD-III | 须为 `true`。 |
| `audit.immutable` | boolean | 是 | LGD-III | 须为 `true`。 |
| `medical` | object | 否 | — | Medical AI Profile（见 §4）。 |

> 本表为规范条文的人类可读描述；规范-实现分歧的仲裁顺序与判定细则见 §2.4（v0.2 新增）。

### §2.4 规范-实现仲裁与判定细则（v0.2 新增）

**仲裁顺序（P1）**：本件（含 §2.2 字段表与三律判据）为**规范真源**；`MANIFEST.schema.json` 与 `validator` 是对文本的机器化实现。三者出现分歧时：

1. 实现与文本不一致 ⇒ **实现缺陷**：修实现向文本对齐，并留修复记录（先例：2026-09-28 EAI-2a 独立席复算发现默认路径漏检 D1–D5，已修复并推送，commit `092ed118fc`）；
2. 确属文本错误 ⇒ 修文本须留变更留痕并递增版本号，不回改已发布历史版本；
3. 两个独立实现对同一 manifest 判定不一致 ⇒ 以本件条文人工裁定，分歧记录 **append-only** 归档；
4. 对外声明 L 级别时，须注明所用 validator 的发布版本或 commit，保证可复现。

**判定细则（P4/P5，与实现逐条对齐）**：

- **非空判据**：字符串须满足 `str.strip() != ""`（纯空白视同空）；
- **枚举匹配**：`lgd.version` 与 `governance.gates[]` 均为**字符串精确匹配**（大小写敏感）；
- **重复判定**：`governance.gates[]` 内同一取值出现多于一次即拒；
- **顶层字段白名单**：`lgd` / `subject` / `identity` / `evidence` / `governance` / `audit` / `medical`；出现其他顶层字段即拒（对应 schema `additionalProperties: false`）；
- **medical 六字段（P5）**：`medical` 对象出现时，`data_source` / `model_version` / `authorization` 须为非空字符串，`evidence` / `clinical_risk_gates` / `audit` 须为字符串数组且元素全为字符串；六字段缺一即 FAIL。

**失败输出机读格式（P6）**：validator 每条问题输出一行，前缀标明来源层——`[LGD-I 有籍]` / `[LGD-II 有证]` / `[LGD-III 有门禁]` / `[结构]`（严格模式下另有 `[schema]`）；末行输出 `RESULT: PASS` 或 `RESULT: FAIL`；进程退出码 PASS=0 / FAIL=1。该格式即机读契约，下游按前缀与退出码解析。

## §3 合规等级

| 级别 | 名称 | 判据（机器可校验） | v0.1 状态 |
|---|---|---|---|
| L1 | manifest-only | 存在一份符合 §2 的 manifest，三律字段齐备。 | 已定义 |
| L2 | manifest + validator | L1 ＋ `python VALIDATOR/validate_manifest.py <manifest>` 返回 `RESULT: PASS`（exit 0）。可另加 `--schema` 走严格 schema 校验。 | 已定义 |
| L3 | full compliance test | 在 L2 之上，按 `COMPLIANCE.md` 流程跑测试并出具报告。 | **v0.1 不定义为机器可校验**；流程与模板见 `COMPLIANCE.md`，受理与认可口径待发布后公布。 |

- v0.1 只将 **L1、L2** 定义为可机器校验；v0.2 沿用并加注（见下）。
- 达到任一级别均**不构成**任何认证、背书或监管认可（见 `COMPLIANCE.md`）。
- **自声明真值标注（P3，v0.2 新增）**：L1 / L2 的全部判据输入（manifest 内容）与判定输出均来自被治理对象或其治理方的**自报（self-attested）**；对外引用 L1 / L2 结论时，须随附 `self-attested` 标注与所用 validator 版本指针（见 §2.4 仲裁顺序第 4 条）。L1 / L2 不构成任何第三方核验。
- **证据豁免标注（P2，v0.2 新增）**：`evidence.required=false` 是被治理对象的**自声明证据豁免**——依此取得的 L1 / L2 属「弱声明」，对外表述须如实注明豁免存在。三律强度不对称是显式设计：LGD-III（audit 门禁）不设豁免，LGD-II 允许自声明豁免但必须可见。

## §4 Medical AI Profile

可选对象 `medical`，用于描述医疗 AI 场景的补充字段。**v0.1 只定义字段与必填性，不定义取值**；全部六字段在该对象出现时均为必填。

| 字段 | 类型 | 必填（`medical` 出现时） | 语义 |
|---|---|---|---|
| `medical.data_source` | string | 是 | 数据来源。 |
| `medical.model_version` | string | 是 | 模型版本。 |
| `medical.evidence` | string[] | 是 | 证据（可引用 `evidence.items[].source`）。 |
| `medical.authorization` | string | 是 | 权限。 |
| `medical.clinical_risk_gates` | string[] | 是 | 临床风险门禁。 |
| `medical.audit` | string[] | 是 | 审计。 |

- 骨架示例见 `EXAMPLES/example-medical-ai-agent.manifest.yaml`（取值全为中性占位符）。
- 说明：真实医疗 AI Agent 跑合规测试**拟经 UIBC 赛事承接，另行规划**；本草案不含该规划的实施内容。

## §5 版本与演进

- 版本号依 SemVer。`lgd.version` 的取值受 schema enum 约束（当前仅 `"0.1"`；v0.2 为文本澄清发布、未改 Manifest 格式，故枚举不变）。
- **v0.1 = 草案**（预发布）；未经第三方评审。
- 演进规则（v0.1 约定）：
  - 向后不兼容的字段增删改 ⇒ 主版本号递增；
  - 向后兼容的字段新增 ⇒ 次版本号递增；
  - 文本澄清、示例补充 ⇒ 修订号递增。
- 新增字段时，validator 与 schema 须同步更新，并在 `TESTS/` 补充对应用例。
- **v0.2 变更记录（向后兼容澄清，格式不变）**：新增 §2.4 规范-实现仲裁（P1）与判定细则成文（P4/P5/P6）；§3 新增 self-attested 标注（P3）与证据豁免标注（P2）；新增 §7 定位边界声明（V3 口径）。既有 manifest 与测试全部兼容（28/28 回归通过）。

## §6 引用

引用本规范（cite as），见本件顶部统一块：

```
uibc-core/CITATION.cff · concept DOI 10.5281/zenodo.22821834
```

- 概念 DOI 指向长期概念记录；精确复现请按 `CITATION.cff` 指定的版本工件。
- 本件不新增任何时间锚；时间锚以统一块内两项为准。

## §7 定位边界声明（V3 口径 · v0.2 新增）

- **不主张优先权**：注册、证据、门禁三类机制在既有治理与监管实践中各有长期先例；LGD 的主张是**把三类机制链成一条全生命周期治理线程**（组合与统一抽象），并给出机器可校验的最小规范（本件）。
- **已核实最近邻（V3 口径）**：就「资格非单调重估（暂停→恢复、吊销→复权、failure 非终局）」这一增量点，语义最近邻为 HAARF C6 自主权治理族——其 MD §6.6.4「advance to higher autonomy levels or be restricted to lower levels」为双向证据驱动调整，与「降级→恢复」循环结构同构；但该素材全 279 条需求中只写降向转换（deactivate / suspend / revoke / restrict / rollback），**无一条定义恢复路径**，亦未裁定 verification failure 的终局性；且其双向调节作用域是运行时自主权级别（operational envelope），不是登记/准入资格状态生命周期。可辩护表述：**HAARF 有「可被降级」但没有「可以被原谅」**（逐条精读与行级引文见 E-1 归档：`LGD-Core_E-1_HAARF语义精读报告_原文_20260929.md`）。
- **口径边界**：V3 的「资格」= **登记/准入资格状态生命周期**（suspend → reinstate），**不外延**至运行时自主权级别调节；未来版本如放宽该口径，须复审最近邻对照并留变更留痕。
