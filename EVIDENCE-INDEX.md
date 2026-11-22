# EVIDENCE-INDEX — 验到什么程度、证据在哪

> 这张表回答一个问题：**这个仓库的说法，有多少已经被别人（或另一套代码）跑过。**
> 铁律：**验证 ≠ 认可**。本表不登记任何机构背书；`ENDORSEMENTS.md` 第三节的“认可”一栏仍为空。
> 维护规则：新增一次验证，加一行，并写清“谁能重跑、在哪重跑、结果文件在哪”。

## 一、分级（判断一条证据有多硬）

| 级别 | 定义 | 判定要件 |
|---|---|---|
| L1 自我复现 | 同一作者、换环境重跑 | 两次独立运行的原始输出 |
| L2 异体对抗审查 | 不同模型／角色执行，留痕可回溯 | 角色记录、发现条目、处置理由 |
| L3 独立第二实现 | 从规格重建，不 import 主实现 | 交叉比对清单与不一致计数 |
| L3.5 外部语料合规 | 用**别人的**语料与契约驱动本实现 | 语料版本、摘要、逐项结果 |
| L4 第三方外部节点 | 外部方独立跑并回传结果 | 回传的结果文件，而非我们自述 |

## 二、当前记录

| # | 级别 | 事项 | 结论 | 证据与复跑方式 |
|---|---|---|---|---|
| V1 | L1 | 主测试套件 | **1086 例 / `OK (skipped=5)`**（2026-11-23，Windows 11 / Python 3.13.12，`main=3c93973`，305.8 s） | `python -m unittest discover -s tests -p "test_*.py"`（`-s tests` 即可；**不要加 `-t .`**，会报 `Start directory is not importable`；PATH 里要有可执行 `git.exe`，否则两例 `FileNotFoundError`）；Linux 四解释器矩阵由 CI `test` 作业覆盖。**`skipped` 不是定值**（同一套件见过 5 与 7），只以当轮输出为准，不要跨轮对照 |
| V2 | L1 | 压力与规模 | 7 项场景，含内存峰值与倍率 | `python -m unittest tests.stress_test` |
| V3 | L3 | 第二实现交叉校验 | 与主实现逐项对齐，零不一致 | `independent_verifier/cross_check.py`；`tools/lgd_eval.py` |
| V4 | L3.5 | 外部语料合规 | `probityai/agent-evidence-vectors` 0.37.0（suiteRevision 32，digest `bf3e5bef…46e11c1`）：**288 向量，288 通过，0 失败，0 拒绝，0 理由不一致** | `uv tool run "agent-evidence-vectors==0.37.0" --verifier "python -m uibc_core.aee"` |
| V5 | L3.5 | 语言中立一致性语料 | 七步、29 个向量（规范化字节、Ed25519 有效／无效等），固定摘要 | `tools/conformance_vectors.py`；不用本项目实现的反向校验见 `tools/conformance_check.py` |
| V6 | L2 | 红队与假接受率 | 外部攻击者视角，不按自家基准出题 | `tools/redteam_suite.py`、`tools/mutation_benchmark.py` |
| V7 | L2 | 四镜评审与终审 | 结构化评审记录 | `tools/lens_review.py`、`tools/muse_review.py` |
| V8 | L4 | 外部验证节点 | **2**：① Correctover（2026-11-20T01:44:01Z，Linux / Python 3.12.14，commit `8a95747`）；② EMILIA Protocol（2026-11-20T05:13:32Z，macOS arm64 / Python 3.12.14，commit `8160ac6`，回传文件 sha256 `24e59eac…9b85f3`） | 干净克隆、stdlib only：`tools/external_node_check.py` → 两次均 CONSISTENT、负向探针 3/3 被拒；②于同一 commit 我方 Windows 复跑同为 CONSISTENT（`e0c9c3cb…453f0`），两回执并列在 `docs/external-review/`；①另有 `independent_verifier/cross_check.py` → 70 项 / 0 不一致，回执在桥仓 `ai-seats-bridge`。**①同时指出 M17 双验不一致、M20 两边 PASS、`malicious` / `malicious-keyswap` 两边 INCONCLUSIVE**——三条已登记为待办，不是已解决 |
| V9 | — | 外部锚（时间） | OpenTimestamps／Rekor／RFC 3161 三条路径 | `tools/anchor_ots.py`、`anchor_rekor.py`、`anchor_tsa.py` |

## 三、这张表怎么用

1. 对外声称“经过验证”必须带级别。把 L1／L2 说成“第三方验证”属不实陈述。
2. **V8 的 0 不等于项目弱**：它精确表达“独立性的当前来源是同一位作者的两套实现”，这句话本身就是结论，比含糊的“已被验证”有用。
3. **V4 的 288/288 不等于 V8 变 1**：前者是别人写的语料驱动我们的实现，后者是别人跑我们的节点并回传；两类主张不能互换。
4. 缺的是 V8。补齐方式不是写文档，是有人真的跑一次并把结果文件发回。

## 四、为什么单列这张表

此前“谁验过”散落在 `docs/`、`tools/` 结果文件与 README 的一段话里，外部读者要拼三处才能得出一个数。本表把这些压成一张按**强度**而非**时间**排序的清单；数字全部来自结果文件，不手填。
