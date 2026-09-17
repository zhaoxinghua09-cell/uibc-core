# MCP/API 公开范围决定 v1.0

决定人：老二（Steven 2026-09-18 00:35 授权「按照你的意见来」，可随时否决）
日期：2026-09-18

## 决定：读公开、写本地（read-only public, writes stay local）

| 类别 | 接口 | 公开？ | 理由 |
|---|---|---|---|
| IDENTITY | `register` | ❌ 本地 | 注册写入方 = owner 权限，公开即别人替你立户 |
| IDENTITY | `inspect`（读身份） | ✅ 公开 | 只读，无密钥参与 |
| EVIDENCE | `evidence`（追加证据） | ❌ 本地 | 写入方决定 Evidence Root，必须 owner 侧 |
| EVIDENCE | 读 manifest / index | ✅ 公开 | 只读 |
| LIFECYCLE | `event`（追加事件） | ❌ 本地 | 同上，链的写入权=身份权 |
| LIFECYCLE | 读 lifecycle.json | ✅ 公开 | 只读 |
| VERIFY | `verify` | ✅ 公开 | 核心开放点；只读，密钥由调用方自备 |
| VERIFY | `keygen` | ✅ 公开 | 本地生成、不传输，无风险 |
| GATE | `gate` | ✅ 公开 | 决策层，只读；治理文件由调用方显式给出 |
| Certificate | `cert-issue` | ❌ 本地 | 签发=owner 行为；`cert-verify` ✅ 公开 |

## 依据

1. **协议开放性纪律**（总档案 + 2026-09-17 截图 §16）：核心 UIBC 开放、商业化在外围——
   开放的是「验证与决策」，不是「写入权」。
2. **v0.2 HMAC 对称签名边界**：签名/签发能力一旦经网络暴露，等价于把 owner 密钥交出去。
   Ed25519（v0.3）落地前，写接口公开在密码学上不可行——这不是保守，是当前算法下限。
3. **最小可用闭环**：第三方拿到公开只读接口 + 自备 owner key，即可完成
   verify / gate / cert-verify 全部验证类工作——「别人能开始用」已成立。

## 升级路径

- v0.3 Ed25519 + 公钥注册表落地后，`register/evidence` 的**第三方代提交**（带委托签名）
  可重新评估公开。
- MCP 封装：上述只读命令映射为 MCP tools（verify/gate/cert-verify/inspect），
  写命令永不入 MCP 工具清单。

## 实施状态

- v1.0 仅锁定范围（本文件）；MCP server 封装为独立任务，待 G6 发布后启动。
- 若 Steven 否决任何条目：改本文件 → 重跑全量测试 → git 留痕。
