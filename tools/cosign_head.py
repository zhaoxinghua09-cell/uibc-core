"""Head co-signature: two seats sign the same head, and one missing is not enough.

Why: our anchors commit a root, but the head that says "this is the newest
package" is signed by us alone. A single signer cannot witness itself. Sigstore
solves this with a signed checkpoint plus independent cosigners; we solve it with
two roles that must be held by different keys.

    sign   : add one signature (role owner | witness) over the head
    verify : require both roles, each verifiable under its own key, all naming
             the same head, and the two key ids distinct

Usage:
  python tools/cosign_head.py sign   --head <sha256:...> --seed <keyfile> --role owner   --out head.json
  python tools/cosign_head.py sign   --head <sha256:...> --seed <keyfile> --role witness --out head.json
  python tools/cosign_head.py verify --file head.json --owner-seed <keyfile> --witness-seed <keyfile>

Exit: sign 0 ok/1 duplicate role/2 error; verify 0 both hold, 1 not, 2 error.
"""
import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from uibc_core import ed25519  # noqa: E402


def seed_bytes(path):
    raw = open(path, encoding="utf-8").read().strip()
    if raw.startswith("ed25519:"):
        raw = raw.split(":", 1)[1]
    return bytes.fromhex(raw)


def key_id(seed):
    return "sha256:" + hashlib.sha256(ed25519.publickey(seed)).hexdigest()


def message(head, role):
    return json.dumps({"head": head, "role": role}, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def cmd_sign(a):
    seed = seed_bytes(a.seed)
    body = json.load(open(a.out, encoding="utf-8")) if os.path.exists(a.out) else {
        "v": "uibc-head-cosign/1", "head": a.head, "signatures": []}
    if body.get("head") != a.head:
        print("HEAD DIFFERS from the file being extended; refusing")
        return 2
    if any(s["role"] == a.role for s in body["signatures"]):
        print(f"role {a.role} already signed; a role signs once")
        return 1
    body["signatures"].append({
        "role": a.role,
        "key_id": key_id(seed),
        "sig": ed25519.sign(seed, message(a.head, a.role)).hex(),
    })
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(body, f, ensure_ascii=False, indent=2)
    print(f"signed as {a.role}: {body['signatures'][-1]['key_id']} -> {a.out}")
    return 0


def cmd_verify(a):
    body = json.load(open(a.file, encoding="utf-8"))
    seeds = {"owner": seed_bytes(a.owner_seed), "witness": seed_bytes(a.witness_seed)}
    roles = {s["role"]: s for s in body.get("signatures", [])}
    reasons = []
    for role in ("owner", "witness"):
        if role not in roles:
            reasons.append(f"missing {role} signature")
            continue
        s = roles[role]
        try:
            ok = ed25519.verify(ed25519.publickey(seeds[role]),
                                message(body["head"], role), bytes.fromhex(s["sig"]))
        except Exception:
            ok = False
        if not ok:
            reasons.append(f"{role} signature does not verify under the supplied key")
    ids = {roles[r]["key_id"] for r in roles if r in roles}
    if len(ids) < 2:
        reasons.append("owner and witness are the same key: one key cannot witness itself")
    print(json.dumps({"head": body.get("head"), "roles": sorted(roles),
                      "distinct_keys": len(ids), "ok": not reasons,
                      "reasons": reasons}, ensure_ascii=False, indent=2))
    return 0 if not reasons else 1


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sign")
    s.add_argument("--head", required=True)
    s.add_argument("--seed", required=True)
    s.add_argument("--role", required=True, choices=["owner", "witness"])
    s.add_argument("--out", required=True)
    v = sub.add_parser("verify")
    v.add_argument("--file", required=True)
    v.add_argument("--owner-seed", required=True)
    v.add_argument("--witness-seed", required=True)
    a = ap.parse_args()
    return cmd_sign(a) if a.cmd == "sign" else cmd_verify(a)


if __name__ == "__main__":
    sys.exit(main())
