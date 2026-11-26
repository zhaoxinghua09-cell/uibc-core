#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One command for the whole evidence chain, from file bytes to a walked block segment.

The pieces existed but were separate:
  * `tools/anchor_ots.py --verify` answers "is this proof about this file, and
    what does it attest?";
  * `tools/ots_block_crosscheck.py` answers "is that block real, with that root?";
  * its `--chain` answers "is that block under the tip we were shown, header by header?".

A reader should not have to run three tools and trust that the outputs line up.
This runs all three, joins the seams with byte comparisons, and prints **one**
verdict plus the list of things it did not check. Offline by default: it reads the
two committed receipts, so it needs no network and no server.

    python tools/ots_full_verify.py \\
        --file tests/fixtures/anchor/anchored_head.json \\
        --proof tests/fixtures/anchor/ots_head.ots

    python tools/ots_full_verify.py ... --refresh   # re-fetch receipts first

Exit codes: 0 = every joined seam matches; 1 = a seam broke or an input is missing.
"""
import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from tools import anchor_ots  # noqa: E402
from tools import ots_block_crosscheck as cc  # noqa: E402
from uibc_core import tsa  # noqa: E402

DEFAULT_BLOCK_RECEIPT = os.path.join(ROOT, "docs", "anchor-ots-block-977449.json")
DEFAULT_CHAIN_RECEIPT = os.path.join(ROOT, "docs", "anchor-ots-chain-977449.json")
FIXTURES = os.path.join(ROOT, "tests", "fixtures", "anchor")
DEFAULT_TSA = os.path.join(FIXTURES, "freetsa.tsr")
DEFAULT_TSA_CA = os.path.join(FIXTURES, "freetsa_ca.pem")

UNCHECKED = [
    "global most-work chain: needs a Bitcoin Core node (--node), none configured here",
    "competing branches: not enumerated by any explorer API",
    "reorganisation risk beyond the recorded depth: not modelled",
]


def _same(left, right):
    return left is not None and right is not None and left.lower() == right.lower()


def full_verify(file_path, proof_path, block_receipt=DEFAULT_BLOCK_RECEIPT,
                chain_receipt=DEFAULT_CHAIN_RECEIPT, refresh=False, node=None,
                timeout=30, tsa_token=None, tsa_cabundle=DEFAULT_TSA_CA):
    steps, problems = {}, []

    # 1. the proof must be about this file
    v = anchor_ots.verify(file_path, proof_path)
    steps["proof_binds_file"] = {
        "ok": bool(v.get("readable") and v.get("bound")),
        "file_digest": v.get("file_digest_sha256"),
        "proof_digest": v.get("proof_digest_sha256"),
    }
    if not steps["proof_binds_file"]["ok"]:
        problems.append("the proof does not read as a timestamp for this file")
        return {"verdict": "STOPPED_AT_PROOF", "steps": steps, "problems": problems,
                "unchecked": UNCHECKED}

    # 2. the attestation's message must be the root inside the header
    atts = [(h, bytes(m)) for h, m in cc.block_attestations(proof_path)]
    steps["proof_carries_block"] = {"ok": bool(atts),
                                    "heights": sorted({h for h, _m in atts})}
    if not atts:
        problems.append("the proof carries no Bitcoin block attestation")
        return {"verdict": "STOPPED_AT_ATTESTATION", "steps": steps,
                "problems": problems, "unchecked": UNCHECKED}

    blk, blk_problems = cc.check_receipt(block_receipt)
    roots = {cc.display(m) for _h, m in atts}
    joins_root = blk["merkle_root_from_header"] in roots
    joins_hash = _same(blk["header_sha256d"],
                       blk["sources"].get("blockstream.info", {}).get("block_hash"))
    steps["header_receipt"] = {
        "ok": not blk_problems and joins_root,
        "receipt": block_receipt,
        "problems": blk_problems,
        "root_in_attestation": joins_root,
        "header_hashes_to_block": joins_hash,
        "height": blk.get("height"),
    }
    if not steps["header_receipt"]["ok"]:
        problems.append("the header receipt does not join to the proof's attestation")
        return {"verdict": "STOPPED_AT_HEADER", "steps": steps,
                "problems": problems, "unchecked": UNCHECKED}

    # 3. the segment from that block up to the tip
    ch, ch_problems = cc.check_chain_receipt(chain_receipt)
    joins_segment = (_same(ch["block_hash"], blk["header_sha256d"])
                     and ch["headers"][-1]["height"] == blk["height"] + 1
                     if ch.get("headers") else False)
    steps["chain_receipt"] = {
        "ok": not ch_problems and joins_segment,
        "receipt": chain_receipt,
        "problems": ch_problems,
        "starts_one_block_above": joins_segment,
        "headers": ch.get("headers_from_attested_to_tip"),
        "work": ch.get("cumulative_work_hex"),
        "node": ch.get("node"),
    }
    if not steps["chain_receipt"]["ok"]:
        problems.append("the chain receipt does not join to that block")
        return {"verdict": "STOPPED_AT_CHAIN", "steps": steps,
                "problems": problems, "unchecked": UNCHECKED}


    # 4. the other anchor type, if a token is supplied: RFC 3161 over the same digest
    if tsa_token:
        with open(file_path, "rb") as f:
            data = f.read()
        with open(tsa_token, "rb") as f:
            tsr = f.read()
        with open(tsa_cabundle, "rb") as f:
            ca = f.read()
        ok, info, tsa_problems = tsa.verify_token(tsr, hashlib.sha256(data).digest(), ca)
        digest_join = (info or {}).get("digest_hex") == steps["proof_binds_file"]["file_digest"]
        steps["rfc3161"] = {
            "ok": bool(ok) and digest_join and bool((info or {}).get("signature_verified")),
            "provided": True,
            "token": tsa_token,
            "gen_time": (info or {}).get("gen_time"),
            "digest_in_token": (info or {}).get("digest_hex"),
            "digest_matches_file": digest_join,
            "signature_verified": (info or {}).get("signature_verified"),
            "tsa": ((info or {}).get("tsa") or {}).get("common_name"),
            "problems": tsa_problems,
        }
        if not steps["rfc3161"]["ok"]:
            problems.append("the RFC 3161 token does not cover this file")
            return {"verdict": "STOPPED_AT_TSA", "steps": steps,
                    "problems": problems, "unchecked": UNCHECKED}
    else:
        steps["rfc3161"] = {"ok": False, "provided": False,
                            "reason": "no token supplied; only the OTS anchor was judged"}

    node_doc = ch.get("node") or {}
    doc = {"file": file_path, "proof": proof_path,
           "verdict": "FULL_CHAIN_OF_EVIDENCE_VERIFIED",
           "steps": steps,
           "digests": {"file": steps["proof_binds_file"]["file_digest"],
                       "attestation_root": sorted(roots)[0],
                       "block_hash": blk["header_sha256d"],
                       "block_height": blk.get("height"),
                       "headers_verified": ch.get("headers_from_attested_to_tip"),
                       "segment_work": ch.get("cumulative_work_hex")},
           "problems": [],
           "anchors": {"open_timestamps": True,
                       "rfc3161": bool(steps.get("rfc3161", {}).get("ok")),
                       "both_anchors_verified": bool(steps.get("rfc3161", {}).get("ok"))},
           "most_work_established": bool(node_doc.get("checked")),
           "unchecked": UNCHECKED}
    return doc


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--file", required=True)
    ap.add_argument("--proof", required=True)
    ap.add_argument("--block-receipt", default=DEFAULT_BLOCK_RECEIPT)
    ap.add_argument("--chain-receipt", default=DEFAULT_CHAIN_RECEIPT)
    ap.add_argument("--node", metavar="RPC_URL")
    ap.add_argument("--tsa-token", metavar="TSR",
                    help="RFC 3161 token over the same file; judged offline against the CA bundle")
    ap.add_argument("--tsa-cabundle", default=DEFAULT_TSA_CA)
    ap.add_argument("--refresh", action="store_true",
                    help="re-fetch the receipts from the network before verifying")
    ap.add_argument("--timeout", type=int, default=30)
    a = ap.parse_args(argv)

    if a.refresh:
        blk = cc.crosscheck(a.proof, timeout=a.timeout)
        with open(a.block_receipt, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(blk, indent=2, sort_keys=True) + "\n")
        ch = cc.chain_check(a.proof, timeout=a.timeout)
        with open(a.chain_receipt, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(ch, indent=2, sort_keys=True) + "\n")

    doc = full_verify(a.file, a.proof, a.block_receipt, a.chain_receipt,
                      node=a.node, timeout=a.timeout,
                      tsa_token=a.tsa_token, tsa_cabundle=a.tsa_cabundle)
    print(json.dumps(doc, indent=2, sort_keys=True))
    print("verdict=%s" % doc["verdict"])
    if doc["problems"]:
        for p in doc["problems"]:
            print("problem: %s" % p)
    return 0 if doc["verdict"] == "FULL_CHAIN_OF_EVIDENCE_VERIFIED" else 1


if __name__ == "__main__":
    sys.exit(main())
