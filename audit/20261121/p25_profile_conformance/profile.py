# -*- coding: utf-8 -*-
"""Profile 适配层：消费 AIP / AgIS / Clawdentity 的撤销产物，按 GTP-1 的 6 条判定。

定位：不定义第 5 份撤销草案。只回答一个问题——
"当你拿到这些草案产出的撤销材料时，按本 profile 判定，会不会漏掉撤销？"

三条 profile 立场（与三份草案的默认相反，需明确声明）：
1. 无历史不可篡改证明 → strict 模式拒绝（CRL 可被重放旧版本）
2. 状态 unknown / 缺失 → 拒绝（不交给"本地策略"自由裁量）
3. 超过 max_age → 拒绝（不接受 Clawdentity 的 fail-open）
"""
import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


# ---------------- 基础 ----------------
def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def unb64u(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def fp(pub) -> str:
    raw = pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return hashlib.sha256(raw).hexdigest()[:32]


def sign_jwt(claims: dict, priv) -> str:
    head = b64u(b'{"alg":"EdDSA","typ":"CRL"}')
    body = b64u(json.dumps(claims, sort_keys=True, separators=(",", ":")).encode())
    msg = f"{head}.{body}".encode()
    return f"{head}.{body}.{b64u(priv.sign(msg))}"


def verify_jwt(token: str, pub) -> dict:
    try:
        head, body, sig = token.split(".")
        pub.verify(unb64u(sig), f"{head}.{body}".encode())
        return json.loads(unb64u(body))
    except (InvalidSignature, ValueError, KeyError) as e:
        raise ValueError("bad_signature") from e


# ---------------- 三种格式归一化 ----------------
def norm_aip(doc: dict) -> dict:
    """AIP Revocation Object / CRL -> 内部快照。"""
    return {
        "kind": "aip", "issuer": doc.get("iss"),
        "issued_at": doc.get("iat"),                    # unix 秒
        "expires_at": doc.get("exp"),
        "history_proof": False,                          # CRL 无链式证明
        "entries": [{"entity": r.get("agentDid") or r.get("target_id"),
                     "type": r.get("type", "full_revoke"),
                     "scopes": r.get("scopes_revoked", []),
                     "serial": doc.get("jti")} for r in doc.get("revocations", [])],
    }


def norm_agis(doc: dict) -> dict:
    """AgIS Agent Status 文档 -> 内部快照（单实体）。"""
    ttl = (doc.get("cache") or {}).get("ttl_seconds", 60)
    return {
        "kind": "agis", "issuer": "agis", "entity": doc.get("agent_id"),
        "status": doc.get("status"), "issued_at": None,
        "expires_at": _ts(doc.get("updated_at")) + ttl,
        "history_proof": False, "entries": [],
    }


def norm_clawdentity(claims: dict) -> dict:
    """Clawdentity CRL（JWT claims）-> 内部快照。"""
    return {
        "kind": "clawdentity", "issuer": claims.get("iss"),
        "issued_at": claims.get("iat"),
        "expires_at": claims.get("exp"),
        "history_proof": False,
        "entries": [{"entity": r.get("agentDid"), "type": "full_revoke",
                     "scopes": [], "serial": r.get("jti")}
                    for r in claims.get("revocations", [])],
    }


def _ts(s):
    if isinstance(s, (int, float)):
        return int(s)
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())


# ---------------- 判定 ----------------
def judge(snap: dict, entity: str, now: datetime, state: dict,
          max_age_minutes: int = 15, strict: bool = True,
          request_scope: str = None) -> tuple:
    """返回 (verdict, reason)。verdict ∈ ALLOW / DENY。"""
    now_s = int(now.timestamp())
    iso_s = snap.get("issued_at")

    # 1 时效
    if iso_s is not None:
        if now_s - iso_s > max_age_minutes * 60:
            return "DENY", "stale(fail_closed)"          # 覆盖 Clawdentity 的 fail-open
        if iso_s > now_s + 300:
            return "DENY", "future_dated"
    exp = snap.get("expires_at")
    if exp is not None and now_s > exp:
        return "DENY", "expired"

    # 2 重放：iat 回退即旧版 CRL 重放
    prev = state.get(snap.get("issuer") or "_")
    if prev and iso_s is not None and iso_s < prev:
        return "DENY", "replay(older_iat)"
    if prev is None and iso_s is not None:
        pass

    # 3 历史不可篡改证明：只对"列表型"快照要求（单实体状态文档没有可追加的历史）
    single_entity = snap.get("kind") == "agis"
    if not single_entity and not snap.get("history_proof"):
        if strict:
            return "DENY", "no_history_proof"
        if snap.get("kind") not in {"aip", "clawdentity", "aip_store", "agentpin"}:
            return "DENY", "unknown_kind"

    # 4 状态语义（AgIS）
    if snap["kind"] == "agis":
        if entity != snap.get("entity"):
            return "DENY", "entity_mismatch"
        st = snap.get("status")
        if st in {"revoked", "compromised"}:
            return "DENY", f"status:{st}"
        if st in {"unknown", "suspended", "deprecated", None}:
            return "DENY", f"status:{st}(fail_closed)"   # 不交给本地策略
        return "ALLOW", "status:active"

    # 5 撤销命中（含 scope 粒度）
    for e in snap["entries"]:
        if e["entity"] != entity:
            continue
        if e["type"] == "scope_revoke":
            if request_scope in e["scopes"]:
                return "DENY", "revoked:scope"
            continue
        return "DENY", f"revoked:{e['type']}"
    return "ALLOW", "not_revoked"
