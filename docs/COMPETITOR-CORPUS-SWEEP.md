# 一次扫完 171 条：竞品语料有多少能被外人复算（上游 HEAD `39daf704`）

对象：`probityai/agent-evidence-vectors` 的 `vectors-poc-evidence/package/poc_evidence_vectors/corpus`，2026-11-25 抓到 HEAD `39daf704`（2026-11-25T04:11:38Z），**171 个 JSON**（inclusion 37、consistency 23、token 87、chain 15、canonical 9）。

之前我们只看过三条 `size=0`（`docs/upstream-package/competitor-defects/README.md`）。三条是抽样，抽样只证明抽样。这次把每条向量都按它自己写的数字重算一遍，只看两个问题：

1. 不拿对方代码，这条文件能不能被复算？
2. 能复算的那些，文件自己的数字和它自己发布的 verdict 对得上吗？

判据全部是公开标准，没有一条来自对方代码：

- **inclusion**：叶 = `SHA-256(0x00 ‖ record)`；按 `index`、`tree_size` 折叠 `proof`，比对 `root`；`proof` 条数先按 `(index ^ (size-1))` 的分解定出应有多少条；`index` 越界、`tree_size = 0` 却带非空树根，都是数字自己给出的结论。
- **consistency**：用 `old_root` 和 `proof` 推出第二棵树应有的根，比对 `new_root`；`old_size = 0` 但 `old_root` 不是空树常量、`new_size < old_size`、证明链不通，同样是数字自己给出的结论。
- **canonical**：把 `text` 用 **RFC 8785（JCS）** 规范化——一个公开标准，`tools/jcs.py` 自己实现，不借任何库——再比对 `canonical_sha256` 与 `canonical_len`。
- **token / chain**：判定最终靠 schema 与签名语义，签名的"可验性"单独量出来（见下），但不把签名通过当成 verdict。

![覆盖度](COMPETITOR-CORPUS-COVERAGE.svg)

（图由 `tools/build_corpus_sweep_svg.py` 从收据生成，`--check` 在 CI 里跑；数字改不了图，图也不会自己漂。）

## 结果（`corpus-sweep-39daf704.json` 是收据）

| 类别 | 向量 | 可复算 | 发布 accept | 发布 reject | 与数字一致 | 与数字矛盾 |
|---|---|---|---|---|---|---|
| inclusion | 37 | 37 | 22 | 15 | 37 | 0 |
| consistency | 23 | 23 | 10 | 13 | 23 | 0 |
| canonical | 9 | 9 | 9 | 0 | 9 | 0 |
| token | 87 | 0 | 17 | 70 | — | — |
| chain | 15 | 0 | 5 | 10 | — | — |
| **合计** | **171** | **69（40%）** | 63 | 108 | **69** | **0** |

四句话读完：

1. **40% 能复算**（69/171），而且 **69 条全部自洽**：0 条出现"发布 accept，却给出自己的数字造不出的根"，也 0 条给出 JCS 造不出的规范化摘要。
2. **canonical 那 9 条是对得上公开标准的**：`JCS(text)` 逐条复现 `canonical_sha256` 与字节长度，9/9。这条是我们的新发现，也是把可复算比例从 35% 抬到 40% 的那 9 条。
3. **token 的签名能验，但 verdict 不能**：87 条里 **74 条的 Ed25519 签名在 `JCS(body 去掉 signature)` 上验得过**（17/17 的 accept 全部通过；13 条 reject 签不过，正合其 reject 预期）。签名约定可以从文件本身推出来，可 verdict 还要看 schema，所以 token 仍然计为不可复算——签名通过不是 verdict。
4. 所以"上游 0/3"那三条的毛病，量级就是三条，不是一类系统性错误。写成"他们有 171 条问题"是不诚实的，这份扫描正好挡住那种写法。

## 这份扫描不能证明什么

