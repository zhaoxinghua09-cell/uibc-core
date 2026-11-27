## 0.5.8 — 2026-11-27 构建（**未发布到 PyPI**：缺 trusted publisher）

- **构建事实**：本机（Windows 10 / Python 3.13）`tools/build_conformance_bundle.py 0.5.8` → `conformance/uibc-conformance-0.5.8.zip` **389,203 B** / `sha256:a5c0e5b703ee8dd9293844d759df9cf2fad2b865c9271c98c7548393ddf71ffc`，pin `anchors/pins/uibc-conformance-0.5.8.sha256`；空目录 `python run.py` → `strict 58/58`，rc=0。**同一棵树在 Linux 上构建得到的是另一套字节（389,201 B / e57c052f…）**——归档并不跨操作系统逐字节相同，所以 pin 必须连"哪台机器构建"一起说。
- **为什么不是把 0.5.7 升为正门**：0.5.7（389,197 B / `fd37e0f8…512a`）已公开、pin 已发布。升正门要改版本串 → `uibc_core.pyz` 变 → 必须重封 → 覆盖已公开字节，撞 `tests/test_published_bytes_are_never_rewritten.py`。一个版本号对应一套字节，所以另起 0.5.8。
- **没有发布，是决定**：PyPI 上本仓仍无 trusted publisher 条目（0.5.0–0.5.6 都走 long-lived token，`tools/check_pypi_provenance.py` 报 `2 of 2 file(s) lack provenance`）。条目建好之前推 `v0.5.8` 只会再造一份无 provenance 的产物，故 **tag 未推、PyPI 未动**。
- **换行这条写下来**：归档与回执必须在 **git 归一化之后的工作树**上产生。用 Git-data API 传 blob 不经过 `text=auto eol=lf`；而手动把整树刷成 LF 会改坏 `accept-binary` 这类本来就存 CRLF 的用例（58 → 57）。这次只改动了版本、文档与 pin 这几处文本，语料与 oracle 的字节一律不动。
- **发布页读 pin 的读取器修了一处**：`tools/make_release_pin.py` 先试 `gh release view <tag> --json assets`，再退回两条 API 查询。第一次推 tag（run 45987858244，v0.5.8 的首个 tag）时两条 API 查询都以 `cannot read v0.5.8: cannot iterate over: null` 结束，页面上却明明有九个附件——于是发布页因缺自己的 pin 一直停在 draft。`gh release view` 对 draft 与公开页都能解析，不再拿 null 去迭代。
- **生成器改了一处**：`tools/outsider_rerun.py` 写 `docs/outsider-rerun-receipt.json` 与 `docs/OUTSIDER-RERUN.md` 时显式 `newline="\n"`。此前在 Windows 上这两个文件按平台默认写成 CRLF，而仓库以 `* text=auto eol=lf` 归一化，于是同一棵树在两台机器上算出的摘要不同（实测 2,517 vs 2,521 文件、两套 tree 摘要）。改成 LF 之后，这类文件不再随构建主机漂移。
- **别人拿自己的包来测这条入口已入仓**：`tools/bring_your_own.py` + `interop/CONSUMERS.json` + `interop/README.md` + `tests/test_bring_your_own.py`。判据不看退出码：`accept` 只要有一条检查报 FAIL 就算失败，`reject` 只要拒了却没点出你写的那条检查也算失败；setup 问题退 3 且**不写回执**；回执里的 `run_by` 原样记录、没人签名就留 null。实测：对随包 58 例 **58/58**（`--from-kit` 与 `--pyz <zip>:uibc_core.pyz` 两种取法都跑过），对项目外三个包 **3/3**。`CONSUMERS.json` 把「产什么、吃什么、还吃不下什么」写成机器可读：其中 SCITT COSE 向量明确记为 `not-consumed`（直喂 0/3，经外部 rail 27 条 0 通过）。
- **派生件**：`conformance/oracle` 30 例按 0.5.8 重发（与 main 逐字节只差版本串，往返不一致 0 处）；`conformance/MANIFEST.sha256` 795 条。

## 0.5.6 — 2026-11-27 发布（格式 v2：未声明证据从「点名告警」升为「默认 FAIL」）

- **发布事实（发版后补写，放在最前面，因为读者先要的是字节和哈希）**：PyPI `uibc-core 0.5.6` 于 2026-11-27 01:46 UTC 上传 —— `uibc_core-0.5.6-py3-none-any.whl` 226,327 B / `sha256:34eda43c…5699`，`uibc_core-0.5.6.tar.gz` 3,940,189 B / `sha256:2b31e7af…0b80`。一致性语料归档 `conformance/uibc-conformance-0.5.6.zip` 388,388 B / `sha256:31bbeff40e67…9d14`，pin 见 `anchors/pins/uibc-conformance-0.5.6.sha256`；同一棵树上重跑 `tools/build_conformance_bundle.py 0.5.6` 得到同字节（该工具有 `identical:` 分支）。
- **语料没有跟着重封（这是决定，不是漏做）**：`conformance/cases` 仍是 0.5.5 时期封的那批，`min_verifier_version` 留在 `0.5.0`。原因是被 `Trusted verify (base-owned oracle)` 打出来的：用 0.5.6 重封 58 例会把每例门槛抬到 0.5.6，而那条 job 用**基线树**（本次 PR 的基线是 0.5.5）判 PR 的语料，读到高于自己的门槛就判 INCONCLUSIVE —— 6 个 accept 例当场全变 INCONCLUSIVE，job 记 MISMATCH。所以语料与验证器分两轮：这一轮升验证器、语料保持旧封；下一轮再重封，并事先接受"基线判不了"这个已知结果。`conformance/oracle` 的 30 例与本轮一致（`tools/oracle_check.py` → `ORACLE: PASS`）。
- **两件 PyPI 产物都没有 provenance**：本轮仍走 long-lived token（`twine` + `__token__`），不是 trusted publishing；`python tools/check_pypi_provenance.py --pkg uibc-core --version 0.5.6` 报 `2 of 2 file(s) lack provenance`。0.5.0–0.5.5 同缺陷，未修。
- **Zenodo 没有为 0.5.6 存缴**：`CITATION.cff` 因此仍钉 `0.5.5`（tests/test_archive_scope.py 把这条钉死）。拿 0.5.5 的 DOI 去引 0.5.6 的字节是错的，README 也这样写。

- **release 页那句话是假的，本轮改掉（2026-11-27 复核时发现）**：README 与 `docs/AUDIT-KIT.md` 曾写 "release page carries the same bytes, attached on 2026-11-27"。实测 `GET /repos/zhaoxinghua09-cell/uibc-core/releases/tags/v0.5.6` → **404**：`v0.5.6` tag 被 `release-tags-immutable` 规则集冻住（tag 不可删、不可复用，第二个 release 报 `tag_name was used by an immutable release`，已上传的副本停在草稿里）。这一轮把两处改成"release 页不承载该归档、只从树内 raw URL 取"，`tools/check_outsider_entry.py` 改成"要么点名活资产、要么明写 release 页不承载"，并堵住"文档打印 404 链接"这一类；新增两条回归（`tests/test_outsider_entry.py`）。顺带修掉 `docs/AUDIT-KIT.md` 里 0.4.1 段把 36 例写成 `58/58` 的旧笔误。
- **外部 AI 逐例复核的另一条发现（P1，未修）**：SiliconFlow `deepseek-ai/DeepSeek-V3` 独立跑完 58 例，54 例与期望一致；4 个 accept 例（02/03/04/05）被判拒，理由是它把"`evidence/` 下所有文件必须在 manifest 里声明"当硬规则，而本格式允许追加树/追加证据。共识率 93.1%，但这条说明**规范文字不足以让独立判读者推出"允许扩展"**，属下一轮要补的判定文本。

- **上一轮留下的那句话，这一轮做掉**：0.5.5 把沉默改成点名（`warnings` + stderr 一行），但默认仍判 PASS。当时写明的理由是"这是格式版本问题，不是补丁"。现在按版本做：`uibc submit` 在 `manifest.json` 写 `format_version: 2`，验证器读到 2 即对 `evidence/` 下索引未声明的文件判 **S1 FAIL**，不必加 `--strict`。
- **为什么不追溯收紧 v1 包**：一个 2026-11 之前封的包，封的时候规则是宽松的。事后把它判死，等于用今天的法判昨天的手续。v1 包（manifest 无该字段或为 1）行为完全不变：S1 PASS + `warnings` 点名它放过的文件，措辞里写明"本包为 format v1"。
- **未知版本不按 v1 判**：`format_version: 3` 这类本验证器没实现的值，S1 判 `INCONCLUSIVE`，detail 点名版本号与"已知 1、2"。理由与 `min_verifier_version` 门槛同构——拿旧规则判新格式，会在自己没读过的字段上报 PASS。
- **改动面**：`uibc_core/verify.py`（读 `format_version`、`evidence_complete = strict or fmt == 2`、S1 三态、报文新增顶层 `format_version`）；`uibc_core/cli.py`（`submit` 写 `format_version: 2`）；`__init__.py` 版本 0.5.5 → **0.5.6**；`docs/STRICT-MODE.md` 增 v2 一节与迁移说明。
- **测试**：`tests/test_strict_mode.py` 8 → **15** 项，新增 7 条（v2 不传 flag 即 FAIL、v2 干净包 S1 PASS、v2 仍豁免格式结构件、v1 保持 note+warning、v3 判 INCONCLUSIVE、`.lock` 不算证据、点文件不能借 `.lock` 的豁免）。全量结果见文末实测行。
- **改这一版时被自己的新规则打了一拳（记在这里，因为它比改动本身重要）**：v2 一上来，本仓自己刚封的包**全部 FAIL**——`uibc_core/locking.py` 往 `evidence/.lock` 写锁文件，而 v2 把 `evidence/` 下每个未声明文件都判死。处理方式不是"把 v2 放宽"，是**按名字豁免 .lock**（`_EVIDENCE_NOT_EVIDENCE`），并另加一条负控：`evidence/.payload` 这类点文件**仍然 FAIL**。按"任何点文件都豁免"会直接开出藏证据的口子。
- **同一轮发现的第二个真缺陷（S13 覆盖率）**：`evidence/merkle.json` 删掉两个证明、size 与 root 仍描述整棵树时，**open 与 pinned 两档都 PASS**（corpus_erm E2 root-untouched）。原因：S13 只验证"递上来的证明"，从不问"每片叶子是否都有证明"——`size 5 / root X / 3 个 proof` 被读成一棵完整的树。已改为**必须覆盖每个索引文件**，缺一条即 FAIL。这条属判决口径变化，写在版本号里（0.5.6）。
- **ERM 三族并进自测（D2）**：新增 `tools/corpus_erm.py` + `benchmarks/corpus/mutation-corpus-erm.json`（15 例）+ `tests/test_corpus_erm.py`（4 条）。族：`seal-encoding`（base64 等价写法，S6 拦 6/6）、`merkle-double`（删两叶证明，S13 拦 3/3）、`trunc-recompute`（截断并重算两个 head，S8 拦 3/3）、`evidence-dotfile`（点文件负控，S1 拦 3/3）。**不并进 500 例**：500 例的条数与族名被十余处断言钉住，重编号会让"同一批用例"失去可比性。
- **一条预测被自己的语料推翻**：我原本把 `trunc-recompute` 预期为"存活"（包内没有东西能证明曾经更长），实测 **S8 三例全拦**。已按实测改写 docstring 与文档：自洽缩短拦得住，**回滚**（换成更旧的、自洽的包）才是只能靠外部钉 head 的那一类。
- **500 例：重生成，结论不变**。`BASE` 现在由 0.5.6 产出（带 `format_version: 2`），重跑 `tools/mutation_corpus.py`：open **60/500 = 12.0%**、pinned **20/500 = 4.0%**、head-pinned **0/60**，与上一版逐字相同；变化的只是每族 `caught_by` 更全（`evidence-add` 现在也记 S1）。`docs/MUTATION-CORPUS.md` 由工具重生成（新增 ERM 一节），`tools/build_corpus_doc.py` 里写死的 `D:\lgd-work\uibc-core-r19` 改为**相对路径**——那是作者机器上的路径，外人克隆后跑不通。
- **对 ERM 表的影响（诚实记账）**：本仓 `M06` 现在分两种情况——v2 包**必拦**，v1 包仍 PASS 但带点名告警。对外表格的"逃逸"格应改为"v1 包逃逸 / v2 包不逃逸"，而不是笼统写"已修"。

## 未发布 — 2026-11-27（PASS 不再沉默：放过的文件要点名，而不是只藏在 S1 的 detail 里）

- **起因（外部实测，不是自查）**：ERM（Escape-Rate Matrix）用与 proofbundle/proofline 同一套 12 族变异器打本仓，`M06 注入未声明文件`（往 `evidence/` 放一个 index 从未声明过的文件）在 open / `--pubkey` / `--expect-head` **三档都返回 PASS、退出码 0**。同一族对两家第三方验证器都是 FAIL。
- **为什么不直接改默认**：`tests/test_strict_mode.py` 开头那句理由是真的——格式自己就往 `evidence/` 放树、链、锚点、策略件，把所有未声明文件判死会让现存包全灭。这是**版本问题**，不是补丁问题，所以默认仍 PASS。
- **改的是"沉默"这一半**：`verify()` 的报文新增顶层 `warnings`。宽松模式下若 `evidence/` 下有 index 未声明的文件，`warnings` 里出现 `{code: "S1_UNCOMMITTED_EVIDENCE", detail: ...}` 并点名到文件；`--strict` 已经判 FAIL，故不再重复告警；干净包恒为空数组。CLI 把同样一句打到 **stderr**（`warning [S1_UNCOMMITTED_EVIDENCE]: …`），stdout 的 JSON 契约与退出码一个字节不动。
- **为什么放在顶层而不是只写 detail**：detail 是给人读的字符串，机器无法门控。现在调用方可以写 `if report["warnings"]: 升级为人工复核`，不必解析中文括号。这一条同时把"我们量别人、不量自己"的口子堵上——ERM 表里本仓那一行的逃逸项附了修复状态。
- **实测**：`tests/test_strict_mode.py` 8 passed（新增 4 条：宽松模式点名、严格模式不重复告警、干净包无告警、CLI 保留 `"strict": true`）；全量 `pytest tests` 2156 passed / 31 failed / 31 skipped——31 failed 为**先于本次改动即存在**的环境性失败（RFC3161 真令牌、发布者时间戳、thesis 表、JS 验证器），已用 `git stash` 在改动前后同一子集对比确认（5 failed / 21 passed 两次一致）。
- **留待版本化**：`M18 root extra file`（包根未声明文件）本来就判 FAIL，未受影响；把"未声明证据"从告警升为默认 FAIL 仍应走 format version bump。


- **为什么扩**：25 家是代表取样，评委最容易的攻击是"你挑了弱的"。这次按 org 分散补 15 家（`TBD54566975/ssi-sdk`、`TBD54566975/dwn-sdk-js`、`cheqd/cheqd-node`、`cheqd/sdk`、`kiltprotocol/kilt-node`、`iotaledger/identity.rs`、`digitalbazaar/jsonld-signatures`、`digitalbazaar/vc`、`transmute-industries/verifiable-data`、`alastria/alastria-identity`、`energywebfoundation/iam-client-lib`、`hyperledger/aries-framework-javascript`、`openwallet-foundation/acapy-plugins`、`blockchain-lab-um/masca`、`web3id/web3id`），同一组正则、同一 `score_one`、每家钉 commit。
- **结果**：40 家，最好仍 **3/10**（现在 11 家并列 3 分），本仓 **10/10**；分布 0 分 **27** 家、1 分 1 家、2 分 1 家、3 分 11 家。**扩样没有把结论变小，也没有把差距变小**。
- **门槛同步抬**：`MIN_REPOS` 25 → **40**、`tests/test_competitor_parity.py` 的仓数下限同步；样本只能变大，不能缩。
- **两处真缺陷被扩样打出来**：① 解包器遇到上游 tar 的**绝对符号链接**（`iotaledger/identity.rs` 的 `bindings/wasm/.license_template`）整包失败 → 改为按成员逐个解（只写常规文件，链接跳过）；② 引用实测把**一次 TLS 抖动记成死链**（17 条 status=0）→ 加三次退避重试。重测：**40 条引用 0 死、9 条 301 且 9/9 在新名下仍 200**。
## 未发布 — 2026-11-26（清单从收据里请出来：8 KB 的收据 + 一行一文件的账本）

- **问题（自己上一轮留下的）**：上一轮把逐文件 sha256 塞进了 `docs/outsider-rerun-receipt.json`，收据从 8 KB 涨到 305 KB。功能对，但两件事变糟：一是只有机器愿意打开它，人翻不动；二是一个文件动了，diff 里显示的是一整行 300 KB 的 JSON 变红，看不出是哪一条。
- **做法**：清单独立成 `docs/OUTSIDER-FILES.txt`，一行 `sha256  path`，按路径排序；收据里只留一个引用 `files_manifest: {path, sha256, entries}`。`--run` 两份一起写；`--check` 先验清单自身的 sha256 与条数（**清单被手改也会被抓**，`MANIFEST FILE: … was edited`），再逐文件比对点名 `DRIFT`。清单与收据、看板、生成页一起进摘要排除集（四件，测试里的断言跟着改）。
- **实测**：收据 **2 097 B**、清单 **283 879 B**（2456 条）；`OUTSIDER OK: receipt matches this disk (2456 files, 30887a3b83bd, content f5e6e4af6dd1), 4 steps passed`；`INVENTORY OK (2460 paths, all present)`；`BOARD OK`；`tests/test_outsider_rerun.py + test_outsider_board.py` 22 passed / 1 skipped。
- **边界**：拆开不改变任何一根轴（四件生成物照旧排在外面）；变化只在"人能读"和"git diff 认得出来"。断言 A37。

## 未发布 — 2026-11-26（收据能点名"是哪个文件动了"，不再只说"有字节动了"）

- **问题**：三根摘要只能回答"动不动"，回答不了"哪个"。上一轮把成员的来源钉死之后，剩下的失败信息仍然是一句 `CONTENT: receipt describes tree … but this tree hashes to …`——对一个外人来说，这句话没有下一步；对我们自己也是：跑完整套 `pytest` 会重写 `tools/out/mutation_benchmark.json` 里的 `meta.generated_at_utc`，于是重封前后摘要一定变，可是报告里看不出是这个文件。
- **做法**：收据多一栏 `files_sha256`——每个成员一条 sha256（排除三件生成物）。`--check` 先按文件逐个比对，对不上的直接打 `DRIFT <path>: receipt <前 12 位> now <前 12 位>`（最多 8 条，多的报总数），再给结论。原来那句写死"可能是 mutation_benchmark.json"的提示换成"上面点名了"。
- **代价与边界**：收据从 8 KB 变成约 230 KB（2455 条）。它本来就在摘要排除集里，所以三根轴一个数都没动；换来的是一句话：**换一台机器、不联网、不装 git，也能说出是哪一个文件的哪一个字节变了**。
- **实测**：跑完整套 `pytest`（2162 条）之后 `--check` 现打 `DRIFT tools/out/mutation_benchmark.json: receipt … now …`；把该文件从提交里还原、再 `--run` 重封，`OUTSIDER OK: receipt matches this disk (2455 files, 86c05b15a2e8, content 904ddf75ae20), 4 steps passed`。
- **通道对齐（同一轮内自查发现）**：清单必须取自**收据声称的那一条通道**。克隆里 `git cat-file` 的 blob 是存储字节，检出按 `.gitattributes` 规整成 LF——若清单固定从磁盘取，CI 每次都会把 83 个文件误报成 `DRIFT`。所以 `run()` 用提交视图时清单也从 blob 生成，`check()` 按命中的视图取；换行差异（`DELIVERY MATCH`）与坏名（`NAMES-ONLY`）这两种已解释的情况下不再打印 `DRIFT`，免得用一份真清单去回答另一个问题。
- 断言 A36；`tests/test_outsider_rerun.py` 增 2 条（收据带每文件清单；改一个字节要点名到那个文件）。

## 未发布 — 2026-11-26（收据的"成员"不再取决于这台机器上恰好有什么）

- **起因（实测缺陷）**：同一棵树上先跑一遍测试、再 `--run`，收据写下了 **2819 个文件**；而陌生人从这里克隆或解包得到的是 **2453**。差的那 366 个是测试跑出来的草稿（`benchmark/corpus/cases/M01/evidence/.lock`、`files/action.log` 等），仓里从未提交。也就是说，收据把"作者机器上的残留"记成了"仓库的样子"——正是我们一直在找的那类问题：同一句话，两个人打开看到不同的数。
- **为什么不能靠 `.gitignore`**：第一版按 `.gitignore` 排除，把 `dist/` 也排掉了——那是仓里**故意 force-add** 的发布件，`.gitignore` 写着忽略、git 却照样跟踪。猜不出"忽略"与"已跟踪"的差别，就会在另一头错。
- **做法**：把成员**发布**出去。`docs/TRACKED-FILES.txt` 一行一个路径；`tracked_files()` 有 `.git` 时问 `git ls-files`、没有时读这份清单，不再"看见什么算什么"。写这份清单只有两条路：克隆里问 git，或一棵**新鲜归档**上显式 `--inventory-write --from-archive`（这是工具唯一无法自证、必须由调用者声明的一句）；跑过测试的树一律拒写。新增 `--inventory-check`：有 `.git` 时与 `git ls-files` 求对称差，差一条即 FAIL。
- **实测**：故意塞入 `benchmark/corpus/cases/M99/evidence/scratch.log` 后 `--check` 仍是 `OUTSIDER OK: receipt matches this disk (2455 files, fdec7f0c32e7, content …), 4 steps passed`；`INVENTORY OK (2458 paths, all present)`。
- **顺带修掉**：旧格式收据（只有 `tree_sha256`，无 `content/lf/delivery`）现在被按名字拒收，`VERDICT: STALE RECEIPT (4 field(s) missing)` 并附修法；看板 `--check` 同样给判决而不是 `KeyError`。
- **已知副作用（不改代码，写在这里）**：跑完整的 `pytest` 会重写 `tools/out/mutation_benchmark.json`，差在一个 `meta.generated_at_utc` 时钟戳。它在成员清单里（克隆者也有这份文件），所以重封之后摘要会动；`--check` 现在在纯 `CONTENT` 失败时直接点名这件事和修法（从提交里还原，或重新 `--run`）。
- 断言 A35；`tests/test_outsider_rerun.py` 增 3 条（草稿不动摘要、清单缺口点名、旧收据拒收），`tests/test_outsider_board.py` 增 1 条。

## 未发布 — 2026-11-26（真装真跑 + 301 落到新名 + D3 区间进正表）

- **真装真跑（`tools/parity_realrun.py`）**：把 `did-jwt`@`63663c1f` 和 `ethr-did-resolver`@`6e0bd477` 装到 `D:\realrun` 跑它们自己的套件。
  - `did-jwt`：16 文件 / **506 用例全过** / 4.22 s / exit 0。额外探针 `pnpm run canary` 退出 1，原因是 `canary/unpack.mjs` 用 `new URL(import.meta.url).pathname`，在 Windows 上把路径算成 `D:\D:\realrun\did-jwt`——是脚本的 POSIX-only 缺陷，不是它的三层一致性不存在。
  - `ethr-did-resolver`：19 文件 / 182 用例，**178 过 / 1 红 / 3 跳过** / 19.51 s / exit 1。红的那条是 `resolves on mainnet with versionId`，与实时主网状态深比较不一致，网络/链状态相关。原样 `pnpm -r test` 在 Windows 上直接失败（脚本写成 `HARDHAT_CONFIG=... vitest run`），设环境变量后才是上面这份结果。
  - **纪律**：实跑记录 `docs/competitor-realrun.json` 里 `affects_score` 全为 false，`score_impact.changed_scores=0`；`--check` 有一个用例专门拒绝"声称改分"的记录。绿不等于本表的任何一维——它量的是"有没有可复算的变异证据"。
