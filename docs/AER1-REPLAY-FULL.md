# AER-1 全语料逐向量复现：143/143

- 日期：2026-11-18
- 语料：`draft-zambo-aer1-26`，kit 1.5.7，`base_url=https://zambo.dev/aer1/corpus/v1.5.7/`
- 工具：`tools/aer1_vector_replay.py`（49 个）+ `tools/aer1_receipt_verifier.py`（94 个）
- 结论：**143/143 复现**。两个工具都不 `import uibc_core`，也不 import 发布方自己的 runner。

## 1. 分工

| 工具 | 覆盖 | 结果 |
|---|---|---|
| `aer1_vector_replay.py` | merkle 9、unicode 5、chain 7、chain-v07 28 | 49/49 |
| `aer1_receipt_verifier.py` | 单收据 64（valid 21、invalid 36、invalid-profile 1、anchored 6）、anchor 判定 8、id-binding 6、chain commitment 8、workflow 8 | 94/94 |
| 合计 | 143 个向量 / 146 项检查 | **143/143** |

单收据那 64 个是按 `§3`–`§6` 的字段规则逐个判定：base64 必须是**规范拼写**（非零 pad bit 也算拒），payload 必须严格 UTF-8，时间必须是**真实日历**（2 月 30 日、1900-02-29、闰秒 60 秒全部拒），id 必须是小写 UUID 且不能是 nil UUID，provenance 必须是三个类之一且不得含控制字符 U+0000–U+001F 与 U+007F，`output_hash` 必须重算相等，`input_hash` 在 payload 记录 `inputs` 时按 §7.1 规范 JSON 重算。

## 2. 三处"规范这么写、语料不是这样"的地方

这三条是在跑向量时撞出来的，不是我们代码的 bug。写出来，是因为它们决定了任何第三方实现能不能"照规范做对"：

### 2.1 `metadata_hash`：规范强制，语料违反，官方 runner 没实现

§6 步骤 4 写得很硬：`receipt_schema_version` 为 `0.4` 或更高时 **MUST** 带 `metadata_hash`，且「a "0.4" receipt without metadata_hash MUST fail」。

实际情况是：语料 `valid/` 里有 **10 份 0.4 收据没有 `metadata_hash`**（`bound-04`、`deep-nesting`、`edge-numbers`、`empty-members`、`input-hash-multikey-20`、`large-payload`、`maximum-offset-timestamp`、`optional-members-18`、`typographic-unicode`、`uuid-v1-core`），全部被标为应通过。发布方 runner 的 `check()` 里也没有任何 `metadata_hash` 重算逻辑。

我们的处理是两边都留：

```bash
python3 tools/aer1_receipt_verifier.py --kit <kit>                  # 143/143，随语料
python3 tools/aer1_receipt_verifier.py --kit <kit> --strict-metadata # 按 §6 文本，这 10 份被拒
```

也就是说：**照规范写会在这 10 个向量上失败，照语料写会漏掉规范的一条 MUST。** 这不是实现者的选择问题，是规范与语料得先对齐。

### 2.2 `entry_count` 与 `seq` 对"1.0"的态度相反

§7.1 明确 `seq` 的 `1` 与 `1.0` 等价，两者都接受；§7.3 说 `entry_count` 是「a JSON number with an integer value」。按同一读法，`entry_count: 1.0` 应当接受。

但向量 `x-entry-count-float` 期望 **invalid**。我们按向量实现（`entry_count` 必须是 JSON 整数 token），并在代码里注明这是语料 pin 的行为、不是规范文字的自然推论。

### 2.3 尾部换行：Python 的 `$` 会放过它

`invalid/id-trailing-newline` 与 `invalid/provenance-trailing-newline` 两个向量要求"带尾部 `\n` 的 id / provenance 必须被拒"。用 `re.match("...$")` 判定时 Python 的 `$` 也匹配串尾前的位置，`"uuid\n"` 会被放过——我们第一版实测就漏了这两个（76/88）。改成锚定到串尾（`\Z`）后转绿。这一条对任何用正则做字段校验的实现都成立。

## 3. 这一批仍然不是"互操作"

143 个向量复现的是**发布方公布的期望值**。它证明的是：

- 我们能从规范文本重建对他们的向量判定；
- 他们的向量本身可下载、可逐字节核验（77 文件 SHA-256 全对、`evaluated_set_digest` 与其发布值一致）。

它不证明：

- 我们的收据能被他们的 verifier 接受（收据 schema 不同，这一格没动）；
- anchor 真的接上了外部基础设施。离线语料里"可解析"是按构造判定的（RFC 2606 `.invalid` 域的 log 永远解析不了，`.example` 视为可解析），我们没有真的去连 Nostr relay 或 OTS 日历；
- 我们比他们更"正确"。2.1 那条只说规范与语料彼此不一致，不构成谁对谁错的结论。

## 4. 复跑

```bash
# 取语料（77 文件，逐个核对 SHA-256）
curl -sL -o index.json https://zambo.dev/aer1/corpus/v1.5.7/index.json
# 按 index.json 的 files 清单逐个下载到 ./kit/ 下，保持相对路径

python3 tools/aer1_vector_replay.py    --kit ./kit   # 49/49
python3 tools/aer1_receipt_verifier.py --kit ./kit   # 94/94
```

两个工具都是标准库，零安装。任何一项不符，请把输出发我们，我们按你的数字改。
