# 外部评审输入模板（可复跑）

本文件是第 4/5 轮使用的输入骨架。**材料段不在此文件内**——复跑者需要用本目录同级的证据文件自行拼装，这样材料来源可独立核对，而不是相信作者贴过来的长文。

## System 提示

```
你只输出 JSON。硬规则：
1. quote 必须逐字复制【材料】部分的片段（20–60 字符），格式：文件名::原文片段。
2. quote 不得与【待评断言】任何一句相同或近似；若只能复述断言，说明材料没有依据，该条必须判 不可核。
3. 调用方会用脚本逐条核对 quote 是否真出现在【材料】里；不在即整份回执作废。
```

## User 提示结构

```
【硬规则】…（同上三条）
【待评断言】C1 … C15（每条一句话，附一手源 URL）
【材料】                  ← 分界标记，本审计脚本用 --material-from 指定它
=== FILE: verify_all.json ===
<原文>
=== FILE: dual_operator_witness.json ===
<原文>
…（competitors.json / score.json / perf_matrix.json / adversarial_v11.json /
    report.md 相关节选 / README.md / uibc_core 的 tlog.py、status_list.py、
    witness.py、witness_registry.py）
```

## 期望回包

```json
{
  "claims": [
    {"id": "C1", "verdict": "可核|不可核", "quote": "文件名::原文片段", "note": ""}
  ],
  "adversary": {"q1": "最容易被击穿的断言", "q2": "…", "q3": "…"},
  "overall": {"verdict": "NO_DEFECT | DEFECTS(n)", "top_defect": "C2", "summary": "…"}
}
```

## 已知的坑（本轮实测）

1. 材料整段倒进 `quote` 字段会撑爆 `max_tokens`，JSON 被截断——所以限 20–60 字符片段。
2. 不加硬规则时，模型会把断言原句当 quote 返回；整份 prompt 做 substring 会 100% 命中，限定材料段才现原形。
3. `--assertions` 必须喂入断言文本，否则 `RESTATED` 这一档检测不出来。
