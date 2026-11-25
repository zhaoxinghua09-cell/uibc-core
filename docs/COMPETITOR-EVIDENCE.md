# 竞品实证：官方 did:bid 驱动的字节审计（2026-11-26）

这一页存在的理由很简单：**"对方没做 X" 如果没有可复跑的核查，就只是意见**。所以下面每一条都钉在一个 commit 上，并且有一支脚本能把结论重新算出来——而且**方向是反的**：脚本在我们这些"对方没做"的断言不再成立时会红，不会因为我们不去看它而一直绿。

```
python tools/audit_official_bid_driver.py
```

- 对象：`caict-4iot-dev/uni-resolver-driver-did-bid`（DIF Universal Resolver 的 did:bid 驱动，中国信通院相关组织账号发布）
- commit：`5a933656eb9631bc65ba535f4bb69aa893d79a79`（2022-11-09，最后一次提交，消息 `mod DID method url`）
- 文件：`src/main/java/uniresolver/driver/did/bid/DidBidDriver.java`，324 行，sha256 `f589fb8692de24afb8609a75b75bda47cf536b6b457d17f6bdd1e29dacf28ec3`
- 许可：Apache-2.0（本文引用，不搬运文件）
- 仓库规模：25 个文件；`src/test` 下只有 jetty 配置，**没有任何测试类**

## 实测结果（2026-11-26 跑出）

| # | 断言 | 证据（行号以钉住的 commit 为准） |
|---|---|---|
| 1 | 非零 `errorCode` 一律坍缩成同一句 | 守卫在 77 行 `if(jsonResponse.get("errorCode").getAsInt() != 0)`，随后 78 行 `throw new ResolutionException("docuement not exist")`——协议 §4.2.5 的 11 个码在这里只剩一句"文档不存在"（连拼写都是 `docuement`） |
| 2 | 没有按码分档的分支 | 整个文件不含 `case N:` / `errorCode == N` 形式的码常量 |
| 3 | 没有 §4.2.4 的 verify 处理 | 全文 `verify` 出现 **0 次**；没有 `?verify=true` 的请求构造，也没有 `data.verify` 的读取 |
| 4 | `delegateSign` 只被搬运、未被验签 | `delegateSign` 相关 9 行，全部是 `get("signer")` / `get("signatureValue")` 取字段后 `put` 回 metadata（233–235 行），没有任何 verify/check/validate 调用 |
| 5 | `proof` 直接塞进 metadata，不重算 | 174 行 `methodMetadata.put("proof", gson.fromJson(proof, Map.class))`——把签名原样转述，不验证 |

## 这意味着什么，以及不意味着什么

**意味着**：在"能解析"这个目标上，官方驱动做到了；在"解析结果是否可信、错误码是否可分级处理"这两件事上，它的公开实现没有做。这与我们读协议的结论一致：协议 §4.2.4 写着"确保递归解析过程中每个经过的解析服务都是可信的"，但参考实现把 `delegateSign` 当字段搬运，把 11 个码当一个码。

**不意味着**：不意味着信通院的服务端没做校验——驱动只是客户端，服务端可能在别处校验。也不意味着这套实现"错"——DID Core 的 `RESOLUTION_ERROR` 只有少数几类，把协议码压成一句话是**为了适配上层**的常见做法，代价是调用方再也分不出"没找到"与"验签失败"。我们的判断只针对"公开可复算的这一层"。

## 我们对应做了什么（可对照检查）

| 官方驱动的行为 | 我们的行为 | 证据 |
|---|---|---|
| 11 码 → 一句 `document not exist` | 11 码分级，3/7 可重试、6/8/10 归 not_found、9 单独归 security | `uibc_core/bid_protocol.py::BID_RESPONSE_CODES`、`tests/test_bid_protocol.py` |
| 不处理 `?verify=true` | `resolve_bid_trusted` 把服务自述 / 自己的重验 / 背书三态分开 | `tests/test_bid_trusted.py`（15 条）、`tools/demo_bid_trusted.py` |
| `delegateSign` 只搬运 | 真验签；取不到签名者公钥时记 `unchecked`，不冒充通过 | `verify_delegate_sign`、bench J8.6–J8.8 |
| `proof` 原样转述 | 去 proof → JCS → Ed25519 → Base58 重算，且 JS 侧独立复算同一字节串 | `tests/test_bid_crossjs.py`、`tools/verify-js/bid.mjs` |
| 无测试 | 该仓 `src/test` 无测试类；我们 BID 相关 100+ 条，bench 外部 J 组 46 条 | `UIBC/uibc-bench` `harness/s11_bid_protocol.py` |

## 复跑须知

- 脚本默认走网络（`raw.githubusercontent.com`，失败会退回 GitHub contents API 并校验同一 commit）。离线环境用 `--file` 指向本地副本。
- 脚本**不为 CI 强依赖**：它审的是别人的仓库，网络与对方仓库的稳定性不该让我们的 CI 变红或变绿。它是给人跑的工具，结论写在本页。
- 对方一旦修了上面任何一条，脚本退出码非 0，本页必须跟着改。这就是它存在的价值。

## 附：RFC-011（二进制解析）有没有公开实现

同一天、同一套 code search 查询（`org:caict-4iot-dev`）：`headerLength`、`replyCode`、
`messageLength`、`0x2100` 四个查询的 `total_count` **都是 1**，唯一命中就是 RFC-011
正文文件本身。全站查 `unitId bidDocument` 共 51 条，该组织内仍只有这一份正文。

因此对 §4.3 这条线，能说的只有：**公开默认分支上没有任何参考编解码器**。不能说官方没有
实现——code search 不覆盖私有仓与未索引分支，链节点内部代码也看不到。这也决定了我们
那一层的验收方式：不靠"跟官方一致"，靠编码/解码互逆、随机字节不崩、以及把每条推断做成
可翻转的参数（`uibc_core/bid_binary.py::ASSUMPTIONS`）。
