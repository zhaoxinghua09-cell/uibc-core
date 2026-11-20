"""Registration templates (6.1.1 d) and cross-protocol header mapping (7.3.1 c).

    6.1.1 d) 宜支持元数据模板化，提供面向不同行业或场景的标准元数据模板，降低注册门槛。
    7.3.1 c) 应支持跨协议扩展头映射，建立源协议字段到目标协议字段的映射规则。

Both are "宜/应" clauses that are easy to fake and easy to get wrong in the same
way: publishing a template nobody validates, or an header map that drops the one
field the next hop needs (usually the trace id). So the templates here are
checked against the real validator, and the header map declares, per target
protocol, which source header fills which slot - and marks the slots it cannot
fill instead of quietly passing None along.
"""

TEMPLATES = {
    "medical-device": {
        "schema": "uibc-a2a-registry/1",
        "description": "医械场景：证据链类智能体（变更前基线、影响评估、监管提交）",
        "required": ["name", "id", "capabilities", "protocols", "endpoint",
                     "organization"],
        "example": {
            "name": "pccp-evidence-verifier",
            "id": "did:web:verify.medxpert.cn",
            "capabilities": [
                {"name": "uibc/verify", "description": "校验 PCCP 变更证据链 S1-S6"},
                {"name": "uibc/gate", "description": "给出放行/挂起/驳回判定"},
            ],
            "protocols": ["a2a/1.0", "jsonrpc-2.0"],
            "endpoint": "https://verify.medxpert.cn/a2a/",
            "organization": {"name": "MedXpert", "identifier": "did:web:medxpert.cn"},
            "vc": {"issuer": "did:web:medxpert.cn", "status": "active",
                   "valid_until": "2030-01-01T00:00:00Z"},
            "authorization": {"scopes": ["uibc/verify", "uibc/gate"]},
        },
        "notes": ["端点主机名应与 did:web 主机名一致（6.1.1 b 绑定）",
                  "证据链类智能体不要申请写权限（9.2.2 a 最小权限）"],
    },
    "government-service": {
        "schema": "uibc-a2a-registry/1",
        "description": "政务服务场景：事项办理智能体（材料完整性、时限合规）",
        "required": ["name", "id", "capabilities", "protocols", "endpoint",
                     "organization"],
        "example": {
            "name": "service-matter-checker",
            "id": "did:web:agent.example.gov.cn",
            "capabilities": [
                {"name": "material/check", "description": "核对办事材料完整性"},
            ],
            "protocols": ["a2a/1.0"],
            "endpoint": "https://agent.example.gov.cn/a2a/",
            "organization": {"name": "示例政务服务中心",
                             "identifier": "did:web:example.gov.cn"},
            "state": "registered",
        },
        "notes": ["政务场景应先声明数据边界与留痕要求（9.1.1）",
                  "对外只开放查询类能力，写操作留在本域（api-scope）"],
    },
}


def available():
    return sorted(TEMPLATES.keys())


def get(template_id):
    if template_id not in TEMPLATES:
        raise ValueError("unknown template %r (available: %s)"
                         % (template_id, ", ".join(available())))
    return TEMPLATES[template_id]


def build(template_id, overrides=None):
    """Template example with caller overrides, ready to feed the validator."""
    example = dict(get(template_id)["example"])
    example.update(overrides or {})
    return example


# 7.3.1 c) source header -> per-target-protocol slot. None = no equivalent,
# which callers must surface rather than silently drop.
HEADER_MAP = {
    "trace_id": {"http": "X-AUIB-Trace-Id", "a2a": "X-AUIB-Trace-Id",
                 "mcp": "X-MCP-Trace-Id"},
    "source": {"http": "X-AUIB-Source", "a2a": "X-AUIB-Source", "mcp": "X-MCP-Client"},
    "target": {"http": "X-AUIB-Target", "a2a": "X-AUIB-Target", "mcp": "X-MCP-Resource"},
    "protocol_version": {"http": "X-AUIB-Protocol-Version", "a2a": "X-AUIB-Protocol-Version",
                         "mcp": "X-MCP-Version"},
    "timestamp": {"http": "X-AUIB-Timestamp", "a2a": "X-AUIB-Timestamp", "mcp": None},
}


def map_headers(headers, target_protocol):
    """Translate our extension headers into the target protocol's slots.

    Returns {"headers": {...}, "unmappable": [...]}. Callers must treat a non-empty
    `unmappable` as a partial forward: the next hop will be missing context, and
    pretending otherwise is how cross-protocol trace chains break (9.1.2 d).
    """
    if target_protocol not in ("http", "a2a", "mcp"):
        raise ValueError("unknown target protocol %r" % (target_protocol,))
    lowered = {k.lower(): v for k, v in (headers or {}).items()}
    out, unmappable = {}, []
    for slot, per_protocol in HEADER_MAP.items():
        source_name = HEADER_MAP[slot]["http"]
        value = lowered.get(source_name.lower())
        if value is None:
            continue
        target_name = per_protocol.get(target_protocol)
        if target_name is None:
            unmappable.append({"slot": slot, "value": value,
                               "reason": "no equivalent header in %s" % target_protocol})
            continue
        out[target_name] = value
    return {"headers": out, "unmappable": unmappable,
            "target_protocol": target_protocol}
