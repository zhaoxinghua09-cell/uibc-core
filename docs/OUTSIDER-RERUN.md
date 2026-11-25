# 外人重跑：换一个目录、换一套环境，还成不成立

生成时间 2026-11-25T17:43:13Z，运行环境 Python 3.12.11 / Linux。

做法：把仓库整棵拷到临时目录（不含 `.git`、不含任何缓存），用只保留白名单变量的干净环境，在该目录下跑四个公开入口；每一步记录退出码与输出末行；整棵树的 sha256 一并记下。

| 步骤 | 命令 | 退出码 | 结果 | 耗时 |
|---|---|---|---|---|
| gate | `tools/mutation_gate.py` | 0 | PASS | 0.2s |
| parity | `tools/competitor_gate_parity.py` | 0 | PASS | 0.2s |
| demo | `tools/demo_bid_binary.py` | 0 | PASS | 0.1s |
| tests | `-m pytest tests/test_mutation_gate.py tests/test_competitor_parity.py -q` | 0 | PASS | 3.6s |

**树摘要 `e7fcbb1f5a7476a6…`（2424 个文件，排除本页与 receipt 自身）**。

复核：`python tools/outsider_rerun.py --check`（重算摘要＋逐步判定），或 `--run` 重新跑一遍。
