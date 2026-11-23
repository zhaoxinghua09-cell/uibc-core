# 测试台账机器化 —— 候选补丁包（未应用）

**性质**：候选 PR 方案，仅新增文件。**未修改任何仓库。**
**日期**：2026-11-19
**仓库**：`zhaoxinghua09-cell/uibc-core`，HEAD `2eb9763`

---

## 1. 为什么做这个

任务书第二轮 P0-1 原文：

> 核实 543 项测试及跳过项。统一 543 / 527 / 328 等历史测试数字及对应命令。

实测结果：

- **"543" 在整个仓库里 0 次出现**（`*.md` 全文扫描）。它不是真实数字，是任务书里传下来的一句话。
- 仓库里真实存在的历史数字有 **549 / 529 / 527 / 507 / 328 / 305**，分散在 README、AGENTS.md、CHANGELOG、EVIDENCE-INDEX，**彼此矛盾**。
- 每一个都没有绑定 commit SHA、命令、Python 版本、依赖集合。

所以问题不是"数字错了"，是**数字根本无法核对**。这轮把它变成可复算的台账。

---

## 2. 实测结果（本轮真实跑出来的）

```
commit      2eb97631c1202d892721faaf595f486adc3c9beb   (main, dirty=True)
python      3.13.18        pytest 9.2.0        Windows
collected   642
passed      617
failed      1
errors      0
skipped     24
duration    103 s
```

**必须写清的局限**：克隆树 `dirty=True`（里面有此前的构建产物与实验文件），
所以这组数字对应的是"`2eb9763` + 本地若干未提交产物"，**不是干净的 `2eb9763`**。
要拿到干净数字，必须在干净检出上重跑——CI 里是干净的。

---

## 3. 文档数字 vs 实测（机器扫出来的漂移，20 条）

| 文件:行 | 声称 | 实测 | 差 |
|---|---|---|---|
| `README.md:26` | 549 | 642 collected / 617 passed | −93 / −68 |
| `README.md:48` | 549 | 同上 | 同上 |
| `README.md:146` | 549 | 同上 | 同上 |
| `README.en.md:57` | 549 | 同上 | 同上 |
| `AGENTS.md:34` | 549 | 同上 | 同上 |
| `CHANGELOG.md:151` | 529 | 同上 | −87 |
| `CHANGELOG.md:194` | 527 (skipped=2) | 同上（skip=24） | −90 / skip 差 22 |
| `CHANGELOG.md:560` | 305 | 同上 | — |
| `CHANGELOG.md:578` | 507 | 同上 | — |
| `EVIDENCE-INDEX.md:21` | **328 项通过** | 617 passed | **−289** |

**结论**：`EVIDENCE-INDEX` 的 V1 行落后 289 项。它还是"证据索引"的主表第一行。

`288 / 143` 这两组是外部语料向量数（V4 / INTEROP-REGISTRY），与本地套件不是同一口径，扫描器只是把它们也列出来了，**不算漂移**——脚本把"外部语料数"和"本地套件数"混在一张表里，这本身是口径问题，需人工确认。

---

## 4. 那 1 个失败：平台性，不是产品缺陷

```
FAILED tests/test_robustness.py::TestHostileInput::test_every_hostile_input_is_answered_and_refused
  → tools/redteam_robustness.py 退出码 1
```

复跑 `tools/redteam_robustness.py` 看到：

```
symlink-out  JS=INCONCLUSIVE  PY=INCONCLUSIVE  PROBLEM
9 of 10 hostile inputs answered by both implementations and refused
```

根因：本机创建符号链接失败——

```
OSError [WinError 1314] 客户端没有所需的特权
```

即 Windows 未开开发者模式/无符号链接权限，`symlink-out` 这个用例无法构造，两个实现都返回 `INCONCLUSIVE`，harness 把它记为 PROBLEM。

**判定**：
- **FACT**：在该 Windows 主机上，1 个用例因符号链接权限失败。
- **INFERENCE**：Linux CI 上大概率绿（Linux 普通用户可建符号链接）。
- **NOT VERIFIED**：GitHub CI 当前是否绿，我未查。
- **不能说**"主分支是红的"——只能说"在 Windows 上红"。这是两件事。