- **不等于跑过他们的验证器**。这里只重算文件里的数字与标准化摘要，没有执行他们的代码，也没有对他们的实现下任何结论。
- **0 矛盾不等于实现正确**。文件自洽只说明"测试数据没写错"，不说明"被测实现算对了"。
- **签名通过不等于 accept**。74/87 签名验得过，只是说签名层没问题；一条能被拒掉的向量照样可以带一个合法签名。
- **chain 那 15 条连签名都没试**：它们的记录是嵌套的，签名覆盖哪一段由 schema 决定，这次没有猜。
- **一次快照**。171 个文件的 sha256 全在收据里，任何人可以按 `39daf704` 重抓、逐个对哈希、再跑一遍拿到同样的 69/0/102。

## 怎么自己跑

一条命令，无需安装、无需 clone 上游：

```bash
python tools/stranger_competitor_check.py
# bytes: 171 checked, 171 match
# sweep: 171 vectors, 69 replayable, 69 consistent, 0 inconsistent, 102 not replayable
# control: 196 applied, 183 detected, 13 ambiguous, 0 unexplained
# VERDICT: REPRODUCED
```

它按顺序做三件事，任一步不一致就停在那一步并说清哪一条不对：

1. **下载**上游 `39daf704` 的 tarball（标准库，不装包），或 `--dir` 指向你手上已解包的副本；
2. **核对字节**：171 个文件的 sha256 逐个对收据 `corpus-sweep-39daf704.json`。字节不一致时后面什么都不算——"字节不是我们扫的那份"本身就是结论；
3. **重跑两个工具**并逐字段对收据，`--json` 输出一个对象供脚本消费，`--selftest` 不需要网络和语料。

用 git 手动复现也仍然可以（下面这套），但**一条命令**这条路才是外人真的会走的那条：

```bash
git clone https://github.com/probityai/agent-evidence-vectors && cd agent-evidence-vectors
git checkout 39daf704
python <this repo>/tools/sweep_competitor_corpus.py \
  --dir vectors-poc-evidence/package/poc_evidence_vectors/corpus --json
# TOTAL 171 vectors, replayable without their code 69 (40%), consistent 69, inconsistent 0, not replayable 102
```

`python tools/sweep_competitor_corpus.py --selftest` 是一组断言：常量、折叠、证明条数规则、下标规则、倒序尺寸规则、JCS 的键序与转义，以及最容易自我美化的那条——分类函数（accept+match 才算一致、reject+mismatch 才算一致）。

## 这个"0 矛盾"是能自己站住的：196 处改动，183 处被认出来

报"零"的工具，必须让人看见它会失手。"69 条自洽、0 条矛盾"是个否定结论；一个从没失败过的检测器，和一个永远输出零的检测器，在读数上分不出来。

所以再加一道自证（`tools/sweep_mutation_control.py`，收据 `docs/upstream-package/competitor-defects/sweep-mutation-control.json`）：拿**真语料**里那 69 条被判为一致的向量，逐条按"向量坏掉时的样子"改一处——根翻一个十六进制位、record 翻一位、proof 里某个哈希翻一位、proof 少一条、下标越界、声称的树尺寸变一格——再看扫描器还认不认它是"数字与 verdict 自相矛盾"。

| 类别 | 家族 | 施加 | 认出 | 尺寸歧义 | 无法解释 |
|---|---|---|---|---|---|
| inclusion | root / record / proof 位 / proof 丢 / index | 108 | 108 | — | 0 |
| inclusion | tree_size +1 | 22 | 14 | 8 | 0 |
| consistency | old_root / new_root / proof 位 / proof 丢 | 38 | 38 | — | 0 |
| consistency | new_size +1 | 10 | 5 | 5 | 0 |
| canonical | digest / len | 18 | 18 | — | 0 |
| **合计** | | **196** | **183** | **13** | **0** |

两点必须写清，否则这张表就会被读成 100%：

