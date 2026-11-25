# 断言复跑对照表（Claims Register）

> 2026-11-19 建。用途：**把每一句能对外说的话，钉到一条外人能跑的命令上。**
> 规则只有三条：**没有命令的话不对外说；命令必须外人能跑；命令跑不通，就撤回那句话。**

## 为什么要有这张表

竞品都报数字：13,000 个测试、10 项风险全覆盖、p99 < 0.1ms。这些数字有个共同特点——**你没法验**。

这张表反过来做：先列出我们想说哪几句话，再问"这句话靠哪条命令成立"。**命令不存在的，那句话现在就不许说。**

这不是谦虚，是唯一能让"第三方复核"从口号变成动作的办法。

## 一、可复跑（外人五分钟能自己验）

| # | 对外断言 | 复跑命令 | 期望输出 | 不符意味着什么 |
|---|---|---|---|---|
| A1 | 全套件在本机跑绿的前提是装 extras；具体测试数随平台与 extras 变化，本文不钉固定数字 | `python -m unittest discover -s tests -p "test_*.py"` | 末尾一行 `Ran N tests … OK`（带 `.[verify,interop]`）；裸解释器（缺 `cryptography`）会失败；仓内钉定的规范计数在 `STATUS.md` / `EVIDENCE-INDEX.md` | 数字与仓内规范页不符，说明测试被删/改，或规范页过期——两者都要修，不能只改一个 |
| A2 | 本仓构造的 21 类单点篡改、三种模式接受率 9.5% / 4.8% / 0%（该集合不代表全部已知篡改类型） | `python tools/mutation_benchmark.py` | 三行接受率 + `unexplained_accept = 0` | 基准被放宽，或某类拦截失效 |
| A3 | 基准全程不联网 | **断网后**重跑 A2 | 与联网时逐位一致 | 存在隐藏的网络依赖 |
| A4 | **校验核心**零第三方依赖（Ed25519 在仓内实现）；**全量套件**需 `.[verify,interop]` | 新建空 venv、不装任何包，分别跑 `python -m uibc_core.cli demo` 与 A1 | 空 venv：`demo` 通过；A1 成片失败（缺 `cryptography`） | 若空 venv 全套件也绿，说明依赖声明写错；若 `demo` 也失败，说明核心被外部包污染 |
| A5 | `PASS` 的确切含义 | `grep -r "no violation was detected" .` | 命中唯一原句（中英各一处） | 话术漂移，或出现"通过=安全"类改写 |
| A6 | M17 换钥重签属定义域边界 | 对比 open 与 pinned 两种模式结果 | open 放过、pinned 拦住 | 该结论错，须重写 |
| A7 | M20 整包回滚只有 head-pinned 能拦 | 对比三模式结果表 | 仅 head-pinned 拒绝 | 同上 |
| A8 | 文本许可为 CC BY 4.0 | 读 `LICENSE` 与 README 许可节 | 两处一致，无"保留所有权利"残留 | 许可声明冲突，引用者会踩坑 |
| A9 | 三仓首屏互链（定义→执行→技能） | 三仓各跑一次：`for r in uibc-core lgd-theory agent-skills; do curl -sf https://github.com/zhaoxinghua09-cell/$r/raw/main/README.md \| grep -c "zh-guide"; done`（离线则 `git clone --depth 1` 后 `grep -c "zh-guide" README.md`） | 每仓各含另外两仓的 `zh-guide` 链接（计数 ≥2） | 互链断了，"枢纽"不成立 |
| A10 | 技能库规模（119 个技能目录） | 在 `agent-skills` 仓根目录：`ls -d skills/*/ \| wc -l` | `119` | 数字注水，或目录被删 |
| A11 | 整包复核延迟（median / p95 / max，**机器相关量**） | `python tools/latency_probe.py` | Windows/Py3.13：median **19.74** / p95 **26.64** / max **38.75**；Linux/Py3.12：median **7.67** / p95 **7.85** / max **8.44**（2026-11-20）、**7.78** / **8.69** / **10.02**（11-21）、**7.39** / **7.55** / **8.38** 与 **7.20** / **7.27** / **8.20**（11-22 两次，各 n=50）、**31.71** / **35.82** / **36.91**（11-22 晚，干净克隆 + 装 extras，同机同命令 4 倍差）；同时打印 m_M12 `FAIL` 行。**对外只说“数十毫秒量级的单包复核”，不引用小数** | 两机数量级不同属正常（机器相关）；若 m_M12 未被拒，比延迟不符更严重 |
| A12 | 外部引用可达性 | `python tools/check_citations.py` | 逐条打印 HTTP 状态码（可达 200；403/反爬与超时分别标注） | 某条标"可达"实际不可达，等于引用造假 |
| A13 | 红队 16 例：13 拒 / 1 灰区 / 2 定义域放行 | `python tools/redteam_suite.py` | RT05 `INCONCLUSIVE`；RT08、RT10 `PASS`；其余 `FAIL`。RT05 的判定逻辑见脚本内 RT05 分支：删 `seal.json` 后既非完整包亦无篡改证据，故记"无法判定"而不敢判拦 | 出现新的 `PASS` 或新的 `INCONCLUSIVE` 说明拦截面变了，缺口节须重写 |
| A14 | README 里的克隆命令照抄可跑通 | 原样执行 README 的 `git clone --depth 1 --branch main …`，再跑 `python tools/external_node_check.py` | 打印 `CONSISTENT` | 命令失败＝引用正确但操作错误，比 404 更隐蔽（2026-11-20 发现旧版写 `release/v1.1-precheck`，该分支不存在） |
| A15 | 公开合规包**字节自证**（不是结论自证）：下载物、pin、用例三者对得上，且 58 例全过 | `python tools/check_vector_package.py` | 四行 ok（MANIFEST / archive pin / coverage / suite 58/58）；另 `sha256sum -c conformance/MANIFEST.sha256` 独立复算 | 任一行为 FAIL，说明发布物与清单脱节——此时所有"可复跑"的说法都不成立。**边界**：它证明的是"你拿到的字节是我们发布的字节"，不证明用例设计正确，也不证明判定结论必真 |
| A16 | 覆盖矩阵公开且含空白单元：19 项检查中 16 项有用例，S9/S16/S19 无**直接**用例，逐条给出理由与替代验证路径（替代路径不计为向量覆盖） | `python tools/conformance_coverage.py --print` | 打印 `16/19 covered`，并列出 `S9, S16, S19`；`conformance/coverage.json` 的 `reason` 字段写替代路径 | 若某空白项没有 reason，说明是用例缺口而非结构限制——必须补用例，不能补说明 |
| A17 | 突变基准报告 α 也报告 β，并给 Wilson 上界；第二套算子族单列 | `python tools/mutation_controls.py` | 保持型 10 例假拒绝 **0/10**（两模式，上界 ≤27.8%）；第二套算子 11 例假接受 **0/11**（三模式，上界 ≤25.9%）；3 个变异在 `ambiguous_excluded` 里写明裁决理由 | 若只报 α 或把 0 写成“0%”，即违反本法：0/10 的上界仍是 27.8%，不能当日结论 |
| A18 | 竞品 171 条语料里 69 条（40%）能被外人按公开标准复算，69 自洽、0 矛盾、102 不可复算（HEAD `39daf704`） | 抓 `probityai/agent-evidence-vectors` 到 `39daf704`，`python tools/sweep_competitor_corpus.py --dir <…/corpus> --json` | 末行 `TOTAL 171 vectors, replayable without their code 69 (40%), consistent 69, inconsistent 0, not replayable 102`；逐文件 sha256 见收据 `docs/upstream-package/competitor-defects/corpus-sweep-39daf704.json` | 任一数字变动＝语料被改过，或我们的判据被放宽；必须先解释再改文档 |
| A19 | 那个“0 矛盾”是检测器真的会失手才有的：196 处注入改动，183 处被认出，13 处属尺寸歧义，0 处无法解释 | 同一份语料上 `python tools/sweep_mutation_control.py --dir <…/corpus>` | `TOTAL applied 196, detected 183, ambiguous 13, unexplained 0`；收据 `…/sweep-mutation-control.json` | 若 `unexplained` 出现非零，说明漏检而不只是歧义——“0 矛盾”立刻失去支撑，须撤回该句 |
| A20 | 上面 A18、A19 两句，外人**一条命令**就能自己复得，不需要 clone 上游、不需要装任何包 | `python tools/stranger_competitor_check.py`（本机无网则 `--dir <已解包 corpus>`） | `bytes: 171 checked, 171 match` → `sweep: … 69 replayable … 0 inconsistent, 102 not replayable` → `control: 196 applied, 183 detected, 13 ambiguous, 0 unexplained` → `VERDICT: REPRODUCED`；`--json` 输出单个对象 | 任一步 `DIFFERS`／`DIFF`／退出码非 0，说明字节或数字有一处对不上——此时 A18/A19 只能引用“当时那次”的收据，不能对外说“可复得” |
| A21 | 上述 69/0/102 不是某一天的偶然：上游 `22764551`（v0.38.0）与 `39daf704` 两快照之间，171 个文件**零字节变化**，两次扫描同一组数字 | `python tools/compare_corpus_snapshots.py --a …/corpus-sweep-22764551.json --b …/corpus-sweep-39daf704.json` | `22764551 vs 39daf704: IDENTICAL`；`manifest digest 7169d876… / 7169d876…`；`changed 0`；两条收据 totals 逐字段相等 | 判定变 `DIFFERENT` 或摘要不同，说明上游动过这批字节——那时 A18 必须按新快照重跑，旧数字只能标注为“截至 22764551–39daf704” |
| A22 | 收据引用的那批字节若被上游改动，**当天可见**，不需要有人想起来重查 | `python tools/watch_upstream_corpus.py`（定时作业 `upstream-corpus-watch.yml` 每天 03:10 UTC 跑同一命令） | `upstream: <head> (171 files, digest 7169d876…)` → `VERDICT: NO DRIFT`，退出 0；有变动则 `DRIFT` + 点名 changed/added/removed 并退出 1 | 若显示 `DRIFT` 而页面仍写 69/171，说明收据已过期，A18/A20 必须立刻按新快照重跑或标注截止日期 |
| A23 | A18 的 69/171 是**用同一把尺子量出来的**：我们的 63 条 RFC 9162 语料在同一组折叠函数下 **63/63 可复算、63 一致、0 矛盾**，叶摘要 50/50 可重建、自述重构根 57/57 与折叠吻合；另 4 条 `VALID_BUT_SIZE_UNAUTHENTICATED` 单列不计入 VALID | `python tools/measure_own_corpus.py`（`--check` 核对收据，`--selftest` 14 条） | `TOTAL 63 vectors, replayable 63 (100%), consistent 63, inconsistent 0, not replayable 0`；`leaf digests rebuilt 50 of 50 vectors that state one; own reconstructed_root agrees 57 of 57 stated; 4 vectors are VALID_BUT_SIZE_UNAUTHENTICATED`；收据 `docs/upstream-package/measurements/own-corpus-replay.json`（清单摘要 `f9079358…`） | 任一条变为不可复算或矛盾＝我方语料或判据退化，A18 的对照就失去意义；`--check` 报 stale＝向量被改过而收据未更新，文档里的 100% 立刻过期 |

