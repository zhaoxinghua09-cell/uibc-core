# Phase 28 公开证据包（2026-11-26）

这个目录是为了让外部评审者**不必相信任何一句自述**，直接拿到可读的产物。

在此之前，15 条待评断言里有 9 条被判 `不可核`，原因不是评审者苛刻，而是**产物不在公开仓**（只在作者本机 `D:\lgd-work\phase28-20261125`）。本目录把它们搬出来。

## 五分钟版：这个包到底证明了什么、没证明什么

**它证明的（你可以自己跑出来，不必信我）**：UIBC 现行协议能做文件级选择性披露——交 1 份正文 + 全部哈希 + 封条，验证方确认该文件属于此包且未被改；它也如实暴露四个硬限制：`evidence_root` 不是 merkle 根（哈希列表必露）、没有 redaction 语义、三类关联泄露是结构性的、零知识能力为零。

**它没证明的（四条，写在这里就是为了防止被误读）**：没有外部独立评审（S6 的调用方与被评审方同一人，`E1 = REFUSE`）；没有第三方见证或运营方（全是本地密钥/同机模拟）；没有独立评测账号；没有专家签字。

**判据现状（S0–S11 十二门）**：5 门过 / 3 门部分过 / 4 门未过，`can_stake_new = False`。未闭合的四面**全部**需要另一个主体真跑或真签，不是我这一侧再跑一遍能补的。

## 文件 → 断言对照

| 文件 | 支撑哪些断言 | 说明 |
|---|---|---|
| `verify_all.json` | C1 附近（工程自检） | 一键验收 `p28_verify_all.py` 的机读结果 |
| `dual_operator_witness.json` | C3、C9 | 双运营方 2-of-3 共签、六类伪造全拒的机读结果；`honest_caveat` 明确写"同机模拟，不是第三方" |
| `adversarial_v11.json` | C3、C9 | 0.7 档 17/17 对抗结果 |
| `perf_matrix.json` | C12 | 单条证明 512 B、相对整包省 96.2% 的原始数字 |
| `competitors.json` | C4 | **31 项**竞品（2026-11-26 由 28 二次补充）与逐条官方页事实复核；新增三项里 **两项对我方不利**：C2PA 的断言级 redaction 领先我们、W3C VC Forgery Defense 已在 W3C 轨道而我们的见证方仍是演示密钥 |
| `score.json` | C5 | 96/100 自评的逐项构成 |
| `report.md` | C6、C8 | 完整审计报告（含 §29 变更记录、§30 竞品补录、§32 外部通道实测） |
| `outsider-pack.zip` | C7 | 外人复跑包（23 条目 / 52,574 B，含 README 9 步与 checksums） |
| `board.html` | C6 的可视化侧 | 单文件看板（31 项口径），4 张内联 SVG，零外链，断网可开 |
| `s6-external-ai-receipt.json` | C10 | v0.1：硅基流动 `DeepSeek-V3` 前两轮回包（只给 URL 的形态），判 `REFUSE` |
| `s6-external-ai/` | C10、C5、C15 | **v0.2：五轮结构化回执 + `claims.md` + 输入模板 + 复跑审计命令**；含"13 可核实为 1/13"那次翻转的完整记录 |
| `s9-anonymous-probe.md` | C13、C14、C11 的复核方法 | 匿名实测：双通道 8/8、clone rc=0、CI 25 项 |
| `sha256-list.txt` | 全部 | **仓内副本 40 项**（家机封印清单为 47 项，差 7 项是本机私有产物——台子 harness 三件等，不随仓发布），可逐项核对 |

## 三条边界（引用时请连着说）

1. **全部合成数据**；见证方与状态列表运营方都是本地密钥或同机模拟，**没有第三方主体**。
2. 与 SD-JWT VC / ISO mDL / SCITT 的关系是**语义对齐**：对上 5 处，**字节可互认 0 处**。
3. 96/100 是**自评**，不是认证；CI 绿只证明代码在矩阵上可跑，不证明设计正确。

## 仍然不可核的部分（直说）

- **C10（外部 AI 通道状况）**：通道是通的、五轮都跑了，但**调用方与被评审方是同一人**，供应商不独立，所以这条在任何"独立评审"意义上都不成立；判定质量经机检为 12/14 真引用，够当辅助复核，不够当背书。回执与被推翻过程见 `s6-external-ai/`。
- **C2（台子 15 PASS / 基线 158）**：`uibc-bench` 是作者本机的测试台，不在本仓。`S9_匿名实测` 能在本仓复现的部分是 `tools/outsider_rerun.py --check` 的四步，不包含台子的 s11 场景组。

## 复跑

```bash
git clone --depth 1 https://github.com/zhaoxinghua09-cell/uibc-core.git
cd uibc-core
python tools/outsider_rerun.py --check      # 期望：OUTSIDER OK ... 4 steps passed，rc=0
python tools/quote_audit.py \
    --receipt docs/evidence/20261126-phase28/s6-external-ai/receipt-v0.2.json \
    --material docs/evidence/20261126-phase28 uibc_core \
    --assertions docs/evidence/20261126-phase28/s6-external-ai/claims.md \
    --check                                  # 期望：backed=12 / restated=1 / unbacked=1，rc=1（有缺陷，故意的）
```

## 本目录自身的哈希

见 `sha256-list.txt`（它会随本仓每次提交重算；若与本目录文件不符，以 `git hash-object` 为准）。
