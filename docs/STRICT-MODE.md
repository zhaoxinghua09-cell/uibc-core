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

## 论文里怎么写

- 默认宽松不是疏漏，是**向前兼容**的取舍：收紧会令既有包全部失效。
- 严格模式让「未声明文件」在**新包**上成为可判定的违规，因此可以这样写一句：「本实现提供严格模式，对 `evidence/` 下未声明文件判 FAIL，并豁免格式自身的结构成员（共 5 类）」。
- 不能写成「已完全覆盖」：默认模式仍然只记 note，这句话必须带上模式限定。

## 复跑

```bash
python3 -m unittest tests.test_strict_mode -v
```