## 二、未建（**这些句子现在不许对外说**）

> 本节曾有三行，其中两行（延迟、引用可达）在 2026-11-19 复核时发现**脚本早已在仓内**（`tools/latency_probe.py`、`tools/check_citations.py`），已移入 A 区 A11/A12，并附上实跑输出。**判断"有没有命令"必须列目录，不能凭印象。**

| # | 想说的那句话 | 缺什么 | 补法 |
|---|---|---|---|
| B1 | 门禁规则命中率 | 根本没有基准集 | 先建 50 条"该拦"与 50 条"不该拦"的标注集，再报准召 |

## 三、结构性不可验证（永远不能靠一条命令证明）

| # | 断言 | 为什么不能 |
|---|---|---|
| C1 | 外部复核节点数 | 只能由**别人**自报，自己数不了自己 |
| C2 | OTS 锚是否已落定 | 依赖外部服务状态，离线不可判定 |
| C3 | "观测边界外"的事 | 边界外本就没观测，谈不上证明 |

**这三条的写法只能是"当前状态 + 日期"，不能写成结论。**

## 四、用它做一次自检（含一次误判的纠正）

第一遍扫（凭印象写表）：判定"延迟数字无脚本支撑"，列为 B1——**判错了**。

第二遍扫（列目录 + 实跑）：

