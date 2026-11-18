# 外部锚定：竞品实测与我们补到哪一步

哈希链能抓篡改与重排，**抓不住截断**：删掉尾部，剩下的链条照样自洽，丢掉的那段看起来就像"跑得更短的一次运行"。唯一解法是把根提交到运营方改不了的地方。这一格我们原来是 0。

## 1. 竞品到底做到了什么（读源码，不读宣传）

| 对象 | 实现位置 | 后端 | 状态 |
|---|---|---|---|
| **AAC** | `python/agent_action_capsule/anchor.py`（377 行） | 两条面：`DEFAULT_ANCHOR_ENDPOINT = https://anchor.agentactioncapsule.org/v1/digest`（仅 POST，GET 返 **405**，服务在）；`_DEFAULT_TS_URL = https://ts.agentactioncapsule.org`（**HTTP 200**）走 COSE_Sign1 → SCITT TS → COSE Receipt | 真实现，自家端点 |
| **AER-1 官方 SDK** `aer1-pydantic` | `aer1_pydantic/anchor.py` | Nostr 多 relay（`wss://relay.primal.net`、`wss://relay.ditto.pub` …）+ OpenTimestamps 日历 `https://alice.btc.calendar.opentimestamps.org` | 真实现，去中心化 |
| **uibc-core**（我们，改前） | — | — | **无** |

两家的共同点很清楚：**只有根（32 字节摘要）过网**，正文、输入输出、工具名一概不上行。AER-1 SDK 的注释把这条写得很直白——"a root is a commitment, not a leak"。

## 2. 我们补了什么

`tools/anchor_chain_head.py`，**零依赖**（只用 `urllib`），默认 dry-run：

```bash
python3 tools/anchor_chain_head.py --package fixtures/clean.uibc            # 只打印，不联网
python3 tools/anchor_chain_head.py --package fixtures/clean.uibc \
    --submit --out /tmp/anchors                                            # 真提交
```

- 从 `manifest.json` 读 `evidence_root`（不重算：那是包自己的主张，`verify` 已经校验过一致性）；
- 直接把 root 的 32 字节作为 `POST /digests` 的 body（root 本身就是 SHA-256 值，不做二次哈希，否则会掩盖到底在承诺什么）；
- 三个日历并发提交（alice / bob / finney），**单日历失败不中断**，成功的证明照常落盘；
- `.ots` 证明校验魔数后才落盘，并写 `anchor-record.json` 记录"哪个根 → 哪份证明"。

## 3. 魔数不是猜的

`OTS_MAGIC` 与参考实现逐字节对齐：python-opentimestamps `opentimestamps/core/timestamp.py:276` 的 `DetachedTimestampFile.HEADER_MAGIC`，**31 字节**：

```
\x00OpenTimestamps\x00\x00Proof\x00\xbf\x89\xe2\xe8\x84\xe8\x92\x94
```

`tests/data/ots-format-sample.ots` 是**用官方库真实序列化出来的**一份 `DetachedTimestampFile`（OpSHA256 + `BitcoinBlockHeaderAttestation(800000)`，78 字节），测试直接拿它验证我们的判定，而不是拿我们自己造的假证明自证。改一个头字节就应被拒——测试里钉住了这条。

## 4. 一个只有踩过才会写下来的坑

**锚定证明不能写回包内。** 把 `.ots` 记成 package 的 evidence，会改变包的内容 → 改变 Evidence Root → 你锚定的那个根已经不是包现在的根了。这个错**不会报错**，只会让锚定悄悄失效。

所以 `anchor()` 遇到 `--out` 落在包目录内直接抛 `ValueError`，并有对应测试。证明必须放在包**旁边**，由 `anchor-record.json` 绑定。

## 5. 现在是什么状态（不美化）

- **`state: "pending"`，不是 anchored。** 日历返回的是**待确认**证明；要等 `ots upgrade` 成功（约 1 小时）把它升到 Bitcoin 承诺，再 `ots verify` 才有"在某个区块高度已存在"的证据。在此之前说"已锚定"就是撒谎，所以报告字段就叫 pending。
- **真实提交次数：0。** 代码路径用本地 mock 日历端到端跑通（断言 body 恰为 32 字节、路径 `/digests`、证明落盘、魔数通过），但**没有任何一个字节真的发到公共日历**。按约定，向第三方公共服务提交属于对外动作，需要你点头。
- 因此在这一格里，AAC 和 AER-1 SDK 仍然领先我们——他们有真实锚定记录，我们只有能跑的实现。

## 6. 真提交要做什么（一条命令）

```bash
python3 tools/anchor_chain_head.py --package fixtures/clean.uibc --submit --out /tmp/anchors
```

上行内容：一个 32 字节摘要（公开仓库里示例包的 Evidence Root）。三个日历，各收一份。不包含任何业务内容。

拿到 `.ots` 后约 1 小时：

```bash
pip install opentimestamps-client
ots upgrade /tmp/anchors/*.ots
ots verify /tmp/anchors/*.ots
```

## 7. 复跑

```bash
python3 -m unittest tests.test_anchor_chain_head -v     # 8 项
python3 tools/anchor_chain_head.py --package fixtures/clean.uibc   # dry-run，应 exit 0
```