---

## 5. 改了什么（只新增 3 个文件）

| 文件 | 作用 |
|---|---|
| `tools/gen_test_ledger.py` | 跑 pytest（junit-xml），产出绑定 commit/Python/pytest/依赖/命令/时长的台账 JSON |
| `tools/scan_claims.py` | 扫 `*.md` 里的数字声称，与台账对齐，输出漂移清单（只报告，不改文档） |
| `.github/workflows/test-ledger.yml` | CI：每次 push 生成台账 + 扫漂移，台账作为 artifact 上传 |

台账结构（`test-ledger/1`）：

```json
{"schema":"test-ledger/1","generated_at":"...","duration_seconds":103,
 "command":"python -m pytest -q --tb=no ...","scope":"(whole repo)",
 "git":{"commit":"2eb9763...","branch":"main","dirty":true,"git_exe":"...git.CMD"},
 "env":{"python":"3.13.18","pytest":"9.2.0","platform":"Windows-..."},
 "deps":["cryptography==50.0.2","fastmcp==4.2.0","pytest==9.2.0", ...],
 "totals":{"collected":642,"passed":617,"failed":1,"errors":0,"skipped":24},
 "skipped_detail":[{"test":"...","reason":"pip install agent-action-capsule"}, ...],
 "failed_detail":[...],
 "ledger_digest":"sha256(...)"}
```

`skipped_detail` 是关键：24 条 skip 逐条带原因（缺 `agent-action-capsule`、缺 `agent_evidence_vectors` 语料）。任务书要求"核实跳过项"，这才叫核实。

---

## 6. 验证

| 项 | 结果 |
|---|---|
| 真实跑全套并生成台账 | **成功**，642/617/1/24，103 s |
| 漂移扫描 | 40 条声称，20 条漂移，输出 `claims.json` |
| workflow YAML 解析 | 6 个 step，通过 |
| `git apply --check`（原仓） | **exit 0** |

自跑命令：

```powershell
python tools\gen_test_ledger.py --repo . --out evidence/test-ledger.json
python tools\scan_claims.py --repo . --ledger evidence/test-ledger.json --out evidence/claims.json
```

---

## 7. 剩余风险

| 风险 | 级别 | 说明 |
|---|---|---|
| 台账在 dirty 树上生成 | P1 | 数字对应"commit + 本地产物"，不能直接当干净基线；CI 里才是干净的 |
| 跑全套 100 s+ | P3 | CI 可接受；本地迭代建议 `--scope tests/test_x.py` |
| 扫描器会误抓外部语料数（288/143） | P2 | 已在报告里区分口径，但脚本本身不区分，需加白名单 |
| Windows 上 1 例必红 | P2 | 建议给该用例加 `skipUnless(能建符号链接)`，否则 Windows 开发者永远看到红 |
| CI 未固定 action SHA | P2 | workflow 内已留 TODO |

---

## 8. 建议的动作顺序

1. 先给 `test_robustness` 的 symlink 用例加平台跳过条件（否则"全绿"永远做不到）。
2. 合并台账 workflow，让 `evidence/test-ledger.json` 成为**唯一真源**。
3. 再把 README / EVIDENCE-INDEX 里的硬编码数字改成"见 `evidence/test-ledger.json`"，而不是写死 549/328。

第 3 步必须人工做——我不改文档数字，因为那等于替你们决定"该写多少"。

---

## 9. 累计：四个 P0 的产物

| P0 | 目录 | 用例 | 可应用 |
|---|---|---|---|
| MedXpert 时效统一 | `p26_medxpert_freshness/` | 12 + 7 | 是 |
| LGD-Eval 评测/授权分离 | `p27_eval_authz/` | 18 | 是 |
| UIBC 版本一致性 | `p28_version_gate/` | 13 | 是 |
| UIBC 测试台账 | `p29_test_ledger/` | 真实跑 642 项 + 漂移扫描 | 是 |
