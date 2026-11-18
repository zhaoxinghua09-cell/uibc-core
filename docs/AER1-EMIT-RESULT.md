# AER-1 产出侧：我们的收据被他们的实现接受

- 日期：2026-11-18
- 工具：`tools/emit_aer1_receipts.py`
- 结论：5 个证据包共 9 份 AER-1 0.4 收据，**我们自校验 PASS，发布方 runner 也 PASS**

## 1. 为什么这一步比 143/143 更要紧

`docs/AER1-REPLAY-FULL.md` 记的是**复现他们公布的期望值**：我们能读懂他们的向量并算出同样的判定。但那仍然是"读"，不是"写"。

这一步是写：把我们的证据包渲染成 AER-1 收据，然后交给**他们自己的代码**判。判定者不是我们。

```bash
python3 tools/emit_aer1_receipts.py \
    --package fixtures/clean.uibc \
    --out /tmp/aer1_emit.json \
    --publisher-runner <语料目录>/base/conformance.py
```

发布方的 runner 是运行时从语料目录加载的，**没有 vendor 进我们的仓库**——要让他们的代码判我们的字节，而不是判我们手里的副本。

## 2. 我们公布并钉住的字节布局

§3.3 要求生产者把记录输入的字节布局公布出来，否则别人无法复现 `input_hash`。我们用的：

- canonical payload = 成员名按码点排序、字符串外无空白、`ensure_ascii=False` 的 UTF-8 编码；
- 收据 id = 由 `evidence_root`、序号与该条证据路径确定性派生，铸成带 RFC 4122 variant 位的 UUIDv4；
- `created_at` 取该条证据自己的 `created_at`（真实事件时间，不是生成时间）；
- `metadata_hash` 按 §3.1 重算：恰好六个成员、`tool` 限 `name/scope/version`、码点排序、§7.1 转义；
- payload 内自带 `receipt_schema_version: "0.4"` 与 `issuer_claims.provenance_class`，使 §6 的版本一致性与溯源绑定两条检查两边都有值可比。

一条证据一份收据：AER-1 是一个 tool call 一份，我们的证据索引正好是逐条记录。

## 3. 实测

| 证据包 | 收据数 | 我方判定 | 对方判定 |
|---|---|---|---|
| `clean.uibc` | 2 | PASS | PASS |
| `deleted.uibc` | 2 | PASS | PASS |
| `duplicated.uibc` | 3 | PASS | PASS |
| `malicious.uibc` | 2 | PASS | PASS |
| `malicious-keyswap.uibc` | 2 | PASS | PASS |

工具同时核对每条证据的 `content_hash` 与文件字节是否一致；不一致会单独打印 `EVIDENCE INTEGRITY`，不会静默放过。

## 4. 红队：八种篡改，两个实现各判一次

| 篡改用例 | 我方 | 对方 | 我方 strict |
|---|---|---|---|
| 原样 | PASS | PASS | PASS |
| 改 payload 一个字节 | FAIL | FAIL | FAIL |
| 换掉 `output_hash` | FAIL | FAIL | FAIL |
| 把 provenance 重标成 `EXECUTED BY US`（payload 里仍是 LOGGED） | FAIL | FAIL | FAIL |
| `created_at` 写 2 月 30 日 | FAIL | FAIL | FAIL |
| 删掉 `metadata_hash` | PASS | PASS | **FAIL** |
| 非规范 base64（改一个 pad bit） | FAIL | FAIL | FAIL |
| id 尾部带换行 | FAIL | FAIL | FAIL |

这张表的意义有两个：一是证明对方 runner 真在判定（七种篡改它都拒了），二是我方与对方在唯一一处结论不同——`metadata_hash` 缺失。那正是上一轮发现的规范与语料冲突：规范说必拒，语料说必过，他们照语料，我们默认照语料、`--strict-metadata` 照规范。

## 5. 一个必须说清的限定

`malicious.uibc` 的收据同样 PASS。这不表示"恶意包被洗白了"：AER-1 §10.2 写得很明确，绑定与收据不转移主张——一份有效收据只证明"这份记录被如此记录、字节未被改动"，不证明被记录的动作合法或正确。我们的包本身携带的攻击检测结论在 `uibc_core` 那边，与这份收据是两件事。把这两件事分开，恰恰是这套格式诚实的地方。

同理，这也不等于"我们的收据可以在他们的生产系统里被公开解析"——那需要一个稳定的公开 URL 与他们的解析端点，我们没做。

## 6. 一条命令自证

外人不必读这份文档就能自己判。把语料目录传进去，它会跑完上面全部三件事：

```bash
python3 tools/aer1_interop_demo.py --kit /path/to/aer1/kit --json /tmp/demo.json
```

输出是两列判定加两类**性质完全不同**的分歧：

| 统计项 | 含义 | 实测 |
|---|---|---|
| `cross-implementation divergence` | 我们和对方对同一份收据结论不同——那意味着有一方错了 | **none** |
| `default-vs-strict divergence` | 我们自己两种模式不同——那是规范与语料的冲突，不是谁错 | `drop metadata_hash (PASS vs FAIL)` |

把这两类分开计数是有意的：第一类为零才说明互操作真的成立；第二类不为零，说明矛盾在规范里，而且我们两边都如实报了出来。退出码 0 表示一切符合文档所述。

## 7. 复跑

```bash
python3 -m unittest tests.test_emit_aer1_receipts -v      # 11 项，零外部依赖
python3 tools/emit_aer1_receipts.py --package fixtures/<包>.uibc \
    --out /tmp/out.json --publisher-runner <语料>/base/conformance.py
```
