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

Consistency (a different question)
----------------------------------
    python tools/verify_rekor_inclusion.py --consistency --from receipt.json

Inclusion at one size does not show that the earlier tree is a prefix of the
later one. `--consistency` takes an earlier head (a receipt from this tool, or a
checkpoint text), asks the log for the consistency proof between that size and
the current head, and folds it with the RFC 6962 algorithm ported from
transparency-dev/merkle `proof/verify.go`. Both checkpoints' signatures are
verified. Heads from different origins (different tree ids) are not compared:
a consistency proof across a shard boundary is not a claim this tool makes.
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
LOG_PUBLIC_KEY = "https://rekor.sigstore.dev/api/v1/log/publicKey"
LOG_META = "https://rekor.sigstore.dev/api/v1/log"
LOG_PROOF = "https://rekor.sigstore.dev/api/v1/log/proof?firstSize=%d&lastSize=%d"


def fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "uibc-rekor-inclusion"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def fetch_text(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "uibc-rekor-inclusion"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


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


DASH = "\u2014 "  # the em dash that opens a signature line in the signed-note format


def split_note(checkpoint: str) -> tuple[bytes, list[tuple[str, bytes]]]:
    """Split a signed note into (signed bytes, [(name, signature bytes), ...]).

    The signed bytes are the three text lines each terminated by a newline, i.e. up
    to and including the newline that ends the root line; the blank line and the
    ``— name base64`` lines are not signed. The signature bytes start with a 4-byte
    key id (here the log id) followed by the raw signature (DER ECDSA for Rekor).
    """
    text = checkpoint.replace("\r\n", "\n")
    lines = text.split("\n")
    first_sig = next((i for i, line in enumerate(lines) if line.startswith(DASH)), None)
    if first_sig is None:
        raise ValueError("checkpoint carries no signature line")
    body = "\n".join(lines[:first_sig])
    if not body.endswith("\n"):
        body += "\n"
    sigs = []
    for line in lines[first_sig:]:
        if not line.startswith(DASH):
            continue
        rest = line[len(DASH):]
        name, _, b64 = rest.partition(" ")
        sigs.append((name, base64.b64decode(b64.strip())))
    return body.encode(), sigs


def _conclude(proof_ok: bool, sig_state) -> tuple[str, str]:
    """三值结论：True=已验 / False=已证伪 / None=无法判定（缺依赖或缺公钥）。

    规矩：无法判定不得报成已验。原实现用 `is not False`，等于把"没查"当成"没罪"。
    """
    if not proof_ok:
        return "failed", "inclusion/consistency proof does not hold"
    if sig_state is True:
        return "verified", ""
    if sig_state is False:
        return "failed", "checkpoint signature is invalid"
    return "inconclusive", ("checkpoint signature could not be checked "
                            "(cryptography missing or log key unavailable)")


def _exit_for(rec: dict) -> int:
    """0=verified / 1=failed / 3=inconclusive（与 docs/EXIT-CODES 对齐）"""
    c = rec.get("conclusion")
    if c == "verified":
        return 0
    if c == "inconclusive":
        return 3
    return 1


def verify_checkpoint_signature(checkpoint: str, key_pem: bytes) -> dict:
    """Verify the checkpoint's ECDSA signature against the log's public key."""
    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
    except ImportError:
        # The core is stdlib-only; the signature check is part of the `verify` extra.
        # Say so instead of crashing in the middle of a verification run.
        return {"verified": None, "curve": None, "signers": [],
                "why": 'cryptography is not installed; run: pip install "uibc-core[verify]"'}

    body, sigs = split_note(checkpoint)
    key = load_pem_public_key(key_pem)
    if not isinstance(key, ec.EllipticCurvePublicKey):
        return {"verified": False, "why": "the log key is not an EC public key",
                "curve": None, "signers": []}
    results = []
    for name, raw in sigs:
        if len(raw) < 5:
            results.append({"name": name, "key_id": None, "verified": False})
            continue
        key_id, sig = raw[:4].hex(), raw[4:]
        try:
            key.verify(sig, body, ec.ECDSA(hashes.SHA256()))
            ok = True
        except Exception:  # noqa: BLE001 - any verification failure is "not verified"
            ok = False
        results.append({"name": name, "key_id": key_id, "verified": ok})
    return {"verified": any(r["verified"] for r in results),
            "curve": key.curve.name, "signers": results}


# --- consistency between two tree sizes --------------------------------------
# Ported from transparency-dev/merkle proof/verify.go (Go, Apache-2.0), the
# implementation behind the RFC 6962 consistency proof. Inclusion at one size
# says nothing about an earlier tree being a prefix of it; a consistency proof
# does, and Rekor serves one at /api/v1/log/proof?firstSize=&lastSize=.

def _popcount(x: int) -> int:
    return bin(x).count("1")


def _tz(x: int) -> int:
    """Trailing zero bits; x must be positive."""
    return (x & -x).bit_length() - 1


def _chain_inner(seed: bytes, proof: list[bytes], index: int) -> bytes:
    for i, h in enumerate(proof):
        seed = node_hash(seed, h) if (index >> i) & 1 == 0 else node_hash(h, seed)
    return seed


def _chain_inner_right(seed: bytes, proof: list[bytes], index: int) -> bytes:
    for i, h in enumerate(proof):
        if (index >> i) & 1 == 1:
            seed = node_hash(h, seed)
    return seed


def _chain_border_right(seed: bytes, proof: list[bytes]) -> bytes:
    for h in proof:
        seed = node_hash(h, seed)
    return seed


def _decomp_incl_proof(index: int, size: int) -> tuple[int, int]:
    inner = (index ^ (size - 1)).bit_length()
    return inner, _popcount(index >> inner)


def _decomp_subtree_proof(start: int, end: int, size: int, border: int,
                          proof: list[bytes]) -> tuple[list[bytes], list[bytes]]:
    h = ((end - 1) ^ start).bit_length()
    fork_level = ((end - 1) ^ (size - 1)).bit_length()
    shift = _tz(end - start)
    sub_inner = min(h, fork_level) - shift
    inner = fork_level - shift
    sub_border = max(0, border - _popcount((end - 1) >> h))
    return proof[0:sub_inner], proof[inner:inner + sub_border]


def _root_from_subtree_consistency(start: int, end: int, size: int,
                                   proof: list[bytes], sub_root: bytes) -> bytes:
    if end == size:
        level = ((end - 1) ^ start).bit_length()
        index = start >> level
        want = _popcount(index)
        if len(proof) != want:
            raise ValueError("wrong proof size %d, want %d" % (len(proof), want))
        return _chain_border_right(sub_root, proof)

    fork_level, border = _decomp_incl_proof(end - 1, size)
    shift = _tz(end - start)
    inner = fork_level - shift

    seed, p_start = proof[0], 1
    if (end - start) == 1 << shift:
        seed, p_start = sub_root, 0
    if len(proof) != p_start + inner + border:
        raise ValueError("wrong proof size %d, want %d"
                         % (len(proof), p_start + inner + border))
    proof = proof[p_start:]
    mask = (end - 1) >> shift

    if p_start == 1:
        sub_inner, sub_border = _decomp_subtree_proof(start, end, size, border, proof)
        hash1 = _chain_inner_right(seed, sub_inner, mask)
        hash1 = _chain_border_right(hash1, sub_border)
        if hash1 != sub_root:
            raise ValueError("the proof does not chain to the earlier root")

    hash2 = _chain_inner(seed, proof[:inner], mask)
    return _chain_border_right(hash2, proof[inner:])


def root_from_consistency_proof(size1: int, size2: int, proof: list[bytes],
                                root1: bytes) -> bytes:
    """The root the second tree must have, given the first tree's root and a proof."""
    if size2 < size1:
        raise ValueError("size2 (%d) < size1 (%d)" % (size2, size1))
    if size1 == 0:
        raise ValueError("a consistency proof from an empty tree is meaningless")
    if size1 == size2:
        if proof:
            raise ValueError("size1=size2, but the proof is not empty")
        return root1
    if not proof:
        raise ValueError("empty proof")
    return _root_from_subtree_consistency(0, size1, size2, proof, root1)


def consistency_check(first_size: int, first_root_hex: str, first_checkpoint: str,
                      second_checkpoint: str, proof_hex: list[str],
                      key_pem: bytes | None = None) -> dict:
    """Verify that the earlier tree is a prefix of the later one, signatures included."""
    proof = [bytes.fromhex(h) for h in proof_hex]
    origin2, size2, root2 = checkpoint_root(second_checkpoint)
    out = {
        "first_size": first_size, "second_size": size2,
        "first_root": first_root_hex, "second_root": root2,
        "proof_nodes": len(proof),
        "origins": {"first": checkpoint_root(first_checkpoint)[0] if first_checkpoint else None,
                    "second": origin2},
    }
    out["same_origin"] = (out["origins"]["first"] == origin2) if first_checkpoint else None
    try:
        folded = root_from_consistency_proof(first_size, size2, proof,
                                             bytes.fromhex(first_root_hex)).hex()
        out["folded_root"] = folded
        out["folded_equals_second_root"] = folded == root2
    except ValueError as exc:
        out["folded_root"] = None
        out["folded_equals_second_root"] = False
        out["why_not"] = str(exc)

    sig2 = verify_checkpoint_signature(second_checkpoint, key_pem) if key_pem else {"verified": None}
    out["second_checkpoint_signature"] = sig2.get("verified")
    if first_checkpoint and key_pem:
        out["first_checkpoint_signature"] = verify_checkpoint_signature(
            first_checkpoint, key_pem).get("verified")
    else:
        out["first_checkpoint_signature"] = None

    _proof_ok = bool(out["folded_equals_second_root"]
                     and out["same_origin"] is not False)
    out["conclusion"], out["inconclusive_reason"] = _conclude(
        _proof_ok, sig2.get("verified"))
    out["verified"] = out["conclusion"] == "verified"
    return out


def check_entry(entry: dict, key_pem: bytes | None = None) -> dict:
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
                             "text": checkpoint,
                             "root_equals_proof_root": root_hex == proof["rootHash"]}
        if key_pem:
            sig = verify_checkpoint_signature(checkpoint, key_pem)
            out["checkpoint"]["signature"] = sig
            out["checkpoint"]["signature_verified"] = sig["verified"]
        else:
            out["checkpoint"]["signature_verified"] = None
    else:
        out["checkpoint"] = None

    folds = out["folds_against"].get("proof_log_index", {}).get("match")
    cp_ok = out["checkpoint"]["root_equals_proof_root"] if out["checkpoint"] else True
    sig_ok = out["checkpoint"]["signature_verified"] if out["checkpoint"] else None
    out["conclusion"], out["inconclusive_reason"] = _conclude(
        bool(folds and cp_ok), sig_ok)
    out["verified"] = out["conclusion"] == "verified"
    if not folds:
        out["why_not"] = ("the proof does not fold to its own root against its own index; "
                          "if entry_log_index differs, folding against it is never correct")
    return out


