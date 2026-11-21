# -*- coding: utf-8 -*-
"""gtp-rev/1 撤销 feed —— v2：Ed25519 真签名 + 公钥钉扎 + 轮换 + 撤销。

相对 v1（HMAC）的修正：
- v1 用 HMAC，"能验的人也能签"，生产不可用。v2 改为 Ed25519 非对称签名。
- 新增签名者身份绑定：签名有效 ≠ 身份可信。密钥必须**已钉扎给该 issuer**。
- 新增密钥轮换（由旧钥签名的轮换声明）与密钥撤销（进入撤销列表后即刻失效）。

诚实边界：
- 钉扎信任锚仍是人工配置（TOFU/预置），本实现不解决"第一次怎么信"。
- 纯本地，无网络。
"""
import hashlib
import json
from datetime import datetime, timedelta, timezone

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

TOL = 300  # 时钟偏斜容差（秒）


def canon(o) -> bytes:
    return json.dumps(o, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def fp(pub) -> str:
    """公钥指纹：对 Raw SPKI 取 SHA-256，取前 16 字节十六进制。"""
    raw = pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return hashlib.sha256(raw).hexdigest()[:32]


def chain_head(entries) -> str:
    """只增不删的机器保证：h_i = SHA256(h_{i-1} || canon(entry_i))。"""
    h = "0" * 64
    for e in entries:
        h = sha(h + canon(e).decode())
    return h


def payload(feed: dict) -> bytes:
    return canon({k: feed[k] for k in
                  ("feed_version", "issuer", "serial", "issued_at",
                   "next_expected_by", "entries", "chain_head", "signer_fp")})


class Keyring:
    """钉扎的公钥集合： issuer -> {fingerprint: public_key}，外加已撤销指纹。"""

    def __init__(self, pins: dict):
        self.pins = {i: dict(m) for i, m in pins.items()}
        self.revoked = set()

    def pin(self, issuer: str, pub):
        self.pins.setdefault(issuer, {})[fp(pub)] = pub

    def lookup(self, issuer: str, fingerprint: str):
        if fingerprint in self.revoked:
            return None
        return self.pins.get(issuer, {}).get(fingerprint)


def issue(issuer: str, serial: int, entries: list, issued_at: datetime,
          priv: Ed25519PrivateKey, ttl_minutes: int = 60) -> dict:
    feed = {
        "feed_version": "gtp-rev/1",
        "issuer": issuer,
        "serial": serial,
        "issued_at": issued_at.isoformat(),
        "next_expected_by": (issued_at + timedelta(minutes=ttl_minutes)).isoformat(),
        "entries": entries,
        "chain_head": chain_head(entries),
        "signer_fp": fp(priv.public_key()),
    }
    feed["sig"] = priv.sign(payload(feed)).hex()
    return feed


def verify(feed: dict, state: dict, keyring: Keyring, now: datetime,
               pinned_issuers=None) -> str:
    if feed.get("feed_version") != "gtp-rev/1":
        return "REJECT:version"
    if pinned_issuers and feed.get("issuer") not in pinned_issuers:
        return "REJECT:unknown_issuer"

    signer = feed.get("signer_fp", "")
    key = keyring.lookup(feed["issuer"], signer)
    if key is None:
        # 两种不同失败：未钉扎（可能是陌生钥） vs 已撤销（明确不可信）
        if signer in keyring.revoked:
            return "REJECT:key_revoked"
        return "REJECT:signer_not_pinned"

    try:
        key.verify(bytes.fromhex(feed.get("sig", "")), payload(feed))
    except (InvalidSignature, ValueError):
        return "REJECT:bad_signature"

    if chain_head(feed["entries"]) != feed.get("chain_head"):
        return "REJECT:tampered_chain"

    prev = state.get(feed["issuer"])
    if prev:
        if feed["serial"] < prev["serial"]:
            return "REJECT:serial_rollback"
        if feed["serial"] == prev["serial"] and feed["chain_head"] != prev["chain_head"]:
            return "REJECT:equivocation"
        if len(feed["entries"]) < prev["count"]:
            return "REJECT:append_only(truncated)"
        if chain_head(feed["entries"][: prev["count"]]) != prev["chain_head"]:
            return "REJECT:append_only(rewritten)"

    if datetime.fromisoformat(feed["issued_at"]) > now + timedelta(seconds=TOL):
        return "REJECT:future_dated"
    if now > datetime.fromisoformat(feed["next_expected_by"]) + timedelta(seconds=TOL):
        return "STALE"
    return "ACCEPT"


def apply_effects(feed: dict, keyring: Keyring, state: dict) -> list:
    """在 verify 返回 ACCEPT 后调用：落实轮换/撤销/水位，返回已执行的动作。"""
    done = []
    for e in feed["entries"]:
        kind = e.get("kind")
        if kind == "KEY_ROTATION" and e.get("old_fp") == feed["signer_fp"]:
            new_fp = e["new_fp"]
            if new_fp in keyring.revoked:
                continue
            keyring.pins.setdefault(feed["issuer"], {})[new_fp] = None  # 占位，待带钥重钉
            done.append(f"ROTATE:{e['old_fp']}->{new_fp}")
        elif kind == "KEY_REVOKED":
            keyring.revoked.add(e["key_fp"])
            done.append(f"REVOKE_KEY:{e['key_fp']}")
    state[feed["issuer"]] = {"serial": feed["serial"], "count": len(feed["entries"]),
                             "chain_head": feed["chain_head"]}
    return done


def decide(entity: str, feeds: list, state: dict, keyring: Keyring, now: datetime,
           pinned_issuers=("platform-A", "platform-B")) -> tuple:
    """多源合并：并集。任一源 STALE/REJECT → 整体不能放行。"""
    statuses, revoked = {}, set()
    for f in feeds:
        st = verify(f, state, keyring, now, pinned_issuers)
        statuses[f["issuer"]] = st
        if st == "ACCEPT":
            revoked |= {e["entity_id"] for e in f["entries"] if "entity_id" in e}
        elif st == "STALE":
            return "DENY:stale_source", statuses
        else:
            return f"DENY:{st.split(':')[1]}", statuses
    return ("DENY:revoked" if entity in revoked else "ALLOW"), statuses
