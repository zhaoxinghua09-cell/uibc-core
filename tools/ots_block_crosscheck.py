#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cross-check an OpenTimestamps Bitcoin block attestation against real block headers.

Why this exists: `--verify` can only tell you a proof *carries* a block
attestation -- the tool that produced it says so itself ("block header NOT
cross-checked here"). That sentence is where verification used to stop. This
tool finishes the step with arithmetic anyone can repeat:

  * a block header is 80 bytes; its Merkle root sits at bytes 36..68, little-endian;
  * sha256(sha256(header)) IS the block hash -- so a header pinned to a hash is
    pinned to a block;
  * an OpenTimestamps `BitcoinBlockHeaderAttestation` commits the digest chain to
    the block's Merkle root, stored the same little-endian way.

So: same header bytes -> same hash -> same Merkle root -> the attestation's
message. Nothing here trusts a server; the servers only supply bytes that then
have to hash to the right thing.

Two independent operators are asked (blockstream.info and blockchain.info);
disagreement between them is reported as a failure, never averaged away.

    python tools/ots_block_crosscheck.py --proof <proof.ots> --out <receipt.json>
    python tools/ots_block_crosscheck.py --check <receipt.json>   # offline, no network

Exit codes: 0 = header matches the attestation and the sources agree;
1 = mismatch, disagreement, or a proof without a block attestation.
"""
import argparse
import hashlib
import json
import sys
import urllib.request

HEADER_LEN = 80
MERKLE_OFFSET = 36
MERKLE_LEN = 32

SOURCES = {
    # name -> (block-hash by height, merkle root by block hash)
    "blockstream.info": ("https://blockstream.info/api/block-height/{height}",
                         "https://blockstream.info/api/block/{block_hash}"),
    "blockchain.info": ("https://blockchain.info/block-height/{height}?format=json",
                        "https://blockchain.info/rawblock/{block_hash}"),
}


def sha256d(blob):
    return hashlib.sha256(hashlib.sha256(blob).digest()).digest()


def merkle_root_of_header(header):
    """Stored bytes (little-endian) of the Merkle root inside an 80-byte header."""
    if len(header) != HEADER_LEN:
        raise ValueError("block header must be 80 bytes, got %d" % len(header))
    return header[MERKLE_OFFSET:MERKLE_OFFSET + MERKLE_LEN]


def display(blob):
    """Bitcoin shows hashes big-endian; the header stores them little-endian."""
    return blob[::-1].hex()


def block_attestations(proof_path):
    """[(height, msg_bytes)] for every BitcoinBlockHeaderAttestation in a proof."""
    from opentimestamps.core.serialize import StreamDeserializationContext
    from opentimestamps.core.timestamp import DetachedTimestampFile

    with open(proof_path, "rb") as f:
        dtf = DetachedTimestampFile.deserialize(StreamDeserializationContext(f))
    found = []

    def walk(t):
        for att in t.attestations:
            if type(att).__name__ == "BitcoinBlockHeaderAttestation":
                found.append((att.height, bytes(t.msg)))
        for _op, child in t.ops.items():
            walk(child)

    walk(dtf.timestamp)
    return found


def _get(url, timeout):
    req = urllib.request.Request(url, headers={"User-Agent": "uibc-ots-crosscheck/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _json(url, timeout):
    return json.loads(_get(url, timeout).decode("utf-8"))


def fetch_header(block_hash, timeout=30):
    """80 header bytes from blockstream, which serves the raw hex."""
    hexstr = _get("https://blockstream.info/api/block/%s/header" % block_hash,
                  timeout).decode("ascii").strip()
    return bytes.fromhex(hexstr)


def fetch_views(height, timeout=30):
    """Ask each independent operator which block is at `height` and what root it has."""
    views = {}
    for name, (by_height, by_hash) in SOURCES.items():
        try:
            if name == "blockchain.info":
                doc = _json(by_height.format(height=height), timeout)
                blk = doc["blocks"][0]
                views[name] = {"block_hash": blk["hash"], "merkle_root": blk["mrkl_root"]}
            else:
                block_hash = _get(by_height.format(height=height), timeout).decode().strip()
                doc = _json(by_hash.format(block_hash=block_hash), timeout)
                views[name] = {"block_hash": block_hash, "merkle_root": doc["merkle_root"]}
        except Exception as e:  # noqa: BLE001 - a source being down is data, not a verdict
            views[name] = {"error": "%s: %s" % (type(e).__name__, str(e)[:120])}
    return views


def fetch_tips(timeout=30):
    """Current chain tip height from each operator, so depth is measured, not assumed."""
    tips = {}
    for name, url in (("blockstream.info", "https://blockstream.info/api/blocks/tip/height"),
                      ("blockchain.info", "https://blockchain.info/q/getblockcount")):
        try:
            tips[name] = int(_get(url, timeout).decode().strip())
        except Exception as e:  # noqa: BLE001
            tips[name] = {"error": "%s: %s" % (type(e).__name__, str(e)[:120])}
    return tips


def crosscheck(proof_path, height=None, timeout=30):
    atts = block_attestations(proof_path)
    if not atts:
        return {"proof": proof_path, "verdict": "NO_BLOCK_ATTESTATION",
                "attestations": [], "ok": False}
    heights = sorted({h for h, _m in atts})
    if height is not None and height not in heights:
        raise SystemExit("proof has no block attestation at height %s (has %s)"
                         % (height, heights))
    height = heights[0] if height is None else height
    # the attestation stores the root little-endian, exactly as the header does;
    # both are recorded, but every comparison below happens on the same byte order
    msgs_le = sorted({m.hex() for h, m in atts if h == height})
    msgs = sorted({display(bytes.fromhex(h)) for h in msgs_le})

    views = fetch_views(height, timeout)
    agreed = [n for n, v in views.items() if "block_hash" in v]
    errors = {n: v["error"] for n, v in views.items() if "error" in v}
    hashes = {v["block_hash"] for v in views.values() if "block_hash" in v}
    roots = {v["merkle_root"].lower() for v in views.values() if "merkle_root" in v}

    doc = {"proof": proof_path, "height": height,
           "attestation_msgs": msgs,
           "attestation_msgs_le": msgs_le,
           "attestations": len(atts),
           "sources": views,
           "sources_answering": agreed,
           "sources_agree_on_hash": len(hashes) == 1,
           "sources_agree_on_merkle_root": len(roots) == 1}

    if not agreed or len(hashes) != 1:
        doc["verdict"] = "SOURCES_DISAGREE"
        doc["ok"] = False
        return doc

    block_hash = hashes.pop()
    header = fetch_header(block_hash, timeout)
    doc["header_hex"] = header.hex()
    doc["header_sha256d"] = display(sha256d(header))
    doc["merkle_root_from_header"] = display(merkle_root_of_header(header))

    checks = {
        "header_hashes_to_block_hash": doc["header_sha256d"] == block_hash,
        "merkle_root_matches_attestation":
            display(merkle_root_of_header(header)) in msgs,
        "merkle_root_matches_sources":
            len(roots) == 1 and doc["merkle_root_from_header"] == roots.pop(),
    }
    doc["checks"] = checks
    tips = fetch_tips(timeout)
    doc["tip_heights"] = tips
    numbers = [v for v in tips.values() if isinstance(v, int)]
    doc["confirmations"] = (min(numbers) - height) if numbers else None
    doc["depth_meets_6"] = bool(doc["confirmations"] is not None and doc["confirmations"] >= 6)
    doc["ok"] = all(checks.values())
    doc["verdict"] = "HEADER_MATCHES_ATTESTATION" if doc["ok"] else "MISMATCH"
    return doc


def check_receipt(path):
    """Re-derive everything a receipt claims, offline: no network, no trust."""
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    header = bytes.fromhex(doc["header_hex"])
    problems = []
    if display(sha256d(header)) != doc["header_sha256d"]:
        problems.append("header does not hash to the recorded block hash")
    if display(merkle_root_of_header(header)) != doc["merkle_root_from_header"]:
        problems.append("merkle root recomputed from header differs from the recorded one")
    if doc["merkle_root_from_header"] not in doc["attestation_msgs"]:
        problems.append("merkle root is not one of the attestation messages")
    if not doc.get("checks", {}).get("header_hashes_to_block_hash"):
        problems.append("receipt itself records a hash mismatch")
    tips = [v for v in doc.get("tip_heights", {}).values() if isinstance(v, int)]
    if tips and doc.get("confirmations") != min(tips) - doc["height"]:
        problems.append("recorded confirmation depth is not min(tip) - height")
    return doc, problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--proof")
    ap.add_argument("--height", type=int)
    ap.add_argument("--out")
    ap.add_argument("--check")
    ap.add_argument("--timeout", type=int, default=30)
    a = ap.parse_args(argv)

    if a.check:
        doc, problems = check_receipt(a.check)
        print(json.dumps({"receipt": a.check, "ok": not problems,
                          "problems": problems,
                          "verdict": doc.get("verdict")}, indent=2))
        return 0 if not problems else 1

    if not a.proof:
        ap.error("either --proof or --check is required")
    doc = crosscheck(a.proof, a.height, a.timeout)
    text = json.dumps(doc, indent=2, sort_keys=True)
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(text + "\n")
    print(text)
    print("verdict=%s" % doc["verdict"])
    return 0 if doc.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
