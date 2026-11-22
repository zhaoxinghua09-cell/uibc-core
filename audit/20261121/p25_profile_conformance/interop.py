# -*- coding: utf-8 -*-
"""互操作判定 CLI —— 第三方拿到撤销产物后，一条命令得到判定。

用法：
  python interop.py --format agentpin     --file doc.json  --entity agent-X [--strict]
  python interop.py --format agis         --file status.json
  python interop.py --format aip          --file crl.json   --entity did:aip:abc [--strict]
  python interop.py --format clawdentity  --token crl.jwt --pubkey <hex> --entity did:x

输出：JSON（verdict / reason / snapshot 摘要），并给出可解释原因。
退出码：0 = ALLOW，1 = DENY（便于脚本集成）。
"""
import argparse
import base64
import json
import sys
from datetime import datetime, timezone

from profile import (judge, norm_aip, norm_agis, norm_clawdentity,
                     verify_jwt, unb64u)


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def to_snapshot(args):
    if args.format == "agentpin":
        doc = load(args.file)
        return {
            "kind": "agentpin", "issuer": doc.get("entity"),
            "issued_at": _iso(doc.get("updated_at")),
            "expires_at": None, "history_proof": False,
            "entries": [{"entity": a["agent_id"], "type": "full_revoke",
                         "scopes": [], "serial": None}
                        for a in doc.get("revoked_agents", [])],
        }
    if args.format == "agis":
        return norm_agis(load(args.file))
    if args.format == "aip":
        return norm_aip(load(args.file))
    if args.format == "clawdentity":
        if not args.pubkey:
            sys.exit("clawdentity 需要 --pubkey（Raw Ed25519 公钥，hex 或 base64url）")
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        raw = bytes.fromhex(args.pubkey) if all(c in "0123456789abcdefABCDEF" for c in args.pubkey) \
            else unb64u(args.pubkey)
        try:
            claims = verify_jwt(args.token, Ed25519PublicKey.from_public_bytes(raw))
        except ValueError:
            return {"kind": "clawdentity", "issuer": None, "issued_at": None,
                    "expires_at": None, "history_proof": False, "entries": [],
                    "sig_error": True}
        return norm_clawdentity(claims)
    raise SystemExit(f"unknown format {args.format}")


def _iso(s):
    if not s:
        return None
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--format", required=True,
                    choices=["agentpin", "agis", "aip", "clawdentity"])
    ap.add_argument("--file")
    ap.add_argument("--token")
    ap.add_argument("--pubkey")
    ap.add_argument("--entity")
    ap.add_argument("--scope", default=None)
    ap.add_argument("--max-age", type=int, default=15, dest="max_age")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--state", help="已见状态 JSON（用于重放检测）")
    a = ap.parse_args()

    snap = to_snapshot(a)
    if snap.get("sig_error"):
        print(json.dumps({"verdict": "DENY", "reason": "bad_signature"}, ensure_ascii=False))
        return 1
    state = load(a.state) if a.state else {}
    verdict, reason = judge(snap, a.entity or "", datetime.now(timezone.utc),
                            state, a.max_age, a.strict, a.scope)
    print(json.dumps({"verdict": verdict, "reason": reason,
                      "format": a.format, "entities": len(snap.get("entries", [])),
                      "strict": a.strict, "max_age_minutes": a.max_age},
                     ensure_ascii=False, indent=2))
    return 0 if verdict == "ALLOW" else 1


if __name__ == "__main__":
    sys.exit(main())
