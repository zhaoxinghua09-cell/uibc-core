# -*- coding: utf-8 -*-
"""gtp-rev/1 对抗测试：正向 / 负向 / 边界 / 多源合并。"""
import json
from datetime import datetime, timedelta, timezone

from rev_feed import chain_head, decide, issue, sign, verify

T0 = datetime(2026, 11, 19, 9, 0, tzinfo=timezone.utc)
NOW = T0 + timedelta(minutes=30)
RESULTS = []


def case(cid, desc, got, want):
    ok = got == want or (want.endswith("*") and got.startswith(want[:-1]))
    RESULTS.append({"id": cid, "desc": desc, "got": got, "want": want, "pass": ok})
    print(f"{'PASS' if ok else 'FAIL'}  {cid}  {desc}\n       got={got} want={want}")


E = lambda eid: {"entity_id": eid, "kind": "IDENTITY", "target": eid,
                 "reason_code": "key_compromise", "effective_at": T0.isoformat(),
                 "scope": "all"}

# --- 正向 ---
f1 = issue("platform-A", 1, [E("agent-X")], T0)
case("T01", "新鲜 feed，签名与链一致 → 接受", verify(f1, {}, NOW), "ACCEPT")

# --- 撤销语义 ---
st1 = {"platform-A": {"serial": 1, "count": 1, "chain_head": f1["chain_head"]}}
f2 = issue("platform-A", 2, [E("agent-X"), E("agent-Y")], T0 + timedelta(minutes=10))
st2 = {"platform-A": {"serial": 2, "count": 2, "chain_head": f2["chain_head"]}}
case("T02", "被撤销实体 → DENY", decide("agent-X", [f2], st1, NOW)[0], "DENY:revoked")

# --- 回滚 / 等价冲突（基准 = 已见 serial 2 的状态）---
case("T03", "序号回滚（serial 1 < 2）→ 拒绝", verify(f1, st2, NOW), "REJECT:serial_rollback")
fx = issue("platform-A", 2, [E("agent-X")], T0)          # 同 serial 不同内容
case("T04", "同序号不同内容（equivocation）→ 拒绝", verify(fx, st2, NOW), "REJECT:equivocation")

# --- 只增不删 ---
fcut = issue("platform-A", 3, [E("agent-Y")], NOW)       # 宣称"新版本"，但删掉了历史首条
case("T05", "截断历史（删除首条）→ 拒绝", verify(fcut, st2, NOW), "REJECT:append_only*")
fswap = issue("platform-A", 3,
              [dict(E("agent-X"), reason_code="false_positive"), E("agent-Y")], NOW)
case("T06", "重写历史条目 → 拒绝", verify(fswap, st2, NOW), "REJECT:append_only*")

# --- 时效 ---
stale = issue("platform-A", 2, [E("agent-X")], T0, ttl_minutes=1)
case("T07", "超过 next_expected_by → STALE", verify(stale, {}, NOW), "STALE")
skew = issue("platform-A", 2, [E("agent-X")], NOW + timedelta(minutes=20), ttl_minutes=60)
case("T08", "签发时间未来 20 分钟（超容差）→ 拒绝", verify(skew, {}, NOW), "REJECT:future_dated")
okskew = issue("platform-A", 2, [E("agent-X")], NOW + timedelta(minutes=3), ttl_minutes=60)
case("T09", "签发时间未来 3 分钟（在容差内）→ 接受", verify(okskew, {}, NOW), "ACCEPT")

# --- 伪造 ---
forged = dict(f1, entries=[E("agent-Z")])
forged["chain_head"] = chain_head(forged["entries"])
case("T10", "改内容不重签 → 拒绝", verify(forged, {}, NOW), "REJECT:bad_signature")
forged2 = dict(f1, issuer="platform-EVIL")
forged2["sig"] = sign(forged2)
case("T11", "未钉扎的签发方 → 拒绝", verify(forged2, {}, NOW), "REJECT:unknown_issuer")

# --- 多源并集 ---
fa = issue("platform-A", 1, [E("agent-X")], T0)
fb = issue("platform-B", 1, [], T0)
case("T12", "A 撤销、B 未撤销 → DENY（并集）", decide("agent-X", [fa, fb], {}, NOW)[0], "DENY:revoked")
case("T13", "两源都未撤销该实体 → ALLOW", decide("agent-Z", [fa, fb], {}, NOW)[0], "ALLOW")
case("T14", "其中一个源 STALE → 整体不能放行", decide("agent-Z", [fa, stale], {}, NOW)[0], "DENY:stale_source")

# --- 正常追加 ---
case("T15", "合法追加（count 1→2）→ 接受", verify(f2, st1, NOW), "ACCEPT")

n = sum(1 for r in RESULTS if r["pass"])
print(f"\n{'-'*46}\ncases={len(RESULTS)} pass={n} fail={len(RESULTS)-n}")
with open("rev_feed_results.json", "w", encoding="utf-8") as fh:
    json.dump({"total": len(RESULTS), "pass": n, "results": RESULTS}, fh, ensure_ascii=False, indent=2)
raise SystemExit(0 if n == len(RESULTS) else 1)
