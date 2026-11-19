# 归档缺口：DOI 指向的包里有 6 项检查，仓库里有 19 项

**实测日期 2026-11-18。可复算：`python3 tools/check_citation_scope.py`。**

## 怎么发现的

上一轮做了证据索引，这轮顺手核对引用元数据，看到 `CITATION.cff` 钉在 `0.2.1`、正文写 `0.3.3`。第一反应是"版本号漂移，改一下"。**这个判断是错的**——`0.2.1` 不是漏改，是 Zenodo 真正归档的那一份。所以问题不是号码不一致，是**别的**。

于是去取归档里真实的东西。`CITATION.cff` 里记着归档的 revision `402ac6b3…`，从那里取出 `uibc_core/verify.py`：

```
167 行
record("S1" …) record("S2" …) record("S3" …) record("S4" …) record("S5" …)
"id": "S6"
```

**六项。** 当前仓库是 954 行、十八项。

| | 归档 `0.2.1`（`402ac6b`） | 当前 `main` |
|---|---|---|
| `verify.py` | 167 行 | 954 行 |
| 检查 | S1–S6（6 项） | S1–S19（19 项）+ S0 兜底 |
| 审计器 / 套件 / 端点 / 跨实现导出 | **均不存在** | 有 |

## 这意味着什么

引用是一个承诺：跟着链接走，应该拿到你说描述的东西。现在跟着 DOI 走，拿到的是一个**只做六项检查的验证器**。

所以任何这样的表述：

> "UIBC 通过 19 项检查验证证据包"

配上这个 DOI，**都是有问题的**——读者下载后找不到 S7 以后的任何一项。不是"版本旧一点"，是**读者会认为我们在夸大**。

这类错误在评审、答辩、期刊编辑手上是最容易被一击命中：下载 → 打开 `verify.py` → 数行数 → 结论。

## 处置

1. **`CITATION.cff` 的 message 里写明作用域**，不再让读者自己去发现：DOI 支持 S1–S6；S7–S19 只能挂仓库状态。
2. **`docs/ARCHIVE-BASELINE.json`** 记录基线：那个 revision、那段 sha256、那六项检查、以及这份测量的**局限**（只数了检查 id，没有数行为；当时 S1–S6 的覆盖也比现在薄）。
3. **`tools/check_citation_scope.py`** 随时复算：哪些能挂 DOI、哪些不能。归档里有而当前没有的检查会让它以非零退出——那是能力被削弱的信号，不该悄悄发生。
4. **`tests/test_archive_scope.py`** 把上面三条钉住。

## 没有做的，以及为什么

**没有补归档。** 让 S7–S19 也能被引用，只有一条路：给当前状态做一次新归档（新 Zenodo 版本 + 新 tag）。这是对外动作，需要明确授权。

**更正一处我自己写错的事实（2026-11-18 晚）**：本文最初写"仓库连一个 tag 都没有，无法从 git 重建 0.2.1"。这句话是错的。仓库有 `v0.2.1` 标签，指向提交 `f5d7b29b`；该提交的 `uibc_core/verify.py` 与归档快照 `402ac6b3` 的**逐字节相同**（`sha256 = 78cc6439…`）。所以 `0.2.1` 是可从 git 重建的。

同时核到 `v0.3.3` 标签指向 `251b10b3`，其 `verify.py` 与 PyPI 上 `0.3.3` 的 sdist **逐字节相同**（`sha256 = 1bec7fa3…`）。

这两条合起来说明一件事：**发布流程本身是诚实的**——每次发布都真的发出了当时仓库的样子。问题不是发布做错了，是**发布停在 `0.3.3`，而仓库继续长了**。

**没有把 `0.2.1` 说成过时。** 它没做错任何事，它只是老了。真正错的是拿旧包去背书新能力。

---

## English

The DOI in `CITATION.cff` pins the 0.2.1 snapshot. Its verifier is **167 lines and six checks (S1–S6)**; the repository is 1221 lines and nineteen. Everything built after 2026-09-18 — the auditor, the outside kit, the endpoint, the cross-implementation exports, and thirteen checks — is in **no archived artifact**.

So a sentence like "UIBC verifies packages against nineteen checks" carrying that DOI is not merely stale: a reader who follows it and opens `verify.py` will not find thirteen of them. That is the exact shape of an overclaim, and it is the first thing a reviewer checks.

What this PR does instead of hiding it: states the scope in `CITATION.cff`, records the baseline measurement with its limits, and ships a tool that recomputes which claims the DOI can carry. What it does **not** do: archive the current state. That needs a new Zenodo version and a repository tag — an outbound act, and one worth deciding rather than assuming.
