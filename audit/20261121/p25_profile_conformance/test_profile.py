# -*- coding: utf-8 -*-
"""Profile 一致性测试：用 AIP / AgIS / Clawdentity 三种真实格式，验 12 个判定。

目的不是评价草案对错，而是证明：
同一套判定规则，在这三种格式上都不会漏撤、不会把 unknown 当通过、
不会因为"缓存还在有效期内"就放行一个已撤销的 Agent。
"""
import json
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from profile import (b64u, fp, judge, norm_aip, norm_agis, norm_clawdentity,
                     sign_jwt, verify_jwt)

NOW = datetime(2026, 11, 19, 9, 0, tzinfo=timezone.utc)
S = int(NOW.timestamp())
R = Ed25519PrivateKey.generate()
EVIL = Ed25519PrivateKey.generate()
RESULTS = []


def case(cid, desc, got, want):
    ok = got == want
    RESULTS.append({"id": cid, "desc": desc, "got": got, "want": want, "pass": ok})
    print(f"{'PASS' if ok else 'FAIL'}  {cid}  {desc}\n       got={got} want={want}")


def aip(revocations, iat=None, exp=None, jti="crl-0001"):
    return {"iss": "https://registry-a", "jti": jti,
            "iat": iat if iat is not None else S - 60,
            "exp": exp if exp is not None else S + 900,
            "revocations": revocations}


def agis(entity, status, updated_at):
    return {"agent_id": entity, "status": status, "updated_at": updated_at,
            "cache": {"ttl_seconds": 60}}


def clawd(revocations, iat=None, exp=None):
    claims = {"iss": "https://registry-c", "jti": "crl-01",
              "iat": iat if iat is not None else S - 120,
              "exp": exp if exp is not None else S + 600,
              "revocations": revocations}
    return claims


# ---------- AIP ----------
s_aip = norm_aip(aip([{"agentDid": "agent-X", "type": "full_revoke", "jti": "rev-1"}]))
case("P01", "AIP CRL 新鲜 + 实体被撤销 → DENY",
     judge(s_aip, "agent-X", NOW, {}, strict=False)[0], "DENY")
case("P02", "AIP CRL 新鲜 + 实体未涉及 → ALLOW（宽松模式）",
     judge(s_aip, "agent-Y", NOW, {}, strict=False)[0], "ALLOW")
case("P03", "AIP CRL 在 strict 模式 → 缺历史证明，拒绝",
     judge(s_aip, "agent-Y", NOW, {}, strict=True), ("DENY", "no_history_proof"))
s_scope = norm_aip(aip([{"agentDid": "agent-X", "type": "scope_revoke",
                        "scopes_revoked": ["payments"], "jti": "rev-2"}]))
case("P04", "AIP scope_revoke 只封 payments：请求 payments → DENY",
     judge(s_scope, "agent-X", NOW, {}, strict=False, request_scope="payments")[0], "DENY")
case("P05", "AIP scope_revoke 同一条：请求 read → ALLOW",
     judge(s_scope, "agent-X", NOW, {}, strict=False, request_scope="read")[0], "ALLOW")
case("P06", "AIP CRL 超 max_age（40 分钟 > 15）→ DENY",
     judge(norm_aip(aip([], iat=S - 2400)), "agent-Y", NOW, {}, strict=False),
     ("DENY", "stale(fail_closed)"))

# ---------- AgIS ----------
case("P07", "AgIS status=revoked → DENY",
     judge(norm_agis(agis("agent-X", "revoked", "2026-11-19T08:59:30Z")), "agent-X", NOW, {}),
     ("DENY", "status:revoked"))
case("P08", "AgIS status=unknown → DENY（不交本地策略）",
     judge(norm_agis(agis("agent-X", "unknown", "2026-11-19T08:59:30Z")), "agent-X", NOW, {}),
     ("DENY", "status:unknown(fail_closed)"))
case("P09", "AgIS status=active 但 cache ttl 已过（5 分钟前更新）→ DENY",
     judge(norm_agis(agis("agent-X", "active", "2026-11-19T08:55:00Z")), "agent-X", NOW, {}),
     ("DENY", "expired"))
case("P10", "AgIS status=compromised → DENY",
     judge(norm_agis(agis("agent-X", "compromised", "2026-11-19T08:59:30Z")), "agent-X", NOW, {}),
     ("DENY", "status:compromised"))

# ---------- Clawdentity（签名 JWT CRL）---------
tok = sign_jwt(clawd([{"agentDid": "agent-X", "jti": "rev-9"}]), R)
claims = verify_jwt(tok, R.public_key())
s_cl = norm_clawdentity(claims)
case("P11", "Clawdentity CRL 签名有效 + 实体被撤销 → DENY",
     judge(s_cl, "agent-X", NOW, {}, strict=False)[0], "DENY")
case("P12", "Clawdentity CRL 超出其 max age（20 分钟 > 15）→ DENY（覆盖 fail-open）",
     judge(norm_clawdentity(clawd([], iat=S - 1200, exp=S + 6000)), "agent-Y", NOW, {}, strict=False),
     ("DENY", "stale(fail_closed)"))

# ---------- 附加：重放与伪造 ----------
case("P13", "旧 CRL 重放（iat 回退）→ DENY",
     judge(s_cl, "agent-X", NOW, {"https://registry-c": S - 60}, strict=False),
     ("DENY", "replay(older_iat)"))
bad = tok.rsplit(".", 1)[0] + "." + b64u(EVIL.sign(b"x"))
try:
    verify_jwt(bad, R.public_key())
    verdict = ("ALLOW", "sig_ok")
except ValueError:
    verdict = ("DENY", "bad_signature")
case("P14", "Clawdentity CRL 签名伪造 → DENY", verdict, ("DENY", "bad_signature"))

n = sum(1 for r in RESULTS if r["pass"])
print(f"\n{'-'*46}\ncases={len(RESULTS)} pass={n} fail={len(RESULTS)-n}")
with open("profile_results.json", "w", encoding="utf-8") as fh:
    json.dump({"total": len(RESULTS), "pass": n, "results": RESULTS}, fh, ensure_ascii=False, indent=2)
raise SystemExit(0 if n == len(RESULTS) else 1)
