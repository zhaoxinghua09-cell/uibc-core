# UIBC 赛事章程 v0.1（草案，待组委会审议）

**全称**：Unified Interoperable Benchmark Contest（UIBC 赛事线）
**赛季主题**：迁移的判定与问责（Judgment & Accountability under Migration）
**定位**：自治智能体赛道 · 独立品牌。赛事是 UIBC 协议的第一次公开实测：
**不考理念，考可运行的判定与问责**。

## 与 uibc-core 的关系

赛事五环节全部运行在 uibc-core 已交付的工程件上（这不是比喻，是验收标准）：

| 赛事环节 | 运行在 | 验收证据 |
|---|---|---|
| 提交门户 | `.uibc` 密封包 + submit CLI | 提交物本身可被 verify（S1-S6） |
| 反作弊/身份核验 | Registry + gate（S2 身份，ALLOW/DENY/HOLD） | gate 输出即核验记录 |
| 作品查重 | verifier + 独立第二实现交叉核验 | 70/70 一致性为判定底座 |
| 评审打分 | rubric 映射 UIBC-MEM 四项 Preservation（M2-M5） | 评审维度=协议检查项，非主观印象分 |
| 赛题生成与存证 | fixtures 方法论 + Certificate + DOI 锚定 | Benchmark 即 executable evidence |

## 三条赛道

- **code**：提交可运行实现 + `.uibc` 证据包（主赛道）
- **theory**：规范/协议论文级提案（须附最小可执行示例）
- **design**：落地实施方案（须附失败模式分析）

## 机器门禁 + 人工终裁

1. 机器门禁（自动，不可绕过）：提交包 verify PASS 才进入评审；gate 判
   DENY 的提交直接退回并附报告。
2. 人工终裁（不可让渡）：评审工具为决策支持，**最终裁定权归组委会**；
   打分须双评委独立进行后再合议。
3. AIGC 标识：所有 AI 辅助产出按 GB45438-2025 标注（赛题、评审辅助、
   提交物中 AI 生成部分均须声明）。

## 身份链

四规范（本目录 + 上游规范）→ 认证防伪（提交包 HMAC 封签）→ 成果 DOI
存证（赛后）→ 理论回流（获奖作品回流为 fixtures / failure corpus /
独立实现）。

## 诚实边界

- 平台工具当前为决策支持级，非终裁系统。
- 查重相似度算法为示意实现，正式查重须 MinHash/SimHash + 人工判定。
- 赛题生成器输出为底稿（实测同主题不同难度返回同底稿），须人工精修后
  发布——PROBLEMS.md 中标注了每题的来源与审核状态。
