# SPEC: tencentdb-agent-memory 验收适配器（v0.1 提案）

> 立项依据：Steven 2026-09-18 批复「按照你的建议」。对标报告核心结论：腾讯 Agent Memory（22.7k★）
> 无独立验证机制，其迁移工具 `bin/migrate-sqlite-to-tcvdb.mjs` 迁完**没有验收环节**——本项目补这一格。

## 1. 定位

用 UIBC-MEM 四项 Preservation 给「Agent Memory 记忆搬家」当验收员：
迁移前抽指纹 → 迁移后对指纹 → PASS / 精确 FAIL（改哪条、哪个字段，报得到条）。

## 2. 数据对象（查证于 src/core/store/sqlite.ts）

- 源端：SQLite 库，表 `l0_conversations`（对话层）、`l1_records`（原子事实层）、`embedding_meta`
- 目标端：腾讯向量库 TCVDB（迁移工具写）；验收取**迁移工具回读导出**或 TCVDB export 快照
- 四项映射：
  | UIBC 项 | Agent Memory 字段域 | 含义 |
  |---|---|---|
  | M2 Fact | l1 content 本体 | 事实没变 |
  | M3 Attribution | 来源会话/agent 标识 | 谁说的没丢 |
  | M4 Citation | 源 l0 引用/时间戳 | 出处可回溯 |
  | M5 Version | 记录版本/更新时间 | 版本不错位 |

## 3. 接口（CLI，纯标准库，零依赖）

```
python verify_agentmemory.py extract --sqlite <path> --out manifest.json   # 逐条 sha256 指纹清单
python verify_agentmemory.py compare --before manifest.json --after manifest2.json --report report.md
python verify_agentmemory.py root --before manifest.json                   # 汇总 root 指纹
```

输出遵循 UIBC-MEM 语义：PASS / `FAIL mem-xxx: <field> changed` 精确报错；顺序无关（按记录 ID 对齐）。

## 4. 范围外（诚实边界，与专栏口径一致）

不验：语义漂移（嵌入相似度）、迁移过程本身、检索质量。只验「字节级没搬坏、署名出处版本没丢」。

## 5. 里程碑

- M1 extract（对 SQLite 读指纹）——可离线开发
- M2 compare + 报告——可离线开发
- M3 全链路 demo：真实 SQLite → migrate → TCVDB 回读 → 验收报告 → **专栏 03《22.7k 星的记忆系统，搬家我不放心》素材**
- 运行环境：本地环境（个人机器）

## 6. 红线

- 只读：适配器绝不写 Agent Memory 数据目录
- Agent Memory 为外部项目：只读其导出物，不 fork 不改其代码
