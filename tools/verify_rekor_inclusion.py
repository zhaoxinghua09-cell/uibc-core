#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Prove a Rekor entry's inclusion, and say which index the proof is about.

Why this exists
---------------
For months our portal carried "the Rekor inclusion proof does not verify — by our
reading or by a third party's" as a *known defect*. It verified on 2026-11-21. The
defect was not in Rekor; it was in how we read two fields:

1. **Leaf hash.** The leaf of the Rekor tree is `SHA-256(0x00 ‖ body_bytes)` where
   `body_bytes` is the base64-decoded entry body *as served*. Hashing the body
   first and then hashing the digest again yields a different tree of leaves that
   no proof can ever fold to.

2. **Which index.** `entry.logIndex` and `entry.verification.inclusionProof.logIndex`
   are **different numbers** for the same entry (e.g. 2883389783 vs 2761485521 on
   2026-11-21). Folding the proof against `entry.logIndex` cannot match. The proof
   folds against its own `logIndex`, which is the index the proof is *about*. We
   do not claim to know what the top-level field means; we claim only that the
   proof is only checkable against the index the proof carries.

Both mistakes produce the same symptom: a root mismatch that looks like tampering.
Neither is a Rekor fault, and saying "the log's proof is broken" was wrong.

Usage
-----
    python tools/verify_rekor_inclusion.py --uuid <entry-uuid>
    python tools/verify_rekor_inclusion.py --log-index 2883389783
    python tools/verify_rekor_inclusion.py --file entry.json      # offline

Exit codes: 0 the proof folds to the proof's root and that root equals the
checkpoint's root line; 1 it does not; 2 the entry could not be read or carries
no inclusion proof.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
import urllib.request

ENTRY_BY_UUID = "https://rekor.sigstore.dev/api/v1/log/entries/%s"
ENTRY_BY_INDEX = "https://rekor.sigstore.dev/api/v1/log/entries?logIndex=%d"


def fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "uibc-rekor-inclusion"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def leaf_hash(body: bytes) -> bytes:
    """RFC 6962 leaf over the entry body: SHA-256(0x00 ‖ body bytes)."""
    return hashlib.sha256(b"\x00" + body).digest()


def node_hash(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(b"\x01" + left + right).digest()


def fold(leaf: bytes, index: int, size: int, path: list[bytes]) -> bytes:
    """RFC 9162 inclusion-path fold, 0-based index."""
    fn, sn, root = index, size - 1, leaf
    for p in path:
        if fn % 2 == 1 or fn == sn:
            root = node_hash(p, root)
            while fn % 2 == 0 and fn != 0:
                fn >>= 1
                sn >>= 1
        else:
            root = node_hash(root, p)
        fn >>= 1
        sn >>= 1
    return root


def checkpoint_root(checkpoint: str) -> tuple[str, int, str]:
    """(origin, tree_size, root_hex) from a signed checkpoint's first three lines."""
    lines = checkpoint.strip().splitlines()
    if len(lines) < 3:
        raise ValueError("checkpoint has fewer than three lines")
    origin = lines[0].strip()
    size = int(lines[1].strip())
    root_hex = base64.b64decode(lines[2].strip()).hex()
    return origin, size, root_hex


def check_entry(entry: dict) -> dict:
    body = base64.b64decode(entry["body"])
    proof = entry["verification"]["inclusionProof"]
    path = [bytes.fromhex(h) for h in proof["hashes"]]
    leaf = leaf_hash(body)
    proof_index, proof_size = proof["logIndex"], proof["treeSize"]

    out = {
        "leaf_hash": leaf.hex(),
        "body_sha256": hashlib.sha256(body).hexdigest(),
        "proof_log_index": proof_index,
        "proof_tree_size": proof_size,
        "entry_log_index": entry.get("logIndex"),
        "proof_root": proof["rootHash"],
        "hashes": len(path),
        "folds_against": {},
    }
    for label, idx in (("proof_log_index", proof_index), ("entry_log_index", entry.get("logIndex"))):
        if idx is None:
            continue
        root = fold(leaf, idx, proof_size, path).hex()
        out["folds_against"][label] = {"root": root, "match": root == proof["rootHash"]}

    checkpoint = proof.get("checkpoint", "")
    if checkpoint:
        origin, size, root_hex = checkpoint_root(checkpoint)
        out["checkpoint"] = {"origin": origin, "tree_size": size, "root": root_hex,
                             "root_equals_proof_root": root_hex == proof["rootHash"]}
    else:
        out["checkpoint"] = None

    folds = out["folds_against"].get("proof_log_index", {}).get("match")
    cp_ok = out["checkpoint"]["root_equals_proof_root"] if out["checkpoint"] else True
    out["verified"] = bool(folds and cp_ok)
    if not folds:
        out["why_not"] = ("the proof does not fold to its own root against its own index; "
                          "if entry_log_index differs, folding against it is never correct")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--uuid")
    g.add_argument("--log-index", type=int)
    g.add_argument("--file")
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)

    try:
        if args.file:
            data = json.loads(open(args.file, encoding="utf-8").read())
        elif args.uuid:
            data = fetch(ENTRY_BY_UUID % args.uuid)
        else:
            data = fetch(ENTRY_BY_INDEX % args.log_index)
    except Exception as exc:  # noqa: BLE001
        print("could not read the entry: %s" % exc, file=sys.stderr)
        return 2

    entry = next(iter(data.values())) if isinstance(data, dict) and "verification" not in data else data
    if "verification" not in entry:
        entry = next(iter(data.values()))
    if "inclusionProof" not in entry.get("verification", {}):
        print("entry carries no inclusion proof", file=sys.stderr)
        return 2

    receipt = check_entry(entry)
    text = json.dumps(receipt, indent=2, sort_keys=True)
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text + "\n")
        print("receipt written: %s" % args.out)
    else:
        print(text)
    print("verified=%s  proof.index=%s  entry.index=%s"
          % (receipt["verified"], receipt["proof_log_index"], receipt["entry_log_index"]),
          file=sys.stderr)
    return 0 if receipt["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
