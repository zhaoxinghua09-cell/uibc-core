# -*- coding: utf-8 -*-
"""gtp-rev/1 v2（Ed25519）对抗测试：19 用例。

覆盖：正向、撤销语义、回滚/分叉、只增不删、时效、伪造、
     签名者身份绑定、密钥轮换、密钥撤销、多源并集。
"""
import json
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from rev_feed_v2 import Keyring, apply_effects, decide, fp, issue, verify

T0 = datetime(2026, 11, 19, 9, 0, tzinfo=timezone.utc)
NOW = T0 + timedelta(minutes=30)

A = Ed25519PrivateKey.generate()
A2 = Ed25519PrivateKey.generate()   # A 的轮换后新钥
B = Ed25519PrivateKey.generate()
EVIL = Ed25519PrivateKey.generate()

KR = Keyring({"platform-A": {fp(A.public_key()): A.public_key()},
              "platform-B": {fp(B.public_key()): B.public_key()}})
RESULTS = []


def case(cid, desc, got, want):
    ok = got == want or (want.endswith("*") and got.startswith(want[:-1]))
    RESULTS.append({"id": cid, "desc": desc, "got": got, "want": want, "pass": ok})
    print(f"{'PASS' if ok else 'FAIL'}  {cid}  {desc}\n       got={got} want={want}")


def E(eid):
    return {"entity_id": eid, "kind": "IDENTITY", "target": eid,
            "reason_code": "key_compromise", "effective_at": T0.isoformat(), "scope": "all"}


def st_of(feed):
    return {feed["issuer"]: {"serial": feed["serial"], "count": len(feed["entries"]),
                             "chain_head": feed["chain_head"]}}


f1 = issue("platform-A", 1, [E("agent-X")], T0, A)
f2 = issue("platform-A", 2, [E("agent-X"), E("agent-Y")], T0 + timedelta(minutes=10), A)
st1, st2 = st_of(f1), st_of(f2)

# --- 正向 / 撤销 / 回滚 / 分叉 ---
case("T01", "Ed25519 签名有效，链一致 → 接受", verify(f1, {}, KR, NOW), "ACCEPT")
case("T02", "被撤销实体 → DENY", decide("agent-X", [f2], {}, KR, NOW)[0], "DENY:revoked")
case("T03", "序号回滚 → 拒绝", verify(f1, st2, KR, NOW), "REJECT:serial_rollback")
fx = issue("platform-A", 2, [E("agent-X")], T0, A)
case("T04", "同序号不同内容（分叉）→ 拒绝", verify(fx, st2, KR, NOW), "REJECT:equivocation")

# --- 只增不删 ---
fcut = issue("platform-A", 3, [E("agent-Y")], NOW, A)
case("T05", "截断历史 → 拒绝", verify(fcut, st2, KR, NOW), "REJECT:append_only*")
fswap = issue("platform-A", 3,
              [dict(E("agent-X"), reason_code="false_positive"), E("agent-Y")], NOW, A)
case("T06", "重写历史 → 拒绝", verify(fswap, st2, KR, NOW), "REJECT:append_only*")

# --- 时效 ---
stale = issue("platform-A", 2, [E("agent-X")], T0, A, ttl_minutes=1)
case("T07", "超 next_expected_by → STALE", verify(stale, {}, KR, NOW), "STALE")
skew = issue("platform-A", 2, [E("agent-X")], NOW + timedelta(minutes=20), A)
case("T08", "签发时间未来 20 分钟 → 拒绝", verify(skew, {}, KR, NOW), "REJECT:future_dated")
okskew = issue("platform-A", 2, [E("agent-X")], NOW + timedelta(minutes=3), A)
case("T09", "未来 3 分钟（容差内）→ 接受", verify(okskew, {}, KR, NOW), "ACCEPT")

# --- 伪造（v1 无法区分这三类，v2 可以）---
forged = issue("platform-A", 1, [E("agent-Z")], T0, A)
forged["entries"][0]["reason_code"] = "tampered"      # 签名后再改内容
case("T10", "改内容不重签 → bad_signature", verify(forged, {}, KR, NOW), "REJECT:bad_signature")
evil = issue("platform-A", 1, [E("agent-Z")], T0, EVIL)
case("T11", "未钉扎的密钥冒名签发 → signer_not_pinned",
     verify(evil, {}, KR, NOW), "REJECT:signer_not_pinned")

# --- 多源并集 ---
fa = issue("platform-A", 1, [E("agent-X")], T0, A)
fb = issue("platform-B", 1, [], T0, B)
case("T12", "A 撤销、B 未撤销 → DENY（并集）", decide("agent-X", [fa, fb], {}, KR, NOW)[0], "DENY:revoked")
case("T13", "两源都未撤销 → ALLOW", decide("agent-Z", [fa, fb], {}, KR, NOW)[0], "ALLOW")
case("T14", "一源 STALE → 整体不放行", decide("agent-Z", [fa, stale], {}, KR, NOW)[0], "DENY:stale_source")
case("T15", "合法追加（1→2）→ 接受", verify(f2, st1, KR, NOW), "ACCEPT")

# --- 密钥轮换 ---
# 轮换声明必须携带全部历史（否则本身就被"只增不删"拦下，这正是 T05 的语义）
rot_entry = {"entity_id": "agent-W", "kind": "KEY_ROTATION",
             "old_fp": fp(A.public_key()), "new_fp": fp(A2.public_key()),
             "effective_at": NOW.isoformat(), "scope": "all"}
rot_feed = issue("platform-A", 3, f2["entries"] + [rot_entry], NOW, A)
case("T16", "旧钥签名的轮换声明 → 接受", verify(rot_feed, st2, KR, NOW), "ACCEPT")
acts = apply_effects(rot_feed, KR, {})
case("T17", "轮换已落实（含动作记录）", acts[0] if acts else "none",
     f"ROTATE:{fp(A.public_key())}->{fp(A2.public_key())}")
case("T18", "新钥用其私钥签名的 feed 需要重新钉扎公钥后才接受",
     verify(issue("platform-A", 4, [E("agent-X")], NOW, A2), {}, KR, NOW),
     "REJECT:signer_not_pinned")
KR.pin("platform-A", A2.public_key())
case("T19", "重新钉扎新公钥后 → 接受", verify(issue("platform-A", 4, [E("agent-X")], NOW, A2), {}, KR, NOW), "ACCEPT")

# --- 密钥撤销 ---
KR.revoked.add(fp(A2.public_key()))
case("T20", "签名密钥被撤销后 → 拒绝", verify(issue("platform-A", 5, [E("agent-X")], NOW, A2), {}, KR, NOW),
     "REJECT:key_revoked")

n = sum(1 for r in RESULTS if r["pass"])
print(f"\n{'-'*46}\ncases={len(RESULTS)} pass={n} fail={len(RESULTS)-n}")
with open("rev_feed_results_v2.json", "w", encoding="utf-8") as fh:
    json.dump({"total": len(RESULTS), "pass": n, "results": RESULTS}, fh, ensure_ascii=False, indent=2)
raise SystemExit(0 if n == len(RESULTS) else 1)