```
tools/latency_probe.py     → base PASS median 19.74ms / p95 26.64ms / max 38.75ms（50 次）
                             m_M12 FAIL  median 18.42ms（10 次）
tools/check_citations.py   → 逐条打印引用 HTTP 状态码
```

两条命令**本来就在仓里**。第一遍之所以判错，是因为当时用的是临时采样脚本 `D:\tmp\lat.py` 的笔记，没有去列 `tools/` 目录。

**这次误判本身是这张表的第一个战果**：它证明"凭印象判断有没有证据"是不可靠的，哪怕判断者是自己。规则因此补了半条——**判断"这句话有没有命令"时必须`ls tools/`，不许凭记忆。**

修订后回扫《凡自治之物》第 1、2 期与三仓 README：

- **A 区**：测试（数随平台/extras 变化，规范计数见 `STATUS.md`）、9.5%/4.8%/0%、PASS 口径、M17/M20 性质、延迟、引用可达、红队 16 例、克隆命令——全部有命令，且已实跑。
- **一处口径不一致（2026-11-20 已修正）**：第 2 期与 README 曾引临时脚本的 p50 18.2ms / p99 33.6ms，与仓内 `latency_probe.py` 的输出不同源。现已统一为仓内命令口径，并按"两台机器、各带日期"并列；单一分位数不再作为卖点。
- **本轮新增的三条（都是抓到自己的错）**：① 测试数曾写 303/313，且与仓内 `STATUS.md` 的规范计数不符，A1 改为"只跑命令、不钉数字"；② "空 venv 仍全绿"不成立，A4 重写为"核心零依赖 ≠ 全套件零依赖"；③ README 的 `--branch release/v1.1-precheck` 指向不存在的分支，新增 A14 专测"照抄命令能不能跑"。
- **B 区**：仅剩门禁命中率一行，尚未在对外材料中使用。
- **C 区**：三仓 README 未将其当作结论使用，仅作状态陈述。

