# 网关能力自证矩阵 — T/ISC 0174-2026

生成时间：2026-11-21T01:05:59.229730+00:00（脚本：`tools/gateway_conformance.py`，探针 37/37 通过）
标准原文：[T/ISC 0174-2026](https://www.isc.org.cn/profile/2026/10/30/1e2b29f9-8aab-438a-9114-e8eadc5f04cd.pdf)

**判定口径**：PASS = 条款要求的行为存在且有可复跑证据；PARTIAL = 部分存在、缺口已写明；MISSING = 本网关不做这件事。不做四舍五入。

| 汇总 | 全部条款 43 | 其中“应” 34 |
| --- | --- | --- |
| PASS | 21 | 17 |
| PARTIAL | 22 | 17 |
| MISSING | 0 | 0 |

| 能力域 | PASS | PARTIAL | MISSING |
| --- | --- | --- | --- |
| 协议适配 | 7 | 4 | 0 |
| 安全防护 | 4 | 6 | 0 |
| 路由寻址 | 4 | 3 | 0 |
| 身份分发 | 6 | 9 | 0 |

## 逐条

| 条款 | 应/宜 | 要求 | 判定 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- |
| 6.1.1 a) | 应 | 提交完整注册元数据（名称/唯一标识/能力描述/支持协议/通信端点/所属组织） | [+] PASS | adapters/a2a/registry.py R1-R7；tests/test_gateway_registry.py | - |
| 6.1.1 b) | 应 | 元数据校验机制；宜绑定所属组织/服务端点/可验证凭据 | [+] PASS | registry.binding_report B1-B7；tests/test_gateway_registry.py#BindingTests | 绑定为“校验一致性”（主机名/签发者/状态/范围），非链上注册 |
| 6.1.1 c) | 宜 | 支持元数据在线编辑且变更需审核 | [~] PARTIAL | gateway/registry/update：先校验→待审→approve 才落地，全程进 journal | 审核只是单点 approve 布尔确认 + 留痕，没有多人审批流转；变更也未写回注册文件 |
| 6.1.1 d) | 宜 | 提供面向行业/场景的元数据模板 | [+] PASS | adapters/a2a/templates.py（medical-device / government-service，模板本身过同一校验器） | - |
| 6.1.2 a) | 宜 | 为每个智能体生成网关内唯一、可跨域解析的标识 | [~] PARTIAL | uibc_core/did.py；our DID: did:web:verify.medxpert.cn | did:web 的 .well-known 尚未在公网发布，跨域解析实测缺一环 |
| 6.1.2 b) | 宜 | 多种标识生成策略（随机/层级/密码学） | [~] PARTIAL | did.py 支持 did:key（密码学）、did:web（层级域名）；did_cn.py 另接受六种信通院系标识（did:cn / ioa / cndid / ctid / oan / cndomain，见 docs/spec-sources/did-cn-specs.md） | 仍无随机标识策略；无公开规范的方法一律拒绝（有意，不猜） |
| 6.1.3 a) | 应 | 身份全生命周期闭环（注册/启用/停用/注销） | [+] PASS | adapters/a2a/state.py；tests/test_gateway_lifecycle.py | - |
| 6.1.3 b) | 应 | 状态变更即时生效：停用即阻断全部通信；恢复需重校验 | [+] PASS | 每请求 require_active + 403；resume 重跑 B1-B7 | - |
| 6.2.1 a) | 应 | 基于语义查询的标准接口，支持关键词精确/模糊查询 | [~] PARTIAL | server.search_agents（字段加权关键词，含模糊子串） | 是关键词加权，不是语义嵌入检索；称“语义”会过誉 |
| 6.2.1 b) | 应 | 查询结果按相关性/可用性/延迟/历史表现排序 | [~] PARTIAL | 按相关性得分排序 + name/id 稳定次序 | 无可用性、延迟、历史表现三类指标参与排序 |
| 6.2.2 a) | 应 | 查询结果过滤，仅返回授权可见的智能体 | [+] PASS | 仅 enabled 状态进检索（_visible_records） | - |
| 6.2.2 b) | 应 | 查询接口访问控制与限流 | [~] PARTIAL | limit 上限 100（MAX_DISCOVER_LIMIT） | 无限流/鉴权：任何人都能查这张表 |
| 6.3.1 | 应 | 身份与操作数据定时/主动备份，加密存储，增量+全量 | [~] PARTIAL | adapters/a2a/backup.py：全量/增量快照 + SHA-256 清单；gateway/backup | 6.3.1 b) 加密存储未实现：零依赖不自造密码学，manifest 里如实记 encrypted=false |
| 6.3.2 | 应 | 故障自动检测、告警、快速恢复、跨域容灾 | [~] PARTIAL | backup.detect_corruption（哈希漂移 + JSON 不可解析 → 告警）+ 校验后恢复；gateway/backup | 无跨域标识解析数据与授权策略的容灾；无自动定时备份调度（需外部 cron） |
| 6.3.3 | 应 | 注册/操作数据加密存储传输并脱敏 | [~] PARTIAL | 传输可置于 TLS 反代后（deploy/） | 状态文件明文落盘；无脱敏处理 |
| 7.1.1 a) | 应 | 支持 A2A 等主流智能体通信协议接入与转发 | [+] PASS | adapters/a2a/server.py；tests/test_a2a_adapter.py | - |
| 7.1.1 b) | 应 | 支持通用模型接口定义规范（如 MCP/OpenAPI）的解析与校验 | [~] PARTIAL | adapters/a2a/specs.py：工具描述符解析与校验（名称/描述/inputSchema/required） | 只覆盖工具描述符（MCP/function-calling 形态）；不解析完整 OpenAPI 文档 |
| 7.1.2 a) | 应 | 支持 TCP 与 HTTP/HTTPS 传输；宜 WebSocket/SSE/gRPC | [+] PASS | ThreadingHTTPServer + JSON-RPC over HTTP | 无 WebSocket/SSE/gRPC（宜项） |
| 7.2.1 a) | 应 | 跨协议的智能体服务发现，不同协议可统一检索定位 | [~] PARTIAL | 统一检索数据结构已就位（/agents、agent-record） | 只有 A2A 一个协议域；无第二个协议接入，跨协议无从实测 |
| 7.2.1 b) | 应 | 处理 Agent Card、Agent Record 等服务描述 | [+] PASS | agent-card.json + /agent-record.json（uibc-agent-record/1） | - |
| 7.2.2 a)-b) | 应 | 异构消息格式（JSON/XML）自动识别转换且语义保持 | [+] PASS | adapters/a2a/transform.py：json↔xml + 逐元素类型标记 + 往返比对 | 只覆盖 JSON 与 XML 两种（a 项“至少”满足）；其他格式一律拒绝而不是猜 |
| 7.2.2 e) | 宜 | 消息转换结果语义一致性校验，失败拒绝并记安全事件 | [+] PASS | transform.convert 往返不一致即抛 SemanticDrift；server 记录 semantic-drift 事件并拒绝转发 | - |
| 7.3.1 a) | 应 | 统一的应用层消息扩展头规范（注册、跨域转发） | [~] PARTIAL | server.TRACE_HEADERS 定义 5 个头 | 未固化为规范文档，无第二个网关实测互认 |
| 7.3.1 c) | 应 | 跨协议扩展头字段映射规则 | [+] PASS | templates.HEADER_MAP（http/a2a/mcp 三列）；填不上的槽位显式列入 unmappable | 映射目标是我们自定义的槽位名（X-MCP-*），不是对方规范里的既定字段 |
| 7.3.1 d) | 宜 | 跨网关扩展头最小公共字段（源/目标/请求/追踪/版本/时间戳） | [+] PASS | X-AUIB-Trace-Id 等 5 字段 + 透传实测 | - |
| 7.3.2 a) | 应 | 协议版本协商机制 | [~] PARTIAL | X-AUIB-Protocol-Version 头已定义 | 头只是声明，无协商算法与降级路径 |
| 8.1.1 a) | 应 | 路由规则版本管理与回滚 | [+] PASS | adapters/a2a/router.py RouteTable：不可变版本快照 + 指针回滚 + 可落盘；gateway/routes | 回滚是移动指针，不重写历史；无并发写冲突检测（单进程假设） |
| 8.1.1 b) | 宜 | 基于标识/服务名/API 路径的静态路由 | [+] PASS | RouteTable.match(agent/service/api)，前缀匹配 + 命中字段回传 | - |
| 8.1.2 a) | 应 | 自然语言请求解析并匹配到智能体 | [~] PARTIAL | 关键词匹配 + 能力标签 | 无句法/语义解析，长句匹配会漏 |
| 8.1.2 b) | 应 | 语义路由决策可解释：依据、得分、候选集、阈值、日志 | [+] PASS | router.semantic_route 回传 threshold/candidates/score/basis/log_entry；低于阈值拒绝指派 | 打分用 Jaccard 词重合，是词面而非向量语义；对同义改写会低分 |
| 8.2.1 a) | 应 | 满足约定的消息转发时延指标 | [+] PASS | metrics 记录每次调用时延与 p50/p95，并统计超预算次数（--latency-budget-ms） | 预算是我们自己声明的 250ms，尚未与对方约定数值；无超时熔断 |
| 8.2.1 b) | 应 | 吞吐/延迟/错误率实时监控与可视化 | [~] PARTIAL | GET /metrics（Prometheus 文本 + JSON snapshot），含请求量/错误率/延迟分位/超预算 | 有指标输出与文本展示，无图表面板与长期趋势分析 |
| 8.2.2 | 宜 | AI 报文解析与转发加速、流式透传、内容感知路由 | [~] PARTIAL | adapters/a2a/accel.py 重复请求缓存（键含包指纹）+ gateway/cache 实测命中率；探针现跑首调/缓存调 p50 | 只对字节完全相同的重复请求生效；不解析模型报文、不流式透传、不做内容感知路由 |
| 9.1.1 a) | 应 | 通信访问日志与异常事件日志 | [+] PASS | adapter.access_log（含 trace/agent/result） | 进程内列表，重启即丢；未落盘 |
| 9.1.1 b)-d) | 宜 | 日志集中存储、检索、维度组合查询、关联分析 | [~] PARTIAL | adapters/a2a/journal.py：JSONL 落盘 + trace/agent/method/时间窗组合过滤；gateway/journal | 无集中日志后端；关联分析只做到按 trace 串链路，没有异常聚合 |
| 9.1.2 a) | 应 | 跨智能体分布式链路追踪，每次调用全局唯一追踪标识 | [+] PASS | X-AUIB-Trace-Id 生成/继承 + 回传 | - |
| 9.1.2 d) | 应 | 跨协议转发时追踪上下文语义连续，优先透传上游标识 | [~] PARTIAL | 同协议透传已实测 | 跨协议路径不存在，故“跨协议连续”不可测 |
| 9.1.3 a) | 应 | 对通信流量实时异常检测 | [~] PARTIAL | tools/guardrail_shim.py（请求级规则拦截） | 规则式、非流量模型；无基线学习 |
| 9.1.3 b) | 应 | 识别提示词注入、指令篡改、身份伪造 | [+] PASS | adapters/a2a/guard.py 内联网关转发路径（12 类规则）+ tools/redteam_suite.py 16 例 + DID 验签 | 规则式识别，召回受规则库限制，未知变体可能漏检；拒绝只记类别与摘要，不落原文 |
| 9.1.4 a)-b) | 应 | TLS 保障机密性完整性；对端证书校验与双向认证 | [~] PARTIAL | deploy/nginx-gateway.conf（TLS1.2+ / ssl_verify_client on / 对端 CA / 深度上限）+ tools/check_deploy_hardening.py 静态校验 | 适配器自身仍只监听 HTTP；mTLS 由部署侧反代执行，需运维签发并部署证书后才真正生效 |
| 9.1.5 a)-c) | 应 | ACL 报文过滤、限速与清洗、安全域隔离 | [~] PARTIAL | deploy/nginx-gateway.conf：geo ACL 白名单 + limit_req/limit_conn + /metrics 独立安全域；tools/check_deploy_hardening.py 校验指令在场 | 网络层由部署侧执行，适配器不自称具备；配置需按真实对端网段替换后才算生效 |
| 9.2.1 a)-b) | 应 | 每请求身份验证与权限校验；差异化权限 | [+] PASS | adapters/a2a/scopes.py：每请求按 method 绑定权限，取 record 的 authorization.scopes 判定；调用方声明 scope 时双重判定；拒绝 HTTP 403 且记 clause | 调用方未声明 scope 时按传输层对端身份放行（basis=transport-peer），对端身份由反代 mTLS 承担；权限未按任务动态最小化 |
| 9.2.2 a)-b) | 应/宜 | 最小权限原则；权限回收与到期预警 | [~] PARTIAL | revoke 立即断权（6.1.3 b） | 无按任务最小化；无到期前预警 |

