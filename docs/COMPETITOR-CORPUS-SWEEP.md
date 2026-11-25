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

画成图是同一件事，也来自同一对收据：`docs/CORPUS-REPLAYABILITY-SAME-RULER.svg`（由 `tools/build_same_ruler_svg.py` 生成，`--check` 让它在任一份收据变动时失效）。图的每一段长度都是读出来的，不是画的：`69 / 171 (40%)` 与 `63 / 63 (100%)` 两条柱子共用一个 171 的刻度，所以"比例"是眼睛也能核的。

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

## 那 102 条不是一句"不可复算"，是三种断法

"102 不可复算"这种话对读者没用：它只说了做不到，没说断在哪。`tools/build_upstream_ledger.py` 把 171 条逐条记成三层，**每一层只用文件自己写下的东西**：

| 层 | 判据 | 条数 | 占 171 |
|---|---|---|---|
| `verdict` | 用文件自述的叶、下标、证明、树尺寸、正文做 RFC 6962/9162 折叠与 RFC 8785 规范化，能直接得出发布 verdict | **69** | 40% |
| `signature-only` | 没有算术可言，但文件携带的每一个签名都在文件自携带的公钥下、对 `JCS(body−signature)` 验得过 | **88** | 51% |
| `nothing` | 以上都不成立：正文解析不了、没有签名、或签名验不过 | **14** | 8% |

逐族拆开（读自收据，不是手填）：

| 族 | 条数 | verdict | signature-only | nothing | 文件缺什么 |
|---|---|---|---|---|---|
| inclusion | 37 | 37 | 0 | 0 | 不缺：叶、下标、证明、树尺寸都在 |
| consistency | 23 | 23 | 0 | 0 | 不缺：两个根、两个尺寸、证明都在 |
| canonical | 9 | 9 | 0 | 0 | 不缺：正文与期望摘要、长度都在 |
| token | 87 | 0 | 74 | 13 | 验收规则（哪些 claim 必填、什么类型、怎么打标签）；正文只给 claim、密钥、签名 |
| chain | 15 | 0 | 14 | 1 | 把相邻记录串起来的规则（chain-break / sequence-gap / truncation / measurement）；记录只给单条 claim 与签名 |

三点值得说清：

1. **"签名验得过"不是 verdict。** 88 条里大多数发布结论是 reject——签名有效恰恰说明它不是被签名否掉的，而是被那套没随文件发布的 schema 否掉的。所以这一层只证明"这堆字节是自洽签过名的"，证明不了"他们的判定对不对"。我们把它单列一层，正是为了不把它混进 69。
2. **14 条 `nothing` 里没有一条是因为"我们懒"。** 13 条 token 是正文非 JSON（`parse-bom`、`trailing-comma`、`lone-surrogate` 等）、不带签名、或签名对不上；1 条 chain（`CHN-N-bad-signature-mid-chain`）是 6 条记录里第几条的签名翻了一位——这一条恰恰是这一层**抓到**的唯一缺陷，也是我们留着它的原因：这一层会失手，也会命中。
3. **判据没有任何一处来自向量名。** 名字只当标签用，`reach` 由 `arith` 与 `signature` 两列算出来，收据里每一行都带着这两列，读的人可以自己重算一遍 `reach`（`tests/test_upstream_ledger.py` 就是这样断言全部 171 行的）。

收据 `docs/upstream-package/competitor-defects/corpus-ledger-39daf704.json`（171 行逐文件、清单摘要 `7169d8760d1ac869…`，与扫描收据同一批字节）；`--check` 在任一行变动时失败。外人一条命令复得：

```bash
python tools/build_upstream_ledger.py --dir <…/corpus>            # 摘要打印
python tools/build_upstream_ledger.py --dir <…/corpus> --check    # 任一行与收据不符即退出非零
python tools/build_upstream_ledger.py --selftest                  # 7 条：可达级、翻转一位、正文非 JSON、自洽
python tools/stranger_competitor_check.py                         # 取上游 tarball，连这一层一起比
```

`tools/stranger_competitor_check.py` 现在多打一行 `ledger: 69 verdict, 88 signature-only, 14 nothing, 88 signatures verify`，并把这份收据**逐行**比对：某一条向量的可达级别动了，就算 `DID NOT MATCH`，不是四舍五入。

