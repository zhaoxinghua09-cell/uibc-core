# -*- coding: utf-8 -*-
"""生成语言中立向量（不生成 mac，由外部实现者按规则自行计算）。"""
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone

KEYS = {"key-A": "secret-A", "key-B": "secret-B"}
NOW = datetime(2026, 11, 19, 9, 0, tzinfo=timezone.utc)


def canon(o):
    return json.dumps(o, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def mac(body, k):
    return hmac.new(KEYS[k].encode(), canon(body), hashlib.sha256).hexdigest()


def digest(o):
    return hashlib.sha256(canon(o)).hexdigest()


base = {"subject": "skill-x", "issued_at": NOW.isoformat(), "verdict": "clean"}
d0 = digest(base)
risky = dict(base, verdict="risky")

vectors = [
    {"id": "V-01", "check": "binding", "subject": "skill-x",
     "evidence": {"key_id": "key-A", "mac": mac(base, "key-A"), "body": base},
     "registered_digest": d0, "expected": "ALLOW"},
    {"id": "V-02", "check": "binding", "subject": "skill-x",
     "evidence": {"key_id": "key-A", "mac": mac(risky, "key-A"), "body": risky},
     "registered_digest": d0, "expected": "REJECT"},
    {"id": "V-03", "check": "binding", "subject": "skill-x",
     "evidence": {"key_id": "key-B", "mac": mac(base, "key-B"), "body": base},
     "registered_digest": d0, "expected": "REJECT"},
    {"id": "V-04", "check": "binding", "subject": "skill-x",
     "evidence": {"key_id": "key-EVIL", "mac": "00" * 32, "body": base},
     "registered_digest": d0, "expected": "REJECT"},
    {"id": "V-05", "check": "usable", "state": "AUTHORIZED",
     "expires_at": (NOW + timedelta(days=20)).isoformat(), "expected": "ALLOW"},
    {"id": "V-06", "check": "usable", "state": "AUTHORIZED",
     "expires_at": (NOW - timedelta(days=1)).isoformat(), "expected": "REJECT"},
    {"id": "V-07", "check": "usable", "state": "UNKNOWN",
     "expires_at": (NOW + timedelta(days=20)).isoformat(), "expected": "REJECT"},
    {"id": "V-08", "check": "transition", "to": "AUTHORIZED", "score_only": True,
     "expected": "REJECT"},
    {"id": "V-09", "check": "transition", "to": "AUTHORIZED",
     "authorization": {"subject": "skill-x", "scope": "runtime",
                       "expires_at": (NOW + timedelta(days=20)).isoformat()},
     "expected": "ALLOW"},
    {"id": "V-10", "check": "compat", "evidence_version": "uibc/0.4.0",
     "rule_version": "rules/2", "engine": "engine/3", "expected": "ALLOW"},
    {"id": "V-11", "check": "compat", "evidence_version": "uibc/0.3.x",
     "rule_version": "rules/2", "engine": "engine/3", "expected": "REJECT"},
    {"id": "V-12", "check": "compat", "evidence_version": "uibc/0.1.x",
     "rule_version": "rules/9", "engine": "engine/9", "expected": "REJECT"},
    {"id": "V-13", "check": "revocation", "object": "auth-x-1",
     "revocations": [{"target": "skill-x", "kind": "IDENTITY",
                      "propagates_to": ["auth-x-1", "auth-x-2"]}], "expected": "REJECT"},
    {"id": "V-14", "check": "revocation", "object": "auth-y-1",
     "revocations": [{"target": "skill-x", "kind": "IDENTITY",
                      "propagates_to": ["auth-x-1"]}], "expected": "ALLOW"},
]

# ---------- 跨平台护照交换（gtp/1）6 条 ----------
EXCHANGE_BASE = {
    "check": "exchange", "entity": "agent-A", "pinned_fp": "fp-A", "identity_fp": "fp-A",
    "rule_version": "rules/2", "engine_version": "engine/3",
    "compat": [["rules/2", "engine/3"], ["rules/2", "engine/2"]],
    "expires_at": (NOW + timedelta(days=20)).isoformat(),
    "requested_scope": ["read"], "granted_scope": ["read", "write"],
    "snapshot": {"age_hours": 1, "revoked": []},
}
FRESH_REVOKED = dict(EXCHANGE_BASE, snapshot={"age_hours": 1, "revoked": ["agent-A"]})
STALE = dict(EXCHANGE_BASE, snapshot={"age_hours": 30, "revoked": []})
NO_SNAP = {k: v for k, v in EXCHANGE_BASE.items() if k != "snapshot"}
VERSION_BAD = dict(EXCHANGE_BASE, rule_version="rules/1", engine_version="engine/1")
EXPIRED = dict(EXCHANGE_BASE, expires_at=(NOW - timedelta(days=1)).isoformat())
OTHER = dict(EXCHANGE_BASE, entity="agent-B", snapshot={"age_hours": 1, "revoked": ["agent-A"]})

vectors += [
    {"id": "V-15", **EXCHANGE_BASE, "expected": "ALLOW"},
    {"id": "V-16", **FRESH_REVOKED, "expected": "REJECT"},
    {"id": "V-17", **STALE, "expected": "REJECT"},          # 快照过期 → fail-closed
    {"id": "V-18", **NO_SNAP, "expected": "REJECT"},        # 无撤销源 → fail-closed
    {"id": "V-19", **OTHER, "expected": "ALLOW"},           # 撤销他人不波及
    {"id": "V-20", **VERSION_BAD, "expected": "REJECT"},    # 评测版本不在兼容表
]

# ---------- 规范化与协商攻击面（V-21…V-30）----------
VECTORS_ADV = [
    # 重复键：两种解析得到两个不同对象，验签"任选其一"就是漏洞
    {"id": "V-21", "check": "canon", "case": "duplicate_key",
     "raw": '{"entity":"agent-A","entity":"agent-B"}', "expected": "REJECT"},
    # Unicode：注册端 NFC，呈现端 NFD —— 必须先归一化再哈希
    {"id": "V-22", "check": "canon", "case": "nfc",
     "registered": "café", "presented": "cafe\u0301", "expected": "ALLOW"},
    # 非标准 JSON 字面量
    {"id": "V-23", "check": "canon", "case": "nan",
     "raw": '{"score":NaN}', "expected": "REJECT"},
    # 超 2^53 整数：JS 静默丢精度，Python 保留 → 必须拒绝而非"两边都算过"
    {"id": "V-24", "check": "canon", "case": "bigint",
     "value": "12345678901234567890", "max_safe": "9007199254740991",
     "expected": "REJECT"},
    # 数字词法不规范（1.0 vs 1）：不同序列化器产出不同字节
    {"id": "V-25", "check": "canon", "case": "float",
     "presented": "1.0", "canonical": "1", "expected": "REJECT"},
    # 版本：对端声明更高/未知版本，静默接受即降级风险
    {"id": "V-26", "check": "negotiate", "peer": "gtp/2",
     "supported": ["gtp/1"], "expected": "REJECT"},
    # 版本：对端低于本地证据版本
    {"id": "V-27", "check": "negotiate", "peer": "gtp/0.3", "local": "gtp/1",
     "supported": ["gtp/1"], "expected": "REJECT"},
    # 多撤销源：取并集，未被任何源撤销 → 放行
    {"id": "V-28", "check": "revmerge", "object": "agent-Y",
     "sources": [{"issuer": "A", "serial": 5, "revoked": ["agent-X"]},
                 {"issuer": "B", "serial": 9, "revoked": []}], "expected": "ALLOW"},
    # 多撤销源：被任一源撤销 → 拒绝
    {"id": "V-29", "check": "revmerge", "object": "agent-X",
     "sources": [{"issuer": "A", "serial": 5, "revoked": ["agent-X"]},
                 {"issuer": "B", "serial": 9, "revoked": []}], "expected": "REJECT"},
    # 时钟偏斜：快照"未来 5 分钟"，在 10 分钟容差内 → 放行（容差不是放宽时效）
    {"id": "V-30", "check": "skew", "age_minutes": -5, "max_age_minutes": 60,
     "tolerance_minutes": 10, "expected": "ALLOW"},
]
vectors += VECTORS_ADV

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vectors.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(vectors, f, ensure_ascii=False, indent=2)
print(f"written {out} ({len(vectors)} vectors)")
