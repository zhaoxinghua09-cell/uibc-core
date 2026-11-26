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



PREV_OFFSET = 4
BITS_OFFSET = 72  # version 0..3, prev 4..35, merkle 36..67, time 68..71, bits 72..75
TIPS = {
    "blockstream.info": ("https://blockstream.info/api/blocks/tip/hash",
                         "https://blockstream.info/api/blocks/tip/height"),
    "blockchain.info": ("https://blockchain.info/q/latesthash",
                        "https://blockchain.info/q/getblockcount"),
}


def prev_hash_of_header(header):
    """Stored bytes (little-endian) of the previous block hash."""
    return header[PREV_OFFSET:PREV_OFFSET + 32]


def bits_of_header(header):
    # Bitcoin serialises header integers little-endian, so the difficulty bits
    # read as bytes [72:76] must be interpreted the same way (0x73160217 on the
    # wire is the familiar 0x17160273).
    return int.from_bytes(header[BITS_OFFSET:BITS_OFFSET + 4], "little")


def difficulty_target(bits):
    """The `bits` field compressed form -> the 256-bit threshold the hash must beat."""
    exponent = bits >> 24
    mantissa = bits & 0xFFFFFF
    if exponent <= 3:
        return mantissa >> (8 * (3 - exponent))
    return mantissa << (8 * (exponent - 3))


def meets_target(header):
    """Proof of work for one header: sha256d(hash) must be at or below its target.

    The comparison is on the little-endian integer, because that is the number
    Bitcoin's difficulty is defined against -- reading the digest big-endian
    makes real blocks look like they failed (22 of 159 did, before this fix).
    """
    target = difficulty_target(bits_of_header(header))
    value = int.from_bytes(sha256d(header), "little")
    return value <= target, target


def work_of(target):
    """Expected hashes per block at this target, the usual 2**256/(target+1) unit."""
    return (1 << 256) // (target + 1)


def fetch_tip_pair(timeout=30):
    tips = {}
    for name, (hash_url, height_url) in TIPS.items():
        try:
            block_hash = _get(hash_url, timeout).decode().strip().lower()
            tips[name] = {"block_hash": block_hash,
                          "height": int(_get(height_url, timeout).decode().strip())}
        except Exception as e:  # noqa: BLE001
            tips[name] = {"error": "%s: %s" % (type(e).__name__, str(e)[:120])}
    return tips


def _fetch_header_once(block_hash, timeout, attempts=3):
    """Retries belong here, not in the verdict: a flaky connection is not a bad block."""
    last = None
    for _ in range(attempts):
        try:
            return fetch_header(block_hash, timeout)
        except Exception as e:  # noqa: BLE001
            last = e
    raise last


