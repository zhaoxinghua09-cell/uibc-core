"""Head co-signature + append-only head chain.

Why: our anchors commit a root, but the head that says "this is the newest
package" is signed by us alone, and nothing says the log only grew. A single
signer cannot witness itself, and a root that matches proves nothing about
size. Two fixes here, both borrowed from public practice and both going
further than the drafts that raised the problem:

  1. cosign : two roles (owner, witness) over the same head, keys must differ.
  2. chain  : successive heads carry the tree size INSIDE the signed message,
              so no one can claim a size the signers did not see; and the
              sequence must only grow, with the root changing whenever the
              size does. The SCITT decision-provenance draft notes its
              anchoring extension does not yet check that the log only grew;
              this check is that gap closed.

Usage:
  python tools/cosign_head.py sign  --head H --tree-size N --seed K --role owner   --out f.json
  python tools/cosign_head.py sign  --head H --tree-size N --seed K --role witness --out f.json
  python tools/cosign_head.py verify --file f.json --owner-seed K --witness-seed K
  python tools/cosign_head.py chain  --file chain.json --owner-seed K --witness-seed K

Exit: 0 all checks hold; 1 something does not; 2 bad input.
"""
import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from uibc_core import ed25519  # noqa: E402
from uibc_core.canonical import canonicalize  # noqa: E402

ROLES = ("owner", "witness")


def seed_bytes(path):
    raw = open(path, encoding="utf-8").read().strip()
    if raw.startswith("ed25519:"):
        raw = raw.split(":", 1)[1]
    return bytes.fromhex(raw)


def key_id(seed):
    return "sha256:" + hashlib.sha256(ed25519.publickey(seed)).hexdigest()


def message(head, role, tree_size, vds=None):
    """The signed statement. tree_size and vds are inside it, so neither the size
    nor the hash identity a signer saw can be swapped afterwards."""
    body = {"head": head, "role": role}
    if tree_size is not None:
        body["tree_size"] = tree_size
    if vds is not None:
        body["vds"] = vds
    return canonicalize(body)


def cmd_sign(a):
    seed = seed_bytes(a.seed)
    if os.path.exists(a.out):
        body = json.load(open(a.out, encoding="utf-8"))
        if (body.get("head") != a.head or body.get("tree_size") != a.tree_size
                or body.get("vds") != a.vds):
            print("head, tree_size or vds differs from the file being extended; refusing")
            return 2
    else:
        body = {"v": "uibc-head-cosign/2", "head": a.head, "vds": a.vds,
                "tree_size": a.tree_size, "signatures": []}
        if a.tree_size is None:
            del body["tree_size"]
    if any(s["role"] == a.role for s in body["signatures"]):
        print(f"role {a.role} already signed; a role signs once")
        return 1
    body["signatures"].append({
        "role": a.role,
        "key_id": key_id(seed),
        "sig": ed25519.sign(seed, message(a.head, a.role, a.tree_size, a.vds)).hex(),
    })
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(body, f, ensure_ascii=False, indent=2)
    print(f"signed as {a.role}: {body['signatures'][-1]['key_id']}")
    return 0


def check_signed(body, seeds):
    """Both roles present, each verifiable under its own key, keys distinct."""
    roles = {s["role"]: s for s in body.get("signatures", [])}
    reasons = []
    for role in ROLES:
        if role not in roles:
            reasons.append(f"missing {role} signature")
            continue
        try:
            ok = ed25519.verify(ed25519.publickey(seeds[role]),
                                message(body["head"], role, body.get("tree_size"),
                                        body.get("vds")),
                                bytes.fromhex(roles[role]["sig"]))
        except Exception:
            ok = False
        if not ok:
            reasons.append(f"{role} signature does not verify under the supplied key")
    ids = {roles[r]["key_id"] for r in roles if r in roles}
    if len(ids) < 2:
        reasons.append("owner and witness are the same key: one key cannot witness itself")
    return reasons, len(ids)


def cmd_verify(a):
    body = json.load(open(a.file, encoding="utf-8"))
    seeds = {"owner": seed_bytes(a.owner_seed), "witness": seed_bytes(a.witness_seed)}
    reasons, distinct = check_signed(body, seeds)
    # vds: the hash identity the reader trusts. A signed vds that differs from it
    # would let peaks computed under two hash functions look comparable.
    if body.get("vds") != a.vds:
        reasons.append(f"vds is {body.get('vds')!r}, reader trusts {a.vds!r}")
    print(json.dumps({"head": body.get("head"), "tree_size": body.get("tree_size"),
                      "vds": body.get("vds"),
                      "distinct_keys": distinct, "ok": not reasons,
                      "reasons": reasons}, ensure_ascii=False, indent=2))
    return 0 if not reasons else 1


def cmd_chain(a):
    """A sequence of signed heads: sizes only grow, and a new size means a new root."""
    body = json.load(open(a.file, encoding="utf-8"))
    entries = body.get("chain", body) if isinstance(body, dict) else body
    seeds = {"owner": seed_bytes(a.owner_seed), "witness": seed_bytes(a.witness_seed)}
    reasons = []
    prev = None
    for i, e in enumerate(entries):
        sig_reasons, _ = check_signed(e, seeds)
        if sig_reasons:
            reasons.append(f"#{i}: " + "; ".join(sig_reasons))
        if e.get("vds") != a.vds:
            reasons.append(f"#{i}: vds is {e.get('vds')!r}, reader trusts {a.vds!r}; "
                           f"accumulators under two hash functions are not comparable")
        size = e.get("tree_size")
        if size is None:
            reasons.append(f"#{i}: no tree_size, so 'only grew' cannot be checked")
        elif prev is None:
            # The first head has no predecessor: whatever it says about its size
            # is the signers' assertion, not a fact anyone can check. Same point
            # the MMR receipts profile makes about verifying from the empty tree.
            # It must be labelled, so a reader never mistakes bootstrap trust for
            # evidence of growth.
            if e.get("bootstrap") is not True:
                reasons.append(f"#{i}: first head has no predecessor; it MUST be "
                               f"marked bootstrap, since growth is unprovable here")
        elif prev is not None:
            if size < prev["tree_size"]:
                reasons.append(f"#{i}: size shrank {prev['tree_size']} -> {size}")
            elif size == prev["tree_size"] and e["head"] != prev["head"]:
                reasons.append(f"#{i}: same size {size} but different root (fork)")
            elif size > prev["tree_size"] and e["head"] == prev["head"]:
                reasons.append(f"#{i}: size grew to {size} with an unchanged root")
        prev = e if size is not None else prev
    print(json.dumps({"entries": len(entries), "ok": not reasons,
                      "reasons": reasons}, ensure_ascii=False, indent=2))
    return 0 if not reasons else 1


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sign")
    s.add_argument("--head", required=True)
    s.add_argument("--tree-size", type=int, default=None)
    s.add_argument("--seed", required=True)
    s.add_argument("--role", required=True, choices=list(ROLES))
    s.add_argument("--out", required=True)
    s.add_argument("--vds", default="sha256",
                   help="hash identity signed with the head (default sha256)")
    for name in ("verify", "chain"):
        v = sub.add_parser(name)
        v.add_argument("--file", required=True)
        v.add_argument("--vds", default="sha256",
                       help="hash identity this reader trusts (default sha256)")
        v.add_argument("--owner-seed", required=True)
        v.add_argument("--witness-seed", required=True)
    a = ap.parse_args()
    return {"sign": cmd_sign, "verify": cmd_verify, "chain": cmd_chain}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
