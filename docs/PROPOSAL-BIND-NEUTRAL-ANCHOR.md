# 绑定中立令牌：一个时间戳同时覆盖两个生态的状态（提案 + 可跑 demo，2026-11-20）

**这一页不是说我们发明了什么。** 我们没做检索去证明这个结构没人提过；这一页只做三件事：说清问题、给出可复算的规则、附一个本机跑通的 demo 与反例。

## 问题（实测，不是设想）

`docs/BINDING.md` 记着：解析 EATF 的 13 个包，可解析 12 个，**12/12 的 imprint 等于各自的载荷摘要**；我方 S16 要求令牌覆盖**包链头**。结果是一个字节全对、签名也对的包搬进我方容器后，S16 仍然判"未覆盖本链头"。

两边都没错。错的是"一个令牌只能关于一件事"这个隐含前提：谁先定下 subject，谁的令牌就只对那个生态有用。

## 构造

subject 不是单个摘要，而是一份**有序的 (格式, 摘要) 列表**：

```json
{"schema": "uibc-neutral-anchor/0.1",
 "created_at": "2026-11-20T00:00:00Z",
 "policy": "1.3.6.1.4.1.99999.1",
 "subjects": [
   {"format": "uibc-checkpoint-head/0.4", "digest": "e8c77afd…", "source": "uibc-core",
    "what": "conformance/oracle/cases/oracle-clean"},
   {"format": "eatf-payload-sha256/1.0", "digest": "1dc36b94…", "source": "eatf-verifier",
    "what": "test-vectors/valid/minimal-roundtrip"}
 ],
 "tsr": "timestamps/anchor.tsr",
 "cabundle": "timestamps/ca.pem",
 "subject_digest_sha256": "bcb6fb6a…"}
```

**规则（写死，好让外人不必读代码就能复算）**：

1. `canonical bytes` = 对 `subjects` 值做 UTF-8 JSON，**对象键按码点排序、无空白、不转义 ASCII、列表保持给定顺序**；
2. `digest` = `sha256(canonical bytes)`；
3. 判词 = 令牌能在给定 CA bundle 下验过**且**其 imprint 等于该 `digest`，才 PASS；材料缺失一律 INCONCLUSIVE，不猜。

顺序参与哈希，是因为"集合"会让两个不同的多格式声明产生同一摘要——那样一来，一个令牌能覆盖的就不止一件事。

## demo（本机、离线、可重跑）

1. 用 OpenSSL 3.5.8 造一个一次性 CA 与 TSA（`openssl ts -reply`），证书扩展 `extendedKeyUsage = critical,timeStamping`；
2. 把上面两个 subject 的 canonical 字节写盘，`openssl ts -query -sha256` 出请求，`openssl ts -reply` 出令牌；
3. 用我方 `uibc_core.tsa.verify_token` 验令牌（不是用造它的工具自己验自己）。

实测：`verify: PASS`，令牌元数据 `signature_verified: True`，`gen_time 2026-11-19T19:21:22+00:00`。

**反例（全部实测为 FAIL/INCONCLUSIVE）**：

| 反例 | 结果 |
|---|---|
| 改掉第一个 subject 的 digest | FAIL（`token does not cover these subjects`） |
| 只调换两个 subject 的顺序 | FAIL（顺序参与哈希） |
| 信封里自报的 `subject_digest_sha256` 与重算不符 | FAIL（`different subject digest`） |
| 缺令牌或缺 CA | INCONCLUSIVE（不猜） |

植入位置：`uibc_core/neutral_anchor.py`、`tests/test_neutral_anchor.py`（6 例）、`tests/fixtures/neutral-anchor/`（一次性 CA + 令牌，随仓库提交，只为让测试不依赖网络与外部 TSA）。

## 这条能说明什么

- **一个真实 RFC 3161 令牌可以同时覆盖两个不同格式的状态**，而且验证者是本项目的实现，不是签发它的 OpenSSL。
- 规则不依赖我方任何私有格式：subject 是普通 JSON，摘要算法写死，任何第三方可复算。

## 这条不能说明什么

- **不能说明被任何外部方采纳**：CA 是我方一次性测试 CA，令牌只为 demo 存在；没有真实 TSA 参与，没有第三方跑过。
- **不能说明"跨格式判词一致"**：一个令牌覆盖两个声明，只解决"时间点相同"，不解决"两套检查对同一证据给同一判词"（那件事目前只做到 3/8 类，见 `docs/INTEROP.md`）。
- **不能说明比对方的设计更好**：只签载荷的令牌本身不覆盖包状态，但他们用签名+收据补了绑定；这是取舍，不是高下。

## 接下来唯一能升级它的一步

拿一个**真实 TSA**（FreeTSA 或商用）对同一份 canonical bytes 出一次令牌，然后把这条 anchor 发给对口的圈子（FG-TIDA 的 WG、W3C APCG），只有别人拿这个结构去用，它才算提案；在那之前它只是本机通过取证的一个构造。

这一步是对外动作，需要明确许可。
