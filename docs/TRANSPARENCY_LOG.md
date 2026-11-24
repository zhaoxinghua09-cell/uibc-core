# 透明日志：我们自己运营的那一个

这份文档回答一个问题：**除了 Rekor、OpenTSA、Zenodo 这些别人的服务，我们自己有没有一个可以被陌生人走一遍的日志？**

2026-11-24 之前没有。此前所有"透明"主张都是"第三方看见过"（我们往 Rekor 追加、找时间戳机构签、在 Zenodo 存档）。那些主张都不假，但它们证明的都是别人看见了什么，不证明我们有一份可被审计的、只增不减的、有头承诺的历史。

现在有一个了：`uibc_core/translog.py`。

## 它是什么

- **叶子**：一条记录的规范形 SHA-256。记录本身交给调用方定义。
- **树**：RFC 6962（Certificate Transparency）的 Merkle 树，实现复用 `uibc_core/merkle.py`。
- **追加**：一条记录一个叶子；日志就是叶子摘要的有序列表。
- **checkpoint**：承诺 `(tree_size, root)`，可以由运营者用 Ed25519 签名。
- **cosignature**：见证人对 checkpoint 的**哈希**签名，域分隔字符串 `uibc-translog-witness-v1` 与运营者的 `uibc-translog-checkpoint-v1` 不同。
  分开的理由很实际：如果见证人签的字节和运营者签的一样，那么运营者的密钥一旦被滥用，就能自己造出"被见证"的头，见证等于零。
- **证明**：包含证明与一致性证明都来自 `uibc_core/merkle.py`，复杂度与 RFC 6962 一致。

## 它刻意不做什么

- **不联网、不起服务、不上数据库。** 日志是一个列表；发布就是一次 git 提交或一份文件落地。任何更重的东西都是我们维护不起的基础设施。
- **不宣称"独立见证"。** 一条 cosignature 证明**某个密钥签了这个头**，不证明持有该密钥的人独立于我们。独立性是人的属性，代码造不出来。下面"现状"一节如实写有几个外部密钥。

## 怎么跑

```bash
python3 tools/translog.py new --out translog/log.json
python3 tools/translog.py append translog/log.json record.json --out translog/log.json
python3 tools/translog.py checkpoint translog/log.json --seed operator.edkey --note "day 1" --out translog/checkpoint.json
python3 tools/translog.py prove translog/log.json 0 --out translog/proof-0.json
python3 tools/translog.py verify-inclusion translog/log.json 0 translog/proof-0.json
python3 tools/translog.py cosign translog/checkpoint.json --seed witness.edkey --out translog/cosig-witness.json
python3 tools/translog.py verify-checkpoint translog/checkpoint.json --pub <hex>
python3 tools/build_translog_explorer.py --log translog/log.json --checkpoint translog/checkpoint.json --out translog/explorer.html
```

## 谁来判它是对的

不是我们自己。`tests/test_translog.py` 里有一条用例，把我们的包含证明交给 **Sigstore 内置的 Trillian 校验器**（`tools/third_party/sigstore_merkle.py`，第三方代码，Apache-2.0）去验；它抛异常就算我们错。我们自己的实现只用来生成证明，不用来自证。

此外所有 size 1–17 的每一片叶子都被逐一验过（153 个子用例），不是抽一条。

## 现状（写清楚，不美化）

| 项 | 状态 |
|---|---|
| 自有 append-only 日志 | 有，`translog/log.json`（示例日志，记录的是本仓库的透明日志启用动作，不是生产流水） |
| checkpoint 签名 | 有，运营者密钥签 |
| 外部见证 cosignature | **0 个** |
| 包含证明 | 有，且被第三方实现独立验证 |
| 一致性证明 | 有，`tests/test_translog.py` 覆盖 |
| 公开可访问 | 在公开仓库内（随仓库发布） |

所以准确的结论是：**从"完全没有自己的日志"前进到"有日志、有头、有证明、有见证机制，但没有外部见证人"**。距离"公开透明日志 + 独立见证"的最后一步，缺的是**人**，不是代码：需要一个愿意用自己密钥对每个 checkpoint 签名的外部方。
