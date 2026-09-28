# 合规测试（Compliance Test）— LGD Core Spec v0.1

```
© 2026 赵兴华 / Steven Zhao·China (ORCID 0009-0001-0512-1237). All rights reserved.
本件为理论文本，不在 Apache-2.0 覆盖范围内，保留所有权利。
```

> 本件说明**第三方如何自行做一次 LGD 合规测试**（`SPEC.md` §3 的 L3 流程）。
> 状态：v0.1 草案。**受理渠道待发布后公布**——v0.1 阶段暂不接收外部提交。

---

## 0. 前置条件

| 项 | 说明 |
|---|---|
| Python | Python 3（本目录 validator 与 tests 只用标准库；`--schema` 需环境装有 `jsonschema`） |
| 待测物 | 一份待测主体的 `LGD Manifest`（YAML 或 JSON，格式见 `SPEC.md` §2） |
| 目录 | 本规范目录 `LGD-Core_v0.1/` |

## 1. 准备 manifest

按 `SPEC.md` §2 字段表填写一份 manifest。可先从示例起步（`EXAMPLES/`），再替换为你自己的对象与字段值。

## 2. 跑 validator

```bash
cd D:/Workbuddy/08-理论体系/LGD-Core_v0.1
python VALIDATOR/validate_manifest.py <你的 manifest 路径>
```

- 预期输出：`RESULT: PASS`（exit code 0）或 `RESULT: FAIL`（exit code 1）；
- FAIL 时逐条给出律别前缀（`[LGD-I 有籍]` / `[LGD-II 有证]` / `[LGD-III 有门禁]`）。

可选的严格 schema 校验：

```bash
python VALIDATOR/validate_manifest.py --schema <你的 manifest 路径>
```

## 3. 跑测试套件（复现规范自身用例）

```bash
cd D:/Workbuddy/08-理论体系/LGD-Core_v0.1
python -m unittest discover -s TESTS -v
```

记录用例数与结果（`OK` / 失败数），作为报告的一部分。

## 4. 按模板报告结果

复制下方模板，逐项填「实录」，勿改写判据列。

```markdown
# LGD Compliance Test Report（v0.1）

- 待测主体（subject）：<type> / <id>
- manifest 文件：<路径或附件名>
- 规范版本：LGD Core Spec v0.1
- 环境：<OS / Python 版本>

## A. 三律实测（validator 实录）

| 律 | 判据 | 结果 | 实录（命令与输出片段） |
|---|---|---|---|
| LGD-I 有籍 | subject.id / identity.owner / identity.version 齐备 | PASS/FAIL | <粘贴输出> |
| LGD-II 有证 | required=true 时 items 非空且含 source+date | PASS/FAIL | <粘贴输出> |
| LGD-III 有门禁 | gates 含 audit；logging 与 immutable 均为 true | PASS/FAIL | <粘贴输出> |

- validator 总体结果：RESULT: <PASS/FAIL>（exit <0/1>）

## B. schema 校验（可选）

- 是否启用 `--schema`：<是/否>
- 结果：<PASS/FAIL/跳过（未装 jsonschema）>

## C. 规范自测（record）

- 命令：python -m unittest discover -s TESTS -v
- 结果：<Ran N tests / OK 或失败数>

## D. 声明

- 本报告由报告方自行执行并如实记录；未经验证的结果不得写入本报告。
- **本报告通过 ≠ 任何认证、背书或监管认可。**
- 报告方签名 / 日期：<填写>
```

## 5. 提交（v0.1 阶段）

- **v0.1 阶段暂不接收外部提交**；**受理渠道另行公告**。
- 本规范已公开（2026-09-28 授权推送）；受理与认可安排以后续正式公告为准。

---

## 边界与免责

1. **非认证**：通过本流程（L1/L2/L3）**不构成**任何认证、背书或监管认可，也不代表任何形式的第三方审定结论。
2. **非质量证明**：validator 只核验 `SPEC.md` §2 的字段判据，不评估待测主体的实体质量、安全性或合规性。
3. **自报属性**：报告方须自报执行环境与实录；本规范不对报告方所填内容作核实。
4. **无外部受理**：v0.1 无可提交的受理渠道；任何以本规范名义声称"已受理"或"已获认可"的表述，均不代表本规范方。

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
