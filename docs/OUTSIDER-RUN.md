# 请帮我做一次独立复跑（约 3 分钟，零安装）

## 不想 clone？

用 `tools/build_outside_kit.py` 打出来的压缩包（`docs/OUTSIDE-KIT.md`）：解压即跑，不联网、不装依赖。源码与声明仍以本仓库为准。

## 连 clone 都不想？

点一次按钮即可：**Actions → one-click outsider run → Run workflow**，或把仓库开在 Codespaces 里直接看终端那一行。说明见 [`docs/ONE-CLICK.md`](ONE-CLICK.md)。这类运行记作"机器运行"，**不**进 `docs/EXTERNAL-NODES.md` 的人员计数。


> 中文完整版（含四件事说明与已知边界）：[`docs/EXTERNAL-NODE-KIT.md`](EXTERNAL-NODE-KIT.md)

> **一条命令版（推荐先跑这个）**：`python3 tools/outsider_audit.py`
> 它会跑基线判定 + 11 条红队变异 + 2 条反假阳性对照，并如实报告哪一项检查抓住了哪一种篡改；
> 有 AER-1 语料时加 `--kit <path>` 连互操作一起跑。任何 SKIPPED 都不计入通过。
> 记录见 [`docs/OUTSIDER-AUDIT.md`](OUTSIDER-AUDIT.md)。

# Run it once on your machine — about 3 minutes, nothing to install

---

## 中文

### 这件事为什么需要你

`uibc-core` 是一个"智能体生命周期证据链"的开源实现。它的 README 第一屏写着这样一句：

> **外部验证节点：2**

意思是：到目前为止，**只有两个不是我的人在自己的机器上把它跑通过**（见
[`EXTERNAL-NODES.md`](EXTERNAL-NODES.md) 两行记录；两位都是我们请来的，算第三方执行，
不算无利害审计）。这一行是我们自己在维护的数字，所以它小得难看，也不美化。

你花三分钟跑一次，就能把这个数字从 2 变成 3。你的结果我们会原样公开，包括你失败的情况。

### 你需要什么

- 一台能上网的电脑（Windows / macOS / Linux 都行）
- Python 3.10 或更高（`python3 --version` 能出结果即可）
- **不需要**安装任何第三方包，不需要账号，不需要给我们任何权限

### 三步

```bash
# 1. 取代码（公开仓库，只读）
git clone --depth 1 https://github.com/zhaoxinghua09-cell/uibc-core.git
cd uibc-core

# 2. 跑一条命令（约 30 秒）
python3 tools/external_node_check.py --out external_node_result.json

# 3. 跑全量测试（可选，约 30 秒）
python3 -m unittest discover -s tests -p "test_*.py"
```

### 你会看到什么

第 2 步正常输出是一行长这样：

```
independent=PASS  reference=PASS(8ms)  probes=3/3 rejected  -> CONSISTENT
```

意思是：两套**独立实现**（一套按规范重写、不与主代码共享）对同一个证据包给出同一个结论，且三个"必须失败"的探针全部被拒——所以这不是一个"永远返回 PASS"的检查器。

第 3 步正常输出：

```
Ran <N> tests in ~40s
OK (skipped=<k>)
```

`N` 我们不写死：套件每天在长，写一个数字就会过期。你机器上的 `Ran N tests` 应与
[`docs/EVIDENCE-INDEX.md`](EVIDENCE-INDEX.md) 第一页的现数一致（那一页由生成器数，不手写）；
对不上时**以你的结果为准**。

`skipped` 通常来自没装的可选依赖（`opentimestamps` / 锚定相关），属旁证检查，不是失败；
如果你看到 skip 原因是"not installed"，同样记下来发给我们。

### 然后请把 `external_node_result.json` 发回给我

文件里只有：版本号、平台、命令行、耗时、各项检查结果。**不含任何你的个人信息**，你可以先打开看一遍再发。

发回方式：邮件 / 微信 / GitHub issue 都行。

### 我们的承诺

1. 你跑出**失败**，我们也照原样贴出来，并在 README 上标为 1 次失败尝试——不删、不改、不解释成"环境问题"。
2. 你的名字如果不想公开，就写"匿名复跑者 #1"，我们不追问。
3. 如果你发现我们的文档和你的结果对不上（比如用例数、skip 数），**以你的结果为准**，文档是我们的错。

---

## English

### Why this needs you

`uibc-core` is an open-source implementation of an agent-lifecycle evidence chain. Its README says, on the first screen:

> **external verification nodes: 2**

Meaning: **two people outside this project have run it on their own machines and sent the file back**. We publish that number ourselves; it is not verification.

Three minutes of your time changes 2 into 3. We will publish your result as-is, including if it fails.

### What you need

- A machine with internet (Windows / macOS / Linux — all fine)
- Python 3.10+ (`python3 --version` should work)
- **No** third-party packages, no account, no credentials from us

### Three steps

```bash
git clone --depth 1 https://github.com/zhaoxinghua09-cell/uibc-core.git
cd uibc-core

python3 tools/external_node_check.py --out external_node_result.json     # ~30s

python3 -m unittest discover -s tests -p "test_*.py"                     # ~30s, optional
```

### What you should see

Step 2 normally prints:

```
independent=PASS  reference=PASS(8ms)  probes=3/3 rejected  -> CONSISTENT
```

Two independent implementations (one written from the spec, sharing no code with the main path) agree on the same evidence package, and three probes that **must** fail are all rejected. That matters: a checker which can only say PASS proves nothing.

Step 3 normally prints:

```
Ran <N> tests in ~40s
OK (skipped=<k>)
```

We do not print `N`: the suite grows every day and a digit in a document expires.
Your `Ran N tests` should equal the live count at the top of
[`docs/EVIDENCE-INDEX.md`](EVIDENCE-INDEX.md), which is generated, not typed.
If they differ, your numbers win.

The six skips are optional `opentimestamps` checks; skipped, not failed.

### Send `external_node_result.json` back

It contains only: version, platform, command line, timings, per-check results. **No personal data.** Open it and read it before sending if you like.

Send by email, chat, or a GitHub issue — whatever is easiest.

### What we promise

1. If your run **fails**, we publish that too, marked as one failed attempt — no deletion, no rewording it as "an environment issue".
2. If you prefer not to be named, you are "anonymous runner #1"; we will not ask who you are.
3. If our documentation disagrees with your numbers (test count, skip count), **your numbers win** and our docs are wrong.

---

## 附：这份邀请本身怎么被验证 / Appendix: how this invitation is itself checked

- 命令与依赖声明来自仓库实测，不是设计稿。
- 邀请里唯一写死的数字是 `CONSISTENT` 这个判词；用例数与 skip 数以你自己跑出来的为准。
- 若你发现任何一处与实际不符，请直接指出——这正是我们在找的东西。

- Every command and dependency claim here comes from a real run, not a design draft.
- The only literal we quote is the verdict word `CONSISTENT`; your test and skip counts are yours to report.
- If any line of this is wrong, say so — that is exactly what we are looking for.