def load_log_key(path: str = "") -> bytes | None:
    if path:
        with open(path, "rb") as fh:
            return fh.read()
    try:
        return fetch_text(LOG_PUBLIC_KEY)
    except Exception as exc:  # noqa: BLE001 - offline use is legitimate
        print("checkpoint signature not verified (no log key: %s)" % exc, file=sys.stderr)
        return None


def load_checkpoint_file(path: str) -> str:
    """A checkpoint from a file: a receipt JSON (its checkpoint.text) or bare text."""
    raw = open(path, encoding="utf-8").read()
    if raw.lstrip().startswith("{"):
        data = json.loads(raw)
        for key in ("checkpoint_text", "text"):
            if key in data:
                return data[key]
        if isinstance(data.get("checkpoint"), dict) and "text" in data["checkpoint"]:
            return data["checkpoint"]["text"]
        raise ValueError("%s is JSON but carries no checkpoint text" % path)
    return raw


def live_tree_head() -> str:
    """/api/v1/log serves the active tree's signed checkpoint; that is our second head."""
    meta = fetch(LOG_META)
    return meta["signedTreeHead"]


def consistency_mode(from_file: str, to_file: str, key_pem: bytes | None) -> int:
    first = load_checkpoint_file(from_file)
    second = load_checkpoint_file(to_file) if to_file else live_tree_head()
    origin1, size1, root1 = checkpoint_root(first)
    _, size2, _ = checkpoint_root(second)
    if size2 < size1:
        print("the 'to' checkpoint is older than the 'from' checkpoint (%d < %d)"
              % (size2, size1), file=sys.stderr)
        return 2
    proof = fetch(LOG_PROOF % (size1, size2))["hashes"]
    receipt = consistency_check(size1, root1, first, second, proof, key_pem)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    print("consistency=%s  %d -> %d  signature=%s  same_origin=%s"
          % (receipt.get("conclusion", receipt["verified"]), size1, size2,
             receipt["second_checkpoint_signature"], receipt["same_origin"]),
          file=sys.stderr)
    return _exit_for(receipt)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--uuid")
    g.add_argument("--log-index", type=int)
    g.add_argument("--file")
    g.add_argument("--consistency", action="store_true",
                   help="verify that an earlier tree is a prefix of a later one")
    ap.add_argument("--from", dest="from_file", default="",
                    help="receipt JSON or checkpoint text for the earlier head")
    ap.add_argument("--to", dest="to_file", default="",
                    help="checkpoint text for the later head (default: the live signed tree head)")
    ap.add_argument("--out", default="")
    ap.add_argument("--log-key", default="",
                    help="PEM file for the log's public key (offline use); "
                         "otherwise fetched from %s" % LOG_PUBLIC_KEY)
    ap.add_argument("--no-signature", action="store_true",
                    help="skip checkpoint signature verification (root comparison only)")
    args = ap.parse_args(argv)

    if args.consistency:
        if not args.from_file:
            print("--consistency needs --from (a receipt JSON or a checkpoint file)", file=sys.stderr)
            return 2
        key = None if args.no_signature else load_log_key(args.log_key)
        try:
            return consistency_mode(args.from_file, args.to_file, key)
        except Exception as exc:  # noqa: BLE001 - could not read is exit 2, not a verdict
            print("could not check consistency: %s" % exc, file=sys.stderr)
            return 2

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

    receipt = check_entry(entry, None if args.no_signature else load_log_key(args.log_key))
    text = json.dumps(receipt, indent=2, sort_keys=True)
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text + "\n")
        print("receipt written: %s" % args.out)
    else:
        print(text)
    print("conclusion=%s  verified=%s  proof.index=%s  entry.index=%s  checkpoint.signature=%s"
          % (receipt.get("conclusion"), receipt["verified"], receipt["proof_log_index"], receipt["entry_log_index"],
             receipt["checkpoint"]["signature_verified"] if receipt["checkpoint"] else "no checkpoint"),
          file=sys.stderr)
    return _exit_for(receipt)


if __name__ == "__main__":
    raise SystemExit(main())