- **301 必须落到新名（`tools/refs_check.py`）**：被 301 的引用不再只记一条 WARN。现在会解析 `Location`、用**同一个 sha** 去新仓再打一次：6 条全部 200（`hyperledger-aries/…`、`hyperledger-indy/…`、`openwallet-foundation/acapy`、`w3c-ccg/did-key-spec`、`decentralized-identity/sidetree`）。新名下的 sha 打不到 404 时 `--check` 红——"改名"只有在同一内容还能打开时才是无害的。
- **D3 区间进正表**：`COMPETITOR-GATE-PARITY.md` 的结论行现在同时写两端（"严规则后最好的一家仍是 3/10，本仓库 10/10"），数字从 `docs/parity-d3-bracket.json` 读，不手写；区间记录里补了 `ours_broad/ours_strict`（由 `score_ours()` 现算，不是写死 10），并加了"本仓行必须与快照一致"的失败条件。
- 测试：`tests/test_parity_realrun.py` 五条（固定 commit 一致、计数与退出码自洽、不许改分、页面必须自述、`--check` 拒绝改分记录）；`tests/test_refs_check.py` 加两条（301 必须在新名下活着、落到 404 必须红）。外人重跑收据的测试清单已并入 `test_parity_realrun.py`。

## 未发布 — 2026-11-26（隐私验证与选择性披露：四个模块进主树，十七项检验进台子）

- **问题**：包里有"已签、已封"，但"这个人该不该看到这一条"没有机制——撤回只能换新包，披露只能整包给出，既不能只给一个字段，也无法让第三方判两个日志是不是同一个历史。
- **做法**：主树新增四个模块。`uibc_core/tlog.py` 是 RFC 6962 一致性证明与离线校验；`uibc_core/status_list.py` 是 131072 位状态表（`MY_INDEX=7`、见证 `k=5/n=3`、`HISTORY=4`）与状态 token；`uibc_core/witness.py` 给 `cosign` / `verify_cosignature`（封条公钥只出验签不出签）；`uibc_core/witness_registry.py` 的 `load_policy` / `verify_quorum` 返回 `(ok, detail)`。七档原型 0.1→0.7 留在 `phase28` 工作区，主树只收模块与文档。
- **台子**：`uibc-bench` 的 `harness/s11_privacy_disclosure.py` 新增 P1–P17（含 P17 双运营方跨进程共签），基线由 157 增至 158，跑出 **15 PASS / 2 REFERENCE / 0 FAIL**。两个 REFERENCE 是"需外部条件"，不计作通过。
- **双运营方 PoC**：`poc/dual_operator_witness.py` 把见证方拆成两个独立子进程、独立密钥目录、独立工作目录，2-of-3 策略下第三家只列入不出签；六类伪造（缺 quorum、重复见证、签名改一字节、陌生密钥、错 checkpoint、封条公钥冒充）全部拒绝。**边界写进产物**：两个运营方同机模拟，不是第三方。
- **文档守卫顺手修红**：`docs/CHECKS-REFERENCE.md` 用 `tools/build_checks_reference.py` 的 `render(build())` 重生成（96 行变动），`paper/paper.md` 的 43 modules 改 47；此前两条守卫在 CI 上红，根因是数字手写、没跟着代码走。
- **没做到的写清楚**：外部独立评审尚未闭合（三条免费通道全堵：OpenRouter `Request path cannot be relayed`、DashScope `AllocationQuota.FreeTierOnly`、硅基流动保险库里没有该 key），现经 `ai-seats-bridge` 投递 Muse 席待回执；真实第三方见证与状态运营方未启用。
- **测试**：`tests/test_checks_reference.py`、`tests/test_doc_facts.py` 守住上面两条文档断言（无新增断言）；合入时 CI 为 21 success / 1 skipped / 0 failure。

## 未发布 — 2026-11-26（把"超越在哪"搬上看板：同一把尺子，25 个仓，我们 10/10，最好竞品 3/10）

- **问题**：`parity` 那一步的尾行已经写着 `25 repositories … best competitor 3/10, this repository 10/10`，但那一行只活在收据的 `tail` 里。读者要回答"凭什么说超越"，还得去开 `docs/competitor-parity.json`。
- **做法**：看板从 `docs/competitor-parity.json` 现读五个维度（D1–D5，各 0–2 分）算总分，页面多一张表：被钉住的仓库数、维度数、最好竞品及其分数、本仓分数、零分仓库数；`--check` 要求页面上的 parity 数字与那份 JSON 现在算出来的完全一致。
- **页面自检加两条**：本仓必须在自己这把尺子上拿满分；任何竞品不得高于本仓——这两条任一被改坏，打开页面就 `SELF-CHECK FAIL`。
- **实测**：`repos 25 / dimensions 5 / best sphereon-opensource/ssi-sdk 3 / ours 10 / zero 15`；`BOARD OK`；断言 A34 增补。

## 未发布 — 2026-11-26（外人打开一屏就够，而且这一屏会自己算一遍）

- **问题**：十道门都在仓库里，但一个陌生人拿到仓之后，第一眼看到的是 README 和一堆 Markdown。数字散在收据、页面、测试里，他无法在一屏里看到"我拿到的是什么、能用什么核"。
- **做法**：`tools/render_outsider_board.py` 生成 `docs/OUTSIDER-BOARD.html`——单文件、零外链、离线可开；把收据的三个摘要、文件数、投递方式、四个步骤和十道门列成一屏，并把快照内嵌在 `<script id="snap">` 里，页面打开时用自己的 JS 重算一遍结论（三个摘要必须 64 位小写十六进制、文件数必须为正、每步 ok、门数 10），不满足就打 `SELF-CHECK FAIL`。
- **防抄错**：门名不是手写的，从 `stranger_own_check.py` 的 `CHECKS` 读出来生成，少一道门就会在 `--check` 里对不上。
- **防外链**：`--check` 会扫页面里所有 `http(s)://`，有一个就红。
- **自指问题**：页面内嵌摘要，所以它和收据、`OUTSIDER-RERUN.md` 一起列入摘要排除集（生产者与检查者用同一集合）。
- **强制**：CI 在十门之后加一步 `python tools/render_outsider_board.py --check`。断言 A34。

## 未发布 — 2026-11-26（收据比的是 HEAD，不是工作区）

- **第二次红，原因不同**：加上折行轴后 CI 仍红。在 Linux 干净克隆上重跑十门是 `10 passed`，说明不是提交的问题——是**工作区**。同一条 job 里排在审计之前的步骤会往树里丢文件（重建的页面、临时产物），工作区因此不再是那个提交。拿工作区当基准，就得接受"别人刚跑过的树"与"这个提交"不是一回事。
- **做法**：`commit_blobs()` 用 `git ls-tree -r` + `git cat-file --batch` 直接读 HEAD 的 blob，`digests_from_blobs()` 在内存里算三根轴；`all_digests()` 同时给两个视图（`commit`、`disk`），`--check` 依次比对，命中哪个就说哪个。`--run` 有 `.git` 时记 `delivery: commit`（与 `git archive` 的字节一致，因此克隆与解包终于对同一个数）。
- **效果**：审计不再被同一 job 里别人的副作用弄红；同时保留了折行轴，解包的人仍可用 `DELIVERY MATCH` 判读。
- **代价写清楚**：`commit` 视图要求 `.git` 与能跑通的 `git`；取不到时自动退回 `disk` 视图，收据里 `delivery` 记 `archive`/`worktree`，判定逻辑不变。

## 未发布 — 2026-11-26（同一个提交、两条通道，两套字节：收据现在说得出来是哪一套）

- **问题**：把 `outsider_rerun.py --check` 收进十门审计后，CI 红了，而红得很委屈——文件集 2437 个两边完全一样，`windows-clone-bytes` 步骤也报 `diverged: 0`。真相是**投递方式**：本仓有 83 个 blob 按 CRLF 存，`.gitattributes` 写的却是 `text=auto eol=lf`；`git archive`（codeload 包）发的是存储的 blob，Linux 检出按属性把行尾折成 LF。所以同一个提交，克隆的人和解包的人手里本来就是两套字节。
- **做法**：`outsider_rerun.py` 加第三根轴 `content_lf_sha256`（每个文件先 CRLF→LF 再哈希），收据多记 `content_lf_sha256` 与 `delivery`（`worktree` / `archive`）。`--check` 四态：字节全同 → OK；仅名字坏 → `NAMES-ONLY` exit 2；**仅换行差 → `VERDICT: DELIVERY MATCH` exit 0**；真有字节动 → `CONTENT` exit 1。
- **实测**：本仓 archive 树 `tree 07d6b0c5ca52 / content 94c43f5e3575 / lf f29a…`；把整棵树 98 个文件折成 LF 后 `--check` 打 `DELIVERY MATCH` 而不是红。
- **不修的代价写清楚**：没有去改那 83 个 blob 的存储形态——那会动全仓摘要、既有快照与随仓语料的哈希；这根轴只负责让收据可判定，不负责抹平通道差异。断言 A32。
- **测试**：`tests/test_outsider_rerun.py` 11 条（新增：折行只动内容摘要、单文件折行被判 DELIVERY MATCH 且严摘要仍不符）。

## 未发布 — 2026-11-26（敏感性检验：把 D1 规则放松，"最好 3/10"会不会翻）

- **为什么要做**：D1 的判据是"一行里同时出现断言和拒绝词"。这门规则是我们自己写的，所以"最好竞品只有 3/10"也可能是我们拼写方式的产物——这正是这类对照表最容易自欺的地方。
- **做法**：`tools/parity_sensitivity.py` 用同一批固定 commit 的 tarball，把规则放宽成"断言行前后 ±2 行内出现拒绝词"，只加分不减分，逐家重算并写 `docs/parity-sensitivity.json` + `docs/PARITY-SENSITIVITY.md`。
- **结果**：25 家里只有 1 家（`decentralized-identity/universal-resolver`）由 0→1，**最好仍是 3/10**，本仓 10/10。多个仓的断言行数翻倍（`did-jwt` 51→117、`ssi-sdk` 123→148），但都早已在 1 分之上，不改变排序。
- **结论写死成判据**：`--check` 离线核对"放宽后最好分不得高于严格最好分"，一旦有竞品在宽松规则下拿到 4 分，直接输出 `withdraw the headline`——那时该撤的是主张，不是把规则改回去。
- **`tests/test_parity_sensitivity.py` 五条**：记录必须覆盖快照全部仓库、放宽不得抬高最好分、只有 D1 可移动、放宽必须真的对至少一家有影响（否则不算敏感性检验）、页面必须写出结论。
## 未发布 — 2026-11-26（看板：单文件、零外链、打开就自己算一遍，算错就红）
- **顺手修红**：`tools/tree_digest_second_impl.py` 把成员清单交给 Python 侧（`tree_digest(root, files)`），但 `outsider_rerun.py` 的两个摘要函数只收 `root`，`second-implementation` 这条 CI 因此在 main 上是红的（`takes 1 positional argument but 2 were given`）。给两个函数加可选 `files=None`（省略时行为不变），本地 `--check` 得 `TREE OK`：Python 与 Node 在 2437 个文件上 `tree_sha256` / `content_sha256` 双轴一致。


- **问题**：九门 S6 要的是"一屏看板、数字现读、单文件零外链、打开自检"。此前只有 PNG/SVG 和 Markdown 表——数字是生成那一刻刻进去的，读者无法分辨哪一行是被手改过的。
- **做法**：`render_html()` 生成 `docs/parity-board.html`：快照 JSON 内嵌在 `<script id="snap">` 里，页面用自己的 JS 现场重算行数、最好竞品、本仓五维之和、谎报上限与最好竞品的大小关系、每家 40 位 commit，把每一条 PASS/FAIL 打在页面上，最后一行给 `SELF-CHECK PASS` / `FAIL — 本页不可信`。
- **零外链是可测的**：全文不含 `http://` / `https://`，也没有任何 `src=`/`href=`（由测试断言），离线双击即可看。
- **无浏览器也能验收**：`tools/board_check.js` 用五行 DOM 桩把页面自己的脚本跑一遍，页面说 PASS 才返回 0，并核对渲染出的行数 = 快照家数 + 1（本仓行）。
- **两个真实 bug 是被这个验收抓出来的**（不是靠人眼）：① Python 模板里的转义被解释成真换行，写进 JS 单引号字符串，页面一打开就 `SyntaxError`；② 页面内嵌 JSON 里的 `<` 未转义会提前闭合块。
- **`tests/test_parity_board.py` 四条**：单文件零外链、内嵌数字与快照逐项一致、页面必须自述"打开自检"且占位符已替换、有 node 时真跑页面脚本并必须 PASS（无 node 则跳过，不是假绿）。
- **外人重跑的第四步顺手扩了**：pytest 列表加入 `test_parity_board.py` 与 `test_refs_check.py`，收据仍四步（不破坏 bench 对 steps=4 的断言），但外人现在连看板与引用一起验。
## 未发布 — 2026-11-26（每一分指到哪一行；D3 从"一个数"改成"一个区间"）

- **问题**：表里写"9 家断言拒绝、9 家有地址派生证据"，读者只能看到计数，看不到是哪一行；也就无法分辨那是真断言还是注释/字面量蹭到的词。
- **做法一（证据行）**：`tools/parity_evidence_lines.py` 把每个计分维度背后的**原始命中行**印出来（`path:line` + 原文，每维最多 3 条），落 `docs/COMPETITOR-EVIDENCE-LINES.md` 与 `docs/competitor-evidence-lines.json`；`--check` 断言"凡是给分的维度，必须能指到至少一行"。
- **顺手抓到一处范围错**：D4 是"跨层同一个退出码"，它的证据在**源码**里（`process.exit(1)`），不在测试文件里。第一版工具只在测试文件里找，`--check` 立刻红出 7 家——这正是"证据在哪儿"必须写死的地方。
- **做法二（D3 区间）**：读证据行时看到 D3 的宽规则把 `publicKeyBase58: '...'` 这种字面量也算成"地址派生"。收紧成只认 `deriveAddress|addressFrom|publicKeyToAddress|toChecksumAddress` 后，**25 家里 9 家掉 1 分**（js-did、veramo、ethr-did-resolver、docknetwork、acapy、aries-framework-go、indy-sdk、indy-vdr、ssi-sdk）。
- **但不许只给收紧后的数**：紧规则同样会冤枉"绑定了地址但没写 derive"的仓。所以 D3 改成**区间**：`docs/D3-BRACKET.md` 同时给宽/严两端的家数与最好分，`tools/parity_d3_bracket.py --check` 只校验"严规则不得高于宽规则"。
- **结论口径因此收紧**：对外只能说"宽规则下最好 3/10、严规则下最好 3/10"——本轮实测两端都是 3，中游 9 家从 3 掉到 2。
- **`tests/test_parity_audit.py` 七条**：每分必须有行、D4 的引用不得来自测试文件、证据条数有上限且可追溯、页面必须列出所有给分的仓、严规则不得高于宽规则、变更清单精确、页面必须自述"区间"。
## 未发布 — 2026-11-26（敏感性检验：把 D1 规则放松，"最好 3/10"会不会翻）

- **为什么要做**：D1 的判据是"一行里同时出现断言和拒绝词"。这门规则是我们自己写的，所以"最好竞品只有 3/10"也可能是我们拼写方式的产物——这正是这类对照表最容易自欺的地方。
- **做法**：`tools/parity_sensitivity.py` 用同一批固定 commit 的 tarball，把规则放宽成"断言行前后 ±2 行内出现拒绝词"，只加分不减分，逐家重算并写 `docs/parity-sensitivity.json` + `docs/PARITY-SENSITIVITY.md`。
- **结果**：25 家里只有 1 家（`decentralized-identity/universal-resolver`）由 0→1，**最好仍是 3/10**，本仓 10/10。多个仓的断言行数翻倍（`did-jwt` 51→117、`ssi-sdk` 123→148），但都早已在 1 分之上，不改变排序。
- **结论写死成判据**：`--check` 离线核对"放宽后最好分不得高于严格最好分"，一旦有竞品在宽松规则下拿到 4 分，直接输出 `withdraw the headline`——那时该撤的是主张，不是把规则改回去。
- **`tests/test_parity_sensitivity.py` 五条**：记录必须覆盖快照全部仓库、放宽不得抬高最好分、只有 D1 可移动、放宽必须真的对至少一家有影响（否则不算敏感性检验）、页面必须写出结论。
## 未发布 — 2026-11-26（看板：单文件、零外链、打开就自己算一遍，算错就红）
- **顺手修红**：`tools/tree_digest_second_impl.py` 把成员清单交给 Python 侧（`tree_digest(root, files)`），但 `outsider_rerun.py` 的两个摘要函数只收 `root`，`second-implementation` 这条 CI 因此在 main 上是红的（`takes 1 positional argument but 2 were given`）。给两个函数加可选 `files=None`（省略时行为不变），本地 `--check` 得 `TREE OK`：Python 与 Node 在 2437 个文件上 `tree_sha256` / `content_sha256` 双轴一致。


- **问题**：九门 S6 要的是"一屏看板、数字现读、单文件零外链、打开自检"。此前只有 PNG/SVG 和 Markdown 表——数字是生成那一刻刻进去的，读者无法分辨哪一行是被手改过的。
- **做法**：`render_html()` 生成 `docs/parity-board.html`：快照 JSON 内嵌在 `<script id="snap">` 里，页面用自己的 JS 现场重算行数、最好竞品、本仓五维之和、谎报上限与最好竞品的大小关系、每家 40 位 commit，把每一条 PASS/FAIL 打在页面上，最后一行给 `SELF-CHECK PASS` / `FAIL — 本页不可信`。
- **零外链是可测的**：全文不含 `http://` / `https://`，也没有任何 `src=`/`href=`（由测试断言），离线双击即可看。
- **无浏览器也能验收**：`tools/board_check.js` 用五行 DOM 桩把页面自己的脚本跑一遍，页面说 PASS 才返回 0，并核对渲染出的行数 = 快照家数 + 1（本仓行）。
- **两个真实 bug 是被这个验收抓出来的**（不是靠人眼）：① Python 模板里的转义被解释成真换行，写进 JS 单引号字符串，页面一打开就 `SyntaxError`；② 页面内嵌 JSON 里的 `<` 未转义会提前闭合块。
- **`tests/test_parity_board.py` 四条**：单文件零外链、内嵌数字与快照逐项一致、页面必须自述"打开自检"且占位符已替换、有 node 时真跑页面脚本并必须 PASS（无 node 则跳过，不是假绿）。
- **外人重跑的第四步顺手扩了**：pytest 列表加入 `test_parity_board.py` 与 `test_refs_check.py`，收据仍四步（不破坏 bench 对 steps=4 的断言），但外人现在连看板与引用一起验。
## 未发布 — 2026-11-26（收据的两个数有了第二种算法：Node 标准库，同一份名单）

- **问题**：上一版给收据加了两根轴（`tree_sha256` / `content_sha256`），但两个数只有一种程序算得出来。一个只有一种程序能算的数，是那个程序的意见。
- **做法**：`tools/verify-js/tree-digest.mjs` 用 Node 标准库把两个数重算一遍——不 import `uibc_core`、不跑 Python、不装 npm 包；`tools/tree_digest_second_impl.py` 把 Python 侧的**文件清单**（NUL 分隔）递过去，两边算的必须是同一批文件，所以它们不可能靠“对同一批别的文件得出同一个数”而通过。
- **三个可能被怀疑的口径**：排序（Node 用 UTF-8 字节序，不是 JS 默认的 UTF-16 码元序，后者会把星形字符排错）、拼接（两边都是 `\n` 连接 + UTF-8 字节）、两个轴的含义（改名只动严摘要、翻字节两个都动）。
- **强制**：CI `second-implementation` job 多一步 `python tools/tree_digest_second_impl.py --check`，两个实现任何一处单边改动都红。
- **`tests/test_tree_digest_second_impl.py` 四条**：本树一致、名单递过去（子集就得出子集）、改名只动严摘要、翻一个字节两个都动。详见 `docs/TREE-DIGEST-SECOND-IMPL.md`，断言 A31。

## 未发布 — 2026-11-26（引用逐条实测：25 条 0 死，6 条被上游改名后 301）

- **问题**：表里每条引用都写成 `github.com/<repo>/tree/<sha>`，但"看起来能点"和"现在真能打开"是两件事。九门 S5 一直卡在"缺逐条 HTTP 三态"。
- **做法**：新增 `tools/refs_check.py`，引用集合**从快照派生**（不手写清单），逐条 GET 并**禁止自动跟随重定向**（`_NoRedirect`），因此 200 / 301 / 404 / 超时四态都看得见；结果落 `docs/refs-report.json` 与 `docs/REFS-DIRECT.md`。
- **实测（25 条竞品引用）**：200 **19** 条、301 **6** 条、**0** 条死。6 条不是死链而是**上游改名**，301 打到新仓：`decentralized-identity/sidetree-core`→`…/sidetree`、`hyperledger/aries-cloudagent-python`→`openwallet-foundation/acapy`、`hyperledger/aries-framework-go`→`hyperledger-aries/…`、`hyperledger/indy-sdk`、`hyperledger/indy-vdr`→`hyperledger-indy/…`、`w3c-ccg/did-method-key`→`…/did-key-spec`。
- **口径**：301 记 `moved` 并在文档里点名去向，不记死；404/超时记死并让 `--check` 失败并点名仓库。本仓行在 tarball 里没有 `.git`（commit 只能是 `unknown`），**宁可不出现在引用表里也不写 `/tree/unknown`**，可用 `UIBC_COMMIT` 注入真实 sha 后再补。
- **`tests/test_refs_check.py` 六条**：引用从快照派生且 URL 形状一致、绝不出现 `unknown`、报告集合与快照一一对应、404 必红并点名、301 记 moved 不记死、页面必须是生成页。
- 生成文档"引用"一节改为指向 `docs/REFS-DIRECT.md`，并写明"不是看起来能点就算"。
## 未发布 — 2026-11-26（本仓那一行不再手写：10/10 由证据算出来）

- **问题**：整张表都在读别人仓里的证据，唯独本仓那五个 2 是 `build_ours()` 里写死的常量。作者给自己打分，这是这类对照表最致命的一处。
- **做法**：`score_ours()` 改成从实跑结果推：三个探针是否在仓里、`mutation_gate.py --json` 的每层是否全过、文档层有没有 `25/25` 覆盖数与空静默集、二进制层有没有 `total=` 覆盖数、门是否一层一码、自证测试里是否有 ≥2 条"要求门失败"的用例。
- **可被证伪**：删一个探针 → 对应维度掉到 0；拿走门 → 四个维度同时掉（因为三层覆盖率是门读出来的）；手改快照里的 `ours.dims` → `--check` 报"not what its artefacts produce"并点名。
- **`tests/test_ours_score.py` 五条**：行等于现算、删探针掉分、删门掉 D4/三层维度、手写行被抓、文档要写明这一行是算出来的。
- 生成文档新增一句："本仓库那一行不是手写"，指向 `score_ours()` 与四条反证。
## 未发布 — 2026-11-26（校准门槛从 10 降到 5：阈值要能过"诚实的小仓"这一关）