一句话的差别：我们的 63 条**每一条都落在 `verdict` 层**；他们的 171 条里 69 条落在这一层，另 88 条只到签名，14 条连签名也到不了。

画成一张图是同一件事：`docs/UPSTREAM-REACH-LADDER.svg`（`tools/build_reach_ladder_svg.py --write` 生成，`--check` 在任一份收据变动时失效）。三段柱共用 171 刻度，段长全部读自收据，柱下还按族给出 `verdict/signature-only/nothing` 三个计数；我方 63 条画在同一刻度上，整条落在 `verdict` 段。

## 那 69 里有 36 条不靠我们的代码

到上一层为止，69 个可复算的 verdict 全是我们自己的折叠函数算出来的——这正是我们自己立的规矩所反对的：得出数字的代码同时充当数字的证书。

所以把竞品的 inclusion 字节交给一份**不是我们写的**实现：`tools/third_party/sigstore_merkle.py`（上游 Rekor 的 Trillian 折法，随仓 vendored，与 `tools/verify_rekor_inclusion.py` 不同一条代码路径），只问一件事——按对方自述的叶子、下标、证明往上折，能不能落在对方自述的根上。

| 口径 | 数字 |
|---|---|
| 竞品 inclusion 向量 | 37 |
| 被该实现折过、可比 | **36** |
| 与其发布 verdict 一致 | **36 / 36** |
| 与我们扫描收据的行一致 | **36 / 36，0 分歧** |
| 未比 | 1（`INC-N-size-zero`：该实现没有 `MTH({})`，不比不判） |

三条边界必须一起说：

1. **只覆盖 inclusion。** consistency 23 条与 canonical 9 条仍是我们自己的算术——这份 vendored 代码没有 consistency 折法，我们也不拿它冒充。收据 `covers` 字段写死这句。
2. **size=0 的那条不比，不算通过。** Sigstore 的空树无根，我们的常量在那里无法被它佐证；把它计成一致就是拿缺席当证据。
3. **一致不等于我们对。** 两份实现同错是可能的；这条只说明"不是我们一家算出来的"。

收据 `docs/upstream-package/competitor-defects/inclusion-second-implementation.json`（逐条 37 行，清单摘要与扫描收据同一批字节），`--check` 任一行变动即失败；外人一条命令 `tools/stranger_competitor_check.py` 现在多打一行：

```
inclusion folded by vendored Sigstore: 36 of 36 agree with the published verdict, 1 not compared
```

复跑：

```bash
python tools/crosscheck_competitor_inclusion_sigstore.py --dir <…/corpus>            # 摘要
python tools/crosscheck_competitor_inclusion_sigstore.py --dir <…/corpus> --check    # 任一行变动即失败
python tools/crosscheck_competitor_inclusion_sigstore.py --selftest                  # 7 条
```

## 干净机器上的实测：一条命令，和一个必须先说清的依赖

2026-11-25 在云主机（Linux，Python 3.12.11，全新解包的 `232deb4c` tarball，没有 clone、没有装包）跑了 `python3 tools/stranger_competitor_check.py`：

```
bytes: 171 checked, 171 match
sweep: 171 vectors, 69 replayable, 69 consistent, 0 inconsistent, 102 not replayable
control: 196 applied, 183 detected, 13 ambiguous, 0 unexplained
ledger: 69 verdict, 88 signature-only, 14 nothing, 88 signatures verify
inclusion folded by vendored Sigstore: 36 of 36 agree with the published verdict, 1 not compared
VERDICT: REPRODUCED
```

同一台机器上用**裸解释器**（`python3 -S`，无 site-packages）再跑一次，暴露出一个此前只有 Windows 测试时才看不见的问题：**ledger 的签名字段需要 `cryptography`**，缺失时它把 88 条记成 `nothing`，于是逐行比对全部不符，命令输出 `DID NOT MATCH`。这等于把"读者少装一个库"报成"我们的数字对不上"。

修法不是让它猜，而是让它**拒绝**：`build_upstream_ledger.py` 在缺库时抛 `SignatureLayerUnavailable`（exit 4，`NOT EVALUATED`），`stranger_competitor_check.py` 捕获后输出 `PARTIAL: the arithmetic matched; the ledger's signature layer was not evaluated`（exit 3），并提示 `pip install cryptography` 以拿到完整结论。