1. **183/183 是"改了算术的"，全部被认出。** 翻根、翻 record、翻 proof、丢 proof、挪下标——这些改动必然让折叠出的根或摘要变样，扫描器一次都没放过。
2. **13 处没认出来的是"只改了声称的树尺寸"**，而且这不是漏，是**算术看不见**：RFC 6962 的根不承诺自己的树尺寸，7 叶的证明在声称 8 叶时照样折回 7 叶的根。所以这类改动正确结论就是"数字仍然自洽"，单独计为 ambiguous，不计入成功也不计入失败。这条边界有正反两个断言钉住（`--selftest`）：2 叶改称 3 叶**必须**被认出（证明条数要求变了），3 叶改称 4 叶且证明仍是两条哈希**必须**认不出（这正是歧义）。

第 2 点不是我们独有的难题：对方语料里就有一条 `INC-O-size-not-bound-by-root`，写明"RFC 6962 的根不绑树尺寸，树尺寸必须由签名 token 认证"。收据顺带查出：171 条里有 **1 组**（`INC-N-root-altered`、`INC-N-wrong-tree-size`、`INC-O-size-not-bound-by-root`）三条共用一个 record、一个下标、一份 proof，只靠 `tree_size` 区分——歧义在他们的语料里是写下来的，我们的控制也把它照原样量了出来。

复跑：

```bash
python tools/sweep_mutation_control.py --selftest     # 13 个家族，11 个算术必认、2 个尺寸歧义
python tools/sweep_mutation_control.py --dir <unpacked corpus>
# TOTAL applied 196, detected 183, ambiguous 13, unexplained 0
```

改动是**确定性**的：翻哪一位由 `sha256(向量 id ‖ 家族名)` 决定，没有随机数，任何人跑同一份语料得到同一组改动、同一组数字，所以收据能被核对而不是被相信。

## 两个 HEAD：同一份字节，同一组数字

一个快照只能说明"那天是这样"。读者有权问下一句：他们后来改了吗，你这数字是不是过期了。答"我们也看过前一个 head，一样"是记忆，不是证据。所以两个快照各出一个文件清单摘要，比较本身是算术：

```
manifest_digest = sha256("path<TAB>sha256<LF" 每行, 按 path 排序)
```

| 快照 | 提交时间 | 文件 | 清单摘要 | 向量 / 可复算 / 一致 / 矛盾 / 不可复算 |
|---|---|---|---|---|
| `22764551`（`v0.38.0`） | 2026-11-24T19:15Z | 171 | `7169d876…` | 171 / 69 / 69 / 0 / 102 |
| `39daf704`（HEAD） | 2026-11-25T04:11Z | 171 | `7169d876…` | 171 / 69 / 69 / 0 / 102 |

两个 head 之间 **171 个文件一个字节都没动**，所以 69/0/102 不是某一天的偶然：他们没在这两次之间修过这批语料，我们的数字也不是快照造成的假象。收据 `corpus-snapshots-22764551-39daf704.json`（判定 `IDENTICAL`），旧快照的收据 `corpus-sweep-22764551.json` 只留摘要不重复 74 KB 清单——摘要相等就是同一批字节，`tools/compare_corpus_snapshots.py` 负责讲这句话，并且在那份摘要与 39daf704 的清单不再相符时失败。

有的读者会问得更远：这两个快照之后他们又改了吗？答案不能靠人记得。`tools/watch_upstream_corpus.py` 取上游**当前 head** 的语料、逐个摘要，与我们收据逐文件比对，只输出两种结论：`NO DRIFT`（同一批字节）或 `DRIFT`（点名改了/多了/少了哪些文件，并退出非零）。`.github/workflows/upstream-corpus-watch.yml` 每天 03:10 UTC 跑一次：没有漂移就安静，漂移就变红。它**只比对、不更新**——重扫并改收据是人做的事（数字、文档、图、登记行要一起动），这个作业只保证这件事不会被漏掉。

