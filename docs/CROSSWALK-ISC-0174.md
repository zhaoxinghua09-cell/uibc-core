# T/ISC 0174—2026 网关能力对照表（uibc-core A2A 网关适配器）

标准：T/ISC 0174—2026《智能体互联网 网联 智能体网关能力要求》（中国互联网协会，2026-10-30 发布）
原文：https://www.isc.org.cn/profile/2026/10/30/1e2b29f9-8aab-438a-9114-e8eadc5f04cd.pdf

## 1. 这份文件是什么，不是什么

**是**：把 0174 的 43 条要求逐条落到本仓库的代码、测试和探针上，并写明每一条的缺口。
**是**：一份可以被外人一条命令复跑的对照——判定不是写死的，探针失败会自动把该条降级为 MISSING。
**不是**：能力评估结论。0174 的评估主体是网关供给方/需求方依据本标准开展的能力评估，我们只是先把自己这半边查清。
**不是**：合规声明。PASS 是我方自证的“行为存在且有可复跑证据”，不等于第三方已认定合格。

判定口径（三条，写下来是为了避免以后自我松绑）：

- `PASS`：条款要求的行为存在，且有可复跑的证据（测试或探针）。
- `PARTIAL`：部分存在，缺口在表里写明。**不四舍五入成 PASS。**
- `MISSING`：本网关不做这件事，并写明为什么。**不写成“规划中”。**

## 2. 怎么复核

```bash
python tools/gateway_conformance.py \
  --md  docs/gateway-conformance-0174.md \
  --json docs/gateway-conformance-0174.json \
  --html docs/gateway-conformance-0174.html
```

脚本在临时目录里现建 UIBC 包、现起环回端口的真实适配器，没有任何 mock 或录制回放。
37 条探针覆盖：转发、状态阻断、恢复重校验、追踪透传、检索过滤、Agent Record、健康检查、
路径穿越拒绝、格式转换往返、跨协议头映射、路由版本回滚、语义路由阈值、指标输出、
日志检索、元数据编辑审核、备份校验与恢复、模型接口描述符校验、scope 越权拒绝、
注入拒绝、重复缓存实测、部署配置静态校验。

```bash
python tools/accel_benchmark.py --packages ./examples --package good.uibc \
  --repeats 30            # 8.2.2 缓存自己的实测数字，换机器自己跑一遍再引用
python tools/check_deploy_hardening.py     # 9.1.4 / 9.1.5 的配置指令在场检查
```

## 3. 汇总（本次运行实测）

| 项 | 数量 |
| --- | --- |
| 条款总数 | 43（“应” 34、“宜” 9） |
| PASS | 21（其中“应” 17） |
| PARTIAL | 22（其中“应” 17） |
| MISSING | 0 |
| 探针 | 37 / 37 通过 |

按能力域：

| 能力域 | PASS | PARTIAL | MISSING |
| --- | --- | --- | --- |
| 身份分发（第 6 章） | 6 | 9 | 0 |
| 协议适配（第 7 章） | 7 | 4 | 0 |
| 路由寻址（第 8 章） | 4 | 3 | 0 |
| 安全防护（第 9 章） | 4 | 6 | 0 |

一句话读法：**43 条没有一条落在“不做”上；22 条 PARTIAL 的缺口全部写明归属——加密存储、网络层 ACL/mTLS 的执行主体是部署侧，性能加速只做实测过的重复缓存。**

## 4. 已实现能力与条款依据

| 能力 | 条款 | 实现位置 |
| --- | --- | --- |
| 注册元数据与绑定校验 | 6.1.1 a/b | `adapters/a2a/registry.py`（R1–R9 / B1–B7） |
| 元数据在线编辑（需审核） | 6.1.1 c | `gateway/registry/update`：先校验→待审→approve 落地，全程入日志 |
| 场景元数据模板 | 6.1.1 d | `adapters/a2a/templates.py`（医械、政务两套，模板本身过同一校验器） |
| 生命周期闸门 | 6.1.3 a/b | `adapters/a2a/state.py`：停用即阻断（403）、恢复重校验、状态可落盘 |
| 备份 / 增量 / 完整性 / 恢复 | 6.3.1 a/c、6.3.2 a/b | `adapters/a2a/backup.py`：SHA-256 清单、漂移告警、校验后恢复 |
| 语义查询（关键词加权） | 6.2.1 a/b、6.2.2 a | `gateway/discover`、`GET /agents?q=`，排序依据与得分回传 |
| A2A 接入转发 | 7.1.1 a | `adapters/a2a/server.py` |
| 模型接口描述符解析校验 | 7.1.1 b | `adapters/a2a/specs.py`（名称/描述/inputSchema/required） |
| Agent Card / Agent Record 统一 | 7.2.1 b | `GET /agent-record.json`（`uibc-agent-record/1`） |
| JSON ↔ XML 转换 + 语义保持 | 7.2.2 a/b/e | `adapters/a2a/transform.py`：逐元素类型标记 + 往返比对，漂移即拒绝 |
| 统一扩展头 + 跨协议映射 | 7.3.1 a/c/d | `server.TRACE_HEADERS` + `templates.HEADER_MAP`（http/a2a/mcp） |
| 路由版本管理与回滚 | 8.1.1 a/b | `adapters/a2a/router.py` RouteTable（不可变快照 + 指针回滚 + 落盘） |
| 语义路由可解释 | 8.1.2 a/b | `gateway/route`：阈值、候选集、得分、依据、决策日志全部回传 |
| 转发时延预算与监控 | 8.2.1 a/b | `adapters/a2a/metrics.py` + `GET /metrics` |
| 访问日志与异常事件 | 9.1.1 a | `adapters/a2a/journal.py`（JSONL，不含报文正文） |
| 日志检索（四维） | 9.1.1 b–d | `gateway/journal`：trace / agent / method / 时间窗 |
| 注入 / 指令篡改识别（内联） | 9.1.3 b | `adapters/a2a/guard.py`：12 类规则，转发前拒绝，记类别与摘要不记原文 |
| 每请求权限判定 | 9.2.1 a | `adapters/a2a/scopes.py`：method→权限，按 record 的 scopes 判，越权 403 |
| 重复请求缓存（实测） | 8.2.2 | `adapters/a2a/accel.py` + `gateway/cache` + `tools/accel_benchmark.py` |
| TLS/mTLS · ACL · 限速（部署侧） | 9.1.4、9.1.5 | `deploy/nginx-gateway.conf` + `tools/check_deploy_hardening.py` 静态校验 |

