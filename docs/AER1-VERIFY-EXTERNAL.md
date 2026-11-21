# AER-1 入站方向：别人的收据，我们判

- 日期：2026-11-18
- 工具：`tools/aer1_verify_external.py`
- 结论：外来真实收据 **21/21 判 ACCEPTED**；无效收据 **36/36 判 REJECTED**，且拒因精确到具体成员

## 1. 这一步补的是什么

前面两步解决的是"我们能不能产出、他们认不认"（`docs/AER1-EMIT-RESULT.md`）。入站方向是另一个问题：**别人送来一份收据，我们能说出它到底是什么**，而不是只会复现他们已经写好的期望值。

区别在于输入是谁的。复现语料时我们拿着"期望 PASS/FAIL"的答案去核对；入站判定时手上只有一份文件，没有任何标签。

```bash
python3 tools/aer1_verify_external.py --receipt path/to/receipt.json
python3 tools/aer1_verify_external.py --dir path/to/receipts/ --expect REJECTED
```

## 2. 输出的是报告，不是布尔

§6 要求报告分三层。这个工具照那个结构输出：

| 层 | 内容 |
|---|---|
| `file_checks` | 重复成员名、非 JSON、非对象、编码问题——**读文件这一层** |
| `structural` | §3 元数据块：成员集、码点排序、串外空白、时间、UUID、base64 拼写 |
| `binding` | §6 版本一致性与溯源绑定：`receipt_schema_version`、`id_verdict` 的输入 |
| `reference_profile` | 参考实现档位（不满足时只降档，不否决） |
| `disinterested` | 利益隔离档位 |
| `anchors` | 每锚三件套：`present` / `evaluated` / `outcome` |
| `id_verdict` | 五值之一：matched·resolved·mismatched·unverified·absent |

## 3. 实测：语料内外来收据逐份判定

| 目录 | 数量 | 我们判 | 语料标注 | 一致 |
|---|---|---|---|---|
| `valid/` | 21 | 全部 ACCEPTED | 全部应通过 | 21/21 |
| `invalid/` | 36 | 全部 REJECTED | 全部应拒绝 | 36/36 |

拒因不是笼统的"不合法"，而是具体的：`canonical_bytes is not valid base64`、`created_at is not a valid calendar date/time`、`id is not a lowercase UUID`、`provenance_class is not a known class`、`canonical_bytes is not the canonical base64 spelling`……

## 4. 为什么它必须是独立工具，而不是 verifier 的一个开关

这条是实测撞出来的，值得记住。

`invalid/duplicate-member-name.json` 的 JSON 原文里有**两个 `output_hash` 成员**，规范 §6 要求拒绝。但 `json.load()` 遇到重复成员会静默保留最后一个——解析成功、dict 结构完好、看不出任何异常。我第一版用一个临时脚本直接 `json.load(open(f))` 跑全量，结果这份被判成 PASS，36 份 invalid 只拒了 35 份。

verifier 本体其实一直有 `first_duplicate_member()`，问题在于**任何新写的调用路径都可能漏掉它**。所以把入站判定固化成工具，让文件级检查成为默认路径而不是可选步骤，并把这件事写成测试（`tests/test_aer1_verify_external.py` 里那条 `test_duplicate_member_is_caught_before_parsing`）。

这类"解析器太宽容"的坑，恰好是外人评测最容易抓、也最容易在自家实现里漏掉的一类。

## 5. 边界

- 语料仍出自同一套 kit（v1.5.7）。这是"外来格式"，不是"外来第三方独立产物"——真正的第三份实现还没有。
- 判决只覆盖结构与绑定；锚的 `outcome` 在离线语料里按 RFC 2606 域构造判定，没有真连 Nostr relay 或 OTS 日历。
- 我们没有生产级解析端点，不承诺任何 URL 层面的可解析性。

## 6. 复跑

```bash
python3 -m unittest tests.test_aer1_verify_external -v          # 6 项，零外部依赖
python3 tools/aer1_verify_external.py --dir <kit>/base/test-vectors/valid --expect ACCEPTED
python3 tools/aer1_verify_external.py --dir <kit>/base/test-vectors/invalid --expect REJECTED
```
