# STRUCTURE — 仓库地图

> 三十秒内要能回答：**哪份是规范、哪份是判定、哪份是锚定、哪份只是证据**。
> 相关入口：`EVIDENCE-INDEX.md`（验到什么程度）、`docs/ECOSYSTEM-MAP.md`（外部关系）、`docs/NAME-COLLISIONS.md`（同名异指）。

## 一、五层

| 层 | 位置 | 职责 | 首选入口 |
|---|---|---|---|
| **规范层** | `docs/`、`lgd-core/`、`ai/`、`llms.txt` | 协议文本、三律、面向机器读者的摘要 | `docs/SPEC-PROPOSAL-v0.1.md` |
| **实现层** | `uibc_core/`（54 模块） | 规范化、签名、判定、门禁、锚定、组合 | `uibc_core/README.md` |
| **工具层** | `tools/`（34 脚本） | 一致性语料、外部视角、红队基准、锚定、发布门禁、场景演示 | `tools/publish_gate.py` |
| **验证层** | `independent_verifier/`、`tests/`、`fixtures/`、`failure_corpus/` | 第二实现交叉比对、测试、对抗夹具、失败语料 | `independent_verifier/`、`EVIDENCE-INDEX.md` |
| **存证与生态** | `dist/`、`timestamps/`、`registry/`、`registry_server/`、`mcp_server/`、`adapters/`、`contest/`、`examples/`、`paper/`、`brand/` | 归档、时间锚、注册表、集成、赛事、示例 | `examples/README.md`、`dist/README.md` |

## 二、`uibc_core/` 的四个功能组

**序列化与密码学基座**：`canonical.py`（规范化字节与哈希）、`encoding.py`（严格 base64——解码器如何静默接受并非 base64 的东西）、`ed25519.py`（RFC 8032，纯标准库）、`signing.py`（v0.3 封签）、`merkle.py`（RFC 6962 风格包含证明）。

**生命周期与链**：`lifecycle.py`（事件状态机）、`chain.py`（线性回执链，S17）、`phantom.py`（被门禁拒绝的调用也要留链——拒绝不留痕等于不可审计）。

**判定**：`verify.py`（PASS/FAIL/INCONCLUSIVE，带范围限定）、`gate.py`（verify 检查、gate 决策）、`policy.py`（策略制品解析，S18）、`compliance.py`（按草案线格式出具回执）、`composition.py`（多份异构记录合成一个可判定个案）、`aee.py`（对抗执行证据的外部验证轨）。

**锚定与对外**：`anchor.py`（S15 事件解析）、`tsa.py`（RFC 3161 令牌）、`certificate.py`、`memory.py`（UIBC-MEM 记忆迁移）、`cli.py`、`mcp_server.py`、`runtime.py`。

## 三、`tools/` 的六组

| 组 | 脚本 | 用途 |
|---|---|---|
| 一致性与外部视角 | `conformance_vectors.py`、`conformance_check.py`、`outsider_run.py`、`external_node_check.py`、`cose_sign1_interop.py`、`aer1_crosswalk.py`、`uibc_to_epaec.py` | 生成语言中立语料；**不用本项目实现**校验语料；外人视角实跑；外部节点一键检查；与 SCITT/AER-1 交叉 |
| 红队与基准 | `redteam_suite.py`、`mutation_benchmark.py`、`lens_review.py`、`lgd_eval.py`、`muse_review.py` | 外部攻击者视角；假接受率对标公开口径；四镜评审；第二实现交叉（**明确不是组织级独立评测**）；终审 |
| 锚定 | `anchor_ots.py`、`anchor_rekor.py`、`anchor_tsa.py` | 三种外部锚：OpenTimestamps、Rekor、RFC 3161 |
| 发布治理 | `pre_push_gate.py`、`push_safe.py`、`publish_gate.py`、`version_gate.py`、`release_status.py`、`whoami_github.py`、`open_pr.py`、`check_citations.py` | 账号门禁；唯一合规推送路径；看板上的数字全部来自结果文件；三处同版校验；本地与公开头对比；外链现场复核 |
| 场景演示 | `compose_demo.py`、`eqms_sample.py`、`eqms_contract.py`、`pccp_case.py`、`guardrail_shim.py`、`latency_probe.py` | 组合验证六场景；eQMS 导出判定；两版本历史裁决；一次工具调用到准入决定；离线验证耗时 |
| 交付物生成 | `attest.py`、`emit_receipts.py`、`embed_verifier.py`、`gen-sbom.py`、`mcp_gate_proxy.py` | 归属五件套；ASQAV 线格式回执；把验证器装进包内；SPDX SBOM；可用的 MCP 门禁适配器（并写明它不是网关） |