## 5. 缺口收敛（v2 时还有 2 条 MISSING，现在 0 条）

| 条款 | v2 | 现在 | 变化 |
| --- | --- | --- | --- |
| 8.2.2 AI 报文加速（宜） | MISSING | PARTIAL | 只做“字节完全相同的重复请求”缓存，键里带包指纹防陈旧判定；命中率与首调/缓存调 p50 由探针现跑，不写“AI 加速”。仍然不解析模型报文、不流式透传。 |
| 9.1.5 ACL / 限速 / 安全域（应） | MISSING | PARTIAL | 交付 `deploy/nginx-gateway.conf`（geo 白名单、limit_req/limit_conn、`/metrics` 独立域），并用 `check_deploy_hardening.py` 把“指令是否在场”变成可失败检查。**执行主体仍是部署侧**。 |

为什么没有把这两条写成 PASS：缓存是我方实测的窄能力，不是标准描述的“AI 报文解析与转发加速”；ACL 的生效取决于运维替换真实网段并部署，适配器内没有网络层证据。写到 PASS 就是把别人的活儿算成自己的。

## 6. PARTIAL 里最可能被追问的五条

1. **6.3.1 b) 加密存储**：备份有完整性清单但没有加密。零依赖项目不自造密码学，manifest 里 `encrypted=false` 明写——宁可被问“为什么没加密”，也不留下“备份=安全”的错觉。
2. **9.1.4 a)-b) TLS 与对端证书校验**：适配器自身只监听 HTTP。`deploy/nginx-gateway.conf` 已写好 mTLS 并对十二条必需指令做静态校验，但证书签发与部署是运维动作，未部署前不能说“已双向认证”。
3. **9.2.1 a) 权限校验**：现在是执行式的。每请求按 method 绑定权限（verify/gate/inspect），record 的 `authorization.scopes` 不含该权限即 403；调用方自带 scope 时再判一层。**缺口**是调用方不声明 scope 时按“传输层对端身份”放行——对端身份由反代 mTLS 提供，因此这一条与 9.1.4 的部署状态绑在一起。
4. **8.1.2 a) 自然语言解析**：Jaccard 词重合打分，不是向量语义；同义改写会低分。
5. **8.2.2 加速**：只缓存字节完全相同的重复请求；首调与缓存调延迟由探针现跑。不接受把缓存命中率读成“报文解析加速”。

## 7. 与相邻标准/草案的关系

- **T/ISC 0175—2026**（OpenClaw 类多智能体协同能力要求）：同样要求身份接入、注册、生命周期与访问控制，与本表 6.1/9.2 高度重合，可作第二份对照。
- **IETF draft-miao-agw-core-functional-architecture-00**：把网关拆成 A2A / MCP / Model Routing / Network 四类，与 0174 四域互为映射；本表的 `templates.HEADER_MAP` 已按 http/a2a/mcp 三列落地，可直接扩到该草案的四类。

## 8. 对外表述的边界

可以用的话：

> 我们按 T/ISC 0174 的四个能力域做了逐条自证：43 条里 21 条通过、22 条部分、0 条不做，缺口与归属都写在表里；自证脚本一条命令可复跑，37 条探针全通过。

不能说的话：

- “已符合 0174”——评估主体不是我们。
- “网关能力完备”——加密存储、mTLS 实际部署、网络层 ACL 的执行不在本适配器内。
- “支持语义检索/语义路由”——目前是词重合打分，不是向量语义。
- “备份已加密”——没有。
- “AI 报文加速”——只有重复请求缓存，命中率与延迟见实测，别改写。

## 9. 边界

本表依据 2026-10-30 发布稿整理；标准若修订，条款编号与措辞需重新核对。
判定结果由 `tools/gateway_conformance.py` 现跑生成，任何手工修改本表数字的版本都不作数。
