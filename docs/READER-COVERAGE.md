# 读者覆盖面（现读，不是手写）

由 `python tools/coverage_matrix.py --write` 生成。数字来自三个读者自己的源码：
参考实现数 `record("Sx")` 与 `{"id": "Sx"}`，Node 读者数代码里的 `note("Sx")` 与 `inconclusive("Sx")`（注释不计），
独立读者取自 `tools/cross_impl.py` 的 V→S 映射。

| 读者 | 源码 | 覆盖 | 缺 | 缺的原因 |
|---|---|---|---|---|
| reference | `uibc_core/verify.py` | 19/19 | — | — |
| node | `tools/verify-js/verify.mjs` | 19/19 | — | — |
| independent | `tools/cross_impl.py (V->S map)` | 15/19（10 条自有结论） | S10, S13, S17, S18 | 10: closure declaration: the independent reader folds it into V7；13: Merkle inclusion: the independent reader has no tree code；17: receipt chain: outside the independent reader's scope；18: policy artefact: outside the independent reader's scope |

**读法**：Node 读者现在 19/19，但其中 S19 与参考实现的 S16/S19 都只能在**读者自己持有的外部输入**
在场时才跑（`--freshness` 状态文件、RFC 3161 时间戳 token）；不传就不是「通过了」，是「根本没跑」——
Node 实现里这两条在不传输入时连一行结果都不发，宁可缺席也不发一个无人核对过的 PASS。
独立读者的价值在于它与参考实现不同源；它缺的四项不补，补齐就等于把它改成参考实现的副本。
