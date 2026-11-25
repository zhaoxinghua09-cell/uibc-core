# §4.3 二进制解析协议：正文在哪、我们读到哪（2026-11-25）

## 一、协议正文指向的链接是空的

《星火·链网BID协议》§4.3 全文只有一句：

> 星火链网BID标识[二进制解析协议规范](https://github.com/caict-4iot-dev/bif-rfcs/tree/main/RFCs/3-ACCEPTED)

`RFCs/3-ACCEPTED` 目录里**只有一个 `.gitkeep`（0 字节）**。所以此前"§4.3 正文未取到、只能明确拒绝"的判断，源于**主协议给的指针指空了**，不是协议没有正文。

正文在隔壁目录：`RFCs/4-ADOPTED/星火链网RFC-011：星火链网BID标识二进制解析协议.md`

| 项 | 值 |
|---|---|
| 仓库 | `caict-4iot-dev/bif-rfcs` |
| commit | `5d471fc1f3d63c670c9d937bb1990fee089feb52`（2025-03-14） |
| 文件 | `RFCs/4-ADOPTED/星火链网RFC-011：星火链网BID标识二进制解析协议.md`，31,156 字节 |
| blob | `4acf27085711bd7149c6d09ee4d902c747d2445f` |
| 本地 sha256 | `c6fc24dd325f98b022c559942f045ab25000fe17bba04da14d48c2a9d62408e5` |

另有 `RFCs/1-PROPOSED/星火链网RFC-017`（二层网络接入）与 `4-ADOPTED` 下的 RFC-001~016；**3-ACCEPTED 与 2-DEMONSTRATED、5-RETIRED 三档都是空的**。也就是说这套 RFC 的分档目录目前只有 `1-PROPOSED` 和 `4-ADOPTED` 两档在用。

## 二、读到的结构（可据此复算）

**消息 = 消息头 + 消息体 + 消息签名**；传输允许 UDP/TCP/HTTP/HTTPS，TCP/UDP 建议端口 2259；UDP 单包 ≤1024 字节，超出分片。

消息头最小 16 字节，大端序：

| 偏移 | 长度 | 字段 | 说明 |
|---|---|---|---|
| 0 | 1 B | version(4bit) + headerLength(4bit) | headerLength 以**4 字节**为单位（16 字节 = 4） |
| 1 | 2 B | flag | QR/TC/RD/DT/TR/CT 各 1 bit，opCode 4 bit，其余待扩展 |
| 3 | 1 B | unUsed | 待扩展（**不解释**） |
| 4 | 2 B | replyCode | 见下面的码表 |
| 6 | 2 B | messageID | 分片序号 |
| 8 | 4 B | transactionID | 会话 ID |
| 12 | 4 B | messageLength | 消息体 + 签名长度 |
| 16 | … | option | optionType(1B) + optionPayload，不足 4 倍数补 0 |

**单元（unit）**：ID 2 B + length 2 B + payload；payload 本身可以再是单元序列。ID 范围：`0x1000–0x1FFF` 为 URP1.0，`0x2000–0x9FFF` 为 URP2.0，`0xA000–0xCFFF` 自定义扩展。

## 三、已经实现的部分（`uibc_core/bid_binary.py`）

- 消息头解析/构造（16 字节定长；变长 option 只读不写，因为正文没给任何 optionType 的 payload 定长）。
- 单元树解析，含越界、长度不匹配、尾部残字节三类拒绝。
- 文档应答与错误应答的**字符串字段**解码：`version`/`id`/`created`/`updated`/`publicKey.*`/`service.*`/`proof.*`/`extension.attributes.*`/`extension.acsns.*`/`extension.verifiableCredentials.*`/`errResponse.msg`。
- 重复出现的叶子 → 列表；重复出现的容器 → 按字段合并（正文没有标记"实例边界"，见第四节）。
- 未知 unit → 进 `unknown`（带 ID、长度、前 32 字节 hex），**不丢、不猜**。

## 三·五、不只是解码器：三层都能反过来算

一个只会解码的实现，外人无法反驳它，因为它说什么都是"读出来的"。所以这一层做成
**编解码器**，三段各有一个可以逐字节检查的逆运算：

| 层 | 正 | 逆 | 承诺 |
|---|---|---|---|
| 消息头 | `parse_header` | `encode_message`（头+可选 option+体） | 字节相同 |
| 单元层 | `parse_units` | `encode_units` | **字节相同，顺序也相同**（含非升序的 unit 序列） |
| 文档层 | `decode_document` | `encode_document` | **语义幂等**：`decode(encode(decode(b))) == decode(b)` |

文档层只承诺语义，原因写在代码里而不是含糊过去：解码结果是一个 dict，dict 不保留
"哪个 unit 在前"，所以逆运算只能给出**规范序**（容器内按 unit ID 升序）。把字节级
承诺放在单元层，是因为那一层的顺序信息还在，能真的逐字节对上。

`Int`/`Long` 的宽度仍然没有人给。现在它有两种走法，都由调用方决定：

- 不给 `integer_widths` → 整数进 `_deferred`，带原始字节（默认，不猜）；
- 给 `integer_widths={"int":2,"long":4}` → 按大端无符号解码；**长度与宽度不符立刻
  raise**，报出 `declared long=8 bytes but carries 4`——真实样例一旦到手，错宽度会
  当场暴露，而不是被悄悄读成错数。

## 三·六、六条假设，每条都能被翻转（`ASSUMPTIONS`）

`python -c "from uibc_core.bid_binary import assumption_report; print(assumption_report())"` 直接打印这张表；
`tests/test_bid_binary_codec.py` 里对两条 `flippable` 的断言是"翻转后输出确实变了"，
不是"文档里写了可翻转"。

| 假设 | 正文缺口 | 处置 | 可翻转 |
|---|---|---|---|
| `flag_bit_order` | §5.1.2.1 按序列字段，无位编号 | 默认第一项=bit15；`flag_bit_order="lsb"` 换成第一项=bit0 | 是 |
| `integer_widths` | `Int`/`Long` 无字节宽度 | 不给宽度不解码；给了就按宽度解，长度不符即报错 | 调用方 |
| `acsns_spelling` | §5.2.1.1.2 用 `0x3610/0x3620`，§5.2.1.4.2 用 `0x3601/0x3602` | 编码默认 `3610`，可切 `3601`；解码两套都收 | 是 |
| `bid_document_collision` | `0x2100` 既是容器又是键 id 列表 | payload 能解析成单元=容器，否则=一个键 id | 启发式 |
| `fragment_reassembly` | 无末片判据 | 不重组，逐片解码 | 未实现 |
| `signature_unit_ids` | 三个签名 unit 无 ID | 不定位签名块 | 未实现 |

## 三·七、敌意输入不是免责声明，是测试

- `test_random_bytes_never_crash_the_decoder`：2,000 组随机字节，解码只允许 `ValueError`。
  面向网络的解码器崩在别的异常上，就是可以被远端打挂的路径。
- `test_random_byte_strings_that_parse_are_stable_under_re_encode`：500 组随机 unit 序列，
  能解开的重编码后语义必须一致——这一条同时否掉"只能解不能编"和"编出来的东西解不回去"。
- `test_unit_layer_preserves_non_ascending_order`：故意倒序，证明规范序只发生在文档层，
  单元层不偷偷排序。

## 三·八、跑得起来的例子，和一张不会骗人的图

一条命令，不需要网络、不需要夹具、不需要起服务：

```bash
python tools/demo_bid_binary.py          # 八幕，最后一行为 ALL OK，退出码 0
python tools/demo_bid_binary.py --flip   # 同一串字节，两种读法并排
```

demo 的每一幕都打印 `OK` 或 `HARD-FAIL`，退出码非 0 就说明模块被改坏了。它做的是同一件事的两面：
把一份 DID 文档编成 342 字节、`hexdump` 出来、再原路解回，然后当场演示"推断是参数"——`msb` 读出
`qr=1`、`lsb` 读出 `qr=0`；AC 号两套编号编出不同字节却解成同一份文档；宽度给错当场 raise。

图不是画出来的，是**算出来的**：`tools/render_bid_binary_layout.py` 从
`uibc_core.bid_binary` 里读 `HEADER_MIN`、`_FLAG_BITS`、`_OPCODE_SHIFT`、`ASSUMPTIONS`，生成
[docs/BID-BINARY-LAYOUT.svg](BID-BINARY-LAYOUT.svg)。生成器里有一句断言：各位段的字节数相加必须
等于 `HEADER_MIN`，否则直接失败——**图不可能和代码对不上而不被发现**。`tests/test_bid_binary_layout.py`
再把生成的 SVG 与仓库里那份做字节比较，手改过就红。

手绘图会随着代码演进而失真，而失真的图比没有图更糟：它看起来仍是证据。

## 四、正文没写够、因此没有实现的部分（逐条给理由）

| 缺什么 | 正文实际情况 | 我们的处置 |
|---|---|---|
| `Int` / `Long` 的字节宽度 | 全文只在**请求**里给过一个 `Short,2字节`；`ttl`、`extension.type`、`service.port`、`acsns` 的 `Int` 与 `ttl` 的 `Long` 都没给宽度 | 不解码，进 `_deferred`，附原始字节与"RFC-011 未给字节宽度"。**猜 4 或 8 再宣布"文档解出来了"是不可接受的** |
| 消息签名单元的 ID | §5.1.2.3 描述签名由 `creator`/`digestAlgorithm`/`signatureValue` 三个 unit 组成，**从未给出它们的 ID** | 不定位签名块；`signature_units_detectable = False`。带签名的报文只做结构解析 |
| 分片重组规则 | §5.1.3 说"第一个分片 messageID=1，后续依次加 1"，但没给"末片判据" | 不做重组 |
| flag 位序 | 只按顺序列了 QR/TC/RD/DT/TR/CT/opCode，**没有位编号** | 按"列表顺序 = 高位在前"实现，并在模块里用 `FLAG_BIT_ORDER_IS_AN_ASSUMPTION` 标死这是假设 |
| 两张返回码表 | §4.2.5：0=success；RFC-011 §5.1.2.1.2：**1=success**，新增 11=authentication required、255="码在扩展 option 里" | 两张表各自保留（`BID_RESPONSE_CODES` 与 `bid_binary.RCODES`），不合并、不互相覆盖 |

## 五、正文自身的两处 ID 冲突

| unitID | 冲突 | 我们怎么读 |
|---|---|---|
| `0x2100` | 既是 `bidDocument`（容器），又是 `bidDocument.authentication`（键 id 列表） | 按 payload 形状判别：能解析成单元序列 = 容器；解析失败 = 一个键 id 字符串。这是**对作者意图的启发式判断**，写在这里而不是藏起来 |
| `0x3601/0x3602` vs `0x3610/0x3620` | §5.2.1.4.2 与 §5.2.1.1.2 对同一对字段给了两套编号 | 两个编号都进 `FIELD_TABLE`，指向同一字段名 |

## 七、官方是否真有二进制实现：用 code search 查，而不是猜

"没有参考实现"这种话必须能被别人重跑，所以下面每一条都是可复现的查询（GitHub code
search，`org:caict-4iot-dev`）：

| 查询 | total_count | 命中 |
|---|---|---|
| `headerLength org:caict-4iot-dev` | 1 | 只有 RFC-011 正文本身 |
| `replyCode org:caict-4iot-dev` | 1 | 只有 RFC-011 正文本身 |
| `messageLength org:caict-4iot-dev` | 1 | 只有 RFC-011 正文本身 |
| `0x2100 org:caict-4iot-dev` | 1 | 只有 RFC-011 正文本身 |
| `unitId bidDocument`（全站） | 51 | 该组织内唯一命中仍是 RFC-011；其余是招投标系统的同名变量 |

结论收窄到能证伪的那一句：**截至 2026-11-25，`caict-4iot-dev` 公开默认分支上不存在
RFC-011 的编解码实现，正文是该组织内唯一提到这些字段的地方。**

不意味着：GitHub code search 只索引默认分支，看不到私有仓、未索引的分支、以及链节点内部
代码；官方可能确有实现而未公开。所以这里不能说"官方没有实现"，只能说"公开可查范围内
没有"。

正因为没有参照物，这一层的正确性只能靠**自洽**（编码/解码互逆、fuzz 不崩、假设可翻转）
而不是靠"和官方一样"。等第一份真实报文到手，`integer_widths` 会立刻用长度校验把错宽度顶出来。

## 六、复跑

```bash
python -m pytest tests/test_bid_binary.py -q          # 16 条
python -c "from uibc_core import bid_binary as b; print(b.RCODES[11], b.KNOWN_ID_COLLISIONS)"
```

取正文（钉在 commit 上，避免"哪天仓库改了、文档说的就不是那版"）：

- 目录：`https://github.com/caict-4iot-dev/bif-rfcs/tree/5d471fc1f3d63c670c9d937bb1990fee089feb52/RFCs/4-ADOPTED`
- 文件：同目录下 `星火链网RFC-011：星火链网BID标识二进制解析协议.md`（31,156 字节，blob `4acf2708…d2445f`）
- 取下来后 `sha256` 应等于 `c6fc24dd325f98b022c559942f045ab25000fe17bba04da14d48c2a9d62408e5`

文件名含全角冒号，命令行直接拼 URL 容易编码出错；用 GitHub 目录页点进去最稳，或用 API：
`https://api.github.com/repos/caict-4iot-dev/bif-rfcs/contents/RFCs/4-ADOPTED?ref=5d471fc1f3d63c670c9d937bb1990fee089feb52` 拿到 `download_url` 再下载。