- 上一版把 `ASSERT_FLOOR` 定在 10，实测把两家**真有拒绝断言**的仓判成 0（`ethr-did-resolver` 6 行、`indy-vdr` 9 行）。阈值不是为了好看，是为了"堆词的 0 分、诚实的给分"，所以降到 **5**。
- 重算后（25 家）：D1 **10** 家、D3 **10** 家、D4 **9** 家、D2 0 家、D5 0 家；最好仍 **3/10**（八家并列），本仓 **10/10**。
- 校准不变：空仓 0、堆词仓 0、诚实仓 1；上限 0/10 < 最好竞品 3/10，`--check` 每次重算并比对。
## 未发布 — 2026-11-26（给度量本身做校准：堆词能骗到几分，量出来是 0）

- **问题**：竞品表数的是关键词，一个仓只要把词写进注释、什么都不测，也能拿分。此前的说法是"关键词检索有漏报"，那是辩解，不是数据。
- **做法**：`calibrate()` 现造三棵合成仓库并按同一 `score_one` 打分——空仓必须 0；**注释里堆满关键词、测试里零断言**的"堆词仓"就是谎报上限；真有 12 条拒绝断言的仓必须拿到 D1。
- **量出的上限**：堆词仓 **0/10**（不是 3、不是 4），因为四个计分维度现在都要求仓内**真断言行 ≥ `ASSERT_FLOOR`=10**（`ASSERT_LINE_RE`）。D1 另加"拒绝类词 ≥10"一条。
- **上限写进快照、每次 `--check` 重算**：`calibration` 块与现算不一致就红；上限 ≥ 最好竞品（3/10）也红——那意味着表已经不能区分人和堆词，主张必须主动缩。
- **重算后的分布（25 家）**：D1 8 家、D2 0 家、D3 8 家、D4 7 家、D5 0 家；最好仍 3/10，本仓 10/10。比上一口径更严，所以有 5 家从 13 掉到 8（它们只有词、断言密度不够）。
- **`tests/test_parity_calibration.py` 六条**：快照校准与现算一致、空仓 0、堆词 0、诚实仓拿分、公开上限必须低于最好竞品、篡改上限被 `--check` 抓。



- **第三批 8 家入库**：`WeBankBlockchain/WeIdentity`、`hyperledger/aries-framework-go`、`hyperledger/aries-cloudagent-python`、`decentralized-identity/did-jwt`、`docknetwork/sdk`、`ceramicnetwork/js-did`、`ontio/ontology-did`、`hyperledger/indy-sdk`。与前两批同一组正则、同一 `score_one`，HEAD 由 `/commits` 取定后记 sha + tarball sha256。
- **25 家的结论**：逐位变异 0 家、门自证 0 家、跨层单一退出码 10 家、文档层拒绝断言 13 家；最好仍是 **3/10**（现在有 8 家并列），本仓库 **10/10**。
- **`MIN_REPOS` 抬到 25**，删任何一家都会失败；`tests/test_competitor_parity.py` 同步 ≥25。
- **新增两条反漂移测试**：文档里的家数必须等于快照家数、且每一行都在表里（防止"表长了、文没动"）；取样必须跨 ≥10 个组织并包含中国国内栈（`WeBankBlockchain`/`caict-4iot-dev`/`ontio`），防止样本变成一个厂商的自拍。
- 推送脚本 `_gh_push_new.py` 新增 `UIBC_PARENT`（固定父提交）与 `UIBC_TREE_ROOT`（本地树文件数与父树不符时**拒绝推送**）——上一轮收据对不上树就是这一类错，现在由脚本先拦。

## 未发布 — 2026-11-26（竞品对照扩到 17 家：结论的分母不再是 9）

- **第二批 8 家入库**：`decentralized-identity/veramo`、`spruceid/ssi`、`spruceid/didkit`、`digitalbazaar/did-io`、`uport-project/ethr-did`、`hyperledger/indy-vdr`、`w3c-ccg/did-test-suite`、`sphereon-opensource/ssi-sdk`，全部按固定 commit 取 tarball、记 sha256，与第一批用同一组正则与同一套打分。
- **结论随分母收紧**：17 家里，**逐位变异 0 家**、**门自证 0 家**；跨层单一退出码 5 家（记 1 的依据是仓内有 CLI 失败码，不是把多层证据收进一个码）；文档层拒绝断言 6 家。最好的一家仍是 **3/10**，本仓库 **10/10**。
- **覆盖只许变大不许变小**：`check()` 加 `MIN_REPOS = 15`，快照被删回 9 家会直接失败并说明"覆盖缩水"；测试同步断言 ≥15。想删一家，必须在文档里说清楚。
- **文档生成反过来算分母**：三条结论、D5 的口径、量不到的清单里的家数都从快照现算（`render_doc`），不再手写"九家/八家"，避免改表不改文。
- 复跑：`--check` 离线重算 17 家分数与表格一致性；`--refresh` 按固定 sha 重新下载重算。

## 未发布 — 2026-11-25（外人重跑：换目录、换环境、不带凭据，还成不成立）

- **收据此前都是作者机器开的**，这是最弱的证人。`tools/outsider_rerun.py` 把证人做成机械的：整棵拷到临时目录（不含 `.git`、不含缓存）、用白名单变量的干净环境（不含任何 token）、在该目录下跑四个公开入口（`mutation_gate.py` / `competitor_gate_parity.py` / `demo_bid_binary.py` / 两个测试文件），逐步记退出码与输出末行，并把整棵树的 sha256 写进 `docs/outsider-rerun-receipt.json`。
- **摘要排除它自己产出的两个文件**（receipt 与本页），生成与校验用同一套排除规则——所以收据不能在不改树的情况下被悄悄刷新。
- `--check` 重算摘要并逐步判定：树被改一个字节、文件数变一个、某步没带自己的标记，都会失败并点名。
- `tests/test_outsider_rerun.py` 五条：摘要稳定且排除自身产物、干净环境里没有凭据、收据与当前树一致、**在副本里多写一行注释摘要就对不上**、副本里没有 `.git`（无法借助作者的历史）。
- 实测：4 步全过（gate 0.4s / parity 0.6s / demo 0.3s / tests 2.7s），树 `43f754c8137c`，2232 个文件。

## 未发布 — 2026-11-25（竞品对照：把"我们更强"换成外人可复算的一张表）

- **一个主张需要一个测量**：`tools/competitor_gate_parity.py` 审计九个 DID 解析/驱动仓库（官方 `did:bid` 解析与注册驱动、DIF universal-resolver、did-resolver、sidetree-core、ION、sidetree.js、did-method-key、ethr-did-resolver），全部按**固定 commit** 取 tarball，记录 tarball 的 sha256 与字节数。
- **五个维度机械打分**（0 无证据 / 1 点状证据 / 2 系统性探针 + 可失败的门）：文档形状拒绝、位级报文变异、地址绑定重算、跨层单一退出码、门自证。分数由原始关键词计数重算（`score_one`），不靠人眼。
- **结果**：最好的一家 **3/10**（ethr-did-resolver：有拒绝断言、地址派生测试、CLI 失败码），本仓库 **10/10**；九个仓库里 **0 家**有位级变异探针、**0 家**有跨层门、**0 家**有门自证。原因写在文档里：八家里没有二进制报文层可变异——RFC-011 在本轮之前没有公开实现。
- **三种模式**：`--check` 离线校验（快照 schema、sha/摘要、分数是否由计数推出、表格与快照是否一致、本仓库门是否仍覆盖三层），`--refresh` 按固定 sha 重新下载重算，`--render` 从快照重生成表格与矩阵。`--check` 退出 0 才印 `PARITY OK`。
- **不越界的说法**：文档写明"计数为 0 只说明源码文本里检索不到，不说明团队没做过"，并列出本表量不到的三类（关键词漏报、私有仓、质量差异）。对外只说一句：公开仓库里，三层变异证据收进一道可失败的门并随仓交付，目前只有本仓库。
- `tests/test_competitor_parity.py` 五条：干净树通过；每家都被 sha 与摘要钉住；**分数与自身计数矛盾时点名报错**；**表格与快照漂移时报错**；文档仍写 10/10 且五个维度都在。
- 矩阵图 `docs/COMPETITOR-GATE-PARITY.svg` 由快照生成（字节可复现），另可用 Pillow 出 PNG 供人眼验收。

## 未发布 — 2026-11-25（变异探针：把"改这一点，谁会发现"变成可复跑的账本）

- **同一套问法打三层**：一次只改一处，只看改完落在哪一类（refused / warned / silent / wrong-error）。`silent` 是唯一要盯的列——它是"协议禁止、实现吞掉"的形状。
- **文档形状 `tools/mutate_document_shapes.py`**：31 个变异体，25 个是 §4.2.1 禁止的形状，**25/25 被拒，silent=0**。删 `id`、`publicKey` 换成对象、`id` 无 `#`、`id` 重复、`controller` 非 BID、`publicKeyHex` 非 hex、`authentication` 指向未定义键、`alsoKnownAs.type` 给 `true`（bool 是 int 子类）、`DIDSubResolver` 缺 `serviceEndpoint` 等逐条拒，报错都点名被改的字段。
- **探针抓到一个真缺口**：删掉 `created` 曾能解析成功。协议 §4.2.1 第 9、10 项原文是"**9.created**：必填字段"、"**10.updated**：必填字段"，原实现只校验格式不校验存在。已改为缺字段即 raise，报错带 `§4.2.1 9.created is 必填 (required)`，`tests/test_mutation_probes.py` 钉住两条。
- **一处合法沉默被下游兜住（实测而非假设）**：`publicKey.type` 写成 `RSA` 解析不报错（正文只说是 String，无枚举）；用 Ed25519 真签后把 type 改成 `RSA`，验签返回 `False`，理由"signature does not verify over the JCS form"。
- **地址绑定 `tools/probe_address_binding.py`**：256 次单比特翻键 → 地址全部改变、**0 次撞回原地址、0 次相互相撞**、每次改 30 字符里的 26–30 个；1710 次单字符替换 → **全部被拒**；截短/补长/中间删一位 → 全部不匹配。用 SDK 夹具而不是 RFC-003 正文印的例子，因为后者在本实现下不复现（两套变体见 `docs/ADDRESS-DERIVATION.md`）。
- 新增 `tests/test_mutation_probes.py` 9 条；`docs/MUTATION-PROBES.md` 记方法、数字、以及这套方法量不到的三处（签名块 ID、分片末片判据、真机样例）。
- **把三个探针收成一道门 `tools/mutation_gate.py`**：一条命令、14 项检查、一个退出码（`GATE OK` / `GATE FAIL`）。门只保留"让数字有意义"的性质——被禁形状全拒且 `silent` 为空、缺 `created`/`updated` 的报错必须带 §4.2.1 项目号、未知字段必须被接受、改标类型必须由验签挡、每一位必被归类且盲位恰等于保留位、翻键必变且 0 相撞、单字符替换全拒。不联网、无额外依赖，单次不到两秒。
- **门要能失败才算门**：`tests/test_mutation_gate.py` 五条，其中两条注入假断言，要求账本报 `failed` 并且失败项点名——证明它不是一个只会打印 OK 的脚本。常规 `pytest` 即门。

- 二进制层沿用同一账本：196 字节 / 1568 位，refused 328 / changed 1226 / blind 14（`docs/BINARY-PROTOCOL.md` 三·十）。

## 未发布 — 2026-11-25（RFC-011 编解码器：把"只能读"补成"能反算"）

主题：一个只会解码的实现没有办法被反驳。这一轮把它做成编解码器，并先把"官方到底有没有实现"查清楚。

- **先取证再动工**：`headerLength`/`replyCode`/`messageLength`/`0x2100` 在 `caict-4iot-dev` 全组织的 code search 命中数都是 **1**，唯一命中是 RFC-011 正文。公开默认分支上不存在参考编解码器（`docs/COMPETITOR-EVIDENCE.md` 附节记了查询与计数，并写明"看不到私有仓，不能推出官方没有"）。
- **三层互逆**：`encode_units`（字节级、含非升序顺序）/ `encode_document`（语义幂等，规范序按容器内 ID 升序）/ `encode_message`（头+option+体）。文档层为什么只承诺语义，写在 `docs/BINARY-PROTOCOL.md` 三·五。
- **六条推断成为参数而非注释**（`ASSUMPTIONS`）：`flag_bit_order`（msb/lsb）、`acsns_spelling`（3610/3601）、`integer_widths`（调用方给，不给就 defer）、`bid_document_collision`（启发式）、分片重组与签名 unit ID（未实现）。两条可翻转的都有"翻转后输出确实变了"的断言。
- **宽度给了就严格**：`integer_widths` 与 payload 长度不符立刻 `raise`（`declared long=8 bytes but carries 4`）——真实样例到手时错宽度当场暴露，不会被读成错数。
- **敌意输入**：2,000 组随机字节只许 `ValueError`；500 组随机 unit 序列解码后重编码语义必须一致。
- 新增 `tests/test_bid_binary_codec.py` 31 条，连原 16 条共 47 条全绿。
- **可运行 demo 与生成式布局图**：`tools/demo_bid_binary.py` 八幕（编→解→翻转假设→宽度硬校验→fuzz），末行 `ALL OK`、退出码 0；`tools/render_bid_binary_layout.py` 从模块常量生成 `docs/BID-BINARY-LAYOUT.svg`，生成器内断言各段字节和等于 `HEADER_MIN`，`tests/test_bid_binary_layout.py` 再拿生成结果与仓库那份做字节比较——手改图即红。新增 5 条测试，与解码/编解码合计 52 条。

### 同一轮的硬化：把"解码器看不出来的改动"补掉

- **逐位翻转探针** `tools/mutate_bid_binary.py`：对一条 196 字节 / 1568 位的有效报文逐位翻转，归成 rejected 328（20.9%）/ changed 1226（78.2%）/ blind 14（0.9%）。盲位只有 6 个未分配 flag 位和整个 `unUsed` 字节，**正文一位都不盲**。
- **探针抓到的第一件事是我们自己的比较写错了**：只比较解出的文档，会把 `replyCode`、`transactionID` 也算成盲位（22 个改为比全部可观测状态后 15 个）。
- **探针抓到的第二个是结构漏洞**：字段按绝对路径写入，容器改了名也解不出差别——把 `publicKey`(0x2110) 改成文档包装层 0x2100，文档一字不差。现在字段必须坐进 `FIELD_TABLE` 路径对应的容器（`documented_parent` 取最长前缀），协议 §5.2.2 的 `errResponse` 例外用 `CONTAINER_EXTRA_PATHS` 显式放行并在注释里引原文；宽容读法用 `strict_placement=False`，把错位记进 `misplaced` 而不是拒收。
- **第二个真漏洞**：编码器把 `authentication` 包成 `0x2100 > 0x2100` 两层壳，示范报文 342 字节。改成裸 `0x2100` 叶子后 196 字节，`0x2100` 的双重身份仍按 payload 形状判别。
- 新增 `tests/test_bid_binary_mutation.py` 5 条（含"盲位恰好是保留位"的断言，期望集合从 `_FLAG_BITS`/`_OPCODE_SHIFT` 推出，不手抄）；`tests/test_bid_binary_codec.py` 31 → 35 条；二进制四组合计 61 条。
- demo 增两幕：`6b` 错容器被拒 + 宽容模式记账，`6c` 逐位翻转的统计；仍以 `ALL OK` 收尾。
- `docs/BINARY-PROTOCOL.md` 增三·九（字段归属）与三·十（逐位翻转）。


## 0.5.5 — 2026-11-25（把 0.5.4 那次发布补成一次干净的）

主题：`0.5.4` 装上能用，但它的 sdist 里带的是一版之前的语料。这一版不新增能力，只把"发出去的东西"和"仓库里的树"重新对齐，并把产生那种错配的顺序固定下来。

- **0.5.4 到底错在哪**：`v0.5.4` 切在 `be99eae`，那次改了版本串、重建了归档，**没有重 emit 语料**——59 个 `manifest.json`/`seal.json` 里仍写着 `0.5.3`。`oracle_check.py --emit` 从同一棵树能重新产出的字节与提交的对不上，所以 `sdist-self-check` 在 main 上红；也是为什么那次打的包是 359,714 字节，而正确的重建是 359,696 字节（它装的是旧语料，多出的字节就是那两处版本串的差）。
- **这一版按顺序做**：`bump 0.5.5` → `oracle_check.py --emit`（`SOURCE_DATE_EPOCH=1794700800`，与 pin 同一锚点）→ `build_conformance_manifest.py`（792 文件）→ `build_conformance_bundle.py 0.5.5` → 写 pin → `status_page.py` → README/AUDIT-KIT 指向同一哈希。四者同源，`sdist-self-check` 与 `test_oracle_reproducible` 才有东西可对。
- **发布资产**：`uibc-conformance-0.5.5.zip`，359,696 字节，456 例，sha256 `9cab24943117801ed4f02c8400a899916f237a1e2e668116eaac4accfb17932e`；pin 在 `anchors/pins/uibc-conformance-0.5.5.sha256`。
- **顺序本身被写进流程**（`221d004`）：发布只在字节已经落在页面上之后才发生。这正是 `publish-mcp` 在 v0.5.3 上撞到的那类竞态——同一个 tag 触发，注册表先查 PyPI，而 PyPI 那时还没有文件（`files=0`），于是它把自己判成失败。重跑一次就过，但"要靠重跑才对"不是流程。
- **门禁**：`check_release_readiness.py --version 0.5.5 --tag v0.5.5` → `READY`；`version_gate.py` → `GATE PASS`；`check_doc_facts.py` → 0 mismatch；`status_page.py --check` → `CURRENT`；`build_conformance_manifest.py --check` → 792 files；`recheck.py` → `29 / COVERED=5 / GAP=8 / PARTIAL=16 / bad=0`。
- **对 0.5.4 的处置，如实写**：PyPI 上的 0.5.4 撤不回来（PyPI 不复用版本号），它的 sdist 就带着旧语料留着；`v0.5.4` 的 release 页为空资产，这一版不回头去补它，因为补上去的只会是那份旧归档。装上 0.5.4 的机器升到 0.5.5 即可，代码路径没有变化，变的是随包附带的语料与哈希。

## 0.5.4 — 2026-11-25（条款级 crosswalk：29 行判词，机器可证伪）

主题：竞品对照里"我们更全"是最容易说空的一句话。这一版把主张收窄到别人没发布的那一列——每个被监管条款对应一个判词，而判词可以被证伪。

- **25 条法规条款 + 4 条工具契约 = 29 行**（`crosswalk/`）：COVERED 不是"我们实现了"，而是"有一个探针，曾经在该条款上被看见失败过"；PARTIAL / GAP 必须写理由；OVERCLAIM（声称覆盖但探针不存在）与 UNDECLARED（探针存在却没登记）直接 exit 1。
- **`tools/recheck.py` 把公开表的每个数字回到字节**：六份 crosswalk 与 README 的声明同源，输出 `total clauses=29 COVERED=5 GAP=8 PARTIAL=16 bad=0`。CI 的 `crosswalk-gate` 与 `windows-probes` 都跑它；数字对不上就红，不靠人记。
- **Windows 控制台的真缺陷**（`uibc_core/cli.py::_utf8_stdout`）：`verify` 在 cp1252 控制台抛 `UnicodeEncodeError`（position 564–587），stdout 为空，下游 `json.loads` 全挂——`windows-probes` 连红的真因。修法是在 `main()` 之前把 `sys.stdout/stderr` 重配成 UTF-8；新增 `tests/test_cli_stdout_encoding.py`，在 `PYTHONIOENCODING=cp1252` 下跑 `verify` 并要求输出可解析 JSON。这个场景在 Linux 上同样能复现，所以它不是 Windows 专属补丁。
- **竞品节重写**（`docs/COMPETITORS.md`）：先承认 InSpec 的 control 确实带 `ref`/`url`/`tag cce:` 条款映射，不能写"他们没有"；再收窄到唯一可证伪的那一列，并自陈三条限制——29 行只是形式主张、InSpec 跑在活系统上、自家验证器的行在第二实现出现前仍是自评。基线 `COMPETITORS.json` 与图 `COMPETITORS.svg` 由脚本生成，改一次必须重跑一次；文档里写的命令都实跑过，没跑过的不写。
- **发布资产**：`uibc-conformance-0.5.4.zip`，359,697 字节，456 例，sha256 `f0cb92932f1e10394343d55f530d534c1efe60860a4975ca49df7d0d4bba6a25`；pin 在 `anchors/pins/uibc-conformance-0.5.4.sha256`。
- **本版是发布就绪门禁第一次真的拦人**（#445 引入的 `readiness` job）：`tools/check_release_readiness.py` 在 tag 上说四件事——三处版本串一致、tag 树里含自己版本的归档、归档内记录的版本一致、tag 名等于 `v<版本>`。它的由来是三连红：`v0.5.1/0.5.2/0.5.3` 各自切在自己的归档之前，于是 lab bundle 每次都在 tag 树上找不到自己那一版。负控制实测：把归档移开 → `NOT READY TO TAG`，rc=1，报的正是生产环境那句话。

## 未发布 — 2026-11-25（§4.3 二进制解析：指针指空了，正文在隔壁）

主题：此前把 §4.3 记成"正文未取到、只能明确拒绝"。这一轮把正文找到了，也把"缺什么"写成了清单。

- **主协议 §4.3 的链接是空的**：它指向 `bif-rfcs` 的 `RFCs/3-ACCEPTED`，该目录只有一个 0 字节 `.gitkeep`。正文在 `RFCs/4-ADOPTED/星火链网RFC-011…md`（31,156 字节，commit `5d471fc1…`）。"协议没写"是误判，**是主文档的指针坏了**。
- **能读的部分**（`uibc_core/bid_binary.py`）：16 字节消息头、单元树（ID 2B + 长度 2B + payload 可递归）、文档应答与错误应答的字符串字段；未知 unit 进 `unknown` 带原始字节；越界/长度不匹配/尾部残字节三类拒绝。
- **不读的部分逐条给理由**：`Int`/`Long` 无字节宽度（整数进 `_deferred` 附原始字节）；消息签名三个 unit 的 ID 正文从未给出（`signature_units_detectable=False`）；分片重组无末片判据；flag 位序无编号（`FLAG_BIT_ORDER_IS_AN_ASSUMPTION`）。
- **正文自身两处冲突**：`0x2100` 同时是 `bidDocument` 与 `authentication`（按 payload 形状判别，启发式写在 `KNOWN_ID_COLLISIONS`）；AC 号子字段 `0x3601/0x3602` 与 `0x3610/0x3620` 两套编号都收。
- **两张返回码表不合并**：§4.2.5 `0=success` vs RFC-011 `1=success`（另有 11、255），合并会把 0 与 1 混成"成功"。
- 测试 `tests/test_bid_binary.py` 16 条；`docs/BINARY-PROTOCOL.md` 记 commit/blob/字节数。

## 未发布 — 2026-11-25（地址可复算：把 4 个大小写字母钉成规则）

主题：上一版把 `did:bid` 地址判成"不透明、只能校验"。这一版把它算清楚，并记下标准与参考实现在同一处步骤上的分叉。

- **根因是字母表**：`brdc-sjcl` 的 Base58 与比特币表只差 4 个字母（`b/B`、`u/U` 各自对调；前 9 位共享），见 `docs/ADDRESS-DERIVATION.md`。这解释了 7/50 的巧合，也让 50/50 成立。
- **版本字节是开关不是默认**：RFC-003 §5.1 第三步要求前置 `0x01`，官方 SDK 注释掉了（`keypair/index.js` 60–62 行）。返回字典带 `version_byte`/`hash_hex`/`key_bytes`。
- **RFC 示例瑕疵也钉住**：打印的 `did:bid:38VPR…` 省略算法与编码字母（应为 `did:bid:ef38VPR…`）；正文给的后缀 22–31 与实测 30–32 不符。
- **语义边界**：地址推导只做自洽性检查，**不做准入**（解析仍按 ABNF 接受）。
- 测试 `tests/test_bid_address.py` 13 条。

