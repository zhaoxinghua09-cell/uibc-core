# 第二个锚定后端：Nostr（BIP-340 + NIP-01），零依赖

日期 2026-11-18 ｜ 工具 `tools/nostr_anchor.py` ｜ 测试 `tests/test_nostr_anchor.py`

## 为什么要第二个后端

一个日历就是一个审查点。AAC 用自己的 SCITT 服务，AER-1 官方 SDK 同时发多个 Nostr relay **和** OTS 日历——理由是一样的：丢掉一个后端不等于丢掉锚定。

我们上一击补了 OTS 日历。这一击补 relay 那一侧。

## 为什么不 `pip install coincurve`

因为这套工具要在评审者**裸 Python** 上跑。所以曲线是自己写的，然后**拿官方向量判它**——这才是能信的理由。

## 五重证据（都可复跑）

| # | 证据 | 结果 |
|---|---|---|
| 1 | **BIP-340 官方测试向量 19 组**（`tests/data/bip340-vectors.csv`，来自 `bitcoin/bips`）：验证判定复现 + 有私钥的向量签名字节复现 | **19/19** |
| 2 | 与 **libsecp256k1**（`coincurve`，Bitcoin Core 用的那套）同 aux 签名 | **逐字节相同** |
| 3 | 与 libsecp256k1 **双向互验**（它验我们的、我们验它换 aux 签的） | 双向 PASS |
| 4 | 与 `pynostr` 独立计算的 **NIP-01 event id** | **完全一致** |
| 5 | 篡改 content / 换签名 → 必须失败 | 必拒 |

裸环境跑：`10 tests OK (skipped=2)`（两个交叉项因未装库而跳过）。装了交叉库的环境：`10 tests, OK`（0 skip）。

**注意第 1 条不可跳过**：复现不了官方向量的密码学实现就是错的，"skip" 不是答案。

## 边界（必须写在明面上）

- **不是硬化密码**：纯 Python 标量乘有时序泄漏，没有 blinded 常数时间努力，没有密钥存储。只适合给**一次性锚定密钥**签摘要，不适合保护价值。
- **发布未实现**：Nostr relay 走 WebSocket，标准库没有客户端；为发消息引入依赖会毁掉这个文件存在的理由。`build_event` / `verify_event` 已完成并测过，**发送是另一件事**，要有 socket，也要有人点头。

## 上行内容

只有 32 字节的 Evidence Root、一个包标签、一个用途串：

```json
{"label":"clean.uibc","purpose":"anchor","root":"<64 hex>","scheme":"uibc-core/evidence-root"}
```

没有证据正文、没有输入输出、没有工具名。

## 用法

```bash
python3 tools/nostr_anchor.py --package fixtures/clean.uibc        # 生成临时密钥并签名，自验
python3 tools/nostr_anchor.py --package fixtures/clean.uibc --seckey <64 hex> --json
```

输出末尾会明确打印 `Not published: publication needs a WebSocket client and your go-ahead.`

## 复跑

```bash
python3 -m unittest tests.test_nostr_anchor -v     # 10 项（2 项交叉需 coincurve/pynostr）
```
