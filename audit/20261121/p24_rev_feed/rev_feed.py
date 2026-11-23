# -*- coding: utf-8 -*-
"""gtp-rev/1 撤销 feed 参考实现 —— 签发方 + 接收方 + 对抗测试。

诚实边界：
- 这里用 HMAC-SHA256 代替非对称签名（本机无签名私钥）。HMAC 意味着
  "能验的人也能签"，生产部署 MUST 换成 Ed25519/ECDSA。本实现只用于
  验证**协议语义**（单调、只增、时效、并集），不验证密码学强度。
- 纯本地、无网络、无外部依赖。
"""
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

KEY = b"rev-issuer-A-secret"
TOL = 300  # 时钟偏斜容差（秒）


def canon(o) -> bytes:
    return json.dumps(o, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def chain_head(entries) -> str:
    """链式哈希：h_i = SHA256(h_{i-1} || canon(entry_i))，起点全零。

    只增不删的机器保证：删掉任何一条历史，重算出的 head 都会变。
    """
    h = "0" * 64
    for e in entries:
        h = sha(h + canon(e).decode())
    return h


def sign(feed: dict) -> str:
    payload = {k: feed[k] for k in
               ("issuer", "serial", "issued_at", "next_expected_by", "entries", "chain_head")}
    return hmac.new(KEY, canon(payload), hashlib.sha256).hexdigest()


def issue(issuer: str, serial: int, entries: list, issued_at: datetime, ttl_minutes: int = 60) -> dict:
    feed = {
        "feed_version": "gtp-rev/1",
        "issuer": issuer,
        "serial": serial,
        "issued_at": issued_at.isoformat(),
        "next_expected_by": (issued_at + timedelta(minutes=ttl_minutes)).isoformat(),
        "entries": entries,
        "chain_head": chain_head(entries),
    }
    feed["sig"] = sign(feed)
    return feed


def verify(feed: dict, state: dict, now: datetime, pinned_issuers=("platform-A",)) -> str:
    """返回 ACCEPT / REJECT:<原因> / STALE。state 为该 issuer 的已见状态（可为空）。"""
    if feed.get("feed_version") != "gtp-rev/1":
        return "REJECT:version"
    if feed.get("issuer") not in pinned_issuers:
        return "REJECT:unknown_issuer"
    if not hmac.compare_digest(sign(feed), feed.get("sig", "")):
        return "REJECT:bad_signature"
    if chain_head(feed["entries"]) != feed.get("chain_head"):
        return "REJECT:tampered_chain"

    prev = state.get(feed["issuer"])
    if prev:
        if feed["serial"] < prev["serial"]:
            return "REJECT:serial_rollback"
        if feed["serial"] == prev["serial"] and feed["chain_head"] != prev["chain_head"]:
            return "REJECT:equivocation"          # 同序号两个不同内容
        if len(feed["entries"]) < prev["count"]:
            return "REJECT:append_only(truncated)"
        # 前缀必须完全一致：删改历史条目会在这里暴露
        prefix = chain_head(feed["entries"][: prev["count"]])
        if prefix != prev["chain_head"]:
            return "REJECT:append_only(rewritten)"

    issued = datetime.fromisoformat(feed["issued_at"])
    if issued > now + timedelta(seconds=TOL):
        return "REJECT:future_dated"
    deadline = datetime.fromisoformat(feed["next_expected_by"]) + timedelta(seconds=TOL)
    if now > deadline:
        return "STALE"

    return "ACCEPT"


def decide(entity: str, feeds: list, state: dict, now: datetime,
           pinned_issuers=("platform-A", "platform-B")) -> tuple:
    """多源合并：取并集。任一源不可用（STALE/REJECT）即整体不能放行。"""
    statuses, revoked = {}, set()
    for f in feeds:
        st = verify(f, state, now, pinned_issuers)
        statuses[f["issuer"]] = st
        if st == "ACCEPT":
            revoked |= {e["entity_id"] for e in f["entries"]}
        elif st == "STALE":
            return "DENY:stale_source", statuses
        else:
            return f"DENY:{st.split(':')[1]}", statuses
    return ("DENY:revoked" if entity in revoked else "ALLOW"), statuses
