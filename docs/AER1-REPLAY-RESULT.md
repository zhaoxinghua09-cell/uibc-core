# AER-1 语料：逐向量复现结果（第一批，49 个向量）

> 全语料（143/143）的总表与规范差异清单见 [`AER1-REPLAY-FULL.md`](AER1-REPLAY-FULL.md)。本篇只记第一批：merkle / unicode / 两代 chain。

- 日期：2026-11-18
- 语料：`draft-zambo-aer1-26`，kit 1.5.7，源 `https://zambo.dev/aer1/corpus/v1.5.7/`
- 工具：`tools/aer1_vector_replay.py`
- 结论：**49/49 复现**，其中 32 个是"必须失败/必须不等"的用例

## 1. 先把语料本身核住

不是从别人的仓库里 copy 一份 JSON 就算数。本次按官方 `index.json` 清单逐个下载：

| 项 | 结果 |
|---|---|
| 下载文件数 | 77（72 个向量文件 + 5 个 downloads 含官方校验器） |
| 逐文件 SHA-256 | 77/77 与清单一致，0 不一致 |
| 重算 `evaluated_set_digest` | `sha256:60bf73f325793e16843370cfa24903bb0d017525cb297e42bebc35857e2db0d2` |
| ZamBo 发布值 | 同上，**逐字节一致** |
| 官方 `conformance.py` 实跑 | `CONFORMANCE OK: 143 vectors, 146 checks` — 同一摘要 |

也就是说：我们引用的这 143 个向量，是可下载、可逐字节核验、且被其官方实现跑通的。

## 2. 然后用自己的实现跑它

`tools/aer1_vector_replay.py` **不 import `uibc_core`**：Merkle 与链的算法按各文件开头的规范原文重新实现。因此 PASS 的含义是"对**书面规则**的这份实现，复现了发布的期望值"，而不是"我们的收据格式接受了他们的收据"。

| 家族 | 向量文件 | 复现 | 其中属于失败面 |
|---|---|---|---|
| Merkle | `merkle-vectors.json`（§8.1） | 9/9 | 2（legacy 构造必须不等） |
| Unicode | `unicode-vectors.json`（§4） | 5/5 | 2（NFC/NFD、NBSP/连字符必须不等） |
| 链（基础） | `chain-vectors.json`（§7） | 7/7 | 5 |
| 链（-07） | `chain-vectors-v07.json`（§7） | 28/28 | 23 |
| **合计** | | **49/49** | **32 / 49 = 65%** |

失败面占 65%，这是这一批里最该看重的数字：一个只会说 PASS 的实现过不了这 32 个。

## 3. 走这条路时撞到的三个真差异

这三条不是"我们的代码小 bug"，是两份规范在细节上的分歧，记录下来对做互操作的同行有用：

1. **Merkle 构造不同**：AER-1 §8.1 是"奇数节点**复制**"（odd duplicated），RFC 6962 是"奇数节点**上提**"（promoted）。同样五片叶子，两棵树给出不同根。仓库里的 `uibc_core/merkle.py` 走 RFC 6962，本工具走 AER-1，两者刻意不共享代码。
2. **整数值浮点算整数**：`seq` 写成 `1.0` 必须被接受（`1` 与 `1.0` 等价），而 `seq` 写成 `true` 必须被拒绝 —— 在 Python 里 `True == 1` 成立，不做显式布尔判定就会放过它。本工具显式拒绝。
3. **字符串转义是 ECMAScript 风格而非 UTF-8 直出**：非 ASCII 写作小写 `\uXXXX`、换行用 `\n` 短转义、U+007F 也要转义。这与 RFC 8785（JCS，非 ASCII 直出）不同；用 `ensure_ascii=False` 会算出不同的摘要。

## 4. 这一批没有覆盖什么

143 个向量中，本批只执行了 4 个向量文件的 49 个（34%）。**未执行：其余 68 个文件**，包括 `anchor-vectors`（8）、`commitment-vectors`（8）、`id-binding-vectors`（6）与 `workflow-*`（7），以及大量小向量文件。

所以：

- 可以说：我们对 AER-1 的 Merkle、Unicode、两代链构造做了**逐向量执行**，49/49；
- 不可以说：我们通过了 AER-1 全语料。`tools/aer1_crosswalk.py` 的类级映射（COVERED 34 类）依然是对其余部分的唯一依据。
- 更不可以说：这是我们收据格式与他们的收据格式的互操作。互操作那一格仍是 `uibc_core/verify.py` 与 AER-1 schema 之间的事，没有做。
