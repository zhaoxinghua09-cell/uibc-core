# 外人重跑：换一个目录、换一套环境，还成不成立

生成时间 2026-11-28T12:13:16Z，运行环境 Python 3.13.18 / Windows。

做法：把仓库整棵拷到临时目录（不含 `.git`、不含任何缓存），用只保留白名单变量的干净环境，在该目录下跑四个公开入口；每一步记录退出码与输出末行；整棵树的 sha256 一并记下。

| 步骤 | 命令 | 必须出现的字样 | 退出码 | 结果 | 耗时 |
|---|---|---|---|---|---|
| gate | `tools/mutation_gate.py` | `0 failed` | 0 | PASS | 1.0s |
| parity | `tools/competitor_gate_parity.py` | `repositories pinned`；`re-scored` | 0 | PASS | 0.9s |
| demo | `tools/demo_bid_binary.py` | `ALL OK` | 0 | PASS | 0.4s |
| tests | `-m pytest tests/test_mutation_gate.py tests/test_competitor_parity.py tests/test_parity_board.py tests/test_refs_check.py tests/test_parity_sensitivity.py tests/test_parity_audit.py tests/test_parity_realrun.py -q` | `passed` | 0 | PASS | 7.4s |

**为什么记的是字样而不只是退出码**：`rc=0` 只说明进程没崩。每一步还记下它必须印出的几处字样（例如 `0 failed`、`repositories pinned`、`passed`），重跑时任何一处没出现，这一步就判 FAIL——所以陌生人不必相信 "PASS" 这个词，他可以看这几处字样自己有没有看见。

**环境也记下来，不让你猜**：`Python 3.13.18` / CPython，`PYTHONHASHSEED=0`（集合顺序不会自己变），`PYTHONNOUSERSITE=1`（谁自己 pip 装的包不能替你做决定），`PYTHONPATH` 清空。当时这台机器上的第三方包共 246 个，清单的 sha256 是 `2746a3af6935e7b3`（全表在收据 `environment.distributions` 里）。
换一台机器时，把 Python 版本对齐、让 pytest 在位即可；若上面那批字样不一致，差异在环境，不在收据。

**树摘要 `40a5efb9a5097df9…`（2552 个文件，排除本页与 receipt 自身）**。
**内容摘要 `92c8230f9bb42120…`（只看每个文件的字节，不看文件名）**。

为什么有两根轴：路径与内容一起算的那个摘要最严，但也会被解包器连累。Windows 自带的 `tar` 把 UTF-8 文件名当 CP936 解，出来的 `r茅sum茅.md` 一个字节都没错，严摘要却红。于是收据同时记一根只算内容的摘要，`--check` 因此能说出是 `NAMES-ONLY`（字节全同、名字坏了，问题在你的解包器）还是 `CONTENT`（真的有字节动了）。
在 Windows 上解包请用 `python -c "import tarfile,sys;tarfile.open(sys.argv[1]).extractall(sys.argv[2])" <包> <目录>`，或直接在 POSIX 上解包。

**第三根轴 `4d6b8694ccd42d77…`：内容摘要再折一次换行（CRLF→LF）**，收据记的是 `commit` 这一路的字节。原因实测：本仓有 83 个文件的 blob 按 CRLF 存，而 `.gitattributes` 写的是 `text=auto eol=lf`——`git archive` 给的是存储的字节，检出给的是规整后的字节，同一个提交两条通道给两套字节。这一根轴用来把"换行差异"与"有人改了字节"分开，`--check` 因此能报 `VERDICT: DELIVERY MATCH`（同名同内容、只差换行）。

**先拿归档**：`conformance/uibc-conformance-0.7.0.zip`，1087869 字节，sha256 `fbdb7b80d341f9fd7761b201175fdcfde40b3f227f1426f95184730865604602`。
这一份不需要我们的任何程序，也不需要信任本页的任何数字——下载后自己算 sha256，对上就说明拿到的正是收据描述的那一份：
- `https://raw.githubusercontent.com/zhaoxinghua09-cell/uibc-core/main/conformance/uibc-conformance-0.7.0.zip`
- `https://codeload.github.com/zhaoxinghua09-cell/uibc-core/zip/refs/heads/main`（解开后在同一个路径下）

对不上就停下：说明有人换过字节，或者你的解包器动过它。

复核：`python tools/outsider_rerun.py --check`（重算两根摘要＋逐步判定），或 `--run` 重新跑一遍。
