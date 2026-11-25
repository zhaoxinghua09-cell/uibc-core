# 已知限制（不是缺陷清单，是"我们知道它这样"的清单）

**2026-11-21。** 这一页专门回答外审最常问的一句："你们的 PASS 到底覆盖到哪里、
哪里你们自己知道不行。" 每一条都写清楚**是什么、为什么、现在怎么处理**，
不写"已修复"除非真的在公开仓库里跑得出来。

| # | 限制 | 为什么存在 | 现在的处置 |
|---|---|---|---|
| 1 | **只改行尾（CRLF/LF）会被判 FAIL**（S4/S8） | 证据按字节哈希，任何字节变化都必须被看见；这是"哈希敏感"的硬化代价，对"无害重排版"是误报 | 不改判据。列为已知限制；需要跨平台阅读时请用 `<path>.uibc` 原样字节，不要过编辑器 |
| 2 | **符号链接逃逸在 Windows 上未测**（红队 RT03） | Windows 默认不授予创建符号链接的权限，测试只能 SKIP | 记为"未测"，不得记为"通过"；Linux 上 RT03 正常执行并按期望 FAIL |
| 3 | **整包回滚只能带外核对**（S9） | 回滚要比较包外 head；包内自证会把"谁说了算"重新交给包本身 | 如实写在验证报告里；不做包内自证 |
| 4 | **最强锚定只到 `anchored`，未达 `witnessed`** | 我们只有 FreeTSA 摘要时间戳 + Bitcoin 区块锚，没有第二个独立见证方为同一摘要联署 | 见 `docs/SPEC-PROPOSAL-v0.1.md` §5；`witnessed` 与链式见证的要求来自 **SCITT receipts/独立 witness 与 1F916-01**，不是 EP-AEC（EP-AEC `-08` 全文 `witness` 出现 0 次），明确标为差距，不声称等价 |
| 5 | **Windows 下两例测试依赖 PATH 里有可执行的 `git`** | `test_quick_run_matches_the_receipt` 与 `test_outside_a_rebase_it_touches_nothing` 都以子进程调 `git`；PATH 里只有 `.cmd` 包装时会 `FileNotFoundError`（`CreateProcess` 不解析 `.cmd`） | Linux CI 全过；Windows 干净克隆：PATH 无 `git.exe` 时 1 失败 / 1 错误，把真实 `git.exe` 所在目录放进 PATH 后 **1082 例 OK（skipped=5，324.5 s）**。仍不写"全平台全过" |
| 6 | **外部评审方收到的证据包可能落后于当前套件** | 事实包从仓库内已提交的结果 JSON 读取；若 JSON 未随套件刷新，评审方看到的是旧快照 | `tools/muse_review.py` 现在会打印所用快照的文件名与 git blob，数字按快照现算，不再写死条数 |
| 7 | **撤销只有屏障，没有分发**：覆盖层缺失时默认 `ALLOW` | 判定器只看得见递给它的文件，包内无法自证"没有人撤销过它"，而这正是分发层的活 | `--require-revocation-coverage` 把"缺失"变成 `HOLD(3)`；`revocation-coverage.json` + `--coverage-max-age` + `--coverage-state` 可以要求新鲜度并拒绝序号回退（2026-11-22 四步实测：ALLOW→ROLLBACK→STALE→DENY）。仍是**自证**：同一持有者签"没撤销"，第三方无法独立确认 |
| 8 | **分发通道是"拉"，有盲窗**：`--coverage-url` 拉不到即 `HOLD`，检测延迟以轮询间隔为上界 | 没有推送通知，也没有第三方证明发布方把撤销都发出来了；轮询式验证方在两次 GET 之间是看不见新声明的 | 端点不可达一律 `HOLD(3)`（`coverage UNREACHABLE`），不回落 `ALLOW`；盲窗可测：本地回环、间隔 0.2 s、24 次随机相位发布 → 两次实测 median 69.3 / 136.1 ms、p95 195.0 / 198.2 ms、max 198.3 / 201.3 ms（`tools/coverage_latency.py`，中位数随发布相位浮动，理论上界仍是"间隔 + 一次 GET"）。对外只能说"上界已实测"，不能说"实时到达" |
| 9 | **两个版本号不同，是有意的**：`pyproject.toml` 是包的发布号（`0.5.3`），`SPEC_VERSION` 是**线路格式**标识（`uibc-core/0.3.3-proposal`） | 已封签的包把 `SPEC_VERSION` 写进了自己的身份字节；改这个常量会让所有旧包的字节语境失效，静默作废它们的自证 | 两者**一起动会出错，所以要分开动**；读者要核"是不是同一份字节"，用 `spec_id()`（`<SPEC_VERSION>@<12 hex>`）而不是发布号。对外解释见 `CHANGELOG` 的 `0.4.0` 条目 |
| 10 | **用例数与 `skipped` 会变，不是定值** | 语料随新增向量增长（`1056` → `1082` → `1086` 都出现过），跳过项随平台与是否装 extras 变化（同一套件见过 5、7、16、31） | 任何文档只写"无 `FAILED`/`ERROR`"，数字以当轮输出为准；已钉的规范计数看 `EVIDENCE-INDEX.md` V1，但它也随快照更新 |

## 怎么核对这一页

```
python -m unittest discover -s tests -p "test_*.py"      # 第 5 条
python tools/redteam_suite.py                            # 第 1、2 条
python tools/muse_review.py                              # 第 6 条（需 key）
```

## 这一页不做什么

不请求认同，只请求纠正：任何一条写得比事实更宽，请直接指出，我改文档而不是改事实。
