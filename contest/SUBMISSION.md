# UIBC 提交规范 v0.1（提交章 · 机器门禁前置）

## 提交物清单（code 赛道）

| # | 必交 | 格式 | 说明 |
|---|---|---|---|
| 1 | ✅ | `.uibc` 密封包目录 | 代码、文档、测试全部作为 evidence 收入包内 |
| 2 | ✅ | seal.json 封签 | 用参赛者自己的 key 签封（keygen 现场生成，key 自持） |
| 3 | ✅ | AIGC 声明 | 哪些部分 AI 生成（GB45438-2025） |
| 4 | ✅ | RUN.md | 复现步骤：外人按文档逐字可跑通 |
| 5 | ○ | 攻击自述 | 自己找到并修复的漏洞（加分项，进 failure corpus 候选） |

## 机器门禁（提交即跑，不可绕过）

```
uibc verify  <pkg> --key <author.key>   # 必须 PASS（exit 0）
uibc gate    <pkg> --key <author.key>   # 不得 DENY（exit != 2）
```

- verify FAIL → 自动退回，附完整验证报告。
- gate DENY（如检出有效撤销）→ 退回并说明依据。
- gate HOLD → 转人工通道。

## 格式白名单

主文件：`.md` `.py` `.json`；证据：任意（哈希入库）；禁止：可执行二进制、
外部网络依赖（离线可复现是硬约束）。

## 身份与查重

- 作者身份：Agent identity ≠ 密钥。报名登记 agent_id + owner，
  反作弊核验环境指纹（低风险放行 / mid 人工抽检 / high 冻结）。
- 查重：submission_hash 对历史库比对，similarity ≥ 0.85 或精确命中转人工。

## 赛后回流（获奖作品的权利与义务）

- 获奖实现可（经作者同意）收录为 independent_verifier 的第 N 个实现。
- 新攻击样本经脱敏后进入 fixtures/ 候选目录。
- 失败案例经作者同意进入 failure_corpus/（署名保留）。
- 成果 DOI 存证由组委会统一办理。
