# 变异探针：每一层都要能说出"改这里，谁会发现"

## 为什么换一种问法

实现自洽、测试全绿，仍然回答不了一个外部问题：**把某个东西改掉一点，这个实现有反应吗？**

所以这一层不再问"我们实现了哪些规则"，而是问"一次只改一处，每一次改动落在哪一类"：

| 类别 | 含义 |
|---|---|
| refused | 当场拒绝，且拒绝的理由指向被改的东西 |
| warned | 接受了，但说了话（合法的宽容 + 告警） |
| silent | 接受了，什么也没说——**这一列才是要看的** |
| wrong-error | 拒绝的方式不对（异常类型错、崩在别的层） |

三个探针用同一套口径，分别打三层。它们都只读、可 `--json`、退出码 0 表示"没有 silent"。

## 一、§4.2.1 文档形状：`tools/mutate_document_shapes.py`

**31 个变异体，25 个是协议禁止的形状，25/25 全部被拒，silent = 0。**

| 变异 | 结果 |
|---|---|
| `id` 删掉 / 换成另一个 BID / 换成数字 | refused（"does not match the request"） |
| `publicKey` 换成对象、条目换成字符串、`id` 缺 `#`、`id` 重复 | refused |
| `controller` 不是 BID | refused（"is not a BID"） |
| `publicKeyHex` 非十六进制、奇数长度 | refused |
| `authentication` 非数组、指向未定义键、条目是数字 | refused |
| `alsoKnownAs` 非数组、`type` 是字符串、`type` 是 `true`（bool 是 int 子类） | refused |
| `service` 非数组、缺 `id`、缺 `type`、`DIDSubResolver` 缺 `serviceEndpoint` | refused |
| `extension` 是字符串 | refused |
| 加一个未知顶层字段 | 接受（协议可扩展，这一类必须被接受） |

### 探针抓到的真缺口：`created` / `updated` 曾被当成选填

删掉 `created`，文档**解析成功**。而协议正文 §4.2.1 第 9、10 项写得很直白：

> **9.created**：必填字段。创建时间。
> **10.updated**：必填字段。上次的更新时间。

原实现只校验"给了就得是 ISO 时间"，没校验"必须给"。已改为缺字段即 `raise`，报错里带 §4.2.1 与项目号（`9.created` / `10.updated`），并由 `tests/test_mutation_probes.py` 钉住。这就是"手写测试只测你想到的用例、穷举变异会测你没想的"的具体差别。

### 一处"合法的沉默"，但它不是洞

`publicKey.type` 写成 `RSA`，解析不报错——§4.2.1 只写"公钥算法类型（String）"，没有枚举，所以解析层无权拒。探针于是往下追一层：用 Ed25519 真签一份文档，再把同一个键的 `type` 改成 `RSA`，问验签器：

```
honest=True  relabelled=False (signature does not verify over the JCS form of the document)
```

改标类型会改变规范化字节，签名立刻不成立。**所以解析层的沉默是有下游兜底的，而且"有兜底"这件事是被实测出来的，不是被假设的。**

## 二、地址绑定：`tools/probe_address_binding.py`

样本用 `fixtures/bid/sdk_address_batch.json` 的第一条（SDK 产出、`address_matches` 能复现）。不用 RFC-003 正文印的那个例子：它在本实现下**不复现**（正文给的是 `did:bid:38VPR…` 形态、SDK 给的是 `did:bid:ef…`，两套变体的差别记在 `docs/ADDRESS-DERIVATION.md`）。拿一个不复现的例子做探针，量到的是另一条规则。

**key → address（256 次单比特翻转）**：地址全部改变，**0 次落在原地址上，0 次彼此相撞**；每次翻一位，30 个字符里有 **26–30 个**跟着变。这说明地址真是键的函数，而不是某种近似。

**address → key（1710 次单字符替换）**：把 30 个字符中的每一个依次换成其余 base58 字符，**1710 次全部被拒**。所以 `address_matches` 比的是整串重算结果，不是前缀或长度。

**长度**：截短一位、末尾补一位、中间删一位——全部不匹配。

**结论要说得准确**：suffix 是 base58 编码的摘要，**任何**等长 base58 串语法上都成立，所以字符串本身不携带完整性；"这个地址属于这把键"只能靠重算，探针证明的正是"重算这条路径上没有被前几位糊弄过去"。

## 三、二进制报文：`tools/mutate_bid_binary.py`（见 BINARY-PROTOCOL.md 三·十）

三层共用同一张账本：196 字节 / 1568 位里，refused 328、changed 1226、**blind 14**（= 6 个未分配 flag 位 + 整个 `unUsed` 字节，正文一位不盲）。

## 四、复跑

```bash
python tools/mutate_document_shapes.py            # 31 个变异体，silent 必须为空
python tools/probe_address_binding.py             # 1710 次替换全拒、256 次翻转全变
python tools/mutate_bid_binary.py                 # 1568 位，blind = 14
python -m pytest tests/test_mutation_probes.py -q  # 9 条契约
```

## 五、这套方法量不到的地方

- **签名块**：§5.1.2.3 给了 `creator`/`digestAlgorithm`/`signatureValue` 三个名字，却不给 unit ID，所以二进制层无法定位签名块；文档层能验签，但那验的是 JSON/JCS 形态，不是报文形态。这两件事不能互相冒充。
- **分片**：§5.1.3 只说 `messageID` 递增，没给末片判据，所以不做重组——"没做"是结论，不是遗漏。
- **真机**：以上全部是对本实现的变异。真实链返回的报文是否会带别的字段、宽度是否与我们的假设一致，要一份真实样例才能定，这是唯一还缺的外部输入。
