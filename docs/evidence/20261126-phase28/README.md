# Phase 28 公开证据包（2026-11-26）

这个目录是为了让外部评审者**不必相信任何一句自述**，直接拿到可读的产物。

在此之前，15 条待评断言里有 9 条被判 `不可核`，原因不是评审者苛刻，而是**产物不在公开仓**（只在作者本机 `D:\lgd-work\phase28-20261125`）。本目录把它们搬出来。

## 文件 → 断言对照

| 文件 | 支撑哪些断言 | 说明 |
|---|---|---|
| `verify_all.json` | C1 附近（工程自检） | 一键验收 `p28_verify_all.py` 的机读结果 |
| `dual_operator_witness.json` | C3、C9 | 双运营方 2-of-3 共签、六类伪造全拒的机读结果；`honest_caveat` 明确写"同机模拟，不是第三方" |
| `adversarial_v11.json` | C3、C9 | 0.7 档 17/17 对抗结果 |
| `perf_matrix.json` | C12 | 单条证明 512 B、相对整包省 96.2% 的原始数字 |
| `competitors.json` | C4 | 28 项竞品与逐条官方页事实复核 |
| `score.json` | C5 | 96/100 自评的逐项构成 |
| `report.md` | C6、C8 | 完整审计报告（含 §29 变更记录、§32 外部通道实测） |
| `outsider-pack.zip` | C7 | 外人复跑包（23 条目 / 52,574 B，含 README 9 步与 checksums） |
| `board.html` | C6 的可视化侧 | 单文件看板，4 张内联 SVG，零外链，断网可开 |
| `s6-external-ai-receipt.json` | C10 | 硅基流动 `DeepSeek-V3` 两次回包的结构化回执（判 `REFUSE`） |
| `s9-anonymous-probe.md` | C13、C14、C11 的复核方法 | 匿名实测：双通道 8/8、clone rc=0、CI 25 项 |
| `sha256-list.txt` | 全部 | 40 项交付物的 sha256 与字节数，可逐项核对 |

## 三条边界（引用时请连着说）

1. **全部合成数据**；见证方与状态列表运营方都是本地密钥或同机模拟，**没有第三方主体**。
2. 与 SD-JWT VC / ISO mDL / SCITT 的关系是**语义对齐**：对上 5 处，**字节可互认 0 处**。
3. 96/100 是**自评**，不是认证；CI 绿只证明代码在矩阵上可跑，不证明设计正确。

## 仍然不可核的部分（直说）

- **C10（外部 AI 通道状况）**：属自述。OpenRouter 与 DashScope 两条不可用，硅基流动可用但两次回包被判 `REFUSE`——这件事只能看回执，不能看结论。
- **C2（台子 15 PASS / 基线 158）**：`uibc-bench` 是作者本机的测试台，不在本仓。`S9_匿名实测` 能在本仓复现的部分是 `tools/outsider_rerun.py --check` 的四步，不包含台子的 s11 场景组。

## 复跑

```bash
git clone --depth 1 https://github.com/zhaoxinghua09-cell/uibc-core.git
cd uibc-core
python tools/outsider_rerun.py --check      # 期望：OUTSIDER OK ... 4 steps passed，rc=0
```

## 本目录自身的哈希

见 `sha256-list.txt`（它会随本仓每次提交重算；若与本目录文件不符，以 `git hash-object` 为准）。
