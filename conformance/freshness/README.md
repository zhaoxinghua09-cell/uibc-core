# 新鲜度向量（两跑成对，不是单包）

由 `python tools/build_freshness_vectors.py --write` 生成；`--check` 只比对不写。
每个案例是「状态文件 + 包覆盖 + 必须得到的判定」三件：S19 的判定取决于读者上一次看见了什么，
单包向量表达不了。`HEAD_BEFORE` 由重放器替换成下面这个 head。

head = `sha256:64c95b247f64f696eb9a76e9900309956783fe7e130334f18b7394570c44f392`

| 案例 | 状态 | 覆盖 | 期望 | 为什么 |
|---|---|---|---|---|
| 01-first-observation | `states/empty.json` | `—` | **INCONCLUSIVE** | a first observation has nothing to compare against; a PASS here would assert the package is newer than something never seen |
| 02-same-package-twice | `states/after-first.json` | `—` | **PASS** | same head as the recorded observation |
| 03-no-state-no-line | `—` | `—` | **ABSENT** | without a state file the check must not appear at all - an unearned PASS on an input nobody supplied is the failure mode this vector catches |
| 04-regressed-sequence | `states/seq-7.json` | `{"freshness_head": {"sequence": 4}}` | **FAIL** | an older sequence presented as current is a rollback |
| 05-fork-same-sequence | `states/seq-7-other-head.json` | `{"freshness_head": {"sequence": 7}}` | **FAIL** | the state records one head at sequence 7 and the package presents another: a fork at the same number, which no later observation can resolve |
| 06-prev-head-mismatch | `states/seq-7.json` | `{"freshness_head": {"sequence": 8, "prev_head": "sha256:0000000000000000000000000000000000000000000000000000000000000000"}}` | **FAIL** | claiming to descend from a head that was never recorded |
| 07-advance-with-prev-head | `states/seq-7.json` | `{"freshness_head": {"sequence": 8, "prev_head": "HEAD_BEFORE"}}` | **PASS** | a genuinely newer state that names the previous head |
| 08-unreadable-state | `states/corrupt.json.txt` | `—` | **FAIL** | a state file that cannot be parsed is a failure to check, not a pass |
