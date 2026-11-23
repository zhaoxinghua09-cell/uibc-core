# -*- coding: utf-8 -*-
"""真实第三方产物互操作（第二家）：agentpin 0.3.0 的撤销文档。

事实来源：PyPI agentpin 0.3.0 解包后的 agentpin/revocation.py 与 pinning.py。
- 撤销文档结构：agentpin_version / entity / updated_at / revoked_credentials /
  revoked_agents / revoked_keys —— **无签名、无序号**。
- 钉扎：TOFU 按 domain，指纹变更 → KEY_PIN_MISMATCH 硬失败（这点它做得好）。
"""
import importlib
import json
import sys
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives import serialization
from pathlib import Path

PKG = r"C:\Users\Administrator\AppData\Local\Temp\xlgd_audit\_pin\agentpin-0.3.0"
sys.path.insert(0, PKG)

from agentpin import revocation as ap_rev          # noqa: E402
from agentpin.pinning import KeyPinStore, PinningResult  # noqa: E402

from profile import judge                          # noqa: E402

NOW = datetime(2026, 11, 19, 9, 0, tzinfo=timezone.utc)
RESULTS = []


def case(cid, desc, got, want):
    ok = got == want
    RESULTS.append({"id": cid, "desc": desc, "got": str(got), "want": str(want), "pass": ok})
    print(f"{'PASS' if ok else 'FAIL'}  {cid}  {desc}\n       got={got} want={want}")


def snap_from_agentpin(doc, age_minutes=0, now=NOW):
    """agentpin 撤销文档 -> 我们的快照。它没有 serial，也没有签名与历史证明。"""
    return {
        "kind": "agentpin",
        "issuer": doc.get("entity"),
        "issued_at": int((now - timedelta(minutes=age_minutes)).timestamp()),
        "expires_at": None,
        "history_proof": False,
        "entries": [{"entity": a["agent_id"], "type": "full_revoke", "scopes": [], "serial": None}
                    for a in doc.get("revoked_agents", [])],
    }


# ---------- 用真实第三方函数构造文档 ----------
doc = ap_rev.build_revocation_document("example.com")
ap_rev.add_revoked_agent(doc, "agent-X", "key_compromise")
ap_rev.add_revoked_credential(doc, "jti-001", "policy_violation")
ap_rev.add_revoked_key(doc, "kid-9", "key_compromise")

case("P22", "第三方文档撤销了 agent-X → 本 profile DENY",
     judge(snap_from_agentpin(doc), "agent-X", NOW, {}, strict=False)[0], "DENY")
case("P23", "第三方文档未涉及 agent-Y → ALLOW（宽松）",
     judge(snap_from_agentpin(doc), "agent-Y", NOW, {}, strict=False)[0], "ALLOW")
case("P24", "strict 模式：该文档无历史证明 → DENY",
     judge(snap_from_agentpin(doc), "agent-Y", NOW, {}, strict=True),
     ("DENY", "no_history_proof"))
case("P25", "该文档的键里没有 sig / serial / chain 字段（可被整体替换或回放而不被察觉）",
     sorted(k for k in doc if k in {"sig", "serial", "chain_head", "signature"}), [])
case("P26", "文档超 15 分钟未更新 → DENY:stale",
     judge(snap_from_agentpin(doc, age_minutes=30), "agent-Y", NOW, {}, strict=False),
     ("DENY", "stale(fail_closed)"))

# ---------- 钉扎：它做得好的一点，我们也要有 ----------
# ---------- 钉扎：用它自己的 EC P-256 密钥生成真实 JWK ----------
from agentpin.crypto import generate_key_pair        # noqa: E402
from agentpin.jwk import pem_to_jwk                  # noqa: E402

_priv_pem, pub_pem = generate_key_pair()      # 返回 (私钥 PEM, 公钥 PEM)
jwk1 = pem_to_jwk(pub_pem, "k1")
store = KeyPinStore()
case("P27", "首次见到 → 钉扎（first_use）", store.check_and_pin("example.com", jwk1), PinningResult.FIRST_USE)
case("P28", "同钥再见 → MATCHED", store.check_and_pin("example.com", jwk1), PinningResult.MATCHED)
jwk2 = dict(jwk1, x=jwk1["x"][::-1])
case("P29", "同 kid 换钥 → CHANGED（它硬失败，这点优于它的撤销侧）",
     store.check_and_pin("example.com", jwk2), PinningResult.CHANGED)
# 它只支持 EC P-256：OKP/Ed25519 的 JWK 会在 thumbprint 处抛 KeyError('y')
okp = {"kty": "OKP", "crv": "Ed25519", "kid": "k1", "x": "11qYAYKxCrfVS_7TyWQHOg7hcvPapiMlrwIaaPcHURo"}
from agentpin.jwk import jwk_thumbprint               # noqa: E402
try:
    jwk_thumbprint(okp)
    okp_result = "no_error"
except KeyError as e:
    okp_result = f"KeyError:{e}"
case("P30", "Ed25519(OKP) 的 JWK 在其 thumbprint 实现上直接抛错", okp_result, "KeyError:'y'")

n = sum(1 for r in RESULTS if r["pass"])
print(f"\n{'-'*50}\ncases={len(RESULTS)} pass={n} fail={len(RESULTS)-n}")
with open("agentpin_real_interop_results.json", "w", encoding="utf-8") as fh:
    json.dump({"total": len(RESULTS), "pass": n, "results": RESULTS}, fh, ensure_ascii=False, indent=2)
raise SystemExit(0 if n == len(RESULTS) else 1)
