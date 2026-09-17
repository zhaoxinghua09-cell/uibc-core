# 赛事对标报告：GitHub 顶级赛事怎么组织（2026-09-18）

调研方法：外部调研代理，对标 10 个 GitHub 公开可查的赛事/benchmark（DARPA AIxCC、SWE-bench、MICCAI Challenges、NeurIPS Competition Track、Kaggle、Advent of Code、GSoC、Hacktoberfest、CTFd、AIcrowd）。

## 核心结论（结论先行）

**uibc-core 赛事定位调整：常驻 benchmark 为主体 + 轻量"赛季"包装**（效仿 AIcrowd rounds）。
理由：①零预算下 hackathon 要集中人力守榜评审，个人运营不可持续；常驻自动评测运营成本趋零；②hackathon 引流是一波峰值，常驻 benchmark 有 SEO 长尾与持续引用；③可验证证据包天然是 benchmark 形态。

## 四问答案（摘要）

1. **评审结构**：混合评审是绝对主流（自动门禁→隐藏集评分→top 复跑+人工审查），rubric 公开已成共识。我们方向正确，缺的是**复跑条款与隐藏集**。
2. **防作弊**：业界五招——①每人定制输入（AoC，机制性防抄）②隐藏集+限次+公私榜分离（Kaggle）③提交复跑+哈希校验④top 人工审查+多账号检测⑤评测日志全公开（SWE-bench）。我们已有机器门禁/查重，**缺：隐藏/轮换测试集、日志不可篡改存档、复跑条款、任务个人化**。
3. **零预算激励**（按效力序）：fame 沉淀（常驻榜单+获奖 writeup）＞可验证凭证（分级 badge+证书）＞学术署名（赛季报告共同作者）＞稀缺性（限量名额）＞first-to-cross 奖。
4. **常驻 vs 一次性**：选常驻（理由见上）。

## 十个对标对象与可抄点（摘要表）

| 对标对象 | 可抄的 1 件事 |
|---|---|
| DARPA AIxCC | 把"开源你的方案"写进获奖条件，比赛沉淀为公共资产 |
| SWE-bench | 强制提交附 reasoning trace，公开全部评测日志（experiments/ 存档） |
| MICCAI Challenges | 最终提交必须是可一键复现的容器，而非结果文件 |
| NeurIPS Track | 章程写明"top 提交将被组织者复跑验证"条款 |
| Kaggle | 公/私榜分离 + 限次提交（一个机制同时防过拟合和探测） |
| Advent of Code | 任务参数个人化：每人拿变体输入，答案不可互换 |
| GSoC | 评审者用 rubric 独立成文档，与参赛者看到的不混用 |
| Hacktoberfest | badge 分级解锁：零成本、可炫耀、驱动持续参与 |
| CTFd | scoreboard freeze + 动态计分，纯配置级实现 |
| AIcrowd | starter kit（fork 即提交的最小模板）+ 赛季报告共同署名 |

## contest/ v0.2 改进执行（按性价比）

1. ✅ SUBMISSION.md 升级：一键复现 + "top 提交将被复跑验证"条款
2. ✅ 章程补隐藏集三段式（validation→sanity→final）+ 限次提交
3. ✅ experiments/ 目录：提交哈希+评测日志存档（append-only）
4. ✅ INCENTIVES.md：零预算激励包（badge 分级+证书+赛季共同署名）
5. ✅ starter-kits/：每题最小提交模板

（完整调研原稿见本文件上方历史版本记录；个别 star 数标"待验证"。）
