# 一次扫完 171 条：竞品语料有多少能被外人复算（上游 HEAD `39daf704`）

对象：`probityai/agent-evidence-vectors` 的 `vectors-poc-evidence/package/poc_evidence_vectors/corpus`，2026-11-25 抓到 HEAD `39daf704`（2026-11-25T04:11:38Z），**171 个 JSON**（inclusion 37、consistency 23、token 87、chain 15、canonical 9）。

之前我们只看过三条 `size=0`（`docs/upstream-package/competitor-defects/README.md`）。三条是抽样，抽样只证明抽样。这次改成把每条向量都按它自己写的数字重算一遍，只看两个问题：

1. 不拿对方代码，这条文件能不能被复算？
2. 能复算的那些，文件自己的数字和它自己发布的 verdict 对得上吗？

复算只做算术，判据来自 RFC 6962 / RFC 9162：

- **inclusion**：叶 = `SHA-256(0x00 ‖ record)`；按 `index`、`tree_size` 折叠 `proof`，比对 `root`；`proof` 条数先按 `(index ^ (size-1))` 的分解定出应有多少条；`index` 越界、`tree_size = 0` 却带非空树根，都是数字自己给出的结论。
- **consistency**：用 `old_root` 和 `proof` 推出第二棵树应有的根，比对 `new_root`；`old_size = 0` 但 `old_root` 不是空树常量、`new_size < old_size`、证明链不通，同样是数字自己给出的结论。
- **token / chain / canonical**：判定靠签名与 schema、靠记录签名、靠规范化器，**没有数字可折叠**，一律记成“不可复算”，不计入分母之外的任何“通过”。

![覆盖度](COMPETITOR-CORPUS-COVERAGE.svg)

（图由 `tools/build_corpus_sweep_svg.py` 从收据生成，`--check` 在 CI 里跑；数字改不了图，图也不会自己漂。）

## 结果（`corpus-sweep-39daf704.json` 是收据）

| 类别 | 向量 | 可复算 | 发布 accept | 发布 reject | 与数字一致 | 与数字矛盾 |
|---|---|---|---|---|---|---|
| inclusion | 37 | 37 | 22 | 15 | 37 | 0 |
| consistency | 23 | 23 | 10 | 13 | 23 | 0 |
| token | 87 | 0 | 17 | 70 | — | — |
| chain | 15 | 0 | 5 | 10 | — | — |
| canonical | 9 | 0 | 9 | 0 | — | — |
| **合计** | **171** | **60（35%）** | 63 | 108 | **60** | **0** |

三句话读完：

1. **35% 能复算**。剩下 111 条（65%）没有数字可折叠，外人不拿他们的代码就判不了——这不是缺陷，是这批语料的设计：它测签名与 schema，不测算术。
2. **能复算的 60 条全部自洽**：0 条出现“发布 accept，却给出自己的数字造不出的根”。也就是说这份语料在算术上是干净的；我们没有找到第四条 `size=0` 那类问题。
3. 所以“上游 0/3”那三条的毛病，量级就是三条，不是一类系统性错误。写成“他们有 171 条问题”是不诚实的，这份扫描正好挡住那种写法。

## 这份扫描不能证明什么

- **不等于跑过他们的验证器**。这里只重算文件里的数字，没有执行他们的代码，也没有对他们的实现下任何结论。
- **0 矛盾不等于实现正确**。文件自洽只说明“测试数据没写错”，不说明“被测实现算对了”。
- **不可复算不是“不透明”**。token 那 87 条给了公钥和签名字节，理论上可验签；这次没做，因为那要引入他们的 schema 语义，会变成“用他们的规则判他们的规则”。
- **一次快照**。171 个文件的 sha256 全在收据里，任何人可以按 `39daf704` 重抓、逐个对哈希、再跑一遍拿到同样的 60/0/111。

## 怎么自己跑

```bash
git clone https://github.com/probityai/agent-evidence-vectors && cd agent-evidence-vectors
git checkout 39daf704
python <this repo>/tools/sweep_competitor_corpus.py \
  --dir vectors-poc-evidence/package/poc_evidence_vectors/corpus --json
# TOTAL 171 vectors, replayable without their code 60 (35%), consistent 60, inconsistent 0, not replayable 111
```

`python tools/sweep_competitor_corpus.py --selftest` 是 13 条断言：常量、折叠、证明条数规则、下标规则、倒序尺寸规则，以及最容易自我美化的那条——分类函数（accept+match 才算一致、reject+mismatch 才算一致）。

## 与我们自己的语料摆在一起

我们 63 条 RFC 9162 语料（inclusion 50 + consistency 13）没有一条要求读者信任我们的代码：每条都带正孪生、拒绝词表，并被 pymerkle、Sigstore `merkle.py`、Go `transparency-dev/merkle` 三份实现各自独立判过（`docs/THIRD-PARTY-CROSSCHECK.md`）。对方 171 条里 60 条能这样被判，111 条不能。

这是本轮唯一可比的“体量”：**可被外人独立复算的向量条数**，不是总条数。总数（3,069 套件条目 vs 63）我们不比，因为追不上也不影响可核验性。
