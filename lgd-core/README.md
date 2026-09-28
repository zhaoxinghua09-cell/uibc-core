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

> 以上权属宣告统一块按 `LGD对外表述规范_v1.2` §3.2 整块复制，未删改。

---

## 一句话定位

**LGD Core Specification v0.1 = LGD 三律（有籍 / 有证 / 有门禁）的机器可校验规范。**

- 指针（可复算）：`VALIDATOR/validate_manifest.py` ＋ `TESTS/`（28 项测试）；
- 复现命令见下方「快速上手」，逐条给出可运行的命令行。

## 分层结构

```
「凡自治之物」                ← 概念层（问题域）
        │
        ▼
LGD Theory — 自治治理原则
        │
        ▼
LGD Core / Spec              ← 本目录（规范层）
        │
        ▼
LGD-I 有籍 · LGD-II 有证 · LGD-III 有门禁   ← 三律（并列，非递进）
        │
        ▼
Compliance / Audit
        │
        ▼
Skills / Agents / Systems
        │
        ▼
UIBC — 挑战 / 验证 / 实验
```

> 命名口径：对外理论名一律为 **LGD**；「凡自治之物」为概念层（问题域）表述，不构成独立理论名。

## 规范中心（8 条目）

| # | 条目 | 内容 | 状态 |
|---|---|---|---|
| 01 | What is LGD | 分层定位与本索引 | ✅ 在位：本文件 `README.md` |
| 02 | Three Laws | 三律定义、对应字段、校验方式（并列非递进） | ✅ 在位：`THREE-LAWS.md` |
| 03 | Specification | Manifest 格式、合规等级、Medical AI Profile、版本演进 | ✅ 在位：`SPEC.md` |
| 04 | Reference Implementation | 参考实现 | 🔗 指向外部仓：`uibc-core`（Apache-2.0，见 `CITATION.cff`） |
| 05 | Compliance Test | 合规测试流程与报告模板；validator ＋ tests | ✅ 在位：`COMPLIANCE.md`、`VALIDATOR/`、`TESTS/` |
| 06 | Examples | 最小 agent / 医疗 AI / 非合规 三示例 | ✅ 在位：`EXAMPLES/` |
| 07 | UIBC | 挑战 / 验证 / 实验 | 🔗 外部：另行规划（本草案不含赛事件） |
| 08 | Research & Papers | 引用与论文入口 | 🔗 外部：`cite as` 见上方统一块（concept DOI `10.5281/zenodo.22821834`） |

## 快速上手

```bash
cd D:/Workbuddy/08-理论体系/LGD-Core_v0.1

# 1) 按三律校验一份 manifest（PASS/FAIL ＋ 逐条原因；exit 0/1）
python VALIDATOR/validate_manifest.py EXAMPLES/example-minimal-agent.manifest.yaml

# 2) 严格 JSON Schema 校验（环境装有 jsonschema 时启用）
python VALIDATOR/validate_manifest.py --schema EXAMPLES/example-medical-ai-agent.manifest.yaml

# 3) 跑测试套件
python -m unittest discover -s TESTS -v
```

## 目录结构

```
LGD-Core_v0.1/
├── README.md
├── SPEC.md
├── THREE-LAWS.md
├── MANIFEST.schema.json
├── COMPLIANCE.md
├── VALIDATOR/
│   └── validate_manifest.py
├── TESTS/
│   ├── __init__.py
│   ├── test_validator.py
│   └── examples/            （夹具：合法×2 ＋ 非法×2）
├── EXAMPLES/
│   ├── example-minimal-agent.manifest.yaml
│   ├── example-medical-ai-agent.manifest.yaml
│   └── example-noncompliant.manifest.yaml
└── LICENSE
```

## 许可分层

| 层 | 载体 | 许可 |
|---|---|---|
| 代码 | `VALIDATOR/`、`TESTS/` | Apache-2.0（见 `LICENSE`） |
| 理论文本 | `README.md`、`SPEC.md`、`THREE-LAWS.md`、`COMPLIANCE.md` | 保留所有权利（不在 Apache-2.0 覆盖范围内） |

## 边界声明

1. **草案**：v0.1 为草案；截至本草案，**未经任何第三方评审**。
2. **已公开**：本目录已随 uibc-core 公开仓发布（2026-09-28，Steven 授权推送）；代码 Apache-2.0，理论文本保留所有权利。
3. **不构成认可**：通过本目录的 validator 或测试，**不等于**任何认证、背书或监管认可。
4. **示例非声明**：`EXAMPLES/` 全部为中性示例（占位符 `placeholder:*` / `YYYY-MM-DD`），不含真实产品名、机构名，也不构成任何未经核实的声明。
