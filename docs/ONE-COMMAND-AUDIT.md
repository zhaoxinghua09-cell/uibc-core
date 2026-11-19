# 一条命令，一个陌生人，两个实现，四个问题

前三轮把锚补齐到：钥、头、时刻、位置。但它们分散在五个命令里，而且只有我们写的那个实现能判。这一轮把这两件事一起处理。

## 先看输出

```
$ python3 tools/outsider_chain_audit.py
VERDICT: OK
  the line is sound                      expect CHAIN OK   python CHAIN OK   node CHAIN OK   ok
  newest bundle matches its anchor       expect ANCHORED   python ANCHORED   node ANCHORED   ok
  superseded bundle is refused           expect FAILED     python FAILED     node -          ok
  a withheld anchor is called stale      expect STALE      python STALE      node -          ok
```

**0.877 秒**，剥掉 `PYTHONPATH`、在空目录里跑，两套实现并排给答案。

它自己造两个 bundle、把它们串成链、然后问四个问题。陌生人不需要先理解我们的目录结构，也不需要先装 Python 包。

## 第二个实现也判链

`tools/verify-js/chain.mjs` —— 与 `anchor_chain.py` 无共享代码，用 `node:crypto` 自己算 `sha256(JCS(四个字段))`。

为什么值得多写一份：**只有一个实现能判的检查，只有一个机器可能提出异议**；而异议正是 bug 被发现的方式。

| 场景 | Python | Node |
|---|---|---|
| 链完整 | CHAIN OK | CHAIN OK |
| 缺中间一个 | CHAIN BROKEN | CHAIN BROKEN |
| 同一 seq 两次 | CHAIN BROKEN | CHAIN BROKEN |
| 前驱摘要被改写 | CHAIN BROKEN | CHAIN BROKEN |
| 链到 2，已知有 3 | STALE (5) | STALE (5) |

五条全部冻结在 `tests/test_chain_second_impl.py`，断言的是**两方一致**，不是某一方的答案。

Node 版不判包（那是 `anchor.mjs`）、不判时间戳（那是 `anchor_check.py`）。**一个问题，一个工具** —— 一个工具判三件事，出问题时你不知道是哪件错了。

## 一次刻意的重复

`chain.mjs` 里复制了 `anchor.mjs` 的六行 JCS，而不是抽成共享模块。共享 helper 是多一个会漂移的东西；规则本身只有六行，两处各写一次比一处写错被两处继承更安全。

## 它证明的与不证明的

**证明**：一个只有 Node 的机器，不装我们的包，能独立判断这条锚链是否完整、这个 bundle 是否等于它钉住的状态、旧包是否被拒、被扣下的新锚是否叫 STALE。

**不证明**：链是真的。仓库里没有 `anchors/`，没有一次发布，这一切仍发生在临时目录里。`IMPLEMENTATION-STATUS` 仍是零 —— **能力齐了，见证没有**。

```
584 tests · doc_facts 0 · falsifiability 19/19 · 4 问全绿 · 0.877 s
```
