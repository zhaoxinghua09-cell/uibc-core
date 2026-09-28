# LGD 三律（Three Laws）— LGD Core Spec v0.1

```
© 2026 赵兴华 / Steven Zhao·China (ORCID 0009-0001-0512-1237). All rights reserved.
本件为理论文本，不在 Apache-2.0 覆盖范围内，保留所有权利。
```

> **硬规则 R41：三律并列，非递进。**
> LGD-I / LGD-II / LGD-III **不设先后、不设权重、不互推**；任一律都不是另一律的前提，也不是另一律的结论。
> 三者构成**并列的合规面**：一份 manifest 须同时满足三律，方为合规（见 `SPEC.md` §3 L2）。

---

## 并列关系图

```
        ┌─────────────┐   ┌─────────────┐   ┌─────────────────┐
        │  LGD-I      │   │  LGD-II     │   │  LGD-III        │
        │  有籍       │ ∥ │  有证       │ ∥ │  有门禁         │
        │  identity   │   │  evidence   │   │  governance     │
        └─────────────┘   └─────────────┘   └─────────────────┘
              ┃                 ┃                   ┃
              ┗━━━━━━━━━━━━━━━━━┻━━━━━━━━━━━━━━━━━━━┛
                       同时满足 = 合规
```

（∥ 表示并列，不表示先后。三个方框之间无箭头。）

---

## LGD-I 有籍（identity）

**定义**：被治理对象**可被声明**——它是什么对象、由谁负责、以哪个版本被声明。有籍即"查得到责任主体与声明版本"。

**对应 MANIFEST 字段**：

| 字段 | 要求 |
|---|---|
| `subject.id` | 非空；对象标识符 |
| `identity.owner` | 非空；责任主体 |
| `identity.version` | 非空；声明版本 |

（`subject.type` 亦为 schema 必填，用于标注对象类型；上列三字段为「有籍」的校验判据。）

**校验方式**：

```bash
python VALIDATOR/validate_manifest.py <manifest>
```

`validate_manifest.py` 中对应 `IDENTITY_FIELDS` 检查块；任一字段缺失或为空 ⇒ 输出 `[LGD-I 有籍] ...` ⇒ FAIL。

---

## LGD-II 有证（evidence）

**定义**：声明所要求的**证据可指向**——需要证据时，证据条目存在，且每条都能追到**来源**与**日期**。

**对应 MANIFEST 字段**：

| 字段 | 要求 |
|---|---|
| `evidence.required` | 布尔值，必填 |
| `evidence.items` | 当 `required=true` 时必填且非空 |
| `evidence.items[].source` | 有 items 时必填，非空 |
| `evidence.items[].date` | 有 items 时必填，非空 |

**校验方式**：

- `evidence.required=true` 且 `items` 为空或缺失 ⇒ FAIL；
- 任一 item 缺 `source` 或 `date` ⇒ FAIL（逐条报 `evidence.items[i]...`）。

---

## LGD-III 有门禁（governance）

**定义**：治理**门禁可执行且可留痕**——门禁清单存在且含审计门禁；审计开关为开、审计记录不可篡改。

**对应 MANIFEST 字段**：

| 字段 | 要求 |
|---|---|
| `governance.gates[]` | 非空数组；取值枚举 `authorization` / `safety` / `audit`；**须含 `audit`** |
| `audit.logging` | 必须为 `true` |
| `audit.immutable` | 必须为 `true` |

**校验方式**：

- `gates` 为空或不含 `audit` ⇒ FAIL；
- `audit.logging` 或 `audit.immutable` 非 `true` ⇒ FAIL。

---

## 三律与合规等级

| 律 | 违反时的输出前缀 | 对应 `SPEC.md` |
|---|---|---|
| LGD-I | `[LGD-I 有籍]` | §2.2 字段表 |
| LGD-II | `[LGD-II 有证]` | §2.2 字段表 |
| LGD-III | `[LGD-III 有门禁]` | §2.2 字段表 |

三律同时满足 ⇒ validator 输出 `RESULT: PASS`（exit 0）；否则 `RESULT: FAIL`（exit 1）。
达到 PASS 只表示符合本规范的三律判据，**不构成**任何认证、背书或监管认可（见 `COMPLIANCE.md`）。

---

## 权属宣告与状态

> 状态：**v0.1 草案**；截至本草案，**未经任何第三方评审**；已公开（2026-09-28 授权推送）。

```text
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