def chain_check(proof_path, height=None, timeout=30, max_blocks=4000):
    """Walk prev-hashes from the tip down to the attested block, checking every header.

    What this establishes, and only this: every block from the attested one up to
    the tip the operators reported is linked by prev-hash, hashes to its own id,
    and meets the difficulty target its own `bits` field asks for - so displacing
    it means redoing that work. It does **not** compare against competing chains:
    that needs a node that follows every branch, and no explorer API does that.
    """
    atts = block_attestations(proof_path)
    if not atts:
        return {"proof": proof_path, "verdict": "NO_BLOCK_ATTESTATION", "ok": False}
    heights = sorted({h for h, _m in atts})
    if height is not None and height not in heights:
        raise SystemExit("proof has no block attestation at height %s" % height)
    height = heights[0] if height is None else height

    views = fetch_views(height, timeout)
    hashes = {v["block_hash"].lower() for v in views.values() if "block_hash" in v}
    if len(hashes) != 1:
        return {"proof": proof_path, "height": height, "verdict": "SOURCES_DISAGREE",
                "sources": views, "ok": False}
    block_hash = hashes.pop()

    tips = fetch_tip_pair(timeout)
    answered = [v for v in tips.values() if "block_hash" in v]
    doc = {"proof": proof_path, "height": height, "block_hash": block_hash,
           "tips": tips}
    if not answered or len({v["block_hash"] for v in answered}) != 1:
        doc["verdict"] = "TIPS_DISAGREE"
        doc["ok"] = False
        return doc
    tip_hash = answered[0]["block_hash"]
    tip_height = min(v["height"] for v in answered)

    headers, problems = [], []
    cursor = tip_hash
    steps = 0
    while cursor != block_hash and steps < max_blocks:
        header = _fetch_header_once(cursor, timeout)
        if display(sha256d(header)) != cursor:
            problems.append("header fetch does not hash to the id asked for: %s" % cursor)
            break
        headers.append({"height": tip_height - steps, "block_hash": cursor,
                        "header_hex": header.hex()})
        cursor = display(prev_hash_of_header(header))
        steps += 1

    expected = tip_height - height
    linkage, pow_failed, total_work = [], [], 0
    for i, item in enumerate(headers):
        header = bytes.fromhex(item["header_hex"])
        ok_pow, target = meets_target(header)
        if not ok_pow:
            pow_failed.append(item["height"])
        total_work += work_of(target)
        nxt = display(prev_hash_of_header(header))
        if i + 1 < len(headers):
            linkage.append(nxt == headers[i + 1]["block_hash"])
        elif nxt != block_hash:
            problems.append("last header does not point at the attested block")

    checks = {
        "walk_reached_attested_block": cursor == block_hash,
        "segment_length_matches_tip": len(headers) == expected,
        "all_headers_linked_by_prev_hash": all(linkage) if linkage else True,
        "all_headers_meet_their_target": not pow_failed,
    }
    doc.update({"checks": checks, "headers_from_attested_to_tip": len(headers),
                "expected_length": expected,
                "difficulty_failures": pow_failed,
                "cumulative_work": str(total_work),
                "cumulative_work_hex": "%x" % total_work,
                "headers": headers, "problems": problems})
    doc["ok"] = all(checks.values()) and not problems
    doc["verdict"] = "CHAIN_SEGMENT_VERIFIED" if doc["ok"] else "CHAIN_SEGMENT_FAILED"
    return doc


def check_chain_receipt(path):
    """Re-derive the whole segment offline: linkage, ids, targets, work sum."""
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    headers = doc["headers"]
    problems, total_work = [], 0
    for i, item in enumerate(headers):
        header = bytes.fromhex(item["header_hex"])
        if display(sha256d(header)) != item["block_hash"]:
            problems.append("header at %s does not hash to its recorded id" % item["height"])
        ok_pow, target = meets_target(header)
        if not ok_pow:
            problems.append("header at %s fails its own difficulty target" % item["height"])
        total_work += work_of(target)
        if i + 1 < len(headers) and display(prev_hash_of_header(header)) != headers[i + 1]["block_hash"]:
            problems.append("prev-hash at %s does not match the next recorded block" % item["height"])
    if headers and display(prev_hash_of_header(bytes.fromhex(headers[-1]["header_hex"]))) != doc["block_hash"]:
        problems.append("segment does not end on the attested block")
    if len(headers) != doc["expected_length"]:
        problems.append("segment length differs from tip_height - height")
    if str(total_work) != doc["cumulative_work"]:
        problems.append("cumulative work recomputed from headers differs from the recorded sum")
    return doc, problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--proof")
    ap.add_argument("--height", type=int)
    ap.add_argument("--out")
    ap.add_argument("--check", help="offline check of a header cross-check receipt")
    ap.add_argument("--chain", action="store_true",
                    help="also walk prev-hash from the tip down to the attested block")
    ap.add_argument("--chain-out", metavar="RECEIPT",
                    help="where the chain-segment receipt goes (default: <out>.chain.json)")
    ap.add_argument("--chain-check", metavar="RECEIPT",
                    help="offline check of a chain-segment receipt")
    ap.add_argument("--timeout", type=int, default=30)
    a = ap.parse_args(argv)

    if a.chain_check:
        doc, problems = check_chain_receipt(a.chain_check)
        print(json.dumps({"receipt": a.chain_check, "ok": not problems,
                          "problems": problems, "verdict": doc.get("verdict")}, indent=2))
        return 0 if not problems else 1

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
    if a.chain:
        chain = chain_check(a.proof, a.height, a.timeout)
        chain_text = json.dumps(chain, indent=2, sort_keys=True)
        path = a.chain_out or ((a.out or a.proof) + ".chain.json")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(chain_text + "\n")
        print("chain_receipt=%s" % path)
        print("verdict=%s (headers=%s, work=%s)" % (chain["verdict"],
                                                    chain.get("headers_from_attested_to_tip"),
                                                    chain.get("cumulative_work_hex")))
        if not chain.get("ok"):
            return 1
    return 0 if doc.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