于是依赖边界现在写在了两条命令的头上，而不是写在文档的脚注里：

| 步骤 | 需要什么 |
|---|---|
| 171 个 sha256、扫描、变异控制、Sigstore inclusion 折 | 仅标准库 |
| ledger 的签名列（88 条） | 再加 `cryptography` |

`tests/test_stranger_competitor_check.py` 用 `python -S` 跑该工具的 selftest 来钉住这条线：算术步骤在任何解释器上都必须能跑。

## 外人的一次实跑，怎么留成可以被机器复核的东西

前一节说的是"外人能自己跑出来"。跑出来之后呢？截图不可核，口述不可核，连"我跑过了"这句话本身也不可核。所以这条命令多了一个出口：

```
python tools/stranger_competitor_check.py --dir <corpus> --receipt out.json
```

`out.json` 只记这台机器当场算出来的东西：171 条的 `checked/match`、扫描四个计数、变异控制四个计数、ledger 四个计数（或"未评估"及其原因）、第三方折的 `compared / agree / not compared`、verdict、退出码、Python 与平台版本，以及**这份 receipt 自己的 sha256**。

复核用另一条命令，在**另一台机器**上重算：

```
python tools/verify_external_run_receipt.py --receipt out.json --dir <corpus>
```

它核四件事：receipt 的 `format`、receipt 自身 sha256 是否覆盖它的内容、`tool_sha256` 是否等于本机正在跑的那份工具、以及每个计数/verdict/退出码是否与重算结果逐项相等。任何一项不符就点名到字段：

```
DIFF sweep.n_replayable: receipt says 70, this machine recomputes 69
VERDICT: NOT VERIFIED
```

实测（本机 Windows，Python 3.13.18，装了 `cryptography`）：`--receipt` 写出后立刻复核 → `the receipt's 8 checks, verdict 'REPRODUCED' and code 0 are what this machine recomputes` / `VERDICT: VERIFIED`。

### 这条通道不开哪扇门

receipt 里**没有身份字段**，复核器也不声称知道是谁跑的。它能证明的是"这些数字在某台机器上被算出来过、且与我在本机重算的一致"，不能证明"跑的人是张三"。所以 `docs/EXTERNAL-RUNS.json` 的 `headline` 仍然是 **0**——我们自己跑的、包括在云主机裸解释器上跑的，都不算外部实跑。这条工具把"想让人核"变成"可以核"，但把"有人核过"留给真的有人来核。

### 一栏在两边不对称时：说明范围，而不是判它错

ledger 那一栏取决于机器：没有 `cryptography` 的机器写出的 receipt 没有这一行，有库的机器能算出来；反过来也一样。所以复核器碰到这种不对称时不报 `DIFF`，而是给一句范围说明，并把结论写成 `VERDICT: VERIFIED (arithmetic only)`：

```
note: the receipt's ledger step was not evaluated where it was written
      (no cryptography); this machine has it, so that row cannot be
      compared - the arithmetic can
the receipt's 4 comparable checks are what this machine recomputes
VERDICT: VERIFIED (arithmetic only)
```

verdict 与退出码跟着那一栏走：跳过了 ledger 的 receipt 记 `PARTIAL`/3，能算的那台记 `REPRODUCED`/0，所以它们也不跨这一栏比；但 receipt 自身必须自洽——跳过 ledger 却写 `REPRODUCED` 会被直接点名（测试里有这条）。\n\n这条规则的理由和上一节一样：**读者少装一个库，不该被记成我们数字不对**；但也不能把"少核了一栏"说成"全核过了"，所以结论后面直接带上 `(arithmetic only)`。

## 那 171 条现在就在仓里：复算不需要下载

此前"你自己跑一遍"隐含一个条件——codeload 要通。对一个要证明"可独立复算"的项目，这是没必要的门槛，也是没必要的争点。

这 171 个向量现在原样躺在 `docs/upstream-package/competitor/corpus/`（340 KB，171 个 JSON，Apache-2.0，`NOTICE.md` 写清来源与"字节未改"）：

```
python tools/stranger_competitor_check.py      # 不加 --dir，读的就是随仓的那份
```

