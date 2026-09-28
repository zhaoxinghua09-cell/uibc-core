# LGD Core Specification v0.1

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
> 状态：**v0.1 草案**；截至本草案，**未经任何第三方评审**；已公开（2026-09-28 授权推送）。

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

> 校验口径以 `VALIDATOR/validate_manifest.py` 与 `MANIFEST.schema.json` 为准；本表为二者的人类可读描述。

## §3 合规等级

| 级别 | 名称 | 判据（机器可校验） | v0.1 状态 |
|---|---|---|---|
| L1 | manifest-only | 存在一份符合 §2 的 manifest，三律字段齐备。 | 已定义 |
| L2 | manifest + validator | L1 ＋ `python VALIDATOR/validate_manifest.py <manifest>` 返回 `RESULT: PASS`（exit 0）。可另加 `--schema` 走严格 schema 校验。 | 已定义 |
| L3 | full compliance test | 在 L2 之上，按 `COMPLIANCE.md` 流程跑测试并出具报告。 | **v0.1 不定义为机器可校验**；流程与模板见 `COMPLIANCE.md`，受理与认可口径待发布后公布。 |

- v0.1 只将 **L1、L2** 定义为可机器校验。
- 达到任一级别均**不构成**任何认证、背书或监管认可（见 `COMPLIANCE.md`）。

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

- 版本号依 SemVer。`lgd.version` 的取值受 schema enum 约束（当前仅 `"0.1"`）。
- **v0.1 = 草案**（预发布）；未经第三方评审。
- 演进规则（v0.1 约定）：
  - 向后不兼容的字段增删改 ⇒ 主版本号递增；
  - 向后兼容的字段新增 ⇒ 次版本号递增；
  - 文本澄清、示例补充 ⇒ 修订号递增。
- 新增字段时，validator 与 schema 须同步更新，并在 `TESTS/` 补充对应用例。

## §6 引用

引用本规范（cite as），见本件顶部统一块：

```
uibc-core/CITATION.cff · concept DOI 10.5281/zenodo.22821834
```

- 概念 DOI 指向长期概念记录；精确复现请按 `CITATION.cff` 指定的版本工件。
- 本件不新增任何时间锚；时间锚以统一块内两项为准。
