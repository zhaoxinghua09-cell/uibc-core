# 外人重跑：换一个目录、换一套环境，还成不成立

生成时间 2026-11-25T20:16:17Z，运行环境 Python 3.13.18 / Windows。

做法：把仓库整棵拷到临时目录（不含 `.git`、不含任何缓存），用只保留白名单变量的干净环境，在该目录下跑四个公开入口；每一步记录退出码与输出末行；整棵树的 sha256 一并记下。

| 步骤 | 命令 | 退出码 | 结果 | 耗时 |
|---|---|---|---|---|
| gate | `tools/mutation_gate.py` | 0 | PASS | 0.4s |
| parity | `tools/competitor_gate_parity.py` | 0 | PASS | 0.6s |
| demo | `tools/demo_bid_binary.py` | 0 | PASS | 0.2s |
| tests | `-m pytest tests/test_mutation_gate.py tests/test_competitor_parity.py tests/test_parity_board.py tests/test_refs_check.py -q` | 0 | PASS | 3.3s |

**树摘要 `72301b1bf28d8e76…`（2433 个文件，排除本页与 receipt 自身）**。
**内容摘要 `0c3b52ac8f63e845…`（只看每个文件的字节，不看文件名）**。

为什么有两根轴：路径与内容一起算的那个摘要最严，但也会被解包器连累。Windows 自带的 `tar` 把 UTF-8 文件名当 CP936 解，出来的 `r茅sum茅.md` 一个字节都没错，严摘要却红。于是收据同时记一根只算内容的摘要，`--check` 因此能说出是 `NAMES-ONLY`（字节全同、名字坏了，问题在你的解包器）还是 `CONTENT`（真的有字节动了）。
在 Windows 上解包请用 `python -c "import tarfile,sys;tarfile.open(sys.argv[1]).extractall(sys.argv[2])" <包> <目录>`，或直接在 POSIX 上解包。

复核：`python tools/outsider_rerun.py --check`（重算两根摘要＋逐步判定），或 `--run` 重新跑一遍。
