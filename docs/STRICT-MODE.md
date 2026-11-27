# 严格模式：把「已知缺口」变成「可选判定」

## 缺口是什么

`evidence/` 目录下如果出现一个索引未声明的文件，默认判定只记一条 note，不判 FAIL。

这个缺口长期写在文档里，理由是真的：

- 这个格式**自己**就把结构件放在 `evidence/` 下——Merkle 树 `merkle.json`、收据链 `chain.json`、锚定集合 `anchors.json`、策略件 `policies.json` 与 `policies/`；
- 每个结构件都由自己那一项检查解析（S13 / S17 / S15 / S18），不是游离文件；
- 早先试过「未声明即 FAIL」，**十几个既有包当场全部失败**——说明这不是一处补丁，是一次格式版本变更，当时已原样撤回。

## 现在的做法

`verify()` 增加一个参数：

```python
verify(pkg)              # 默认：宽松，未声明文件只记 note
verify(pkg, strict=True) # 严格：未声明文件判 S1 FAIL
```

命令行：

```bash
uibc verify <pkg> --strict
```

**豁免清单**（格式自身放置的结构件，严格模式下仍视为合法）：

| 路径 | 由哪项检查解析 |
|---|---|
| `evidence/merkle.json` | S13 |
| `evidence/chain.json` | S17 |
| `evidence/anchors.json` | S15 |
| `evidence/policies.json` | S18 |
| `evidence/policies/*` | S18 |

豁免清单是**代码里的常量**，不是配置文件；写进 `uibc_core/verify.py` 的 `_EVIDENCE_STRUCTURAL`，改动需过测试。

## 实测行为

| 场景 | 默认 | `--strict` |
|---|---|---|
| 干净包 | S1 PASS | S1 PASS |
| 干净包 + `evidence/extra.txt` | S1 PASS（记 note） | **S1 FAIL**，detail 点名该文件 |
| 带 Merkle 树与收据链的包（v1.1） | S1 PASS | S1 **PASS**（结构件豁免生效） |
| 包根出现未声明文件 | S1 FAIL（原有行为） | S1 FAIL |

四种情形由 `tests/test_strict_mode.py`（5 项）逐一守住，其中一项跑真实 CLI，确认退出码为 1。

## 格式 v2：新包默认就是严格（0.5.6，2026-11-27 已发布到 PyPI）

严格模式只解决"能不能判"，不解决"默认判不判"。默认宽松这件事本身仍是一个可测量弱点：ERM 用同一把尺子打本仓，`M06` 在三档默认模式下都拿到 PASS，而同一族对 proofbundle / proofline 都是 FAIL。本树把它落到格式版本上：

- 生产者（`uibc submit`）在 `manifest.json` 写 `format_version: 2`；
- 验证器读到 **2**，就按严格规则判 `evidence/` 下的未声明文件，**不需要 `--strict`**；
- 读到**缺省或 1**，保持旧行为（note + `warnings` 点名），因为那些包封的时候规则就是那样，不能事后追溯收紧；
- 读到**其他数字**，S1 判 `INCONCLUSIVE`——用 v1 规则去判一个自己没读过的格式，和低于 `min_verifier_version` 却照发 PASS 是同一类错误。

`--strict` 保留，含义不变：对**任何**包强制严格，包括 v1 包。

| 场景 | v1 包（缺省） | v2 包 | `--strict`（任意版本） |
|---|---|---|---|
| 干净包 | S1 PASS | S1 PASS | S1 PASS |
| 干净包 + `evidence/extra.txt` | S1 PASS + `warnings` 点名 | **S1 FAIL** | **S1 FAIL** |
| 带 Merkle 树与收据链 | S1 PASS | S1 PASS（结构件豁免） | S1 PASS |
| `format_version: 3` | — | S1 `INCONCLUSIVE` | S1 `INCONCLUSIVE` |

迁移：v1 包若要获得"默认严判"的保护，用 0.5.6 重新 `submit` 封一次即可，内容不必改；不重封的包继续按 v1 规则被正确判定，只是 `warnings` 会一直点名它放过的文件。

两处细节必须写在这里，因为它们各自都是一个口子：

- **`evidence/.lock` 不算证据**：`uibc_core/locking.py` 会在 `evidence/` 下建一个锁文件。v2 第一版把每个未声明文件都判死，结果**本仓自己刚封的包全 FAIL**。豁免按**名字**做（`_EVIDENCE_NOT_EVIDENCE`），不按"点开头"：`evidence/.payload` 仍然 FAIL，负控写在 `tests/test_strict_mode.py`。
- **结构件豁免不等于"树可以只带部分证明"**：`evidence/merkle.json` 的 `proofs` 必须覆盖每一个索引文件，缺一条 S13 就判 FAIL（本树起，发版后即 0.5.6）。此前 `size 5 / root X / 3 个 proof` 会被读成一棵完整的树——由 `tools/corpus_erm.py` 的 `E2-root-untouched` 打出来的。

`tests/test_strict_mode.py` 15 项守住上表四行与上面两条负控。

## 论文里怎么写

- 默认宽松不是疏漏，是**向前兼容**的取舍：收紧会令既有包全部失效。
- v2 之后这条取舍由**生产者声明**承担：新包默认严判，旧包按旧规则判，两句话都能被同一个验证器说清，因此可以写成「未声明证据在 v2 包中默认 FAIL，在 v1 包中为点名告警」。
- 严格模式让「未声明文件」在**新包**上成为可判定的违规，因此可以这样写一句：「本实现提供严格模式，对 `evidence/` 下未声明文件判 FAIL，并豁免格式自身的结构成员（共 5 类）」。
- 不能写成「已完全覆盖」：默认模式仍然只记 note，这句话必须带上模式限定。

## 复跑

```bash
python3 -m unittest tests.test_strict_mode -v
```