## 未发布 — 2026-11-25（DID 对接：BID 协议层，按《星火·链网BID协议》正文实现）

主题：上一版把 `did:bid` 的通路做通了（GET + errorCode + id 校验），但没有读懂回来的文档。读完协议正文后发现三处真缺口，这一版补齐，且每一处都对着条款写测试。

- **§4.2.5 的 11 档响应码不再被压成一个异常**（`uibc_core/bid_protocol.py::BID_RESPONSE_CODES`）：协议给了 0–10 共 11 个码，旧实现把非 0 一律抛成同一句话，于是"没找到"（6，重试无益）和"服务器繁忙"（3，重试有效）在日志里长得一模一样，而"验签失败"（9）这个安全信号也被混进了传输错误。现在每个码带协议原文名字和一个处理类（ok/refused/protocol/transient/security/not_found），`retryable` 与 `not_found` 是可问的属性；未记载的码也保留数字，不假装认识。
- **BID 文档不是 DID Core 文档，这一版把文档读懂**（`parse_bid_document`）：协议 §4.2.1 的文档带 `publicKey[]`（`publicKeyHex`/`controller`/`type`）、`authentication`、`alsoKnownAs{type:Int}`、`extension`（ttl/type/attributes/encrypt/acsns/verifiableCredentials）、`service`、`proof{creator,signatureValue}`。逐条校验：id 必须等于请求的 BID；`publicKey.id` 文档内唯一且必须带 `#`；`controller` 必须是 BID；`publicKeyHex` 必须是十六进制；`authentication` 不能引用未定义的键；`alsoKnownAs.type` 必须是 Int；`DIDSubResolver` 必须有 `serviceEndpoint` 且 `protocol ∈ 0..3`（附录一第 5 张表）；`ttl` 非负整数；`attribute.encrypt ∈ {0,1}`；时间戳必须是 ISO-8601；`proof.creator` 必须是本文档的键。附录一点名的码值之外的值只记 `warnings` 不拒收——附录自己写着"待扩展"。
- **`to_did_core()` 单向投影**：DID Core 侧只认 `verificationMethod`/`authentication`/`service`/`alsoKnownAs`，而 BID 侧是 `publicKey`/`extension` 等；投影时 BID 自有字段全部保留在 `extension` 里，丢掉信息不如不投影。
- **§5 签名真的能跑了**（`sign_bid_document` / `verify_bid_document`）：去 `proof` → 按 RFC 8785/JCS 规范化 → 签名 → Base58。JCS 用的就是仓里已有的 `canonical.canonicalize`（它已与 JS 实现逐字节对齐），所以第三方拿任意 JCS 工具就能重算待签字节；补了 Bitcoin 字母表 Base58（含前导零字节）。Ed25519 闭环自签自验；`proof.creator` 必须同时出现在 `authentication` 里，否则拒绝。SM2 **不做**：没有可独立复算的向量，宁可在文档里写明"此处不可验证"也不假装验过。
- **§4.2.3 子链递归解析**（`resolve_bid_chain`）：主链文档里 `service.type=DIDSubResolver` 指向子链解析地址 → 再解析。带跳数预算和已访问端点集合，环会给 `cycle` 而不是转圈；端点必须是 HTTP(S)。
- **§4.3 二进制解析明确拒绝**（`refuse_binary_resolution`）：用协议自己的 5（operation not supported），不猜格式。
- **`did_cn.resolve()` 的 bid 分支改用同一套信封解析**：错误信息不再坍缩，仍以 `DIDCNError` 抛出以兼容既有调用方；需要码与可重试性的调用方用 `bid_protocol.resolve_bid`。
- 测试 `tests/test_bid_protocol.py` 37 条，每条在名字里写明它钉的是哪一条款（§4.2.1 / §4.2.5 / §5 / 附录一 / §4.2.3）。
- **跨实现核验（这是本轮最该被外人复查的一条）**：签名不是我们自己验自己。`tools/verify-js/bid.mjs` 用**另一套 RFC 8785 实现**（JS 里按 RFC 原文重写，未复用 Python 代码）规范化、用 **node/OpenSSL** 验 Ed25519，对 `fixtures/bid/signed_document.json` 给出 `signature-verified true`，并打印规范化字节的 sha256 与 Python 逐字符比对。两次实现算出同一个 sha256，才叫"第三方能重算"。夹具由 `tools/make_bid_fixture.py` 以固定种子生成（随机种子会让已提交的夹具无法复现，等于把可证伪性换成了一次性快照）。测试 `tests/test_bid_crossjs.py` 4 条：夹具仍能自验、node 能验、两侧 sha256 相同、改一个字段 node 必须拒。
- **用官方 SDK 反查，抓到一个会让真实文档全部被拒的缺陷**：`bid-sdk-nodejs` 1.0.1（Caict 发布）对固定种子给出的 `encPublicKey` 是 `b0 65 66 || 32 字节`——**35 字节**，而协议 §5.4.1 的样例 `b06566f76733ae…` 正是这个形状。此前我们只认 `b0 || key`（33 字节），于是真实 BID 文档的 `publicKeyHex` 一律被当成 35 字节的非法长度，验签直接失败。现在前缀按 `b06566` → `b0` → 裸键三档剥离（`strip_key_prefix`），边长集合 64/70/66；夹具也改用真实编码，JS 侧同步。
- **地址：先撤回一条被放大成"定律"的巧合，再把它算到底**。上一稿写过"`base58(sha256(pub)[10:])` 能复算出官方 SDK 打的同一个地址"，只在一个样本上成立；拿 50 个固定种子批量复算只有 **7/50** 一致，于是又写成"能校验、不能反推"。两句话错在同一处：**字母表用错了**。官方 SDK 走的是 `brdc-sjcl` 的 Base58，字母表与比特币表**只差 4 处**（位置 10 `b/B`、27 `u/U`、34 `B/b`、52 `U/u`，全是大小写对调）；前 9 位 `1`–`9` 相同，所以 7 个不含这 4 个字母的地址偶然相等。换表后 **50/50** 逐字节复现——地址是完全可推导的。
- **新模块 `uibc_core/bid_address.py`**：`derive_did` / `address_matches` / `bitcoin_to_bid_suffix`。版本字节（RFC-003 §5.1 第三步 `0x01`）做成显式开关：RFC 的唯一示例用"带版本字节"精确复现出 `38VPR182Y4uTkq32fykXjbKBPdQZutH`，50 条现行地址用"不带"精确复现——标准文本与参考实现在这一步分叉了，不替任何一方选默认。
- 现在钉住的四条性质（`tests/test_bid_address.py`）：50/50 精确复现；带版本字节时 0/50；用比特币字母表时恰好 7/50；SM2 走 SM3 且落在 ABNF 区间。
- 证据（地址性质）：`tests/test_bid_address.py`（13 条）、`docs/ADDRESS-DERIVATION.md`、`tests/test_bid_address_rule.py`（55 条）、`tools/bid_sdk_address_batch.mjs`、`fixtures/bid/sdk_address_batch.json`；单样本记录 `fixtures/bid/sdk_address.json` 保留，只作"官方输出原样快照"，不再当作可复算的证据。
- **§4.2.2 五个字段接口落地**（`resolve_public_keys` / `resolve_attributes` / `resolve_acsns` / `resolve_credentials` / `resolve_service`）：协议给了五个字段端点，其中 `public-keys` 返回数组而 `public-keys/{id}` 返回单个对象——这个**形状不对称是协议自己的**，调用方若假定"永远是列表"就会错。都按 §4.2.5 的码处理（3/7 重试、6 不重试），都校验 `data.id` 必须等于请求的 BID、`data.version` 必须是字符串，单键查询必须真的是一把键、服务查询必须真的问什么答什么。键 id 要百分号编码（`#` → `%23`），服务查询用半角 `?id=`（协议里印的是全角"？"）。测试 `tests/test_bid_fields.py` 15 条。
- 证据：`uibc_core/bid_protocol.py`、`tests/test_bid_fields.py`
- **§4.2.4 可信解析（`resolve_bid_trusted`）**：协议说可信解析要"对BID文档的公钥和签名内容进行可信验证"，"确保递归解析过程中每个经过的解析服务都是可信的"。最容易犯的错是把 `data.verify` 当结论——那等于把核查交给了被核查方。所以返回的是一个把三件事分开的对象：`server_verify`（解析服务自述，必须是 Bool 字面 `true`，字符串 `"true"` 直接拒）、`signature_ok`（我们自己按 §5 重验文档签名）、`delegate_state`（`extension.delegateSign` 第三方背书：`absent`/`verified`/`invalid`/`unchecked`）。`trusted` = 服务自述 **且** 我们自己验过；`fully_trusted` 还要求背书被核。**签名者公钥取不到时是 `unchecked` 而不是默认通过**——"没有证据"和"证据成立"必须能被区分。
- **`extension.delegateSign` 真的能验**（`verify_delegate_sign`）：`signer` 必须是 BID 键 id，`signatureValue` 是 Base58 的 Ed25519 签名，待签字节是 `publicKey` 字段的 JCS 形式（§5.2 已把排序规则写死，所以这里不另立一套编码）。三方背书没写怎么规范化，这一层是**我们选的**，写进文档而不是留给读者猜。
- **可运行 demo**（`tools/demo_bid_trusted.py`）：起一个真的 `http.server` 当解析服务，四种答法（诚实 / 说验过但文档被动过 / 说没验过 / 带背书），打印五条裁决。第 2 条是全部意义所在：只读 `data.verify` 的客户端在那里会打印 OK。
- 测试 `tests/test_bid_trusted.py` 15 条（请求形如 `{url}/{bid}?verify=true`、服务撒谎必被抓、`"true"` 字符串必拒、`verify=false` 是答案不是异常、背书四态各一条）。
- 证据：`uibc_core/bid_protocol.py::resolve_bid_trusted`、`tests/test_bid_trusted.py`、`tools/demo_bid_trusted.py`
- **SM2 不再"此处不可验证"**：协议 §5 允许 Ed25519 与 SM2 两种，此前我们只做 Ed25519 并如实写明。这一轮把向量问题解决了——不是自己造，而是引国标自己的例题：GM/T 0003.5-2012（GB/T 32918.5）附录 A 给出曲线参数、`dA`、`PA`、`ZA`、`e`、`k`、`(x1,y1)`、`r`、`s` 全套数字，于是实现可以钉在**别人的**数字上。
- 新增 `uibc_core/sm2.py`（纯 Python 大整数 + OpenSSL 的 SM3，无第三方依赖）：曲线运算、`ZA`、`e`、签名与验签。`tests/test_sm2.py` 18 条，逐项对上国标：`PA = [dA]G`、`ZA = b2e14c5c…a4f3`、`e = f0b43e94…8640`、`[k]G` 的 x 坐标、以及用国标给的 `k` 复算出**同一个** `r=F5A03B06…`、`s=B1B6AA29…`。
- **一个自己抓到的错**：`s` 里的 `(1+d)^-1` 一开始用了模 `p` 的逆元，签出来的签名自己的验签器都不认——这正是"能签也能验"要一起实现的原因，只验不签复现不出国标的 r/s，也就发现不了这类错。
- **接进 BID 文档验签**：`verify_bid_document` 见 `publicKey.type` 含 SM2 即走 SM2 路径（64 字节 `x||y`，可带 `b0`/`b06566` 头）。两处协议没规定的地方**明说不猜**：区分标识用 GM/T 默认 `1234567812345678`，成功理由里写出这一点；不同 ID 签的链会判不通过，而不是被当成"验过了"。
- 证据：`uibc_core/sm2.py`、`tests/test_sm2.py`、`uibc_core/bid_protocol.py::_verify_sm2_key`
- **竞品从"说法"变成"字节"**：`docs/COMPETITOR-EVIDENCE.md` 钉住 DIF Universal Resolver 的 did:bid 驱动（`caict-4iot-dev/uni-resolver-driver-did-bid`，commit `5a93365`，2022-11-09，Apache-2.0，324 行，`src/test` 无任何测试类），逐条给出行号：非零 `errorCode` 在 77–78 行坍缩成一句 `docuement not exist`、全文 `verify` 出现 0 次、`delegateSign` 9 行全部只做字段搬运（233–235 行）、174 行把 `proof` 原样塞进 metadata 不重算。
- **这条主张自带反证工具**（`tools/audit_official_bid_driver.py`）：重新下载钉住的字节、重新算行号；**对方一旦修了其中任何一条，脚本退出码非 0**，文档必须跟着改。"他们没做 X"因此不再是一句可以烂在文档里的话。
- 证据：`docs/COMPETITOR-EVIDENCE.md`、`tools/audit_official_bid_driver.py`

## 0.5.3 — 2026-11-25（一致性语料 36→58，第二实现对齐）

- **语料 36 → 58 条**：新增 `tools/redteam_scale.py`（22 条 scale 组变体）与 14 条补充变体（第二文件翻转/截断、第二条非法日期、第二条哈希截断、proof 索引偏移、截断 proof、清零 back-link、倒序 receipts）。期望值全部由实测 `failed_checks` 导出，不手填。
- **6 条如实跳过**：`no check fired; not exportable as a vector`（未知 status、索引倒序、删 seal、砍 seal 签名、schema 拼错、媒体类型换标）。`tests/test_conformance.py` 由「skipped 必须为空」改为「每条 skipped 必须带规定 reason」——把静默跳过，而不是跳过，定义为缺陷。
- **第二实现对齐 58/58**：`tools/verify-js/verify.mjs` 补「两条记录共用同一 evidence_id」与「逐条 created_at 存在但非法（`2026-11-31`）」两项检测；把两边检查编号不一致的 8 条按「一个缺陷一个编号」重划（S4 字节完整性 / S7 索引元数据 / S12 标识与日期 / S3 生命周期语义）。`python tools/assert_second_impl.py` → 58/58、18 检查、0 out of scope。
- **覆盖 16/19**：S9 / S16 / S19 无直接用例，`conformance/coverage.json` 如实标注。
- **发布资产**：`uibc-conformance-0.5.3.zip`，312,642 字节，sha256 `5f3a72cb277dac8f285cd50df304dd9befe762caf42f40b98b907bcfc20cce8c`；归档 = oracle（`SOURCE_DATE_EPOCH=1794700800` 重 emit）= MANIFEST（790 文件）= pin 四者同源。
- **两处发布事故，如实记录**：`v0.5.1` 因先建非 draft release 再上传资产被 immutable 拒绝，删除重建又把 tag 名永久占用；`v0.5.2` 资产可下载，但 oracle 语料仍带旧版本串，不是本树语料。详见 `docs/KNOWN-LIMITS.md` 第 11–12 条。
- **已知脱链**：`v0.5.3` 的 tag 指向 rebase 合入前的提交 `b60a2a00`，不在 `main` 祖先链；immutable release 使 tag 无法移动（422）。字节证明不受影响，但「tag 指向 main 某提交」这句话不成立。
## 未发布 — 2026-11-25（DID 对接：补 did:peer）

- **`did:peer` numalgo 0/2 支持，全离线**：文档由标识本身推导，不需要端点也不需要注册中心。`0z<multibase ed25519>` 与同键 `did:key` 的文档键材料一致（规范明说二者等价）；`2` 解析 `.A/.E/.V/.I/.D` 键元素与 `.S<base64url>` 服务元素，按规范把 `t/s/r/a`、`dm` 还原成全称。
- **numalgo 1/3/4 报 `UNRESOLVED` 而不是 `INVALID`**：它们的文档不在标识里（1 是创世文档的哈希、3 是 numalgo-2 DID 的哈希、4 短形态是长形态的哈希），需要对方提供。新增 `NotSelfResolving` 异常，适配器单独接住——这是同一类"错误信息坍缩"的第三例（前两例是 RegistryEndpointRequired 与线上 did:cn 形态）。
- 明确不声明 `keyAgreement`：从 Ed25519 公钥推 X25519 需要双有理映射，本实现没做，宁可不给也不给一个看起来对的错键。
- 测试 `tests/test_did_peer.py` 24 条，向量取自 Peer DID 方法规范原文样例。

## 未发布 — 2026-11-24（DID 对接：补 did:jwk / did:bid + 修线上 did:cn 误判）

主题：把"身份无关"从口号变成能点名的清单。两件事，一件加能力，一件修错误结论。

- **新增 `did:jwk`**（`uibc_core/did.py::did_jwk_document`）：离线解析（文档就是标识）。两条硬拒绝：JWK 里出现 `d/p/q/dp/dq/qi/oth/k` 一律拒绝（DID 是公开标识，解析器不该替人搬运私钥）；JWK 超过 4096 字节拒绝（不让一条长字符串把本地解码变成无界工作量）。ed25519 → `VERIFIED`，其它键型 → `INCONCLUSIVE`。测试 `tests/test_did_jwk.py` 15 条
- **修 `did:cn` 线上形态被误判为 `INVALID`**：信通院线上平台发的 `did:cn:agent:<base58>` 不在已发布 ABNF 内，`validate()` 拒绝是对的，但适配器把这次拒绝说成了"标识写错了"——等于告诉一个分配正确的智能体它的标识非法。现改为 `UNRESOLVED` 并保留标签（形态可识别 ≠ 分配已确认），回归测试钉住。这是本仓第二次"错误信息坍缩"（第一次是 `RegistryEndpointRequired`）
- **新增 `did:bid`**（`uibc_core/did_cn.py::_check_bid`）：星火·链网 BID，ABNF 两种形状——主链 `ef<base58>`（首字符加密算法、次字符编码算法，按规范两张表读出）与子链 `AC01:<suffix>`；`did:bid:byol` 作为规范明列的例外单独识别，不硬塞进正则。`read` 走 HTTP GET，`errorCode` 非 0 直接抛出，端点必须调用方给（不默认 URL）。测试 `tests/test_did_bid.py` 14 条
- **记下一处规范间冲突**：BID 的 ABNF 允许 `acsn ":" 0*1(suffix)` 的空后缀形态（如 `did:bid:AC01:`），但 DID Core 的 `method-specific-id` 必须以 idchar 结尾；两者不能同时满足。我们按 DID Core 拒绝，冲突写在测试与 `docs/DID-LANDSCAPE.md` §4，不装作看不见
- 新增 `docs/DID-LANDSCAPE.md`：DID 对接全景（9 种已接、主流方法矩阵、三档策略、与 Universal Resolver 的差距口径）
- `docs/EVIDENCE-INDEX.md` 由生成器重算（静态用例数 1557），口径改为"静态计数 ≠ 运行期收集数（参数化会更多、平台跳过会更少）"；`check_doc_facts` 0 mismatch
- 证据：`tests/test_did_jwk.py`、`tests/test_identity_adapter.py`、`docs/DID-LANDSCAPE.md`
## The suite count, counted where it cannot drift

