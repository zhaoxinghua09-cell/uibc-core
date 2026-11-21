# -*- coding: utf-8 -*-
"""真实第三方产物互操作：aip-protocol 0.4.0 的 RevocationStore 记录 -> 本 profile 判定。

与 P01–P14 的区别：那些样本是我按草案文本构造的；这里的记录由
第三方实现的真实类（RevocationRecord / RevocationStore）产生。

第三方源码：PyPI aip-protocol 0.4.0（解包后直接加载 revocation.py，
不安装、不执行其网络代码）。
"""
import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone

from profile import judge

AIP_REV = r"C:\Users\Administrator\AppData\Local\Temp\xlgd_audit\_aipdl\aip_protocol-0.4.0\aip_protocol\revocation.py"

spec = importlib.util.spec_from_file_location("aip_revocation", AIP_REV)
aip = importlib.util.module_from_spec(spec)
sys.modules["aip_revocation"] = aip
spec.loader.exec_module(aip)

NOW = datetime(2026, 11, 19, 9, 0, tzinfo=timezone.utc)
RESULTS = []


def case(cid, desc, got, want):
    ok = got == want
    RESULTS.append({"id": cid, "desc": desc, "got": got, "want": want, "pass": ok})
    print(f"{'PASS' if ok else 'FAIL'}  {cid}  {desc}\n       got={got} want={want}")


def snap_from_store(store, now, age_minutes=0, serial=None):
    """把第三方 store 归一化成我们的快照：它没有 serial，也没有历史证明。"""
    entries = []
    for agent_id, rec in store._revocations.items():
        entries.append({"entity": agent_id, "type": "full_revoke",
                        "scopes": [] if rec.scope == "global" else [rec.scope],
                        "serial": serial})
    return {"kind": "aip_store", "issuer": "aip-protocol/0.4.0",
            "issued_at": int((now - timedelta(minutes=age_minutes)).timestamp()),
            "expires_at": None, "history_proof": False, "entries": entries}


# ---------- 真实产生撤销记录 ----------
st = aip.RevocationStore()
st.revoke("agent-X", reason="key_compromise", revoked_by="did:principal:1", scope="global")
case("P15", "第三方永久撤销 → 本 profile DENY",
     judge(snap_from_store(st, NOW), "agent-X", NOW, {}, strict=False)[0], "DENY")

st2 = aip.RevocationStore()
st2.suspend("agent-Y", duration_seconds=3600, reason="review", revoked_by="did:principal:1")
case("P16", "第三方暂停中 → 本 profile DENY（不看它是否会自行恢复）",
     judge(snap_from_store(st2, NOW), "agent-Y", NOW, {}, strict=False)[0], "DENY")

st3 = aip.RevocationStore()
# 用真实的"暂停已过期"状态：负时长使 suspended_until 落在过去
st3.suspend("agent-Z", duration_seconds=-1, reason="review", revoked_by="did:principal:1")
case("P17", "第三方暂停已过期：它自己 is_revoked=False（fail-open）",
     st3.is_revoked("agent-Z"), False)
case("P18", "同一状态喂给本 profile：仍未拿到可信状态 → DENY:not_revoked 不成立，按无历史证明处理后 ALLOW（暴露缺口）",
     judge(snap_from_store(st3, NOW, age_minutes=20), "agent-Z", NOW, {}, strict=False)[0], "DENY")

st4 = aip.RevocationStore()
st4.revoke("agent-W", reason="policy", revoked_by="did:principal:1", scope="global")
st4.reinstate("agent-W")
case("P19", "第三方 reinstate 会删除记录（历史被抹掉）", len(st4._revocations), 0)
case("P20", "本 profile 在 strict 模式：无历史证明 → 一律 DENY",
     judge(snap_from_store(st4, NOW), "agent-W", NOW, {}, strict=True),
     ("DENY", "no_history_proof"))

# ---------- 结构性缺口（代码级事实） ----------
case("P21", "第三方 store 无单调序号字段（无法检测旧快照重放）",
     hasattr(aip.RevocationStore(), "serial") or hasattr(aip.RevocationRecord, "serial"), False)

n = sum(1 for r in RESULTS if r["pass"])
print(f"\n{'-'*50}\ncases={len(RESULTS)} pass={n} fail={len(RESULTS)-n}")
with open("aip_real_interop_results.json", "w", encoding="utf-8") as fh:
    json.dump({"total": len(RESULTS), "pass": n, "results": RESULTS}, fh, ensure_ascii=False, indent=2)
raise SystemExit(0 if n == len(RESULTS) else 1)
