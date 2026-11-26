# S6 外部 AI 评审：五轮结构化回执与"引用可查性"审计

## 为什么要公开这一份

外部 AI 评审最常见的形态是一张截图或一句"已通过外部评审"。这种证据不可复核：读者无法知道评审者到底看到了什么、引用了什么、有没有凭空写结论。

这一份公开的是**过程数据**：同一个供应商、同一个模型、同一组 15 条断言，在**三种输入形态**下跑了五轮，每一轮都记了 prompt 与回包的 sha256、token 数、耗时，以及**逐条引用是否真的落在被评材料里**。审计脚本是 `tools/quote_audit.py`，任何人都可以用同样的两个文件重跑。

## 数据（`receipt-v0.2.json`）

| 轮 | 输入形态 | 可核/部分/不可核 | 总体判定 | 材料段 quote 命中 | 失效模式 |
|---|---|---|---|---|---|
| 1 | 断言 + 一手源 URL | 5 / 1 / 9 | `DEFECTS(10)` | 未审计 | F1 给-URL-即-可核 |
| 2 | 同上，明示"无原文不得判可核" | 5 / 1 / 9 | `DEFECTS(9)` | 未审计 | F1 复发 |
| 3 | 断言 + 11 个文件全文（42,769 字符） | 13 / 0 / 2 | `DEFECTS(2)` | 整份 prompt 13/13 → **材料段 1/13** | F2 复述断言当引用 |
| 4 | 第 3 轮 + 硬规则（会被脚本核对） | 输出被 max_tokens 截断 | — | 截断前已为真原文 | 输出超限 |
| 5 | 第 4 轮 + quote 限 20–60 字符 | 14 / 0 / 1 | `DEFECTS(1)` | **12/14** | F2 残留 2 条、F3 1 条、F4 漂移 |

**第 3 轮是这一组里最该记住的一轮。** 表面上 13 条"可核"、quote 在整份 prompt 里命中 13/13，看起来无懈可击。把校验范围收窄到材料段才发现：**12 条 quote 命中的是断言原文，不是材料原文**——"全绿"其实只是把题目抄了一遍。如果审计脚本不做范围限定，这份回执会以"外部 AI 13/15 通过"的身份进入结论。

## 三种失效模式

- **F1 给-URL-即-可核**：没有材料时，把"提供了链接"当成"核过了"。提示里明示后仍然复发，说明提示治不了，只能改输入形态。
- **F2 复述-断言-当-引用**：quote 落在断言区而非材料区。**必须限定材料段做 substring**；全 prompt 命中率会骗人。
- **F3 引用真但支撑不足**：C10 引用的是一句真原文，却拿它支撑"外部评审独立于操作方"——原文真，推论假。机检只能发现"是否引用"，不能发现"引用能否支撑"，这一层仍需人看。

## 如何复跑

材料由本目录同级 `20261126-phase28/` 下的文件与仓库根 `uibc_core/` 源码重拼（`verify_all.json`、`dual_operator_witness.json`、`competitors.json`、`score.json`、`perf_matrix.json`、`adversarial_v11.json`、`report.md`、`README.md`，以及 `uibc_core/tlog.py`、`status_list.py`、`witness.py`、`witness_registry.py`）。

```bash
python tools/quote_audit.py \
    --receipt docs/evidence/20261126-phase28/s6-external-ai/receipt-v0.2.json \
    --material docs/evidence/20261126-phase28 uibc_core \
    --assertions docs/evidence/20261126-phase28/s6-external-ai/claims.md \
    --check --write /tmp/quote-audit.json
```

在干净克隆上实测输出（2026-11-26）：

```
claims=15 checkable=14 backed=12 restated=1 unbacked=1 absent=0
backed_rate=85.71%  QUOTE DEFECT(2)
```

`backed=12` 就是第 5 轮的"12/14 真引用"；`restated=1` 是 C15（引用的句子同时出现在断言里，判为复述）；`unbacked=1` 是 C5（quote 的内容在 `score.json` 里并不存在，模型自己简化了一段）。退出码 1，因为它确实有缺陷——**这份审计的价值就在于它不会给自家及格**。

工具还挡掉了一个容易漏的坑：材料目录里放着回执本身时，回执的 quote 会在自己身上命中，全部判 `BACKED`。`read_material` 默认排除回执与输出文件。

`--material-from` 用来把"断言区"与"材料区"分开（本轮 prompt 里用行首 `【材料】` 作分界）；`--assertions` 把"复述断言"判成 `RESTATED` 而不是 `BACKED`。审计结论分四档：`BACKED` / `RESTATED` / `UNBACKED` / `ABSENT`，`--check` 在前三档上退出码为 1。

## 结论与边界

- **这一轮的外部 AI 只能当辅助复核**：第 5 轮 12/14 真引用、精确率约 86%、召回约 80%，仍未达"无人复核即可采"。
- **调用方与被评审方是同一人**，供应商不独立，所以这份回执**不计入任何"独立评审"判据**。判断质量合格不改变独立性不成立。
- 原始回包含本机绝对路径，未随此文件公开；公开的是逐条结构化摘录，回包 sha256 记录在 `receipt-v0.2.json` 内，作者本机可核。
- 全部为合成数据；不主张标准采纳、合规或第三方认证。