**这就是这张表的作用：先抓到自己一次误判，再抓到自己一处数字不同源。**

## 五、引用别人的文章时怎么用

看到一篇讲 AI 治理的文章，问三件事：

1. 它报的数字，**有没有一条命令**能跑出来？
2. 那条命令**需不需要先信任作者的机器**？
3. 它有没有说**自己没拦住什么**？

三条里答不上两条的，当行业综述读，别当证据用。

---

## 六、竞品对标（2026-11-24 实测，本节只写读数与禁写项）

本节存在的理由：上一轮对外材料里出现过"领先""用例最全"一类说法，而 2026-11-24 把两份对手新版逐节读完、把两个公开仓 clone 下来逐文件统计之后，这些话失去了依据。所以把它们**改成读数**，并把不能说的话列在这里。

| 维度 | 我方读数 | 对手读数 | 判定 |
|---|---|---|---|
| 独立实现 | 1 个（部分接收器） | acta-04 §7：四处实现通过其共享套件，其中三个独立维护的 Python 实现（nobulex / APS governance hook / cryptovalid-opencore） | **落后** |
| 上游采纳 | 无等价记录 | acta 已进入 ASQAV 合规 profile、EMILIA 示例、TRACE verifier、receipt-verify 测试集 | **落后** |
| 一致性套件规模 | 36 条用例（30 条带具名检查） | acta `verifier-vectors/` 167 文件（与本回执相关约 56）；vaara `tests/vectors/` 55 个用例目录 | **落后** |
| 树结构 | Merkle 为强制校验项 | sharif-11 新增 `6.4 Optional Merkle Batch Anchoring`（可选） | 领先，但**不唯一** |
| 拒因具名 | 36 条中 30 条按 S 编号逐条给出 | vaara 75 个 `expected.json` 用语义谓词（`signature_ok`、`back_link_ok`、`records_paired` 等）；acta 期望在 runner 侧，`expected/` 仅 4 行样例链 | 领先（编号化）；限定：vaara 谓词粒度更细、acta 属 runner 判定 |

**因此以下表述不许出现在任何对外材料里**：

1. "全面超越""断崖式领先""行业空白"——三个维度实测落后。
2. "唯一实现 Merkle 校验"——sharif 已把它写成可选项；我方是强制项，不是唯一。
3. "用例最多/最全"——36 < 约 56 / 55。
4. "对手不做期望声明"——vaara 做了，粒度还更细；只能说"我方按检查编号逐条给出"。

**可以保留的表述**：按 S 编号逐条给出期望；36 例在册与字节自证（A15）；核验核心零第三方依赖（A4）；红队与负对照的假接受/假拒绝上界（A17）。

**复跑口径**：本节对手读数来自 `git ls-tree` 级统计与原文摘句，原件在发布前审查包（`S2_peer_repos_20261124.json`、`S2逐节定位_20261124.md`）。对手仓更新后本表即过期，引用前必须重跑。

*本表随每次对外材料更新。表内每一条都可被任何人执行；执行结果与本表不一致时，以执行结果为准，并请开 issue。*
