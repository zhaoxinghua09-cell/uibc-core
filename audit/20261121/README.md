# audit/20261121 — 审计产物索引

来源：XLGD 整改审计会话（2026-11-19 起，2026-11-21 推送）
性质：**只读审计产物与候选方案**。不代表已合并、已验证或已发布；不含任何被批准的外部承诺。

## 目录内容

- `p13_anchor_registry/` — RFC3161 / OTS / Rekor 统一锚注册表候选实现 + 样例注册表 + 单测
- `p24_rev_feed/` — 撤销传播 feed（v1 15/15、v2 20/20）
- `p25_profile_conformance/` — 档案一致性 + 真实互操作（aip-protocol 7/7、agentpin 9/9）
- `p28_version_gate/` — 版本一致性门禁（13/13）**注意：装上即让当前 main 变红，属预期失败，需先修版本号**
- `p29_test_ledger/` — 测试台账机器化（实测 642/617/1/24，与文档宣称 543 项不符，漂移 20 条）
- `specs/` — GTP-1 协议规格、档案互操作规格、互操作映射
- `repro_kit/` — 30 条语言中立一致性向量 + 零依赖运行器（Python 30/30、Node 30/30、跨语言 diff 0）

## 怎么复现

```bash
cd audit/20261121/repro_kit && python run.py    # 期望 30/30
node run.mjs                                    # 期望 30/30
cd audit/20261121/p25_profile_conformance && python test_aip_real.py && python test_agentpin_real.py
cd audit/20261121/p24_rev_feed && python test_rev_feed_v2.py
```

## 边界与残余

- 未在 main 分支应用任何候选补丁；`p28` 的失败是设计如此（基线版本号本就滞后）。
- 外部独立复现为 **0**；本目录所有数字均为本地实跑，不得标注为"第三方已验证"。
- 锚验证两条（Rekor inclusion proof、freetsa 时间戳签名）仍为 NOT VERIFIED。