## 与我们自己的语料摆在一起：同一把尺子，两边都量

我们 63 条 RFC 9162 语料（inclusion 50 + consistency 13）没有一条要求读者信任我们的代码：每条都带正孪生、拒绝词表，并被 pymerkle、Sigstore `merkle.py`、Go `transparency-dev/merkle` 三份实现各自独立判过（`docs/THIRD-PARTY-CROSSCHECK.md`）。

但上面那句是**我们的自述**，而 69/171 是**我们量出来的**。把自述和测量摆在一起，读者只能信前者。所以最后一步是把同一把尺子转过来量自己：`tools/measure_own_corpus.py` 读 `docs/upstream-package/scitt-rfc9162/manifest.json` 与每条 `v1/<id>/expected.json`，用**与竞品扫描同一组函数**（`tools/verify_rekor_inclusion.py` 的 `_decomp_incl_proof` / `fold` / `root_from_consistency_proof`，直接 import，不是另写一份）重放全部 63 条。

| 语料 | 向量 | 可独立复算 | 一致 | 矛盾 | 不可复算 |
|---|---|---|---|---|---|
| 上游 `probityai/agent-evidence-vectors`（`39daf704`） | 171 | **69（40%）** | 69 | 0 | 102 |
| 本仓 `scitt-rfc9162` v1 | 63 | **63（100%）** | 63 | 0 | 0 |

这不是两个数字并排，而是**同一个判定函数的两行输出**：`classify()` 的规则也一样——accept 且折叠出所声明的根才算一致，reject 且算术确实说不行才算一致，其余都算矛盾或不可复算。收据 `docs/upstream-package/measurements/own-corpus-replay.json`（清单摘要 `f9079358fda950e1…`，63 条向量逐文件 sha256 在内）。

为了让"100%"不是自我美化，每条还过了三道互不替代的检查，分别计数：

- **叶摘要可重建** 50/50：`SHA-256(0x00 ‖ leaf_input)` 必须等于文件自己写的 `digest_hex`。只折根不算数——叶都没重建出来，"可复算"就是半句。
- **文件自己的重构根与我们的折叠一致** 57/57（有 57 条写了 `reconstructed_root`，另 6 条本来就无折叠可言：`tree_size=0`、新旧尺寸倒置、证明走不下去）。
- **拒绝词来自算术**：17 条 `INVALID_*` 全部由下标越界、证明条数不符、折叠不等、尺寸倒置、旧根不符这类**数字**触发，没有一条是"因为文件写了 INVALID 所以 INVALID"。

第三条之外还有一处必须自己说出来：63 条里有 **4 条是 `VALID_BUT_SIZE_UNAUTHENTICATED`**——根能认证叶，但认证不了声明的树尺寸。这不是我们语料的缺陷，是 RFC 6962 的算术边界；我们把它作为**独立结论词**写进向量、单独计数，而不是折成 VALID 混进 100%。上游同样的边界散在三条形似的向量里（`INC-N-root-altered` / `INC-N-wrong-tree-size` / `INC-O-size-not-bound-by-root`），只能靠上面的变异控制反向发现。

复跑（不需要网络、不需要上游语料）：

```bash
python tools/measure_own_corpus.py            # 63 vectors, replayable 63 (100%), inconsistent 0
python tools/measure_own_corpus.py --check    # 收据与语料不符则退出非零
python tools/measure_own_corpus.py --selftest # 14 条：常量、折叠、条数、下标、尺寸倒置、分类函数
```

这是本轮唯一可比的"体量"：**可被外人独立复算的向量条数**，不是总条数。总数（3,069 套件条目 vs 63）我们不比，因为追不上也不影响可核验性。真正的差别是**比例**：每一条我们的向量，读者都能用别的实现复算；对方的每一条，只有 40% 能做到这一点，其余 60% 只能选择相信。



