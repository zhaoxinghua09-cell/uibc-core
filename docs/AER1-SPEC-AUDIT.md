# AER-1 规范符合性审计：三条断言，两条成立，一条撤回

日期 2026-11-18 ｜ 规范 `draft-zambo-aer1-26`（139,318 B / 3,024 行）｜ 语料 v1.5.7（143 向量）

一条命令复跑：

```bash
python3 tools/aer1_spec_audit.py --kit /tmp/aer1_kit
```

工具只做静态扫描（不 import 对方 runner），结论写在下面，数字由工具产出。

---

## A. `metadata_hash`：**冲突成立**

**规范原文**（不是关键词，是条款）：

- §3.1 表 1：`metadata_hash` 标 **Cond.**，说明栏写 `REQUIRED when receipt_schema_version is "0.4" or later; a verifier MUST recompute and compare it whenever ...`
- §6 步骤 4：`A "0.4" receipt without metadata_hash MUST fail.`（本地正文第 1069–1071 行）

**语料实测**：

| 子集 | schema 0.4 收据 | 缺 `metadata_hash` |
|---|---|---|
| `valid/` | 12 | **10** |
| `invalid/` | 9 | **9** |
| `invalid-profile/` | 0 | 0 |

`valid/` 21 份**全部判 valid**。也就是说：若严格按 §6 执行，这 10 份"有效"向量应当判失败。

**判定**：规范与语料冲突，官方 runner 未实现该 MUST。我们两种模式都给：默认随语料（否则过不了 143/143），`--strict-metadata` 随规范（那 10 份会失败）。这不是我们写错，是规范自身没对齐。

---

## B. 整数值浮点：**歧义成立**

**规范原文**：

- §7.2（`seq`）：`a JSON number with an integer value. The representations 1 and 1.0 are equivalent; both are [accepted] ... MUST reject a non-integer number (such as 1.5)`
- §7.3（`entry_count`）：`the number of entries in the timeline, a JSON number with an integer value.` —— **没有**那句"1 与 1.0 等价"

**语料实测**：两个向量对着来——

| 文件 | 向量 | 写法 | 期望判定 |
|---|---|---|---|
| `chain-vectors-v07.json` | `v07-seq-float-valid` [15] | `seq = 1.0, 2.0` | **valid** |
| `commitment-vectors.json` | `x-entry-count-float` [7] | `entry_count = 5.0`，desc 写 "written as a float with an integer value" | **invalid** |

**判定**：同一句"整数值"（integer value），`seq` 明确接受浮点写法，`entry_count` 明确拒绝。规范对 `entry_count` 少了 `seq` 那句澄清，语料却按"拒绝"执行。建议规范对 `entry_count` 补与 §7.2 同措辞的句子（或反之统一为拒绝），二者必须选一个。

---

## C. 尾部换行：**撤回**

此前 `docs/EXTERNAL-NODE-KIT.md` 写过"尾部换行必须拒，但 Python 的 `$` 默认放过，需锚定串尾"。**这条是错的，本文件正式撤回。**

**规范实测**：全文检索 `trailing` / `newline` —— **零命中**。规范没有任何关于文件尾换行的条款。

**语料实测**：

| 子集 | 文件数 | 以换行结尾 |
|---|---|---|
| `valid/` | 21 | **14** |
| `invalid/` | 36 | 31 |

`valid/` 里 14 份带尾换行且判通过——文件尾换行**不是**违规。

**真正相关的是什么**：我们自己的正则锚定。Python 的 `$` 会匹配"串尾或串尾换行之前"，`\Z` 只匹配真正的串尾。所以带尾换行的**字段值**（例如 `id` 里混进 `\n`）会被 `$` 放过、被 `\Z` 拦住。这是**我们实现的严格性选择**，属于自家实现细节，与 AER-1 规范无关。把它写成"规范要求"是错的，已改。

---

## 为什么这条值得单独写一页

别人写"我们发现了规范的三处矛盾"，我们就得敢写"三处里有一处是我们自己记错了，撤回"。前者是营销，后者是审计。这一页的价值在于：任何人对上面任一条有异议，`tools/aer1_spec_audit.py` 一条命令就能把同样的数字摆出来。
