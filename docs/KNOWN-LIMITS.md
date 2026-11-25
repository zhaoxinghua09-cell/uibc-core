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
| 9 | **两个版本号不同，是有意的**：`pyproject.toml` 是包的发布号（`0.5.5`），`SPEC_VERSION` 是**线路格式**标识（`uibc-core/0.3.3-proposal`） | 已封签的包把 `SPEC_VERSION` 写进了自己的身份字节；改这个常量会让所有旧包的字节语境失效，静默作废它们的自证 | 两者**一起动会出错，所以要分开动**；读者要核"是不是同一份字节"，用 `spec_id()`（`<SPEC_VERSION>@<12 hex>`）而不是发布号。对外解释见 `CHANGELOG` 的 `0.4.0` 条目 |
| 10 | **用例数与 `skipped` 会变，不是定值** | 语料随新增向量增长（`1056` → `1082` → `1086` 都出现过），跳过项随平台与是否装 extras 变化（同一套件见过 5、7、16、31） | 任何文档只写"无 `FAILED`/`ERROR`"，数字以当轮输出为准；已钉的规范计数看 `EVIDENCE-INDEX.md` V1，但它也随快照更新 |
| 11 | **`v0.5.3` 的 tag 不在 `main` 祖先链上** | 仓库禁止 merge commit（405），PR #438 以 rebase 合入，`main` 头变成 `72b14f3d`，而 release tag 仍指向 rebase 前的 `b60a2a00`；仓库开启了 immutable release，`PATCH /git/refs/tags/v0.5.3` 返回 422，移不动 | 归档字节与 pin 一致（312,642 B / `5f3a72cb…`），`sha256sum -c MANIFEST.sha256` 与匿名重下载都能复核；但「tag 指向 main 某提交」不成立。下一版按「先合并 → 在 main 头打 tag → 再建 release」走 |
| 12 | **`v0.5.1` 这个版本名作废，`v0.5.2` 不是本树语料** | `v0.5.1` 先建非 draft release 再上传资产，被 immutable release 拒绝（`Cannot upload assets to an immutable release`）；删除重建又被 `tag_name was used by an immutable release` 拒绝（422），tag 名被永久占用。`v0.5.2` 的资产（`917f8732…`/312,641 B）能下载，但 oracle 语料里仍是旧版本串 | 可引用归档一律以最新已发布 pin 为准（当前 `v0.5.5`，`9cab2494…`/359,696 B）；发布顺序固化为 draft → 上传 → 匿名下载复算哈希 → publish；改号后必须固定 `SOURCE_DATE_EPOCH=1794700800` 重 emit oracle，否则 CI 的 `test_oracle_reproducible` 会红 |
| 13 | **PyPI 与 GitHub 的版本号曾不一致；2026-11-25 06:31 起两边都在 `0.5.5`** | 历史：`0.5.1`/`0.5.2` 经 twine 上 PyPI，`0.5.3` 只在 GitHub release，`pip install uibc-core` 当时拿到 0.5.2 | 现状态：PyPI 已发布 `0.5.4`（05:54:29 wheel / 05:54:31 sdist）与 `0.5.5`（06:31:54 / 06:31:56），MCP registry 版本序列到 `0.5.5`。保留此条是因为 `0.5.2` 未被 yank，`pip install uibc-core==0.5.2` 仍能装到那份旧语料 |
| 14 | **`0.5.4` 的 sdist 带的是上一版语料，且已不可撤回** | 另一条执行线在 05:53 直接推 `main` 并打 `v0.5.4`，没有重 emit：59 个 `manifest.json`/`seal.json` 仍写 `0.5.3`，归档 359,714 B（按本树重建应为 359,697 B）。PyPI `0.5.4` sdist（2,763,097 B，05:54:31）已上传，PyPI 不允许原地替换 | `#456` 已在仓库内重 emit（59 文件、MANIFEST 792、zip 359,697 B / `f0cb9293…`）并合入 `main`；PyPI 那份旧 sdist 只能由所有者 yank，或被 `0.5.5` 取代"最新"地位。GitHub 的 `v0.5.4` release 仍 immutable，资产还是 359,714 B |
| 15 | **`v0.5.5` 的发布页永久缺自己的 pin** | pin 步骤排在 publish 之前，而当时 `make_release_pin.py` 问的是 `/releases/tags/<tag>`——draft 对该端点一律 404，于是 run `45563463379` 在九个资产上传后报 `gh: Not Found`。我随即用 API 把该 draft 打开（`draft=false, immutable=true`），immutable 之后不能再上传，页面上就永远少了 `uibc-release-pin.json` | `#465` 让工具在 404 时回退到 `releases?per_page=100` 按 `tag_name` 匹配（列表能看见 draft），并把这次失败写进 docstring；仓库侧用 `anchors/pins/uibc-release-v0.5.5.json`（9 资产 name/bytes/sha256，`excluded` 记自身）与 `anchors/attestations/v0.5.5/` 承担这一角色。**页面与仓库因此不是逐资产镜像**：页面 9 个，pin 列的是同样那 9 个 |
| 16 | **`anchors/attestations/v0.5.5/` 是抄页面的字节，不是 workflow 写的** | 目录里 `CORPUS-DIGESTS.txt`、`.sig`、`.ots`、`anchor_freetsa.tsr`、`anchor_freetsa_ca.pem` 由我按 release 资产逐字节下载后提交，`ATTESTATION.json` 的 `what` 字段照实写了来源与当时的 404 情形 | 可复核：`python tools/check_release_anchors.py --tag v0.5.5 --dir anchors/attestations/v0.5.5`。这是一次**手工搬运**，下一版仍应由 `release-lab-bundle` 的 attest 步骤产出，否则该链的自证不完整 |

## 怎么核对这一页

```
python -m unittest discover -s tests -p "test_*.py"      # 第 5 条
python tools/redteam_suite.py                            # 第 1、2 条
python tools/muse_review.py                              # 第 6 条（需 key）
python tools/check_release_anchors.py --tag v0.5.5 --dir anchors/attestations/v0.5.5   # 第 15、16 条
```
最后一条在没有 `gh` 的机器上退出 3 并打印 `pin not checked`（本机实测如此），
签名与 OTS 仍会核对并打印 digest `03552772…`；退出 3 是"没量到"，不是"通过"。

## 这一页不做什么

不请求认同，只请求纠正：任何一条写得比事实更宽，请直接指出，我改文档而不是改事实。
