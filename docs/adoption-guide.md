# 小团队落地指南（adoption guide）v0.1

> 回答总档案里的老问题："一个小公司，想按照我们的理念做，怎么落地实施。"
> 原则：**从一条证据开始，不从一套系统开始。**

## 第 0 步：想清楚你要防什么

UIBC 防的是三件事，落地前先对号入座：

| 你担心的事 | 对应层 | 你会用到 |
|---|---|---|
| "AI 干过什么，说不清" | 证据 Evidence | evidence + verify |
| "这个 Agent 是谁，出事找谁" | 身份 Registry | register + owner 字段 |
| "它自己说自己没问题" | 门禁 Gates | gate + 独立验证 |

三件都不担心 → 别上这套东西，纯增加负担。

## 第 1 步（第 1 周）：一条证据封进一个包

```bash
uibc keygen --out owner.key
uibc init agent-a.uibc
uibc register agent-a.uibc --agent-id support-bot-01 --owner 运营部-张三
uibc evidence agent-a.uibc --type ACTION --file 日报.txt --note "客服日报生成"
uibc submit agent-a.uibc --key owner.key
uibc verify agent-a.uibc --key owner.key    # exit 0 = PASS
```

做到这一步，你就有了第一个"事后可审计"的 AI 动作记录。
**验收标准**：故意改一个字再 verify，必须 FAIL。改了测不出 = 部署失败。

## 第 2 步（第 1 个月）：固化为例行流程

- 每个 AI agent 一个包，关键动作（对外发文、数据删除、资金相关）逐条 evidence
- 每周封包一次（submit），密钥由负责人保管（密码库，不进聊天不进代码库）
- 把 `verify --key` 挂进你的 CI 或周末巡检脚本，FAIL 即告警

## 第 3 步（第 1 个季度）：上治理

- 出过争议的包 → `dispute.json` 登记（不删历史，追加）
- 需要作废的包 → `revocation.json`（owner 签发，gate 自动 DENY）
- 对外承诺时 → `cert-issue` 出证书，附在交付物里

## 边界（诚实条款）

1. 小团队 3 步走完 ≈ 每周 30 分钟维护成本。超出这个成本说明用法错了。
2. UIBC 证明"证据没被改"，不证明"AI 干得对"——质量评估是另一回事（Evaluation 不在验证器范围）。
3. v0.2 是 HMAC 对称签名：验证需要 owner 密钥。要"第三方不共享密钥也能验"，等 Ed25519（v0.3）。
4. 不要为了"上系统"而上。没有可审计需求的小团队，第 1 步做完停在那就够了。

## 常见错误（来自我们自己的测试）

- 密钥写进代码仓库/聊天窗口 → 全部作废，立即换钥
- 改了证据文件以为重算 root 就行 → root 与封签是两道锁，都过不了
- 只跑 open 模式 verify 就对外宣称"已验证" → open 模式对伪造是盲的，必须 `--key`
- 时间戳当法律证据用 → 目前未做独立时间锚定，只是本地记录
