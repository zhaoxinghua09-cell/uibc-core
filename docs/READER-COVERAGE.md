# 读者覆盖面（现读，不是手写）

由 `python tools/coverage_matrix.py --write` 生成。数字来自三个读者自己的源码：
参考实现数 `record("Sx")` 与 `{"id": "Sx"}`，Node 读者数代码里的 `note("Sx")`（注释不计），
独立读者取自 `tools/cross_impl.py` 的 V→S 映射。

| 读者 | 源码 | 覆盖 | 缺 | 缺的原因 |
|---|---|---|---|---|
| reference | `uibc_core/verify.py` | 19/19 | — | — |
| node | `tools/verify-js/verify.mjs` | 18/19 | S19 | 19: needs a freshness state file the reader does not hold |
| independent | `tools/cross_impl.py (V->S map)` | 15/19（10 条自有结论） | S10, S13, S17, S18 | 10: closure declaration: the independent reader folds it into V7；13: Merkle inclusion: the independent reader has no tree code；17: receipt chain: outside the independent reader's scope；18: policy artefact: outside the independent reader's scope |

**读法**：Node 读者的 S19 与参考实现的 S16/S19 都需要读者自己持有的外部输入
（新鲜度状态文件、时间戳 token），所以它们是「未跑」而不是「不会」。独立读者的价值
在于它与参考实现不同源；它缺的四项不补，补齐就等于把它改成参考实现的副本。