- `docs/EVIDENCE-INDEX.md` carries one published number, and the tool that generates it (`suite_size()` in `tools/build_evidence_index.py`) asked `unittest` discovery how many cases the suite has. That number depends on **where** you run it: the same commit counts **1157 on Linux and 1156 on Windows**, because discovery imports modules and platform-gated imports differ. So the page was guaranteed to be stale on one platform, and `test_the_doc_in_the_repo_matches_a_fresh_build`, `check_says_what_it_means` and `test_index_number_matches_what_is_measured` failed there. This was found the honest way — `uibc-bench` D1 ("outsider runs the whole suite") failed on a clean Linux clone of main.
- Fix: `tools/suite_count.py` counts `def test_*` (AST, including async) under `tests/`, importing nothing. `build_evidence_index.suite_size()` and `check_doc_facts.measure()` both call it. Same commit → same number on every platform and in every checkout: **1510** on Linux and on Windows, verified 2026-11-24.
- The published line now says what it counts: static `def test_*` count, cross-platform, runtime discovery is slightly lower because of platform skips. Anything else still cites the page rather than retyping a number.
- Note for the record: the previous 1156 had also gone stale against a later commit on its own platform (PR #423 added `tests/test_interop_*`), which is the same defect with a different cause — a single typed digit that nothing re-derives.
- No version bump, same reason as above: the number is bound to a built archive.
## Ten documents, two orderings, measured

- Read all ten ACPs documents (`acps-specs/01`…`10`, each **v02.02**): `docs/ACPS-SPEC-MAP.md` maps what each is, how many times it names AIC, and which ones actually consume the code — ATR (certificate `CN`/`URI:acps://{AIC}`), AIA (mTLS peer check), ADP (`forwardChain`, loop detection), AAC (`agent:{aic}` subject IDs), AMP (logs, `kid` needed because AIC alone cannot pick a key).
- **Contradiction found and measured**: `ACPs-spec-AIC` §3 puts the version arc at position 5; `ACPs-spec-overview` §5.2 puts it at position 9; `ACPs-spec-ATR` §3.1 follows the overview in words. Nine distinct ten-arc samples exist across the corpus; seven carry a checksum that recomputes under salt `0x1234`, and the two that do not are AIP's `…0JU1` / `…0JU2` — `0JU4` with the last character bumped, i.e. placeholders.
- Consequence, stated rather than papered over: **the checksum is order-agnostic** (it hashes arcs 1-9 as text), so both orderings produce codes that verify. The defect is field naming, and it matters downstream (AAC subjects, ADP chains, ATR certificate matching) even though integrity is unaffected. We follow AIC §3, `scope` says so, and there is no invented crosswalk.
- Four new tests pin the corpus measurements, including "both orderings verify" and "AIP's two trailers are placeholders". Conformance file: 21; cross-implementation: 17; with the reader tests, 56 passed across the three files.
- Access recorded: `git clone --depth 1` works (1,937 files); the `contents` API rate-limits (429); `git/tree` returns zero entries. A Windows checkout differs from the API copy by CRLF only (8,149 vs 8,043 bytes, same `sha256:38242a01…23ab` after normalising).
- **No version bump.** `pyproject.toml` stays 0.5.0: this repository's release chain is pinned by `anchors/pins/uibc-conformance-0.5.0.sha256`, a hash of a *built* archive, and `STATUS.md` plus the README digest quote that pin. Bumping the number without building and publishing a new archive broke `test_pin_resolvability`, `test_outward_receipt` and `test_status_page` — measured on a clean Linux tarball: 16 failed at 0.5.2, 49 passed at 0.5.0 across the same seven files. Everything here is recorded as unreleased until an archive exists.

## The AIC text itself, and a checksum we can now decide

- Found the document, not just a crate's copy of it: `ACPs-spec-AIC-v02.02` at `aip-pub/ACPs-community`, path `acps-specs/02-ACPs-spec-AIC/ACPs-spec-AIC.md`. Copy pinned by `sha256:38242a01…23ab` in `docs/ACPS-SPEC-IN-HAND.md`. The earlier "the ACPs repositories are empty" reading came from the `git/tree` endpoint; `contents` returns the tree.
- `uibc_core/acps_identity_code.py`: spec references corrected v02.01 → v02.02; new `verify_acps_code(code, salt)` recomputes arc 10 (CRC-16/CCITT-FALSE over arcs 1-9 ++ salt, Base36 four chars) and returns `VERIFIED` / `INVALID` / `INCONCLUSIVE`. `VERIFIED` carries an evidence entry whose digest is the sha256 of the exact bytes hashed. Without a salt the answer is still "checksum NOT checked", never a guess.
- The document's own worked example passes byte for byte: `salt 0x12 0x34` → `crc 0x646C` → arc 10 `0JU4` on `1.2.156.3088.1.1.34C2.478BDF.3GF546`; `0xFFFF → 1EKF` matches the range the text states for arc 10.
- Third implementation as oracle: `aipub-protocols` 0.0.3 (crates.io, lib `protocols`) compiled unpatched on a Linux VM (cargo 1.100.0, 2026-11-24) and asked for checksums over 16 boundary cases (lowercase, salts 2→16 bytes, both ends of each segment range, ontology form, foreign prefixes). 16/16 agree; the answers are pinned in `tests/test_acps_cross_implementation.py` so they keep agreeing or fail loudly.
- Tests: `tests/test_acps_spec_conformance.py` (21, built only from the text's example, its stated range, deliberate mutations and the other documents' samples) + the cross-implementation file (17). Together with the existing reader tests: 56 passed across the three files.
- **No version bump**, and `CITATION.cff` stays 0.4.2 on purpose: it pins the Zenodo archive, not the working tree. `pyproject.toml` 0.5.0 → 0.5.1 was tried and reverted for the same reason as above — the number is bound to a built archive, not to a code change.

## Anchor: a frozen root, four calendar receipts, no Bitcoin attestation yet

- `docs/anchors/ROOT-28a23ff.txt` and `.ots`: the claims are frozen against commit `28a23ff` (tree `d4656d1`), `sha256(ROOT) = 20c8d31b07bd…bf72`, submitted 2026-11-24 18:30 +08:00 to four OpenTimestamps calendars.
- `ots upgrade` answers `Pending confirmation in Bitcoin blockchain` on all four. So the proof establishes "existed no later than submission, witnessed by four calendars", and **not** "attested on Bitcoin".
- RFC 3161 came back empty: `freetsa.org/tsr` 404, `timestamp.digicert.com` 400 (http) / timeout (https), `timestamp.sectigo.com` 404. The registry keeps `RFC3161 = rejection`; the row is not deleted.
- `docs/ANCHOR.md` states both, and why the root also lives in the repository (GitHub as a second, weaker witness).
## Measured numbers now have to name the commit they came from

- `tests/test_measured_facts_are_pinned.py`: any doc quoting a measured constant (file count, executed test count, tarball size) must also name a commit, or the suite fails.
- Reason, stated in the test itself: `check_doc_facts.py` can recompute everything derived from the tree, but "1,865 files" and "1471 passed" are properties of one commit on one machine. They go stale when `main` moves, and a stale number with no date is how a document starts lying without anyone editing it.
- `docs/REPRODUCTION.md` now declares **Commit under test: `8a41372`**; `docs/COMPETITIVE-LANDSCAPE.md` pins its two counts to the same commit.
- Two new tests; index rebuilt on this branch.
## The other document: the ten-arc code, read on its own terms

- `uibc_core/acps_identity_code.py`: a reader for `ACPs-spec-AIC-v02.01` — ten arcs, per-arc Base36 and length rules, prefix noted rather than pinned.
- **The checksum is never judged.** The salt is per-ARSP and unpublished; a code with a deliberately wrong trailer returns `INCONCLUSIVE`, and `scope` says so. A salt-holder's check would be strictly stronger, and the document says that instead of hiding it.
- Each reader refuses the other document's shape with an explicit reason instead of coercing it; `detect_profile()` labels which one a string belongs to. There is no crosswalk, because neither text contains one.
- `docs/TWO-DOCUMENTS-ONE-CODE.md` puts the two texts side by side and states the consequence: "supports the national agent identity code" is ambiguous until the document is named.
- 18 new tests. EVIDENCE-INDEX rebuilt on this branch; `paper/paper.md` module count updated 35 → 36.
## The third-party implementation, executed in both directions

- `docs/THIRD-PARTY-DIVERGENCE.md`: `aipmc-basic` 0.0.2 fetched from crates.io, built unmodified, and run against our parser — and our parser run against its examples.
- Result: the two families **reject each other**. Its ten-arc form (declared alignment: `ACPs-spec-AIC-v02.01`) fails our parser with profile `aip-acps`; a GB/Z 185.2-shaped eight-arc code fails its `parse`.
- Correction to `docs/COMPETITIVE-LANDSCAPE.md`: "deviates from the standard" was the wrong frame. It implements **a different document**, which makes this an interoperability question for the authors of both.
- Two findings recorded rather than assumed: its `parse` does not verify the checksum (a deliberately wrong CRC still constructs, against its docs' "构造即校验"), and its spec example fails under the published default salt — which is how the private salt becomes visible.
## From one public URL to a green suite, on a machine we did not author on

- `docs/REPRODUCTION.md`: public tarball → fresh venv → `check_doc_facts.py` → `pytest` → `probe_reference_repos.py`, with the exact commands and the observed numbers.
- Observed 2026-11-24 on a Linux host: tarball 200 / 2,568,257 bytes / 1,865 files; `check_doc_facts.py` → 0 mismatch; `pytest` → **1471 passed, 33 skipped, 105 subtests passed** in 426.73 s.
- Two counts are stated side by side because they differ and both are real: 1,173 test functions in the evidence index, 1,471 executed after parametrisation.
- Row 6 stays **partial**: this removes "only works on the author's machine", not "the author is judging the author". 33 skips are a skip, not a pass.
## What the reference implementation lets an anonymous reader see

- `tools/probe_reference_repos.py`: no account, no token, one API call per repo, prints what each default branch actually contains.
- Result 2026-11-24: `ACPs-community` main → **0 files**; the other eight repositories → **README.md only**. The 16.45 K downloads on the landing page are not inspection.
- Consequence recorded in `docs/COMPETITIVE-LANDSCAPE.md`: we may say we **read** its version history and protocol names, and we may not say we cross-checked against its code.
- The same question put to this repository returns **1,865 files** anonymously, tarball 200 without a token. That contrast is the one place on this track where "ahead" means "inspectable", and it is measured rather than asserted.
## The competitive table, with the rows we lose

- `docs/COMPETITIVE-LANDSCAPE.md`: three tracks, every row carrying 标准 / 规范 / 实测 / 读码 as its basis.
- Corrections it forces on us: the reference implementation is at **v2.2.0** (2026-08-31), not the v2.1.0 of the July release; it adopted the OID form in v2.0.0; and **AAC shipped in v2.2.0**, so it is not a concept we can claim to have introduced.
- It also records that the reference repo's `main` currently returns an empty tree, so our cross-check is against its published changelog rather than its code — a partial, not a pass.
- Eight "what best means" criteria scored: five pass, two partial, one zero. The zero is independent evaluation by a separate identity, and it stays zero until someone else does it.
## The did:cn namespace the platform serves is not the one the README publishes

- Measured on `agent.idfactory.cn`: every registered agent reads
  `did:cn:agent:<base58>`, while the CN DID Method Specification fixes
  `2DIGIT.3*5DIGIT.1*128DIGIT`. Until now our adapter refused **all** of them —
  correct against the published ABNF, useless against the live namespace.
- `validate()` is unchanged and still refuses the live form: loosening it would
  mean the adapter no longer checks the document it claims to check.
- `validate_live_agent_id()` is new: it recognises `did:cn:agent:<22-44 base58>`,
  labels itself `published_abnf: False`, and states that shape proves nothing
  about allocation. Two entry points, two labels, no silent merge.
- `docs/TWO-CODES-DIFF.md` puts the two codes side by side across ten
  dimensions, each row citing 标准 / 规范 / 实测. Three divergences are now
  written down instead of inferred: the live namespace has no published ABNF;
  `service` lives in the DID Document for `did:cn` but has no document at all
  for the national code; and **neither track can answer "after revocation, is a
  previously issued credential still valid"**.
- 10 new tests.
## Agent identity code: we read the shape, and stop there

- `uibc_core/agent_identity_code.py` parses `GB/Z 185.2—2026` identity codes
  (the national OID scheme, prefix `1.2.156.3088`) strictly by the published
  clauses: five dot-separated parts over a four-arc prefix, version `1` of a
  35-value range, provider and requester of 1–6 characters, sequence bounded at
  19 (9 ontology + 10 instance, **derived and labelled as derived**).
- **The ceiling is `INCONCLUSIVE`, by construction.** `_verdict()` has one
  return value and no branch that produces `VERIFIED`: allocation belongs to a
  registration service provider, and the standard defines no resolution
  endpoint. A shape check that returned `VERIFIED` would be reporting "this
  identity is real" on the strength of "this string is shaped correctly".
- A reserved version is `UNSUPPORTED`, not `INVALID` — first real use of the
  seven-state vocabulary on a national standard: *not implemented is not wrong*.
- Found and documented a **third-party reading that adds two levels and a
  checksum**: `aipmc-basic` (MIT, crates.io) reads ten arcs, separating ontology
  and instance serials and appending a four-character Base36
  CRC-16/CCITT-FALSE with a non-public salt. None of that is in the standard as
  published, and we cannot recompute the checksum, so `detect_profile()` names
  the profile and `parse_agent_code()` refuses it *with the reason attached*.
  We do not silently accept a private convention, and we do not pretend to
  verify it.
- `duplicates()` exposes management requirement 6(d) (one code, one agent) as a
  report rather than a decision.
- 27 new tests; `docs/AGENT-IDENTITY-CODE.md` states the boundaries and the
  remaining gaps (no issuer, no resolver, AIP reference implementation not yet
  compared); module count 34 → 35 and the evidence index rebuilt.
### Where coverage stops, and why

- `docs/COMPETITIVE-COVERAGE-AAC.md` gains a table of the classes we probed and
  deliberately did **not** run: `standard-history-v0` (69 cases counting rules —
  reproducing them means copying their spec, so it would not be an independent
  check), CBOR classes (no decoder here), MMR classes (different hash family),
  COSE classes (no library), and the registry/text layers.
- Stated conclusion: **2 of 40 is the ceiling for standard-library-only
  recomputation, not laziness.** Running all 40 would first require
  implementing MMR, COSE and CBOR — the numbers would then no longer be
  independent.

### A second class of their vectors, and it agreed the first time

- `tools/crosscheck_aac_history_frame.py` reproduces the `table_binding` /
  `pack_binding` verdicts of `vectors/history-frame-v0`:
  `properties: 22  disagreements: 0` → `OUR JCS REPRODUCES THEIR BINDING VERDICTS`.
- No fix was needed here: our RFC 8785 form over the JSON values they ship
  yields exactly the digests they list, and the five negative cases
  (`pack-digest-mismatch`, `table-digest-mismatch`, `pack-for-another-instance`,
  `pack-translated-in-place`, `pack-carries-checked-string`) disagree as intended.
- Scope stated plainly: this tests **binding** (the digest names the right
  document), not their counting rules.
- `docs/COMPETITIVE-COVERAGE-AAC.md` now counts **2 of 40** classes (5%):
  `json-nesting` (which found a limit we lacked) and `history-frame-v0`
  (which agreed on first run). Both numbers are kept.
- 6 new tests.

### One of their forty vector classes, and the limit we did not have

- `tools/crosscheck_aac_json_nesting.py` runs the `json-nesting` cases from
  `action-state-group/agent-action-capsule` against our reader and JCS.
- First run: `cases: 9  mismatches: 4` — the four 129-deep negatives were all
  accepted. Their spec states a **128-level** JSON nesting limit shared by four
  languages (interop-profile-v1 §5.2, draft Conventions); we had no such limit.
- Fix: `canonical.MAX_NESTING_DEPTH = 128`, `nesting_depth()`,
  `check_nesting()`, called at the head of `canonicalize()`. Re-run:
  `cases: 9  mismatches: 0` → `WE MATCH THEIR NESTING CONTRACT`.
- `docs/COMPETITIVE-COVERAGE-AAC.md` maps all 40 vector directories: exactly
  **1** (2.5%) is computable with the standard library alone; the other 39 need
  MMR, COSE, ed25519, or are registry/text layers — a different stack, so a
  numeric comparison there would be misleading.
- The added limit changed the diagnostics in `conformance`, so
  `docs/THESIS-CH5-TABLES.md` was regenerated by `tools/build_thesis_tables.py`
  (table 5-4: `0 / 0` → `4 / 14`, theirs `4 / 5`). The numbers are computed, not
  hand-edited.
- 8 new tests.

### We ran their vectors, and wrote down the first run that failed

- `tools/crosscheck_scitt_cose_vectors.py` folds the inclusion paths in the
  `scitt-cose` set published by `ietf-wg-scitt/examples` using only
  `uibc_core.merkle`; no COSE library is needed to check a path.
- First run: **all five vectors disagreed** — because we read `leaf_entry` as a
  leaf hash, when it is the leaf *input* digest (RFC 9162: `H(0x00 || leaf_input)`).
  That was our error; corrected run: `vectors: 5  mismatches: 0`.
- Outcomes: `valid-eddsa` and `valid-es256` fold onto their stated roots;
  `fail-tampered-path` folds away as it must; the signature and VDS negatives
  are reported but not adjudicated here, since those failures live outside the
  tree layer.
- `docs/external-review/CROSSCHECK-SCITT-COSE.md` states plainly what this is
  not: not an audit of `scitt-cose`, not a claim of verifier agreement, and not
  a place in anyone's record — their `INTEROP.md` still does not list us.
- 5 new tests, including a note test that fails if the "not an audit" sentence
  or the failed-first-run record is removed.

### The upstream submission is now a package, not a plan

- `tools/build_scitt_vector_package.py` builds and self-verifies a
  SCITT-shaped vector set at `docs/upstream-package/scitt-rfc9162`: five
  vectors (two `VALID`, three named failures) covering the **RFC 9162 SHA-256
  tree and inclusion-path layer only**. Each `expected.json` carries
  `root_true` and a **computed** `reconstructed_root`, so positives must match
  and negatives must differ without any code from this repository.
- Shape copied from the vector set the IETF SCITT WG `examples` repository
  already merged: `v1/<id>/expected.json`, `manifest.json`, `SHA256SUMS`,
  `.gitattributes` pinning files as non-normalized. `sha256sum -c` gives 6/6.
- `docs/UPSTREAM-PR-CHECKLIST.md` closes the three pre-submission checks that
  were open: format (verified against upstream HEAD `727ee03`, verbatim
  quotation of their "a mismatch … is exactly the report the authors want"),
  licensing (both Apache-2.0, SPDX per-directory), and **the one check nobody
  can do for the author** — IETF Note Well / IPR consent, which needs the
  author's own account.
- What the package does not cover is in its README, not an appendix: no
  COSE_Sign1 bytes (no COSE library here), no log receipts, no witness
  cosignatures, no TSA. It is narrower than `scitt-cose` and is not a
  replacement for it.
- Submission status: **not sent.** Opening the PR is an outbound action.

### The external-record gap is an order of magnitude, not a tie

- `docs/LANDSCAPE-2026-11.md` §8: the other draft's `INTEROP.md` lists **nine
  independent parties**, each `ran & verified` with a linked public record
  (EMILIA, Songbo Bu, Tyche, Microsoft/CCF, NANDA/MIT, GlyphZero, APS,
  A2A boundary-seal, GAR/SOOS). This repository has one, and it wrote that
  record itself. `INTEROP.md` does not mention us.
- Their registry states the rule worth copying: *"A name is not evidence;
  a digest is."*
- The only way to close it is to have someone else write us into their record,
  which is an outbound action and is not taken here.
- `tests/test_landscape_corrections.py` (+3): fails if that 9-vs-1 line, or the
  "we are not in their record" line, is edited away, and if any line outside a
  disclaimer claims the gap is closed.

### Two claims about the competition were wrong

- `docs/LANDSCAPE-2026-11.md` §7: an author of another draft states that
  **"an independent party has run the full vector suite … and reproduced 32/32"**
  (SCITT list, 2026-07-14). "Third-party execution" is therefore **not** this
  repository's exclusive property, and the comparison that implied it has
  been retired.
- The same section records that Agent Passport System holds a public
  **OpenChain Community of Conformance** record (2026-07-17), so "no external
  organisation has published anything about it" was also wrong. The precise
  statement is: no organisation has *adopted the protocol*; an organisation
  *published a conformance record* about it.
- What still holds: their independent runs pass in full (32/32, zero
  divergence across implementations); ours produced **two disagreements** on
  a foreign host, and those two rows are now a check that fails if they
  return.
- `tests/test_landscape_corrections.py` (4) fails if either correction is
  edited out, or if the retired comparison reappears outside a line that
  says it is wrong.

# Changelog

All notable changes to `uibc-core` are recorded here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html),
with one project-specific rule: **any change to what produces which verifier
verdict (PASS / FAIL / INCONCLUSIVE) is a breaking change**, regardless of how
small the code diff is.

Status reminder: everything up to and including `0.2.1` is a **PROPOSAL**.
Nothing here is a ratified standard.

---

## [0.4.1] - 2026-11-19

Released so that the version number, the published artifact and the repository
HEAD all name the same bytes. `0.4.0` on PyPI was built on 2026-11-18; `main`
kept moving afterwards (#241, #242), which left the citable artifact behind the
tree it claimed to be. `0.4.1` is built from `main` and is what the registry
record carries.

- No intentional behaviour change beyond what is listed under `[Unreleased]`
  below: the verification path, the twenty checks and the three-valued verdict
  semantics are the same code. Anyone who needs the 2026-11-18 bytes can still
  install `0.4.0`; both are pinned.
- What is different for a reader: `docs/` now carries the external-baseline
  measurements of 2026-11-19 and the one-click outsider run (#242), so a citable
  DOI finally points at a tree a reader can also browse.
- Version strings in `pyproject.toml` and `uibc_core/__init__.py` move together;
  `SPEC_VERSION` stays `uibc-core/0.3.3-proposal` on purpose - it names the wire
  format, not this package's release number, and changing it would silently
  invalidate every package already sealed under it.

## [Unreleased]

### Six China-registry DID methods, each at the level its own text allows (2026-11-24)

- `uibc_core/did_cn.py` (new, standard library only) accepts `did:cn`, `did:ioa`,
  `did:cndid`, `did:ctid`, `did:oan` and `did:cndomain` by their published ABNF,
  and resolves the four that publish a channel — never with a guessed default URL:
  `did:cn` via `GET {base}/did/resolve/<did>` (spec §3.2), `did:ioa` / `did:cndid`
  via an `operation: "read"` envelope (§5.2), `did:cndomain` via HTTPS publication.
  `did:ctid` (vendor SDK, SM2 keys) and `did:oan` (no HTTP read API in the spec)
  are validated and then refused, with the reason stated per method in
  `matrix()`.
- `did.resolve()` gains `endpoint=None` and dispatches the six names to
  `did_cn`; `UnsupportedMethod` now lists what is actually supported.
- The "no published specification, 11 paths returned 401/404" sentence is
  **deleted**, not reworded: all six methods (and `did:wba`) do have public text.
  Replaced by `docs/spec-sources/did-cn-specs.md` (spec URLs, byte counts,
  ABNF, per-method support matrix).
- Recorded finding, in code comments and in the doc: an offline DID document
  cannot be rebuilt from a `did:ioa` / `did:cndid` identifier. The suffix is capped
  at 42 characters, leaving ≤40 for the key body, while a 32-byte Ed25519 key
  needs 43–44 in base58 — the arithmetic, not our laziness, closes that door.
- `tests/test_did_cn.py` (41 cases): spec examples accepted, out-of-grammar
  neighbours refused, endpoint-never-defaulted, envelope shape, document-id
  mismatch, matrix fields, the suffix-length arithmetic, and three CLI cases —
  `register` refuses an `identifier_only` binding, requires `--did-endpoint` for a
  registry method, and proves resolvability before writing the binding.
  `tests/test_did.py`'s "refused not guessed" case is split accordingly: `did:wba`
  and `did:lgd` still raise `UnsupportedMethod`; `did:cn` / `did:ioa` strings
  outside the published grammar now raise `IdentifierError`.
- CLI: `register` / `verify` / `gate` gain `--did-endpoint`; `register` resolves
  the identifier once at write time rather than accepting a binding nobody can
  check, and `resolve_ed25519_key()` passes the endpoint through.
- No version bump in this entry: 0.5.1 would drag ~20 generated-artifact
  consistency tests into red, so the change is booked here and the bump is a
  separate job (regenerate first, then bump).

- CI fix: `actions/checkout` now uses `fetch-depth: 0` in `ci.yml`. The test that
  recomputes the outsider's figures at `8a95747` needs that commit to exist in the
  clone; on a shallow clone it now reports **skipped** with the reason, rather than
  failing, because a missing input is not a passing test either.

### The outsider's receipt is recomputed here, not quoted (2026-11-19)

- `EXTERNAL-NODE-001.md` quoted two figures - `Ran 605 tests` and
  `checks compared: 70, mismatches: 2` - from a host we do not control. Quoting
  numbers nobody here can recompute is the smallest form of hearsay, under a
  heading that says "third-party evidence".
- `tools/verify_external_node_report.py` exports `8a95747` into a scratch
  directory and runs the same two commands. Result on our side:
  `605 tests`, `mismatches: 2`, `AGREEMENT: FAIL - SPEC BUG` - both figures
  match his exactly.
- The skip count does not match: he saw 22, we see 1. Skips follow installed
  extras, which is why no document should carry one.
- The point of the match: **605 and 2 are properties of that commit, not of his
  machine.** A different OS and Python arrived at the same pair because the code
  produced them.
- `tests/test_verify_external_node_report.py` (3 cases): the tool's expected
  figures are read back out of the report itself, the two-line shapes parse, and
  a `--quick` run recomputes the comparison and prints its scope sentence.

### Conflicts on generated files get a script, not a person's afternoon (2026-11-19)

- `docs/EVIDENCE-INDEX.md` and `docs/EVIDENCE-DASHBOARD.svg` are script output.
  Both sides of a parallel branch regenerate them, so every merge conflicted on
  them; one round spent five rebases, two of which were hand-regenerating files
  a script had already known how to print.
- `tools/resolve_generated.py` reads the conflicted paths mid-rebase and
  regenerates the ones a generator owns, then stages them. If a conflicted path
  is not generator output it prints it and exits 1 - a tool that "picks a side"
  on hand-written files can silently drop someone's work, so it refuses to.
- `tests/test_resolve_generated.py` (3 cases): the allow-list stays at exactly
  two paths, every listed generator exists, and outside a rebase the tool
  changes nothing.

### The defect an outsider found is now a check that can fail (2026-11-19)

- External node 001 (Wang Guigui, Debian 13, uid 1001, no `pip install`, README
  commands verbatim) ran `cross_check.py` on `8a95747` and got exit 1: two rows
  on `fixture:duplicated` disagreed (S4 `FAIL` vs `PASS`, S5 `INCONCLUSIVE` vs
  `FAIL`). He then re-ran on `343d906` on his own initiative and got 0 mismatches.
- `tools/external_node_regression.py` re-runs that comparison and fails if the
  two implementations ever disagree on `fixture:duplicated` again. The exit code
  of `cross_check.py` is deliberately not the signal: it was 0 after the fix and
  1 before, and this check has to accept the first and refuse the second.
- Ninth item in `tools/run_all_evidence.py`; `--online` is now
  `9 ok, 0 failed, 0 skipped, 22.8 s`, and the dashboard carries nine rows.
- `tests/test_external_node_regression.py` (2 cases): the parser recognises the
  exact line shape from his report, and the limit ("this does not establish that
  his run is reproducible today") travels with the claim.
- `docs/external-review/RE-RUN-REQUEST.md`: draft, unsent. Asks the same operator
  to run today's `main` on the same host - first run found the defect, second
  confirms the repair, which makes a verification line rather than a second node.
- No claim about being stronger, better, or first appears in any of this.

### The suite size is counted in one place (2026-11-19)

- Eight documents carried the literal test count. Every parallel branch rewrote
  the same eight lines, so every pull request arrived in conflict; this round
  spent four rebases on it before the cause was obvious.
- `README.md`, `README.en.md`, `AGENTS.md`, `docs/COMPOSITION-VERIFIER.md`,
  `docs/CONFORMANCE.md`, `docs/ECOSYSTEM-MAP.md`, `docs/INTEROP-MATRIX.md` and
  `docs/ONE-COMMAND-AUDIT.md` now cite `docs/EVIDENCE-INDEX.md` instead of
  typing the count.
- `tools/build_evidence_index.py` prints what it measured (`641 个用例`); a
  number a generator counts is a number nobody has to retype.
- `tools/check_doc_facts.py` reports a typed count anywhere in `TARGETS` as a
  mismatch even when the number is right: "cite docs/EVIDENCE-INDEX.md instead
  of typing the count".
- `tests/test_doc_facts_cite.py` (2 cases): a correct-but-typed count fails, and
  the index carries the measured number.

### The signature primitive gets a third-party referee (2026-11-19)

- `tools/external_crypto_check.py`: `uibc_core/ed25519.py` is pure Python, so
  verifying our own seals with it is self-consistent even if it were wrong.
  The check verifies the same facts with `cryptography` (OpenSSL): `06` ok/ok and
  `36` fail/fail, agreeing package by package, plus a negative probe - one byte
  changed in the payload must be refused by the third party.
- Eighth item in `tools/run_all_evidence.py`: `--online` runs eight checks
  (`8 ok, 0 failed, 0 skipped, 20.5 s`); the dashboard regenerates with eight rows.
- Limit stated in the tool and in `docs/PAPER-EVIDENCE.md` row 8: RFC 8785
  canonicalisation still uses this repository's JCS implementation and no
  third-party JCS library is installed here, so that layer is not cross-checked.

### The recheck, the adoption note, and a test that exhausted the inode table (2026-11-19)

- `docs/LANDSCAPE-2026-11.md` gains a dated recheck. On specification and
  ecosystem the gap widened: `-05` is 61 pages with seven IANA registry requests;
  `draft-pidlisnyi-aps-04` ships 17 repositories in four languages and two hosted
  services; `draft-munoz-scitt-permit-profile-01` is a third independent author.
- The same recheck finds adoption at zero **across the field**: `arXiv:2606.04193`
  says it in its own words. An adoption count is not a competitive metric -
  nobody leads it, including the largest draft.
- `docs/ADOPTION-MEASUREMENT.md`: the four-bucket method published as something
  copyable, its four limits stated, the UIBC/UPnP name collision recorded, and a
  message draft marked **draft, unsent**.
- `tests/test_verify_js.py::cases_root()` unpacked the archive **once per call**.
  Measured 2026-11-19: `/tmp` held 1,387 `uibc-js-cases-*` directories at 449
  inodes each; the machine's inode table hit 100% (655,360/655,360) and every
  later test failed with "No usable temporary directory". Now one extraction per
  process, removed at exit, with two regression tests; a full run leaves zero
  such directories.
- `tools/check_citations.py` gains four references; the three IETF ones resolve
  at 200.

### v0.4.0 tagged, and the suite is downloadable without an account (2026-11-19)

- Tag `v0.4.0` on the commit that carries the PyPI bytes; release
  `uibc-core 0.4.0` with `uibc-conformance-0.4.0.zip` (114,576 B, sha256
  `9a1ca72f...`) as an asset - a branch moves, an asset does not.
- The stranger's path was exercised rather than assumed: the asset was
  downloaded, its hash compared with the tree, then run against a verifier
  invoked only through the documented CLI contract - `strict 36/36, refused 30/36`.
- `docs/UPSTREAM-SUBMISSION-PLAN.md` now marks steps 1 and 2 done and still says
  steps 3 and 4 are unsent.

### The suite is now addressed to strangers (2026-11-19)

- **`docs/CONTRIBUTION-FALSIFIABILITY.md`**: the 36-package suite stated as an
  offer to any agent-evidence verifier - the CLI contract, the accept half that
  stops a refuse-everything verifier scoring full marks, the two current results,
  and the four limits including the one this document exists to invite someone
  to close.
- **`tools/run_conformance.py --name`**: a third party's result can carry its
  own implementation label instead of ours.

### Adoption is a measurement, not an adjective (2026-11-19)

- **`tools/check_adoption.py`**: asks four parties we do not run - another
  repository, another codebase, a standards body, the nearest SCITT profile.
  All four currently return zero; a non-zero bucket exits 1 so nobody can quietly
  start claiming more.
- **`docs/LANDSCAPE-2026-11.md`**: what the nearest project actually has
  (`draft-mih-scitt-agent-action-capsule-05`, an IETF 126 interop report, two
  PyPI packages, four framework adapters) against what we have (nothing in that
  column). It says the number plainly: not ahead, behind. Then three routes that
  could move adoption off zero, ranked by cost.

### One command, seven checks, one exit code (2026-11-19)

- **`tools/run_all_evidence.py`**: runs the seven things this repository claims,
  offline by default, `--online` for the three that need Zenodo, PyPI, GitHub and
  Software Heritage. 16.3 s, `VERDICT: OK`, exit 0.
- **`docs/EVIDENCE-DASHBOARD.svg`**: the same seven, as a picture, generated by
  `--svg` so it cannot disagree with the run.
- **`docs/PAPER-EVIDENCE.md`**: claim -> command -> measured value -> what it
  cannot support. Including the three limits that would be dishonest to omit.

### The 0.4.0 bytes, pinned and checked across three sources (2026-11-19)

- **`tools/pin_release.py`**: asks PyPI what it serves, downloads both artefacts,
  recomputes SHA-256, and writes `anchors/pins/uibc-core-0.4.0.sha256` in plain
  `sha256sum` format. 1.457 s, both artefacts matched.
- **`tools/check_pins.py`**: the release asset, the index, and the download must
  all agree - any two agreeing is not enough. 2.229 s, `VERDICT: OK`.
- **Release `release-pins-0.4.0`**: the pin published on a channel PyPI cannot
  rewrite.
- **0.4.0 itself** was published by the parallel line on 2026-11-18T17:19Z;
  this entry pins it, it does not claim to have shipped it.

### The anchor moves to a channel the package cannot reach (2026-11-19)

- **Release `anchor-001`**: the same `anchor.json`, published as a downloadable
  asset, so editing the package can no longer edit the anchor in one commit.
- **`tools/check_channel.py`**: takes the anchor from the release and the
  package from the repository, reassembles them, and asks the verifier whether
  they still belong together. 1.383 s, `VERDICT: OK`.
- **`docs/ANCHOR-CHANNEL.md`**: the four channels considered and why this one,
  including what it does not buy (same platform, same account).

### The first anchor inside the repository (2026-11-19)

- **`anchors/001/`**: `seq 1`, a new key, `checkpoint_head sha256:2935c3f4…`.
  The package is the demo fixture, so the head is the number the demo pages
  already print; the key is not the demo key, which is public and must never
  sign a publication.
- **`tests/test_published_anchor.py`**: five offline checks in CI - well-formed,
  ANCHORED, chain accepts it, the JavaScript implementation agrees, and a
  one-byte edit to an evidence file makes S4, S8 and S9 fire.
- **`docs/FIRST-ANCHOR.md`** and **`anchors/README.md`**: what it is, what it
  is not, and how to withdraw it. The anchor and the package share one channel,
  which proves the mechanism and not yet the separation; that needs a channel
  decision, not a commit.

### Three witnesses of the artefact, re-checked (2026-11-19)

- **`tools/check_witnesses.py`**: asks Zenodo, Software Heritage and Sigstore
  Rekor, live, whether what they hold is what we cite. 6 s, exit 0 only if every
  digest matches. Both digests (Rekor SHA-256, Zenodo md5) equal the file in
  `dist/`.
- **`docs/WITNESSES.md`**: what each one proves and does not - witness of the
  artefact, never adoption of the format.
- **`docs/IMPLEMENTATION-STATUS.md`**: a new section 0 separates the two
  numbers. The previous page reported "zero external evidence"; that was a
  counting error, and hiding a DOI that already exists is worse than having none.
- **Not in CI, on purpose**: a third party's outage should not turn our CI red.

### One command, one stranger, both implementations (2026-11-19)

- **`tools/verify-js/chain.mjs`**: the anchor line judged with node:crypto, no
  shared code with `anchor_chain.py`. Five scenarios frozen as *agreement*:
  sound line, gap, replay, rewritten predecessor, withheld anchor (STALE).
- **`tools/outsider_chain_audit.py`**: one command that builds two bundles,
  links them, and answers four questions with both implementations in a
  stripped environment - 0.877 s end to end, exit 0 only on VERDICT OK.
- **Deliberate duplication, stated**: the six lines of JCS are repeated rather
  than shared; a shared helper is one more thing that can drift, and the rule is
  tiny.
- **What it does not prove**: the line is not real. No `anchors/` directory,
  no publication - `docs/IMPLEMENTATION-STATUS.md` still reads zero.

### Anchors that name their predecessor (2026-11-19)

- **`anchor.json` gains `seq` and `prev_anchor_digest`.** A single anchor cannot
  distinguish "current" from "yesterday's, still perfectly self-consistent"; a
  line of anchors that each name the digest before them can.
- **`tools/anchor_chain.py`** judges a directory of anchors: gap, replayed
  position, rewritten predecessor, and a first anchor claiming a predecessor are
  all CHAIN BROKEN; a chain shorter than what the caller already knows is
  **STALE** (exit 5), because "absent" and "withheld" are the same danger.
- **`make_release_bundle.py --prev-anchor`** fills `seq+1` and the predecessor
  digest; **`anchor_check.py --prev`** refuses a rollback by comparing the two.
- **Eight frozen scenarios** in `tests/test_anchor_chain.py`.
- **What it cannot do, stated:** withholding cannot be countered by arithmetic
  here - only by where the anchors are published - and seq 1 has no way to
  prove itself current without an outside record.
- **No real chain exists yet**; `docs/IMPLEMENTATION-STATUS.md` still reads zero.

### The publisher check, done twice (2026-11-19)

- **`tools/verify-js/anchor.mjs`**: the anchor verdict with node:crypto and
  `verify.mjs` - no shared code with `anchor_check.py`, no call into it. Seal
  verified under the anchor's key, `checkpoint_head` compared via
  `--expect-head`, exit 0 only for ANCHORED.
- **The Node path refuses to judge the RFC 3161 block** and says so
  (`timestamp: not judged here`) rather than borrowing the other
  implementation's answer.
- **Four frozen scenarios** (`tests/test_anchor_second_impl.py`): baseline
  ANCHORED on both; a zeroed head, a swapped key and a missing anchor all
  refused by both. Exit-code conventions differ deliberately; the verdict word
  is what gets frozen.
- **`docs/ANCHOR-SECOND-IMPL.md`** states what agreement does not buy: both
  read the same bytes, and no external anchor exists yet.

### A timestamp inside the anchor (2026-11-19)

- **`anchor.json` gains an optional `tsa` block**: an RFC 3161 token plus the CA
  bundle it is checked against, so a stranger can date the anchor offline.
- **Two cover modes, and the difference is printed rather than smoothed over:**
  `covers="anchor_digest"` proves *this claim existed at that time* (token over
  JCS of agent_id/key_id/pubkey/head); `covers="file"` proves some bytes existed
  and is reported as `unbound`, because it dates a publication, not the claim.
- **Four refusals, all tested:** token over other bytes, token without a CA
  bundle ("an unchecked timestamp is not a timestamp"), an unknown cover mode,
  and `anchor_digest` mode given a token that covers something else.
- **The positive path is a real FreeTSA signature** (`tests/fixtures/anchor/
  freetsa.tsr`, 2026-11-17T08:11:35Z), verified offline against the shipped CA -
  a TSA we do not control on bytes we did not design. It covers a release-status
  file, so it exercises `covers=file`; the `anchor_digest` path has full negative
  coverage and needs a live stamp for a positive one.
- **`make_release_bundle.py`** prints the `anchor_digest` to stamp and accepts
  `--tsa-token/--tsa-cabundle` to attach it. A live stamp is a network call to a
  third party, so CI does not perform one.
- **`docs/TIMESTAMP-IN-ANCHOR.md`** states the remaining status plainly: no
  published anchor carries a timestamp yet.


### One file, no install (2026-11-19)

- **`tools/build_zipapp.py`** builds `dist/uibc.pyz`: the verifier, the CLI and
  the anchor check in one standard-library file. `verify`, `explain` and `anchor`
  work with no pip, no network and no checkout.
- **`uibc_core/__init__.py`** reads its own modules through the archive when the
  package sits inside a zipapp, so `SPEC_ID` stays equal to the checkout it was
  built from. A packaged verifier that reported a different provenance than its
  source would be reporting the packaging.
- **`tests/test_zipapp.py`** runs the zipapp from an empty directory with
  `PYTHONPATH` stripped: verify works, `spec_id` matches, `anchor` returns
  ANCHORED on a publisher bundle and exit 1 on a bundle with one byte changed.
- **`docs/ZERO-INSTALL.md`** also records what this does not solve: we build the
  zipapp, it carries no anchor, and it is not signed. It is a different point on
  the convenience axis than a hosted endpoint, not a better one everywhere.


### Anchoring the publisher (2026-11-19)

- **`tools/make_release_bundle.py`**: a publisher bundle = the sealed package plus
  `anchor.json` (public key, key_id, checkpoint head). The head goes into the
  manifest *before* signing - a signed manifest edited afterwards is exactly the
  forgery that row A catches and row B repairs.
- **`tools/anchor_check.py`**: the one command a stranger runs.
  `VERDICT: ANCHORED` only when the signature matches the anchor's key *and* the
  state matches the anchor's head; `NOT ANCHORED` when verification fell back to
  a key the package supplied; refuses to run without an anchor file, because an
  anchor read out of the bundle is the bundle vouching for itself.
- **Measured contrast, now a test:** a repaired, re-signed forgery (row C of
  `docs/FORGERY-ENVELOPE.md`) still verifies `PASS, unanchored` on its own, and
  fails S6 the moment the publisher's anchor is applied. The anchor is the
  only thing that changes the answer, which is why it has to travel separately.
- **`docs/PUBLISHER-IDENTITY.md`**: the five-step release procedure, why the
  key and the head must leave through a channel the package cannot reach, and
  the three things this does not do. Status stated plainly: no release in this
  repository has published an anchor, so every verdict here today is at best
  `PASS, unanchored`.
- **`tests/test_anchor_check.py`** freezes: own bundle anchored; wrong head
  refused (S9); wrong pinned key refused (S6); forgery refused against a real
  anchor while still clean without one; anchor without a key refused.


### A forgery that agrees with itself (2026-11-19)

- **`tools/composed_forgery.py`**: every previous audit measures a *change this
  project can see*. This one performs the attack: rewrite one evidence file, then
  repair the content hash, the evidence root, the index digest and the checkpoint
  head - all of them arithmetic on bytes the attacker owns.
- **Six attacks, measured.** Undeclared rewrite -> FAIL (S4). Repaired rewrite ->
  INCONCLUSIVE (the owner's seal cannot be checked). Repaired and re-signed with
  a key of the attacker's own -> **PASS, `unanchored`**. Same with the publisher's
  key pinned -> FAIL (S6). Same with a published head pinned -> FAIL (S9).
  Seal deleted -> INCONCLUSIVE, never better.
- **The point is row three**, and it is written into the tests rather than the
  pitch: a stranger with no publisher key produces a clean verdict, and the
  verdict says `unanchored` because that is exactly what it can support. PASS
  there means *this key signed these bytes*, not *the publisher wrote them*.
- **`docs/FORGERY-ENVELOPE.md`** prints the six rows, names why each one stops
  where it does, and lists the three things that actually close the gap:
  publish the key (`--pubkey`), publish the head (`--expect-head`), anchor the
  head to an external timestamp or receipt.
- **`tests/test_composed_forgery.py`** freezes all six outcomes, row three
  included, so the boundary cannot drift into a stronger claim later.


### Two defects at once (2026-11-19)

- **`tools/check_combinations.py`**: every other audit here asks about one
  change. This asks about two, which is the question a composed forgery poses -
  a second defect that supplies exactly the consistency the first one broke.
  Fourteen independent mutations, each caught alone; then all 91 pairs and all
  364 triples.
- **Measured: 91 of 91 pairs and 364 of 364 triples fail somewhere.** Zero
  combinations are silent, and zero show the cancelled pattern (both halves
  caught alone, the combination caught nowhere). Under a second, so it is a CI
  step and a test, not a ceremony.
- **The probe corrected itself once:** the undeclared file first went into
  `evidence/files/`, where the format deliberately keeps structural members and
  resolves each by its own check, so nothing moved. The same mutation at the
  package root - where a note that contradicts the evidence has no owner - made
  S1 fail at once. Same defect, two positions, two correct verdicts.
- **`docs/COMBINATIONS.md`** carries the matrix and states the limit plainly:
  three at a time is not "any number", and the family is single-field defects,
  not a chained forgery.


### Two identifier fields that identified nothing (2026-11-19)

- **`evidence_id` was read by no check** for presence or uniqueness. Two entries
  could share an id, or one could carry none, and S4 still called the evidence
  intact - the index is read by position everywhere, so identity was never
  needed. `S4` now requires a non-empty, unique `evidence_id` per entry, in
  Python and JavaScript (F-009).
- **A gap stated is not a gap closed.** `docs/FIELD-COVERAGE.md` had said
  "duplicates are not checked - stated rather than implied". That was honest
  about the hole and still left it open; this closes it, and the document says
  which mutations the new check does and does not catch.
- **The lesson worth keeping:** a field silent to a *changed* value is not
  silent to a *repeated* or *absent* one. For identifiers, the interesting
  mutation breaks identity rather than alters it - which is exactly what a
  value-swapping probe cannot see.
- **One rule attempted and withdrawn in the same PR:** `identity.status` was
  compared against the state the lifecycle reaches, and the clean fixture failed
  - `REGISTERED` against a chain that ends `ACTIVATED` - because the two fields
  describe different things. Withdrawn rather than re-tuned until green; the gap
  stays listed in `docs/FIELD-COVERAGE.md` as a known gap.


### Every field, and who notices when you change it (2026-11-19)

- **`tools/check_field_coverage.py`** asks the F-007 question by measurement:
  for each of the 59 leaf fields a package writes, replace the value with a
  different one of the same shape, run verify, and record every check whose
  result moved - in either direction, not only to FAIL. 36 alterations move
  something; 23 move nothing.
- **The 23 are not a list of holes, they are a list of reasons**, and every one
  is written down: descriptive fields (schema tag, version, media type, note),
  unreferenced values (the chain's last event id, evidence ids, whose uniqueness
  is not checked - stated rather than implied), undecidable ones (per-event
  signatures the format defines no payload for; an HMAC seal whose secret the
  verifier does not hold, where INCONCLUSIVE is the correct answer), and two
  enums nothing validates yet.
- **One real hole, fixed:** `payload_hash` was written by every lifecycle event
  and read by nothing - replace the `null` with any string and every check said
  what it said before (F-008). `S12` now requires 64 lowercase hex when the field
  is declared, in both implementations. This checks the shape of the claim, not
  its correspondence to a payload the package does not ship.
- **Frozen gate:** `tests/test_field_coverage.py` fails if a field becomes
  silent without a reason on record, and also fails if a listed one stops being
  silent (both directions, so the document cannot quietly rot).
- **`docs/FIELD-COVERAGE.md`** carries the full 59-row matrix.


### A field that existed and nobody read (2026-11-19)

- **Second shapes for the five single-sample checks.** Writing them found a
  defect instead of a confirmation. Changing `lifecycle.events[0].agent_id`
  to another agent produced verdict `INCONCLUSIVE` with **S2 PASS and S3 PASS**:
  the identity check compared `identity.json` with `manifest.json` and never
  read the `agent_id` the events themselves carry, so a package could attribute
  its whole lifecycle to somebody else's agent and still be called consistent.
- **S2 now reads it**, in Python and in the JavaScript implementation, and
  reports the event id and both agent ids. The forged package fails S2 and only
  S2 (S3 stays PASS, so the report is not merely "something is wrong").
- **`failure_corpus/F-007.json`** records the finding; regression test
  `tests/test_identity_in_lifecycle.py` asserts both directions.
- **Matrix after the fix:** S1, S2, S3, S11 each have two independent shapes;
  S7 keeps one, because it only runs when the package declares an index
  metadata digest and the fixture does not — a package that makes no claim
  cannot be caught lying about it.
- **529 tests green** (2 skipped), `check_doc_facts` 0 mismatches, second
  implementation agrees on 36/36 cases with 30 named.


### Every check, and something that breaks it (2026-11-19)

- **`tools/check_falsifiability.py`** asks what a verifier project rarely asks
  itself: for each of the nineteen checks, is there a published artefact that
  makes it say FAIL? It collects the answer from the thirty-six exported
  conformance cases (seventeen checks) and from `tools/outsider_audit.py`
  (S16: a real FreeTSA token and four mutations; S9: a pinned head and a
  rollback only the pin can see).
- **Measured: 19 of 19, zero holes.** The tool exits non-zero if that stops
  being true, and CI runs it in the second-implementation job, after the suite
  is exported.
- **`docs/FALSIFIABILITY.md`** records the matrix and the uneven column: five
  checks (S1, S2, S3, S7, S11) rest on a single artefact, which proves they
  are not decoration but not that they catch every shape of forgery.

### Three optimisations on 20,000 files, all reverted (2026-11-19)

- **Profiled the 1.1 s** it takes to verify 20,000 entries: S12 semantics 0.354 s,
  S11 byte scan 0.278 s (0.117 of it the depth walk), JCS canonicalisation 0.154 s,
  SHA-256 of the evidence 0.152 s. Hashing all 20,003 files on its own is 0.170 s
  (8.5 us a file), so I/O is not the bottleneck and never was.
- **Caching `realpath` per directory:** 1.104 s -> 1.093 s, 1%. The OS already
  caches those lookups; the profile was showing time the workload does not pay twice.
- **Stripping string literals with a regex before the depth scan:** 1.146 s. Two
  passes over ten megabytes cost more than the loop they replace.
- **Skipping `fromisoformat` for clearly-past timestamps:** rejected before
  writing it - it only fires on old evidence, and honest benchmarks are near now.
- **All three reverted.** `verify.py` is unchanged; the containment test stays
  one step. `docs/PERF-LOG.md` records the attempts and the floor: 54 us per
  entry, nineteen checks, 60 MiB at 20,000.

### The sixteen tests that were skipping (2026-11-19)

- **Audited `OK (skipped=16)`.** Fifteen of the sixteen were skipping for one
  reason: `.[verify]` does not carry `opentimestamps-client`, `langchain-core`,
  `coincurve`, `pynostr` or `agent-action-capsule`. CI installs the same extra,
  so the interop check against the peer, the live-LangChain measurement, the OTS
  proof check and both Nostr anchors had **never run in CI**. They were in the
  suite, counted in the total, and executed nowhere.
- **They all pass once installed** (`527 OK (skipped=2)`, 42.4 s). Nothing in
  the tests needed fixing, which is the finding: the code was right and the
  gate was hollow.
- **New extra `interop`**, and a new CI job `test-with-extras` that runs the
  full suite with it and then fails on any skip whose reason contains
  "not installed". Green can no longer mean "the hard half was skipped".
- **`docs/SKIPPED.md`** records the list, the categories, and the two skips that
  remain (both deliberate).
- **The new gate caught a second category on its first run:** five
  `test_aee_rail.py` tests were skipping on "agent_evidence_vectors corpus not
  installed" — the rail that reads somebody else's conformance corpus had never
  run in CI either. `conformance` existed as an extra; no job installed it.
  `test-with-extras` now installs `.[verify,interop,conformance]`.

### The neighbourhood, surveyed rather than admired (2026-11-19)

- **`docs/PEER-SURVEY.md` + `docs/PEERS.json`**: six neighbouring projects measured
  from one PyPI JSON and one GitHub REST request each, with no figure quoted from
  a README. Three are the same problem answered differently; three are adjacent
  infrastructure and are used as a maturity bar, not as opponents.
- **The honest split:** last of the seven on distribution (4 releases against
  23-78, 11 stars against 2-1,056) and first, by a wide margin, on
  re-checkability (second implementation, CI agreement assertion at 36/36,
  one-command stranger audit, hostile-input suite, public conformance corpus,
  cost measured to 20,000 evidence files). The second implementation is the
  strongest asset and, by the peer's own RFC 7942 rule, not independence.
- The page states what this changes: the next gain is not another check, it is
  the first row in the adoption table.

### Scale, and a semantic disagreement between the two implementations (2026-11-19)

- **`docs/SCALE.md` + `docs/SCALE.json` + `docs/SCALE.svg`**: verification cost
  measured at 100 / 1,000 / 5,000 / 20,000 evidence files. Python: 0.007 / 0.055 /
  0.282 / 1.104 s, 23.6 / 25.1 / 31.2 / 60.3 MiB peak. Linear at about 55 us and
  1.9 KiB per file.
- **Found by the scale run:** the JavaScript verifier reported **FAIL** for an
  unsigned package where Python reported **INCONCLUSIVE**, both on the same bytes.  The
  absence of a signature is a missing attestation, not a violation; three-valued
  adjudication is this project's claim, and the second implementation was
  contradicting it in the one place the 36/36 conformance agreement never looked,
  because every conformance case carries some seal.
- **Fixed** in `tools/verify-js/verify.mjs`, with a regression test pinning both
  implementations to one answer: `test_an_unsigned_package_is_inconclusive_in_both_languages`.
- Also recorded: S12 refused a first synthetic build whose `created_at` was eight
  hours in the future (`26306 s in the future`) - an unplanned demonstration that
  the check fires.
- `docs/COMPETITORS.md` keeps the missing item: no same-size comparison against the
  peer has been run, because the package formats differ and that would compare
  two different kinds of work.

### 0.4.0 dry run: the package now checks itself (2026-11-19)

- **The sdist could not run its own tests.** First build collected 290 of 526
  tests and produced 6 failures + 97 errors, all of them missing fixtures and
  tools. Fixed in three measured passes (290 -> 475 -> 482 -> 526) by grafting
  every top-level directory instead of guessing which ones tests read.
- **`MANIFEST.in`** now carries everything the suite reads, with the
  measurements and the reasoning written into the file.
- **Wheel verified:** `pip install` of the built 0.4.0 wheel reports 0.4.0 and
  the same eight checks as `main` on the clean package, including S11 and S12
  that 0.3.3 lacked.
- **CI guard:** a new `sdist-self-check` job builds an sdist and runs the suite
  from the unpacked archive, so a directory missing from `MANIFEST.in` fails on
  the pull request rather than in a stranger's hands.
- **`docs/RELEASE-DRY-RUN.md`** records the whole run with commands and timings.

### A stranger's ten minutes, measured (2026-11-19)

- **`docs/STRANGER-TRIAL.md`** records a first run in a directory that had never
  seen this project: clone in 2.3 s, `tools/outsider_audit.py` in 0.3 s, `VERDICT:
  OK` — two commands, no credentials, no dependencies.
- **The same trial found the sentence that stops adoption.** `pip install
  uibc-core` gives 0.3.3, which reports **six** checks on the clean package;
  `main` is 0.4.0 and reports **eight**. The code is better than the package,
  and the package is what a stranger gets.
- **README now states the three version numbers** (`0.4.0` unreleased / `0.3.3`
  on PyPI / `0.2.1` archived) and which one an installer actually receives, with
  a link to the measurement. The previous line called 0.3.3 "the current
  implementation", which stopped being true when 0.4.0 work began.

### Adoption, measured the peer's own way (2026-11-18)

- **`docs/COMPETITORS.md` gains an adoption table**, each merged claim checked
  against GitHub rather than taken from the peer's page: a contribution merged
  into the IETF SCITT working group's shared repository, a third-party product
  shipping their verifier, an independent draft building on theirs, a public log
  with 15134 entries. Ours: zero rows.
- **`docs/IMPLEMENTATION-STATUS.md`** records that in the RFC 7942 four-bucket
  format they use. All four buckets are empty, and the page says so in their
  words rather than in ours.
- **`docs/UPSTREAM-SUBMISSION-PLAN.md`** lists what each external route would
  cost and in what order they have to happen. Nothing in it has been sent.
- The distinction this round makes explicit: a second implementation written
  here is *internal* evidence, however independent it is in code. Only someone
  else running it is external evidence.

### The comparison now re-checks itself (2026-11-18)

- **`tools/check_competitors.py`** re-fetches what a stranger can fetch (PyPI
  JSON, GitHub repo record) for both projects, diffs it against
  `docs/COMPETITORS.json`, and exits non-zero when the world has moved. An
  endpoint that fails to answer is recorded as unmeasured, not estimated.
- **`docs/COMPETITORS.svg`**, built by `tools/build_competitors_svg.py` from the
  recorded baseline, so the picture cannot go stale on its own. Four of its six
  rows point their way; the two that point ours are the two a test count cannot
  buy.
- **`tests/test_competitors.py`** holds the offline half: the baseline is
  complete, and the picture states the same numbers. The network half is
  deliberately not in CI - a flaky gate teaches people to ignore gates.

### A depth ceiling, and a measured peer (2026-11-18)

- **Nesting ceiling, both implementations.** 4000 levels of `[` used to end in a
  stack exhaustion reported as S0 - "the verifier broke", a statement about us
  and not about the input. `MAX_NESTING = 512`, counted outside string literals,
  refuses it as S11. Taken from `agent-action-capsule`, which refuses at 128 with
  a message naming the limit.
- **A manifest that parses as an array** used to reach `.get()` on the Python
  side and raise `AttributeError`, again landing on S0. S1 now reports it.
- **Both sides stop when the bytes never became JSON**: invalid UTF-8, a repeated
  member name, a document past the ceiling, unparseable bytes. Nothing downstream
  is claimed about bytes nobody read.
- **`docs/COMPETITORS.md`** measures `agent-action-capsule` 0.17.0 and this
  project on the same day, with the command for each number, and states plainly
  where this project is behind (specification standing, release cadence, surface
  area, test count) as well as ahead (a second implementation, gated in CI).

### Hostile input: ten cases, ten verdicts, no crashes (2026-11-18)

- **`tools/redteam_robustness.py`** builds ten packages that are not packages:
  not JSON, an array where an object belongs, duplicate member names, a bare
  `NaN`, 4000 levels of nesting, invalid UTF-8, a path that climbs out of the
  package, a symlink to the host, an empty directory, an 8 MB manifest. All
  ten are answered by both implementations and refused by both.
- **A real hole, closed:** Python's `json` module accepts `NaN` by default.
  A manifest carrying `"remark":NaN` used to parse, pass every element check,
  and come out **INCONCLUSIVE** - an honest-looking answer about bytes that
  are not JSON. S11 now refuses it, on both sides: Python via
  `parse_constant`, JavaScript via `JSON.parse` inside S11.
- **S11 moved first in the JavaScript verifier, with an early return.** Bytes
  that are not JSON cannot be judged by any later check; falling through
  reported S0 ("the verifier broke") and hid the check that had the answer.
- `docs/ROBUSTNESS.md` records the table and explains why the two verdict lists
  differ on early failures without being inconsistent.

### The two implementations now agree on every package (2026-11-18)

- **S3 in JavaScript**, both families of rules: the L1-L7 state machine and the
  L8-L12 semantic layer. Coverage 18 of 19; the only check absent is S0, which
  exists only when the verifier itself throws.
- **`agree_with_python: 36 of 36`.** The cross-implementation check no longer
  asks only "does it name an expected check" - the same set of failing checks
  now comes out on every package. It was five apart.
- **A hole found in the Python verifier by the JavaScript one.**
  `manifest.evidence_count` was never compared with the number of index entries,
  so a package declaring two entries and shipping one passed. Fixed.
- **One root cause scored twice.** The JavaScript verifier derived the evidence
  root from hashes S4 had just shown to be wrong, reporting S5 as a second
  failure. S5 is now INCONCLUSIVE when S4 fails, matching Python: it is the
  same finding, not a second one.
- A test that had been naming a case directory that no longer exists
  (`09-edit-the-evidence-root`; the case is `10-...`) was corrected - it had
  been passing against a stale unpacked fixture rather than the shipped suite.

### The second implementation verifies a stranger's timestamp (2026-11-18)

- **S16 in JavaScript, with no dependency and no shared code.** `tools/verify-js/rfc3161.mjs`
  reads an RFC 3161 token with a minimal DER reader built from `node:crypto` alone, checks
  the CMS signature over `signedAttrs` (encoded as `SET OF`, not `SEQUENCE` — the tag that
  catches naive implementations), locates the ESS `signingCertificate` certHash by walking
  the subtree, and proves the signing certificate was issued by a supplied CA and was valid
  at its stamping time. A real Free TSA token for the head in `tests/fixtures/anchor/`
  verifies: `stamped 20261117081135Z, TSA O=Free TSA`.
- **This is the one witness the project cannot mint.** Every other check is witnessed by
  parties we choose: our tree, our head, our pin. A token is dated by somebody else's key,
  and now two implementations built from the spec — with no shared code — reach the same
  verdict on it, in both the accept and the refuse direction.
- **Red team, seven of seven:** the token as received is accepted; a flipped signature bit,
  a wrong anchored digest, a CA that did not issue it, no CA at all, one mutated digit inside
  a signed attribute, and a truncated token are each refused with a distinct reason.
- **S9 in JavaScript.** `--expect-head <head>` supplies the observation made outside the
  package and compares it with the checkpoint state. The pin is never read from the package;
  without it S9 does not appear, because an unchecked rollback must not look like a pass.
- `node tools/verify-js/rfc3161.mjs <token.tsr> <digest-hex> <ca.pem>` is a standalone entry
  point: anyone with Node can reproduce the token verdict without installing anything.
- **Coverage: seventeen of nineteen checks** in the second implementation; `--strict` and
  lenient modes now agree with the Python verifier's defaults.

### Added

- **CI now fails when the second implementation drifts.** `tools/assert_second_impl.py`
  asserts that every package the suite accepts is accepted, every package it
  refuses fails for a reason one of its expected checks names, and no package
  expects a check the JavaScript side does not carry. Verified by breaking it
  on purpose: with S15 forced to pass it names the four anchor packages and
  exits 1; with S15 removed from the covered set it does the same. The new
  `second-implementation` job runs it on every push and pull request. Set
  equality is not required, because the two implementations legitimately
  differ on five packages and forcing equality would make one of them lie.
- **The gate was tested against itself, in the pipeline.** Pull request #134
  removed `S15` from `COVERED` while four packages still expected it: the
  `second-implementation` job failed, `mergeable_state` stayed `blocked` for
  thirty consecutive samples, and the pull request was closed unmerged. The
  required checks on `main` are now `test (3.13)` and `second-implementation`,
  with `strict` and `enforce_admins` on. Recorded in `docs/NEGATIVE-CONTROL.md`.

### Added

- **The JavaScript verifier covers ten of nineteen checks, up from eight.**
  S14 strict base64: pad bits set, missing padding and stray characters all
  decode permissively, so two decoders can disagree about what was signed.
  Only fields the package itself marks as base64 are examined, so a schema
  that does not use base64 cannot be false-flagged. S10 the closure
  declaration: six components must be present and shaped like digests --
  declaration only, because whether those digests match what actually ran is
  not decidable from a package.
- Both checks are silent on a package that declares neither, exactly as the
  Python verifier is: the correct package's report still shows eight checks,
  not ten.

### Measured

- Python: `strict 36/36   refused 30/36`
- JavaScript: `strict 36/36   refused 30/36`
- Identical FAIL set to Python: 31 of 36; named an expected check: 30 (+6 positives)
- Out of scope: 0 packages -- the JavaScript verifier now agrees on all 36

### Added (S17, S18)

- **The second implementation now agrees with the first on all 36 packages.**
  S17 recomputes `previousReceiptHash` over the JCS of the predecessor's signed
  envelope and insists the first receipt of a chain carries 64 zeros. S18
  resolves every `policy_digest` to the artefact shipped next to it, and rejects
  one a receipt declares that resolves nowhere. A tree answers "was this byte
  changed"; only the linear link answers "is this record the successor of that
  record".
- Fifteen of nineteen checks now have two independent implementations. The
  four without one are S0 and S3 (not modelled as separate checks on this side),
  and S9/S16, which need an observation or a key this checker does not hold.
- Measured honestly: the FAIL *sets* still differ on 5 of 30 vectors -- the
  JavaScript side reports a superset (an edited byte also moves the root,
  S4 and S5). Same verdict, finer diagnosis. `named an expected check` is 30
  of 30.

### Added (S15)

- **The JavaScript verifier resolves anchors.** Four vectors, one code path:
  a corrupt inclusion proof, a leaf hash that is not a digest, 30 February,
  and a root this package cannot recompute. The lesson from the Python side
  carries over: the claimed leaf must be the leaf that actually sits at that
  index, or the proof is being checked against a subject the set does not
  contain at that position. Resolving against our own root proves the anchor
  was built from this package; it does not prove a third party saw it, and an
  anchor naming an external log stays unresolved rather than counted.
- Thirteen of nineteen checks now have two independent implementations. The
  four packages still out of scope are S9 (out-of-band pin) and S16/S17/S18.

### Added (S8)

- **The JavaScript verifier recomputes the package checkpoint.** One value
  committing to the whole state: lifecycle head, evidence root, index metadata
  digest, evidence count. A lifecycle-only head was not enough -- adding
  evidence changes the root but leaves the log untouched, so two different
  states shared one head. Truncation, rollback and post-seal replacement inside
  one package are what this detects. A whole-store rollback still needs an
  observation made elsewhere, which is S9 and stays out of scope.
- Both S8 vectors now fail on S8: a rewritten index with content untouched
  (also S7), and a truncated lifecycle log. Packages without a checkpoint_head
  are not examined, exactly as the Python verifier behaves. Twelve of nineteen.

### Added (S13)

- **The JavaScript verifier recomputes Merkle inclusion proofs (RFC 6962).**
  Leaf = SHA-256(0x00 || data), node = SHA-256(0x01 || l || r), an unbalanced
  tail is promoted rather than duplicated -- duplicating it would let two
  different trees share a root. It checks the declared algorithm, the declared
  size against the leaves it computed, the root, each proof's index against the
  order it recomputed, hex shape, and the path itself. All four S13 vectors
  (replaced root, inflated size, corrupted proof, swapped index) now fail on
  S13 rather than on something incidental. A package with no tree is still not
  penalised: eleven of nineteen covered.

---

## [0.4.1] - 2026-11-18 (the second implementation grows)

### Added

- **The second implementation verifies Ed25519 seals, not just structure.**
  `tools/verify-js/verify.mjs` now checks S6 for asymmetric seals: it re-derives
  the canonical payload (identity + manifest, plus lifecycle when the seal says
  so), builds an Ed25519 public key from the one recorded in the package, and
  verifies the signature with Node's own crypto. Coverage goes from seven checks
  to eight of nineteen. An HMAC seal is reported as INCONCLUSIVE, because it
  cannot be checked without the owner's key -- the verifier says so rather than
  guessing.
- **The suite now contains an asymmetric seal.** Two cases: "a package sealed with
  Ed25519" (must be accepted) and "flip one bit in an Ed25519 signature" (must
  fail S6). Until now every case carried an HMAC seal, so the property the
  project keeps claiming -- *a stranger verifies provenance with no secret* --
  had no vector. The seed is fixed, so the case is reproducible byte for byte.

### Measured

- Python: `strict 36/36   refused 30/36`
- JavaScript: `strict 19/36   refused 30/36`
- Identical FAIL set to Python: 13 of 36; named an expected check: 13 (+6 positives)
- `tests/test_conformance.py` no longer hard-codes "5 positives": the counts are
  read from the manifest, so the next case does not break the tests that guard
  the suite.

## [0.4.0] - 2026-11-18

This is the release that makes the eighteen checks reachable. Everything below
that concerns S7-S18 exists in the tree and in no earlier artifact: the
published `0.3.3` verifier reports six checks on the same package that the tree
reports seventeen on (docs/RELEASE-PARITY.md records the measurement).

### Added

- **Twelve checks beyond `0.3.3`:** S7 index metadata, S8 whole-state
  checkpoint, S9 out-of-band pin, S10 attestation closure, S13 merkle proofs,
  S14 strict base64, S15 anchor resolution, S16 RFC 3161, S17 receipt chain,
  S18 policy artefacts, plus the S0 crash fallback and the S11/S12 strictness
  checks in their current form. `python3 tools/check_release_parity.py` prints
  the three-channel comparison.
- **`tools/outsider_audit.py`** -- five red-team stages over one command, with an
  auditor self-test (path gate + behaviour gate) and `--json` output.
- **`tools/build_evidence_index.py`** -- every check mapped to its tests, its
  red-team cover and its docs, measured by running the audit rather than grepping
  the source (`docs/EVIDENCE-INDEX.md`).
- **`tools/build_checks_reference.py`** -- the eighteen checks with the question
  each answers and an explicit three-way classification of their external basis
  (`docs/CHECKS-REFERENCE.md`).
- **`tools/build_outside_kit.py`** -- a whitelisted 43-file audit kit, runnable
  by someone who will not clone the repository.
- **`tools/serve_verify.py`** -- a verify endpoint that accepts bytes and
  refuses hostile archives.
- **`tools/emit_aac_capsule.py`** -- export to the Agent Action Capsule format,
  recomputing the capsule id under JCS and asking their verifier.
- **`tools/check_citation_scope.py`, `tools/preflight_release.py`** -- the two
  gates that stop a claim from outrunning the artifact.

### Changed

- **`pyproject.toml`:** version 0.4.0; the description no longer carries a
  version number, which had drifted from the field beside it.

### Notes on compatibility

Per this project's own rule, any change to what produces which verdict is a
breaking change. Twelve new checks necessarily change verdicts for packages
carrying the fields they inspect, so 0.4.0 is a major-looking bump under a
0.3.x series rather than a patch.

## [Unreleased]

### Added

- **An independent JavaScript verifier** (`tools/verify-js/verify.mjs`): Node standard library only, no import of `uibc-core`, no npm package. It decides seven of the nineteen checks -- S1, S2, S4, S5, S7 (shape *and* the metadata digest), S11, S12 -- and refuses to pretend about the rest, so it never returns PASS. Measured against the same 34 packages: `strict 16/34 refused 29/34`, with an **identical FAIL set to Python on 10 packages** and the same expected check named on 11. Two implementations built from the spec, sharing no code, agreeing on what is broken and why.
- **`tools/cross_impl_check.py`** prints that comparison case by case, so the boundary is a number rather than a claim.
- **Two defects found by the exercise itself.** (a) The "one more declared evidence file" conformance package wrote its declaration under `files` instead of `entries`, so the file was undeclared while the name claimed otherwise; the case now grows the package through the shipped CLI. (b) The JS metadata-digest comparison caught an exception on an absent member and let a tampered note pass -- an `undefined` that Python writes as `null`. Both were caught only because a second implementation ran the same corpus.
- `tests/test_verify_js.py` (4 tests, skipped when Node is absent): a sound package must be INCONCLUSIVE, a flipped byte must fail S4, an edited root must fail S5, and every extra finding must come from a check the implementation claims to run.

### Added

- **The docs/ pages that describe the present now have to stay true.** `tools/check_doc_facts.py` scanned six top-level files; `docs/CONFORMANCE.md` said 305 tests, `docs/COMPOSITION-VERIFIER.md` said 180, `docs/ECOSYSTEM-MAP.md` and `docs/INTEROP-MATRIX.md` said 0.3.0 with 305 tests, all of them about the current project and all of them wrong. A page joins the check by saying so on its first lines, `<!-- facts: current -->`; the five present-tense pages that do are now scanned along with the six. Pages recording a past run (`REVIEW-LOG.md`, `RUN-RECORD-second-machine-20261118.md`) carry no marker and are left alone, because rewriting a run record's numbers would falsify history rather than correct it.
- **One checker bug fixed on the way.** `"15 red-team cases"` was matched by the `cases` rule against the *conformance package* count, so a correct sentence looked stale. Red-team cases now have their own key, and the generic `cases` rule is gone rather than guessed at.
- `tests/test_doc_facts.py` gained two assertions: a marked page that carries a wrong number must be caught, and an unmarked one must not be scanned.

### Added

- **Five positive vectors in the conformance suite**, so it measures correctness instead of pessimism. Twenty-nine packages had to be refused and nothing had to be accepted, which meant a verifier that refused everything scored 29/29 -- full marks for being useless. Now **29 refused + 5 accepted**: the shipped package untouched, the tree-and-chain / extended-evidence / checkpoint shapes appended correctly, and one case where an extra evidence file is added *and declared in the index* so S1 must not fail. Expected verdicts come from this repo's measured run.
- **The positive cases found a real gap at once.** Archived v0.2.1 refuses all 34, the five correct ones included: it cannot read the newer shapes, so its blanket refusal was hiding a forward-compatibility hole. A property of that older release, made visible by the suite.
- `tests/test_conformance.py` asserts that a verifier refusing everything fails every positive case. Measured: always-PASS 5/34, always-FAIL naming S1 1/34, current 34/34 (refused 29/34). Test count 513 -> 514; `docs/REPRODUCE.md` regenerated so its conformance row reads `strict 34/34 refused 29/34`.

### Added

- **`docs/REPRODUCE.md` and `tools/build_reproduce.py`** -- ten rows: the figure in the paper, the command a reader types, and the output recorded when the generator ran it. Every row has its own reader (JSON field, tail line, or regex) because six of the tools print progress before their figure, and taking the first line reported `{` for three of them. Latency here reads 1.367 ms against the paper's 1.225 ms, and the sheet says so rather than smoothing it: a figure from another host is another measurement.
- **`tests/test_reproduce.py`** -- 5 tests, including one that runs a real claim end to end and one that refuses placeholder output anywhere in the sheet.
- The published test count moved 508 -> 513 across README, README.en, AGENTS and the paper, as `check_doc_facts` requires.

### Fixed

- **The paper's own numbers were wrong in three places.** `paper/paper.md` claimed 122 tests (507 run), "three modules" within 24 files (25), and "zero-dependency (stdlib only)" when `[verify]` pulls in `cryptography` and `asn1crypto`. Rewritten to state the stdlib-only core, the optional extra, the INCONCLUSIVE-on-absence behaviour, 507 tests, and 25 modules. The skipped count is described rather than pinned, because it moves between 16 and 17.
- **`tools/check_doc_facts.py` now covers the paper and module counts.** `paper/paper.md` is a target, and `modules` is a measured fact, so a stale count there fails CI too.

### Fixed

- **The README's test count was 328; the suite runs 507.** Corrected in `README.md`, `README.en.md`, `AGENTS.md`, together with the skipped count (6 -> 16) and the recorded runtime.

### Added

- **`tools/check_doc_facts.py`** -- measures tests, checks, audit attacks, red-team cases and conformance vectors, then reads the documents a reader treats as current and reports every number that disagrees. Dated records under `docs/` are excluded on purpose: they are findings from a moment, and rewriting them would falsify a record rather than correct a claim. `--json` and `--files` supported.
- **`tests/test_doc_facts.py`** -- 4 tests: every fact is measurable, no published number is stale, a planted wrong number must be caught, and the two attack counts (36 audit / 15 red-team) must stay distinguishable. Adding a test without updating the README now turns CI red.

### Added

- **Rate limiting on the verify endpoint.** A token bucket per caller, `--rate`/`--burst`, `429` with `Retry-After`, and the limit advertised on `/health`. `X-Forwarded-For` is ignored unless `--trust-forwarded` is passed, because a bucket keyed on a caller-controlled header is not a bucket. Measured at burst 10: 11 of 320 calls under 16 concurrent clients succeeded, 309 refused.
- **`tools/stress_verify.py`** -- concurrency measurement, unlimited and limited in one run.
- **`deploy/`** -- a Dockerfile and instructions so a stranger can run their own endpoint; the image is untested here (no Docker on this machine) and the README says so.
- **`tests/test_rate_limit.py`** -- 8 tests, including the spoofed-header test.

### Added

- **Conformance suite.** 29 packages, each correct and then broken in exactly one way, with the checks a verifier must report. `tools/run_conformance.py --verify "<cmd>"` runs them against any implementation. Expectations come from the audit's measured run, so the suite cannot drift from the report. Measured: current implementation 29/29; archived v0.2.1 (6 checks) 0/29 while still refusing all 29; a verifier that refuses nothing scores 0. See `conformance/README.md`.
- **`tests/test_conformance.py`** -- 6 tests, including the archive-vs-manifest digest check and the rubber-stamp check.

### Added

- **`--strict` mode for S1.** `verify(pkg, strict=True)` and `uibc verify <pkg> --strict` fail any file under `evidence/` that the index never declared, while exempting the five structural members the format places there (`merkle.json`, `chain.json`, `anchors.json`, `policies.json`, `policies/*`). The default stays lenient, because a tightening that invalidates every existing package is a version change, not a fix. See `docs/STRICT-MODE.md`.
- **`tests/test_strict_mode.py`** -- 5 tests covering lenient, strict, exempt, clean, and the real CLI exit code.

- **`tools/build_thesis_tables.py` -> `docs/THESIS-CH5-TABLES.md`.** The six tables a chapter-5 could cite (checks and their basis, basis distribution, attack incidence summary, the two-implementation comparison, the three-channel coverage, the hot-path latency), each generated from the tools' JSON with a "how to regenerate" line beneath it, and an explicit section listing what the chapter must not claim.
- **`tests/test_thesis_tables.py`** -- 6 tests tying each table to the tool it reads.
### Added

- **`tools/check_matrix.py` -> `docs/CHECK-MATRIX.md` and `docs/CHECK-MATRIX.svg`.** Reads the audit's own JSON and prints which attacks move which checks. Two numbers fall out: 32 of 36 attacks isolate exactly one check, and no check is unreachable. The two attacks that move two checks (an impossible date also trips the lifecycle state machine; rewritten index metadata also moves the checkpoint head) are recorded rather than smoothed over.
- **`tests/test_check_matrix.py`** -- 6 tests holding those two claims.

### Fixed

- **The package reported its own version as 0.3.3 while shipping as 0.4.0.**
  `uibc_core/__init__.py` held a literal that had not moved with
  `pyproject.toml`, so every verification report stamped the wrong version. `tools/version_gate.py` now also reads that literal, making it a fourth
  place the gate compares rather than a fourth place to drift.
- **S15 lost its import during this work** and raised
  `NameError: _mk2 is not defined` on any package carrying an anchor; caught by
  the audit builder's own "a correct package must pass" assertion before it
  reached a commit.
- **S13 raised `IndexError` when an evidence file was deleted.** The declared
  order still listed the missing evidence, so `leaves[i]` ran past the end of
  the list the filesystem actually produced, and the exception was caught by
  the S0 fallback. The verdict was right (FAIL) but the reason was
  `IndexError: list index out of range`, which names neither the check nor the
  file. S13 now reports `proof names evidence 'files/action-log.txt' whose file
  is absent`.

### Added

- **Every check now carries its basis.** `uibc_core/basis.py` holds, for each
  check, whether a draft or RFC states the requirement (`direct`), the
  mechanism is borrowed from one (`related`), or this project defines it with
  nothing to point at (`none`) - and a citation for the first two, an empty
  string for the third. Rendered into every report as
  `checks[].basis = {class, citation, note}`.
- **`uibc explain <pkg>`** -- the same verifier, printed for a person: one line
  per check, then its class and citation, then the failure text. `verify` keeps
  emitting JSON unchanged, because scripts parse that and a citation four
  levels down in a JSON blob is not readable.
- **`tests/test_basis.py`** -- 8 tests: only documented classes carry a
  citation, `none` never does, an unknown id borrows nothing, and the shipped
  report matches the module.

- **`tools/compare_diagnostics.py` → `docs/DIAGNOSTICS.md`.** The same six
  kinds of damage applied to our package and to `agent-action-capsule` 0.17.0,
  printing what each verifier says *after* it says FAIL. On the four attacks
  both formats can express, we reported 13 specific reasons against their 5;
  the other two have no counterpart in their format, and are marked n/a rather
  than scored.
- **`tests/test_diagnostics_compare.py`** -- 5 tests, including one that fails
  on purpose if the documented gap (an uncommitted file under `evidence/` is
  only a note, never a failure) ever changes, so the doc cannot drift from
  reality.

### Not changed, on purpose

An attempt to make S1 fail on any uncommitted file under `evidence/` was
reverted: this format itself keeps the anchor event, the policy artefacts and
the receipt chain there, and the tightening failed a dozen existing packages.
That is a format-version change, not a patch.


### Added

- **Handover worked example (`examples/link3-handover-evidence/`):**
  the Link-3 handbook pack — the receiving-side check of a fictional
  device evidence set, in five runs (approved open PASS / approved
  pinned PASS / report swapped after sealing FAIL / rebuilt and
  re-sealed under a substitute key PASS unpinned / same pack FAIL
  pinned). Rebuilt with the released 0.3.3 so the `pip install`
  path reproduces every verdict; the folder README states the
  coverage=legacy scope of these seals in the verifier's own terms.
  Includes the plain-language verify guide (EN + Chinese) and the
  recorded run transcript.

- **Change-evidence worked example (`examples/link1-change-evidence/`):**
  the Link-1 handbook pack — a fictional device AI model update
  (v1.1 -> v1.2) handed downstream as a sealed four-file evidence set,
  in three states (sealed / evaluation report swapped after sealing /
  submitted unsealed) with verdicts PASS / FAIL (S4 names the swapped
  file) / INCONCLUSIVE and gate decisions ALLOW / DENY / HOLD. Built
  with the released 0.3.3 so the `pip install uibc-core` path
  reproduces every verdict; includes a plain-language verify guide
  (EN + Chinese) and the recorded run transcript.

- **AEE rail (`uibc_core/aee.py`): an external verifier for the
  Adversarial Execution Evidence in-toto predicate v0.7**, so the
  `agent-evidence-vectors` conformance corpus (288 vectors) can run
  against uibc-core: `python3 -m uibc_core.aee <statement.json>` under
  the corpus contract (exit 0 = valid; last stdout line one JSON report
  with verdict / codes / result / tiers; consumer key policy via
  `AEE_SUBSTRATE_KEYS`). GATE 0 well-formedness (strict I-JSON,
  vocabulary and corpus digests, coverage partition), GATE 1
  byte-checkable coverage validity (run-binding derivation v2, kind
  constraints, method cap), the 0.7 statement-level commitments, the
  total result recompute, and GATE 2 evidence tiers against pinned
  substrate keys (strict Ed25519). Stdlib only; the RFC 6962 batch root
  reuses `uibc_core.merkle`. Corpus result at build time: 288/288
  (63 accept / 223 reject / 2 indeterminate), reason parity on all
  rejects. Spot-checks live in `tests/test_aee_rail.py` (skipped when
  the corpus package is not installed).

### Fixed

- **Browser verifier (`verify.html`) brought back to parity with the CLI.**
  The page still implemented the v0.3.0 semantics: its seal payload covered
  identity+manifest only, so every package sealed since v1.1 (seal payload
  identity+manifest+lifecycle) failed S6 in the browser while passing
  `uibc verify`. The page now ports the 0.3.3 verifier check-for-check
  (S1–S18 in the reference report order, including S11 strict serialization,
  S12 semantic strictness, and the conditional S7/S10/S13–S18 surfaces),
  canonicalizes with RFC 8785 JCS like the CLI, accepts the legacy payload
  as `coverage=legacy`, supports a pinned checkpoint head (S9), and embeds
  a sample package built with the current release. A 27-run parity corpus
  ships in `tests/verify_html_parity/`; the page and the CLI agree on every
  check. Declared limit: S16 (RFC 3161 tokens) is INCONCLUSIVE on the page
  by design — the port does not parse DER tokens.

v0.3.0 below is the release cut on 2026-11-12: tag `v0.3.0`, GitHub Release published,
and `uibc-core 0.3.0` uploaded to PyPI on 2026-11-12 (sdist + wheel, same bytes as the CI build —
sha256 listed in `docs/pypi-0.3.0-release.md`). The release-triggered `publish-pypi.yml` run
`43150166821` still fails at the upload step because the trusted-publisher registration is not in
place; that workflow is a convenience path, not the only one.


## [0.3.0] — 2026-11-12


### ⚠️ VERDICT-AFFECTING (breaking in effect)

Per this project's own rule above, this release changes what produces
which verdict, in two connected moves. The full semantics are specified
in `docs/verdict-and-seal-semantics.md`.

**1. Three-valued verdicts.** Through 0.2.x the top-level result was
PASS unless a check FAILed, so an INCONCLUSIVE S6 (seal present but not
checkable in open mode) rode under a PASS. An external review (2026-11)
demonstrated the consequence: a fully self-consistent forgery verified
PASS in open mode. From 0.3.0: any FAIL → FAIL; else any INCONCLUSIVE →
INCONCLUSIVE; else PASS. Exactly three fixture cells changed — clean /
malicious / malicious-keyswap in open mode, PASS → INCONCLUSIVE. No
individual check outcome moved; the forgery is still not *detected*
without a key, it is simply no longer *passed*.

**2. Ed25519 public seals.** The v0.2 notes promised an asymmetric seal
for v0.3, pending a `cryptography` dependency decision. The decision
landed differently: Ed25519 (RFC 8032) is implemented in pure Python on
the standard library, and the project stays zero-dependency. An
Ed25519 seal records its public key in the package, so anyone can
verify provenance without the owner's secret (`uibc keygen --ed25519`,
`uibc submit --key`, `uibc verify --pubkey <pin>`). Reports gain an
`assurance` field: `public-key` / `owner-key` / `unattested`.

Also in this release: an unsigned package in open mode is INCONCLUSIVE
at S6 (was SKIP under PASS); `uibc demo` now runs the v0.3 arc
(stranger-verifies → tamper → forge-and-reseal → pinning catch);
`examples/` ships a committed sample package verifiable by any
stranger; the independent verifier mirrors the new semantics so the
two implementations still cross-check; gate HOLD now also results
from an unattested (unsigned) package in open mode.

Note: `CITATION.cff` / `codemeta.json` still pin the archived 0.2.1
artifact and its version DOI; they will be updated when the 0.3.0
archive is deposited.


### ⚠️ VERDICT-AFFECTING (breaking in effect) — released as 0.2.2

Per this project's own rule above, *a change to what produces which verifier
verdict is a breaking change*. This release contains one, in the **memory
migration verifier**:

| Input | Before | After |
|---|---|---|
| migration `target` contains a duplicate `memory_id` | `PASS` when the real entry happened to be kept by dict collapse — reported as "no injections" | `FAIL` / `MALFORMED_INPUT`; duplicate ids rejected on **both** sides |
| `source` and `target` both empty | `PASS` on all four Preservations | `INCONCLUSIVE` / `VACUOUS_INPUT` |

The patch number is used deliberately. `0.3.0` is already committed in the
public narrative to Ed25519 + a public key registry (the standing answer to the
`malicious-keyswap` boundary), and silently renumbering that promise would be a
more confusing change than an honest patch with this notice. **The substance is
breaking; this notice exists so nobody discovers it from a failing suite.**

> **Release status — which version number lives where.**
> `0.2.1` is **already published** (Zenodo DOI `10.5281/zenodo.22821835`; see
> `dist/`) and therefore must never be redefined. So this fix ships as `0.2.2`,
> and the files that describe the *published artifact* — `CITATION.cff`,
> `.zenodo.json`, `codemeta.json`, `dist/` — deliberately still read `0.2.1`.
> `__init__.py` and `pyproject.toml` carry the *working-tree* version.
>
> Consequence worth stating plainly: **the published `0.2.1` contains the two
> memory-migration gaps fixed here.** A `0.2.2` release should be published
> (the existing concept DOI supports "new version"), so that the version a
> researcher cites is not the one with a silent injection path. Publishing is
> an outbound, irreversible action and is left to the maintainer.

### Added
- `fixtures/generate_memory_fixtures.py` — a 22-case memory-migration mutation
  corpus (M0-M5), with the same hand-derived expectation matrix and non-zero
  exit gate as the package fixtures. It is what found the two defects above.
- `fixtures/_matrix_gate.py` — the comparison/rendering/gate logic shared by
  both fixture generators, so the two cannot drift apart.
- `tests/test_fixture_expectations.py` (16 tests) and
  `tests/test_memory_fixtures.py` (19 tests) — gate tests in both directions
  (green when the prior holds, red when it breaks) plus regression locks.
- `MEM_VERIFIER_VERSION` in `uibc_core/memory.py`, carried in every migration
  report so a rubric score can cite which verify produced it (SS31 field).

### Changed
- `fixtures/EXPECTED.md` and `README.md` no longer claim "S4 + S6 signature
  invalid" for the evidence-content mutations. A seal over
  `identity+manifest` cannot be invalidated by rewriting an evidence file, so
  S6 stays `PASS` in those cases and the detection comes from S4/S5/S3. The old
  wording described a defence that never fired.
- Memory migration reports now always carry a `result_code`
  (`OK` / `MALFORMED_INPUT` / `VACUOUS_INPUT`).

### Fixed
- Memory injection was possible through a duplicate `memory_id` in the target:
  the entry was collapsed away before comparison and the report still said
  "no injections" — a silent pass through M2 Fact Preservation (rubric weight
  0.30, the heaviest dimension).
- A migration of nothing scored `PASS` on all four Preservations.
- An empty field value (`{"content": ""}`) was reported as a *missing* field.

### Added
- `LICENSE` (Apache-2.0). Previously `pyproject.toml` declared Apache-2.0 but no
  licence file existed, and `CITATION.cff` warned against redistribution. This
  was a blocking gap for any standards or academic use; it is now closed.
- `codemeta.json` (CodeMeta 2.0) — required for indexing in the Software
  Heritage archive and for cross-repository software metadata exchange.
- `.zenodo.json` — per-deposit metadata so future Zenodo releases inherit the
  correct title, creators, ORCID, licence and keywords.
- `SECURITY.md` — scope, out-of-scope, supported versions, private reporting
  channel, and an explicit statement of the adversarial-testing posture.
- `CONTRIBUTING.md` — ground rules, the full local gate, what we want and what
  we decline.
- `CODE_OF_CONDUCT.md`.
- `CHANGELOG.md` (this file).
- `NOTICE` — third-party attribution.

### Changed
- `CITATION.cff` licence field now points at the real `LICENSE` file.

### Fixed
- `CITATION.cff`: replaced an unverified Software Heritage identifier with the
  values confirmed against the archive API (origin SWHID + snapshot SWHID), and
  corrected the neighbour-benchmark reference — the previous entry paraphrased
  the arXiv title instead of quoting it.
- `sbom.spdx.json` / `tools/gen-sbom.py`: SPDX 2.3 conformance. Element
  identifiers no longer contain underscores, the invalid
  `hasExtractedLicensingInfos` block was dropped (Apache-2.0 is on the SPDX
  licence list, so extracting it as a `licenseId` was wrong), and
  `licenseListVersion` now tracks the current list (3.29.0).
- `NOTICE`: removed a third-party company name from the redistribution note.
- `adapters/tencentdb-agent-memory/SPEC.md`: neutral wording for the runtime
  environment.
- Zenodo record `10.5281/zenodo.22821835`: metadata corrected from MIT to
  Apache-2.0 so the DOI-fixed artifact matches this repository, and the
  description now carries the canonical UIBC expansion and abstract. The
  deposited file bytes are unchanged; only metadata was corrected.
- All of the above came out of an independent three-way expert review
  (standards/compliance, endorsement channels, privacy and credential red
  lines). The review record is `docs/expert-review-2026-09-18.md`.

### Packaging / distribution (no verdict change)

- The MCP server now ships inside the package as `uibc_core.mcp_server`
  with a `uibc-mcp` console script, so `pip install uibc-core` is enough
  to run it; `mcp_server/server.py` remains as a compatibility shim.
- `verify_package` and `gate_check` MCP tools accept `pubkey_hex` to pin
  the expected Ed25519 signer (a substituted key FAILS S6), matching the
  CLI `--pubkey` behaviour.
- README (中文 / English) updated from v0.2.1 to v0.3.0; PyPI metadata
  description and development-status classifier updated to match.

---

## [0.2.1] — 2026-09-17

First publicly archived release. Triple-anchored: GitHub tag + OpenTimestamps
proof + Zenodo DOI.

- **Zenodo DOI:** version `10.5281/zenodo.22821835`, concept
  `10.5281/zenodo.22821834` (resolves to latest version).
- **OpenTimestamps:** `timestamps/uibc-core-0.2.1.zip.ots`, submitted to two
  independent calendars; upgrades to a Bitcoin block attestation on its own
  schedule.
- **Release artifact:** `dist/uibc-core-0.2.1.zip`,
  SHA-256 `59cc1c917ff766af8f6528ceadfea522b8627a2c591e57334aa4afd2a07959f4`.

### Added
- Read-only HTTP registry server (POST refused with 405; corrupt JSONL surfaces
  honestly rather than being swallowed). 9 tests.
- Static registry query page (`registry/index.html`).
- A2A adapter HTTP server — JSON-RPC 2.0 `card` / `verify` / `gate` / `inspect`,
  path-traversal rejection. 15 tests.
- `examples/showcase.py` + `SHOWCASE.md` — a full-lifecycle recorded run.
- `uibc_core/runtime.py` — one-line integration hooks
  (`record_action` / `seal` / `event` / `snapshot`). 9 tests.
- `README.en.md` — full English documentation.
- Contest package: charter, seven curated problems (P-01…P-07) mapped to
  `uibc-core` capabilities with AIGC provenance labels, weighted rubric
  (M2–M5, evidence-required scoring), submission spec with a verify-first gate,
  and a pilot-run record that includes honest tool limitations.
- Resident-benchmark charter v0.2: three-stage evaluation (machine gate →
  hidden set → top-submission re-run), `experiments/` append-only archive,
  starter kits, and a 10-competitor landscape review.

### Changed
- Test counts re-synced across `README.md`, `/ai/faq`, `llms.txt` and the
  manifest (the earlier `71` figure had drifted; the suite is now **115** unit
  cases plus 7 stress scenarios).
- `__version__` and `SPEC_VERSION` aligned to `0.2.1` so that verifier output
  reports match the released package.
- `uibc demo` step 6 now tampers *actual evidence content* instead of appending
  new evidence — the previous version could pass for the wrong reason.
- FAQ clarified the difference between `S6 SKIP` and `S6 INCONCLUSIVE`.
- `llms.txt` no longer implies Merkle-tree construction; the evidence root is a
  canonical hash over the ordered evidence set.

### Fixed
- External-audit findings: FAQ quickstart rewritten and verified command-by-
  command against the CLI; `docs/benchmarks.md` expectations aligned to
  `EXPECTED.md`; README gains an explicit test section; `submit` now returns a
  readable error for an unregistered package instead of failing obscurely.

---

## [0.2.0] — 2026-09-17

The release that closed the v0.1 blind spot.

### Added
- **Seal signatures** (HMAC-SHA256, provisional; Ed25519 planned for v0.3) —
  `seal_sign` / `seal_verify`, CLI `keygen` / `submit --key` / `verify --key`.
- Verifier **S6** with two modes: `open` (unsigned tolerated, verdict stated)
  and `strict` (unsigned or wrongly-keyed ⇒ FAIL).
- `malicious-keyswap` fixture, documenting the out-of-band key-pinning boundary.

### Fixed
- **Full forgery is now detected.** In v0.1, a package whose evidence was
  entirely fabricated verified as clean. `failure_corpus/` keeps the original
  case public rather than quietly patching it away.

### Notes
- Stress scenario `g` added to cover the signing path: 10k `seal_sign` /
  `seal_verify` throughput, and strict `S6` verification on a 500-entry package.
  Re-run live after v0.2: 7/7 OK.

---

## [0.1.0] — 2026-09-17

Initial proposal.

### Added
- Canonical serialization (provisional).
- Lifecycle state machine L1–L7.
- Verifier with scoped report (S1–S5). PASS is explicitly defined as "no
  violation found within the observed evidence boundary" — not absolute trust.
- CLI: `init` / `register` / `event` / `evidence` / `submit` / `verify` /
  `inspect`.
- `uibc demo` — build → seal → verify PASS → tamper → FAIL.
- Golden fixtures across 7 categories (clean / tampered / deleted / duplicated /
  reordered / migrated / malicious), with `EXPECTED.md` recording
  expected-vs-observed. The malicious full-forgery case was **UNDETECTED**; this
  is the documented motivation for v0.2 signatures.
- Determinism check: 7 independent builds produced an identical evidence root.
- Test hardening: 31 unit cases (including a stale-seal S5 regression) and a
  pre-push gate that was itself deliberately violated to confirm it blocks.

### Known issues at this version
- No signatures ⇒ malicious forgery undetected.
- No certificate, gate-decision, memory-migration or registry layer.


## 未发布 — 2026-11-25（修 did:web 策略随传输路径漂移，s02b 三例根因）

- **发现**：`assert_public_host`、禁降级 302、文档体积上限三处限制原先只写在 `_fetch_json` 里。
  任何**自带 fetcher** 的调用方（测试替身、bench 的本地服务用例、适配器）从 `resolve()` 进来时，
  `did:web:127.0.0.1` 会被正常解析——限制"生效与否"取决于哪条代码路径搬字节。这正是 issue #434
  里三个用例 Linux PASS / Windows FAIL 的根因，不是平台差异。
- **修法**：把主机策略与体积上限搬进 `resolve()` 的解析契约（loopback/私网/`.local` 一律拒；返回的文档按
  UTF-8 序列化后超过 2 MiB 一律拒），传输层 `_fetch_json` 保留原检查作为纵深防御。
- 降级 302 仍只能在传输层拒绝（注入 fetcher 时看不到重定向）；这一点在测试与文档里明说，不假装覆盖。
- 新增 `tests/test_did_web_policy.py`（6 条）：注入 fetcher 的 loopback / 私网 / localhost 一律拒，
  公网照常；2.2 MB 文档拒绝、1.5 MB 接受。