## 四、三条阅读路线

**我是外部评审，判断靠不靠得住**：`EVIDENCE-INDEX.md` → `docs/expert-review-2026-09-18.md` → `docs/comparison.md`（含落后项）→ `failure_corpus/README.md`。
**我想复现**：`tools/external_node_check.py`（一条命令、不装东西、产出一个结果文件）→ `tools/outsider_run.py` → `fixtures/EXPECTED.md`。
**我想用**：`uibc_core/cli.py` → `examples/sample-package`（不用密钥也能验）→ `mcp_server/` 或 `adapters/` → `docs/adoption-guide.md`。

## 五、命名与缩写（必读）

**同一缩写有两种写法同时在用（全库 105 份文档实扫结果，非推测）**：

| 写法 | 出现位置 | 性质 |
|---|---|---|
| **Uniform Identity-Behavior Chain** | `codemeta.json` 的 description、`CITATION.cff`、`CITATION.bib` | **机器可读口径**：外部工具、引文管理器、元数据抓取读的是这一处 |
| **unified integrity boundary check** | `README.md` 首段 Name note；另在两份 `docs/external-review/*` 评审留痕中 | 面向人读的通俗解释，并明确否认与临床化学的 UIBC（不饱和铁结合力）相关 |

**已排除的错误说法**（此前有人（包括本文初稿）以为存在）：`Unified Identity-Behavior-Continuity` 在 105 份文档中**零命中**，不要再用；`Unified Interoperable Benchmark Contest` 属 `contest/` 赛事目录内的另一所指，扫描时已排除该目录，不必与协议名混谈。

外部撞名另有两处，已在 `docs/NAME-COLLISIONS.md` 记录并处理：临床化学的 UIBC、墨西哥 UIBCDF。

**建议与规则**：
1. **建议以 `Uniform Identity-Behavior Chain` 为唯一全称**——理由是它已被 CITATION 与 codemeta 承载，是外部抓取的事实入口；改 README 一句话的成本，远低于改元数据后要修订 DOI 记录。
2. 该建议尚未执行：README 首段是作者对外身份的定义，属品牌决策，**不由文档变更代劳**。
3. 对外材料禁止裸用“UIBC”，首次出现写全称或写明“UIBC 协议／UIBC 赛事”。
4. 引用本仓库优先用 DOI 与仓库 URL，不要用缩写作主语。
5. 同类易混：`LGD` 与 `XLGD` 不是一层；`S1–S18` 是检查项编号，`L1–L7` 是生命周期规则编号。

## 六、为什么规范与实现没有拆成两个仓库

成熟项目（in-toto、Sigstore、TUF、SLSA）普遍分仓。本仓库未照做有三条成本理由：**归档已锁定**（概念 DOI 指向包含规范与实现的快照）、**零依赖是卖点**（同仓保证条款与代码逐条对应）、**外链已散出**（W3C／IETF 材料与论文附录指到具体路径）。

补偿方式是逻辑分层而非物理重排：本文件、各目录 README、`EVIDENCE-INDEX.md`。**已发布结构视为冻结**，若拆分应在下一个大版本进行，并为旧路径留转发说明。