## 探针

| 探针 | 结果 | 说明 |
| --- | --- | --- |
| P10_agent_record | PASS | unified Agent Record served |
| P11_healthz_minimal | PASS | healthz exposes status only (cannot over-claim capability) |
| P12_traversal | PASS | path traversal rejected |
| P13_unknown_method | PASS | unknown method rejected |
| P14_access_log | PASS | forwarded call left an access record with trace id |
| P16_convert_roundtrip | PASS | JSON->XML conversion round-tripped and compared |
| P17_drift_detected | PASS | a type-flipped message fails the semantic comparison (7.2.2 e) |
| P18_header_map | PASS | cross-protocol map translates trace id and declares the slot it cannot fill |
| P19_route_rollback | PASS | route table rolled back to version 1 with history kept |
| P1_valid_registry | PASS | 0 error(s), 0 warning(s) |
| P1b_rejects_bad_endpoint | PASS | endpoint without http(s) rejected: True |
| P1c_rejects_non_did | PASS | non-DID identifier rejected |
| P20_route_explainable | PASS | decision returned with threshold, candidates, score and basis |
| P21_route_threshold_holds | PASS | below-threshold request refuses to name an agent |
| P22_metrics_exposed | PASS | /metrics serves counters and latency quantiles |
| P23_journal_query | PASS | journal answers a trace-id query with 1 record(s) |
| P24_edit_needs_review | PASS | metadata change is held until approved (6.1.1 c) |
| P25_edit_revalidates | PASS | invalid edit is rejected before it can be applied |
| P26_template_validates | PASS | published template passes the same validator as real registrations |
| P27_backup_verifies | PASS | snapshot verified against its own SHA-256 manifest (3 file(s)) |
| P28_corruption_alerts | PASS | corrupt live state raises the 6.3.2 a) alarm (2 finding(s)) |
| P29_restore_verified | PASS | restore refuses unverified snapshots and repaired 3 file(s) |
| P2_binding | PASS | org/endpoint/credential/scope binding checks: {'B1': True, 'B2': True, 'B4': True, 'B5': True, 'B6': True, 'B7': True} |
| P30_spec_validation | PASS | tool descriptor parsed and rejected when malformed (D4 on non-object schema) |
| P31_scope_enforced | PASS | caller presenting a scope the record does not grant is refused: HTTP 403, clause 9.2.1 a) |
| P32_injection_blocked | PASS | override payload refused before verification, no payload text in the refusal (categories=['prompt-override']) |
| P33_repeat_cache_measured | PASS | identical repeats served from cache: hits=11 misses=2 hit_rate=0.8462; measured first=0.761ms cached_p50=0.668ms (in-process) |
| P34_deploy_hardening_linted | PASS | deploy config carries mTLS + ACL + rate/connection limits: 12/12 directive(s) |
| P3_forward_verified | PASS | A2A call reached verification and returned PASS |
| P4_agent_required | PASS | call without registered agent refused (fail closed) |
| P5_suspend_blocks_immediately | PASS | next call after suspend -> HTTP 403, state suspended |
| P6_resume_restores | PASS | resume -> HTTP 200 |
| P7_resume_refuses_expired | PASS | resume on expired credential refused: ['B6'] |
| P8_trace_inherited | PASS | upstream trace id preserved in body and header |
| P8b_trace_generated | PASS | gateway-assigned trace id when upstream provides none |
| P9_discover_respects_state | PASS | suspended agent hidden (0), resumed agent visible (1) |
| P9b_ranking_explainable | PASS | ranking basis and per-hit score are in the response |
