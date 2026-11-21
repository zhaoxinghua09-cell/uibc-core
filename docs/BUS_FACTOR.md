# BUS_FACTOR · 单点与交接清单

> 本文回答一个具体问题：**如果维护者明天联系不上，接手的人能不能在 1 天内把系统跑起来并对外负责？**
> 现状（2026-11-21 实测）：**不能**。六个维度全为 1，外部人类贡献者 0。

## 一、六个维度（实测值）

| 维度 | 现状 | 判据/来源 |
|---|---|---|
| 代码所有权 | 1 人 | 5 个主仓 contributors 除作者外只有 dependabot |
| 发布权 | 1 人 | `pypi` 环境 `protection_rules=[]`；分支评审 `null` |
| 密钥控制 | 1 人 | 三把 PAT 存 ucvault/DPAPI（限本机本用户） |
| 规范解释权 | 1 人 | 规范无编号、无 WG |
| 对外沟通 | 1 人 | 4 个账号同人 |
| 事故响应 | 1 人 | 无值班、无备用人 |

## 二、接手包（Recovery Kit）清单

| # | 内容 | 现状 | 存放位置（应为） |
|---|---|---|---|
| 1 | 代码 | ✅ | GitHub + 本地克隆 |
| 2 | 提交/发布流程 | ✅ 部分 | `GOVERNANCE.md`、`VERSIONING.md` |
| 3 | 密钥恢复 | ❌ **缺** | 恢复码需离线纸质/密码管理器（未做） |
| 4 | 环境复现 | ✅ | `README`、`QUICKSTART`、`requirements` |
| 5 | 证据复跑 | ✅ | validator kit + 固定 SHA 样本 |
| 6 | 对外账号 | ❌ **缺** | 账号清单与所有权未文档化 |
| 7 | 客户/伙伴联系人 | ❌ 无客户 | — |
| 8 | 待办与在途决策 | ⚠️ 部分 | 本目录五阶段报告可作基线 |
| 9 | 域名/托管 | ⚠️ 部分 | Pages 托管，无自有域名（待定） |

## 三、接手者 1 天路径（可执行的验证脚本）

```powershell
# 1) 拉起环境
git clone https://github.com/zhaoxinghua09-cell/uibc-core && cd uibc-core
python -m pip install -e ".[verify]"
# 2) 跑测试（Windows 需先把 mingit 的 cmd 目录放进 PATH，否则 subprocess 调 git 会失败）
$env:PATH = "C:\Users\<user>\.local\mingit-2.56.0.4\cmd;$env:PATH"
python -m pytest tests -q
# 3) 跑证据（离线，不联网）
python tools/verify_rekor_inclusion.py --file samples/rekor_entry.json --log-key samples/log.pub
# 4) 看结论档位
#    exit 0 = verified / 1 = failed / 2 = invalid input / 3 = inconclusive
```

## 四、30 天内应补的四件事（成本从低到高）

| 优先 | 动作 | 成本 | 效果 |
|---|---|---|---|
| P0 | 密钥恢复码离线保存（两处，非同一房间） | 0.5 h | 账号失联可恢复 |
| P0 | 把本文的"接手 1 天路径"在**另一台机器**上真跑一遍并记录 | 1 h | 证明可接手 |
| P1 | `pypi` 环境加第二审批人（哪怕是另一个自己的账号） | 10 min | 阻断单点发布 |
| P1 | 账号与所有权清单（4 个 GitHub 账号 + 邮箱 + 域名）写入私有文件 | 0.5 h | 交接不靠记忆 |

## 五、不做"看起来像治理"的事

不设只有 1 人的 TSC、不设无成员的 WG。G0 阶段的正确形态就是"单人 + 公开的自我约束 + 可验证的接手路径"，
等出现第 2 个 maintainer 再按 `GOVERNANCE.md` 的触发条件升级。

---

**变更记录**

- 2026-11-21：首次成文。六维全 1 为当日实测（`gh api repos/.../contributors`、`/environments`、`/branches/main/protection`）。
