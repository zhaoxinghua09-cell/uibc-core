# 地址推导：从"不能反推"到 50/50（2026-11-25）

## 一句话

`did:bid` 地址**可以从公钥完整复算**。上一版写"能校验、不能反推"是错的——错在用了比特币的 Base58 字母表，而官方 SDK 用的是**只有 4 个字母大小写不同**的另一张表。换成那张表，50 条官方地址 **50/50** 逐字节复现。

## 证据链（三步，每步都能被外人重跑）

1. **先有反例**：拿 `bid-sdk-nodejs` 1.0.1 对 50 个固定种子（`tools/bid_sdk_address_batch.mjs`）产出的地址，用 RFC/协议那套 `base58_bitcoin(sha256(rawPublicKey)[10:])` 复算，只有 **7/50** 一致；把 SDK 地址按比特币字母表解码，得到的 22 字节与 `sha256[10:]` 不同。于是当时写成"不可反推"。
2. **再读到底层字节**：SDK 依赖的是 `brdc-sjcl`（不是官方 sjcl）。它的 `sjcl.codec.base58`：
   ```
   alphabets:"123456789AbCDEFGHJKLMNPQRSTuVWXYZaBcdefghijkmnopqrstUvwxyz"
   encode: 大整数反复除 58，前导 0x00 字节各输出一个字面 '1'
   ```
   也就是**结构完全标准**，只有字母表不同。
3. **最后逐位比字母表**：与比特币表逐位置对比，差异**恰好 4 处**：

   | 位置 | BID（brdc-sjcl） | Bitcoin |
   |---|---|---|
   | 10 | `b` | `B` |
   | 27 | `u` | `U` |
   | 34 | `B` | `b` |
   | 52 | `U` | `u` |

   即：**BID 地址 = 比特币 Base58 的结果，把 `b/B`、`u/U` 的大小写对调**。前 9 位（`1`–`9`）完全相同——这解释了那 7/50：那 7 个地址恰好一个都没用到这 4 个字母。

复算与实现：`uibc_core/bid_address.py`，测试 `tests/test_bid_address.py`（13 条），其中 50/50 那条是逐条比对 `fixtures/bid/sdk_address_batch.json`。

## 标准与实现的三处不一致（都是字节级可复现的）

| 事项 | RFC-003 §5.1 正文 | 官方 SDK 1.0.1 | 本文档的处置 |
|---|---|---|---|
| 是否前置版本字节 | 前置 1 字节 `0x01`（第三步），再接 22 字节截断哈希 | 该步骤被注释掉（`keypair/index.js` 第 60–62 行：`// const head = [0x1]`、`// mix = sjcl.bitArray.concat(head, mix)`），输出 22 字节 | `version_byte` 是**显式开关**，不设默认；两种都实现，不替对方选 |
| 示例地址形态 | 打印 `did:bid:38VPR182Y4uTkq32fykXjbKBPdQZutH`（**省略**了算法字母与编码字母） | 一律 `did:bid:ef…`（`e`=Ed25519、`f`=Base58） | 实现按结构章节输出 `ef`；同时用测试钉住"RFC 打印的那种形态不是合法地址"，免得日后有人照着示例写出缺字母的地址 |
| Base58 后缀长度 | 22–31 字节 | 实测 30–32（50 条样本） | 校验按协议 ABNF 的 `(22,42)` 接受；把"正文给的 22–31 与实测 30–32 不符"记在此处，不悄悄改写正文 |

关于版本字节这条，**两面都能逐字节复现**：RFC 的唯一示例用 `version_byte=True` 精确复现出 `38VPR182Y4uTkq32fykXjbKBPdQZutH`；50 条现行地址用 `version_byte=False` 精确复现。所以这不是"谁错了"，而是**标准文本与参考实现在这一步分叉了**，而且没人发过勘误。

## 我们据此做什么、不做什么

**做**：

- `derive_did()` 从公钥算出完整地址，并把每一段（算法字母、编码字母、AC 号、suffix、所用哈希、是否带版本字节）作为返回值交给调用方——两种变体并存时，一个裸字符串会藏掉"用的是哪一种"。
- `bitcoin_to_bid_suffix()` / `bid_suffix_to_bitcoin()`：四个字母互换，让任何现成 Base58 库都能读写 BID 地址。
- `address_matches()`：一致性问题（"这份文档的地址和它的公钥对不对得上"）可以回答了；且**两种变体都算匹配**，因为两种都真实存在。
- SM2 用 SM3 而不是 SHA-256（RFC-003 §4.1.1 第二步），`zf…` 前缀由此出现。

**不做**：

- 不用地址推导做**准入**。解析器仍按 ABNF 接受任何形状合法的地址；推导只是自洽性检查。协议没有规定"地址必须由公钥推导"以外的约束，也不该由我们加。
- 不认定哪一种变体是"正确实现"。要判定得看链上数据，而我们没有可达节点（见 `docs/COMPETITOR-EVIDENCE.md` 与缺口表 C9）。

## 复跑

```bash
python -m pytest tests/test_bid_address.py -q            # 13 条，含 50/50
python -c "from uibc_core.bid_address import derive_did as d; \
print(d('b0d308378e6b5ff0c2b4be3da741538004525d6388e5df32deb79e2b0c02f133c7','Ed25519',version_byte=True))"
```

命令实跑过；`tools/bid_sdk_address_batch.mjs` 需要 `node` 与 `bid-sdk-nodejs@1.0.1`，没装则这条证据退回"已提交的 50 条快照"（快照固定在仓里，仍可逐字节比对）。
