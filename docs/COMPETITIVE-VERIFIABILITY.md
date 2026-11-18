# 可验性横向测评（2026-11-18）

这份文档只记**实测拿到的东西**：哪家能公开下载语料、哪家能离线跑一致性套件、哪家有真的独立第三方。拿不到的写"未取得"，不按宣传语推断。

## 1. 方法

每个对象做三件事，全部在云机（Debian/Linux，Python 3.12）上执行：

1. 抓公开页面 / 规范正文 / PyPI 元数据，记录字节数与关键段落；
2. 能序列化的就 `git clone --depth 1` 下来，统计文件、测试文件、向量数量；
3. 能跑的就把一致性套件**真跑一遍**，记录输出。

## 2. 五个对象

| 对象 | 性质 | 规范 | 语料 | 独立 runner | 双实现 | 独立第三方 | 一条命令自证 |
|---|---|---|---|---|---|---|---|
| **uibc-core**（我们） | 本项目 | 自有 `docs/` + I-D 形状本地草稿（`drafts/`，**未提交**） | fixtures + 143 向量复现 | 我们两个独立实现 | 与发布方双向验收 | **0** | 有 |
| **AER-1 / zambo** | 第三方规范，我们对标对象 | IETF draft-26，正文 139,318 B / 3,024 行 | 143 向量，公开可下载（index 15,706 B） | `base/conformance.py` 1,595 行 | — | 未知 | 部分 |
| **Agent Action Capsule (AAC)** | 竞品 | 13 个 IETF drafts（`draft-mih-*`） | 12 例 commitment 向量 + 向量已贡献进 `ietf-wg-scitt/examples` | `reference_verifier.py` | Python + Go | **2**（EMILIA Protocol、GlyphZero） | 部分 |
| **ARC**（arc-protocol 1.1.4） | 竞品 | GitHub 自述 | **包内无**（`grep -ril 'test.?vector\|conformance'` 为空） | 无独立套件 | — | — | 否 |
| **AgentRust** | 竞品 | 站点称 spec pre-1.0、SDK 0.30.0 | 站点称 "97 portable conformance vectors"，**本体未取得**（`/conformance`、`/vectors` 均 404/503） | 未取得 | — | — | 未取得 |

## 3. 体量实测

| 仓库 | 文件 | 测试文件 | 备注 |
|---|---|---|---|
| uibc-core | 504 | 41（350 个测试用例） | Python 23,322 行 |
| agent-action-capsule | 1,977 | 386 | 含 `INTEROP.md`、`IMPLEMENTATIONS.md` |
| capsule-emit | 1,078 | 629 | 382 个 JSON，含 `commitment-conformance-vectors` |
| ietf-wg-scitt/examples | 39 | — | `test-vectors/`、`receipts/` |

## 4. 真跑过的三件事

1. **AAC commitment 向量**：`python3 commitment-conformance-vectors/reference_verifier.py` → `OK: all 12 cases verified (7 positive, 5 must-fail)`。可跑，规模 12。
2. **ARC 安装**：`pip install arc-protocol` 成功（1.1.4, MIT, 2026-04-03），顶层模块 `arc`，导出 `verify_receipt`、`ReceiptBuilder`、`MerkleTree` 等；CLI `arc-log` 需 `[server]` 额外依赖才启动。**包内没有任何 test vector / conformance 资产**。
3. **跨协议冒名测试**：把 AAC / SCITT 的 28 个 JSON 全部交给我们的 AER-1 判定器（`tools/aer1_verify_external.py`），结果 **0 个被误接受**。异格式不会被冒认成 AER-1。

## 5. 诚实的结论

**不是断崖式领先。** 按这张表，我们是"**单点更深、面上更窄**"：

- 更深：143/143 逐向量独立复现、出站 9 份收据被对方实现验收、入站 21/21 + 36/36 判定、8 种篡改双实现对照、跨协议 0 误接受、350 项测试、一条命令自证。这几项是拿数字堆出来的，同行可以照着复跑。
- 更窄：**独立第三方节点 0**，而 AAC 的 `INTEROP.md` 已登记两家（EMILIA Protocol 三家独立计算、GlyphZero 双向 `ran & verified`）。规范侧 AAC 有 13 个 IETF drafts，我们只有自有 docs。生态侧 AAC 有 14 个框架适配器。

差距最大的一格是第三方，而且它**不在我们能单方面补上的范围内**——那需要真实的人把邀请包接过去跑。

## 6. 下一格怎么补（按性价比）

1. **把 143/143 与双向判定做成对外一句话可复跑的产物**（已有 `tools/aer1_interop_demo.py`），送真人跑 → 第三方 0→1。
2. **把三条规范矛盾写成给人读的差距报告**（不是发邮件，是进仓库的一页），让对方维护者能直接对着改。
3. **AAC 路线的借鉴**：`INTEROP.md` 那种"登记表"结构值得抄——把我们自己的互操作登记做成同样形态（谁、跑了什么、结论、链接），而不是散在文档里。

## 7. 复跑

```bash
# AAC 一致性套件
git clone --depth 1 https://github.com/action-state-group/capsule-emit.git
cd capsule-emit/commitment-conformance-vectors && python3 reference_verifier.py

# 跨协议冒名测试（我们）
python3 tools/aer1_verify_external.py --dir <任一异协议 JSON 目录> --expect REJECTED
```