```
bytes: 171 checked, 171 match
sweep: 171 vectors, 69 replayable, 69 consistent, 0 inconsistent, 102 not replayable
control: 196 applied, 183 detected, 13 ambiguous, 0 unexplained
ledger: 69 verdict, 88 signature-only, 14 nothing, 88 signatures verify
inclusion folded by vendored Sigstore: 36 of 36 agree with the published verdict, 1 not compared
VERDICT: REPRODUCED
```

**代价是要多守一件事**：字节进了仓，"有人改了一个向量而收据照旧"就成了真实风险。所以多了第八道门 `tools/verify_vendored_corpus.py --check`，它不信清单、只信字节：

| 断言 | 内容 |
|---|---|
| 文件列表 | 磁盘上 171 个文件与 `MANIFEST.json` 逐条对齐，缺、多、改都点名 |
| 清单自身 | 清单写的 `manifest_digest` 必须等于它自己那些行重新哈希的结果 |
| 与旧账对得上 | 该摘要必须等于快照收据 `corpus-snapshots-22764551-39daf704.json` 里记下的 `b_digest` = `7169d876…` |

第三条是最要紧的：清单的摘要口径**不是我新定的**，就是扫描与分层账在用的那套（`corpus/` 前缀 + 制表符 + sha256 + 换行，按路径排序）。如果我用一套新口径，一致性就成了自己跟自己比。

`--selftest` 8 条，其中两条是负对照：翻一位必须被抓到且点名文件；私自塞进一个向量必须判"多出来的"而不是默认采纳。测试 `tests/test_vendored_corpus.py` 6 条，另钉住一条——**不加 `--dir` 时必须跑随仓那份，并且打出 `VERDICT: REPRODUCED`**。

**一条补充（本轮实测）**：把 `outsider_rerun.py --check` 收进审计时它红了，原因不是编辑而是**投递**——本仓 83 个 blob 按 CRLF 存、`.gitattributes` 声明 `text=auto eol=lf`，于是 `git archive` 的字节与 Linux 检出的字节不同。收据因此多记一根折行轴（`content_lf_sha256`）与 `delivery`，`--check` 只在纯换行差异时报 `VERDICT: DELIVERY MATCH`（exit 0），真有字节动仍报 `CONTENT`（exit 1）。另外它比的是**提交（HEAD）**而不是工作区：同一个 job 里排在它前面的步骤会往树里丢文件。见 A32、A33。

## 最后一条：审我们自己，也只要一条命令

上面每条结论都有各自的 `--check`。但它们是**分开**跑的，而且通常是在一个被很多次编辑过的树里跑——那正是陈旧最容易藏身的地方。

`tools/stranger_own_check.py` 把七件事一次跑完，并可以在**一份不是我们生成的副本**上跑：

| 检查 | 对应的 `--check` / 门 |
|---|---|
| `own-corpus-receipt` | 我方 63 条收据是一次新鲜测量（`measure_own_corpus.py --check`） |
| `coverage-picture` | 覆盖度图由扫描收据重建（`build_corpus_sweep_svg.py --check`） |
| `two-ruler-picture` | 两比例同轴图由两份收据重建（`build_same_ruler_svg.py --check`） |
| `reach-ladder-picture` | 可达阶梯图由收据重建（`build_reach_ladder_svg.py --check`） |
| `ledger-invariants` | 分层账自身不变量成立（`build_upstream_ledger.py --selftest`） |
| `claims-vs-receipts` | 每个锁定断言仍等于其收据（`audit_claims_receipts.py`） |
| `evidence-index` | 证据索引是这棵树的扫描（`build_evidence_index.py --check`） |

两种跑法：

```bash
python tools/stranger_own_check.py            # 当前检出
python tools/stranger_own_check.py --fresh    # 抓 main tarball，在干净副本上跑
```

实跑两种路径都是 `8 passed, 0 failed` → `VERDICT: SELF-CONSISTENT`。`--fresh` 那条尤其值得看：它证明的不是"我的树是干净的"，而是"**别人拿到的那份 main，七道门全过**"。任一检查失败会打一行原因（失败检查的首行输出），所以"不复现"从来不是一句没有下文的话。

边界：它审**自洽**，不审**正确**。收据可以是错的，只要七处都与它一致；正确性靠前面的算术、第三方实现、变异控制与外部实跑去证明。这条只保证一件事——**没有任何一页比它引用的收据更新或更旧**。
