#!/usr/bin/env python
"""Bit-flip probe: how many single-bit corruptions does the decoder notice?

For a valid RFC-011 message, flip one bit at a time and classify each mutant:

  rejected  - decode raised (length/structure checks caught it)
  changed   - decoded, but the result differs from the original
  blind     - decoded to *exactly* the same document: the format itself carries
              no signal in that bit

The blind set is the interesting output. A format without a signature cannot
detect arbitrary tampering, but it should still be known *which* bits are
semantically dead, because those are the bits an attacker can change for free.

    python tools/mutate_bid_binary.py                    # human table
    python tools/mutate_bid_binary.py --json             # machine output
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uibc_core import bid_binary as BB

WIDTHS = {"int": 2, "long": 4}


def sample_message():
    doc = {
        "version": "1.0.0",
        "id": "did:bid:ef38VPR182Y4uTkq32fykXjbKBPdQZutH",
        "created": "2021-06-24T09:10:09Z",
        "publicKey": {"id": "did:bid:ef38VPR#key-1", "type": "Ed25519",
                      "controller": "did:bid:ef38VPR"},
        "authentication": ["did:bid:ef38VPR#key-1"],
        "extension": {"ttl": 86400, "type": 105},
    }
    units = BB.encode_document(doc, integer_widths=WIDTHS)
    return BB.encode_message(units, 0x01020304)


def _decode(data):
    """Full observable state, not just the document.

    Comparing only the decoded document would call a replyCode or a transactionID
    flip "blind" - which is wrong: a caller reads those fields. The probe must
    compare everything the decoder exposes.
    """
    header, doc = BB.decode_message(data, integer_widths=WIDTHS)
    return (header.version, header.header_length, tuple(sorted(header.flags.items())),
            header.opcode, header.reply_code, header.message_id, header.transaction_id,
            header.message_length, header.option_bytes, repr(doc.as_dict()))


def field_of_bit(bit_index, header_len_bytes=16):
    """Name the byte a bit belongs to, using the header layout, not a guess."""
    byte, offset = divmod(bit_index, 8)
    if byte == 0:
        return "version/headerLength"
    if byte in (1, 2):
        return "flag"
    if byte == 3:
        return "unUsed"
    if byte in (4, 5):
        return "replyCode"
    if byte in (6, 7):
        return "messageID"
    if 8 <= byte <= 11:
        return "transactionID"
    if 12 <= byte <= 15:
        return "messageLength"
    return "body"


def probe(message):
    baseline = _decode(message)
    rejected, changed, blind = 0, 0, []
    total = len(message) * 8
    for bit in range(total):
        mutated = bytearray(message)
        mutated[bit // 8] ^= 1 << (7 - (bit % 8))
        try:
            got = _decode(bytes(mutated))
        except ValueError:
            rejected += 1
            continue
        if got == baseline:
            blind.append(bit)
        else:
            changed += 1
    return {"total": total, "rejected": rejected, "changed": changed,
            "blind": blind, "blind_fields": sorted({field_of_bit(b) for b in blind})}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    msg = sample_message()
    res = probe(msg)
    res["message_bytes"] = len(msg)
    res["sha256_prefix"] = __import__("hashlib").sha256(msg).hexdigest()[:16]
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 0
    print("message: %d bytes, %d bits, sha256[:16]=%s" % (len(msg), res["total"], res["sha256_prefix"]))
    print("  rejected (structure caught it): %4d  (%.1f%%)"
          % (res["rejected"], 100.0 * res["rejected"] / res["total"]))
    print("  changed  (decoded differently): %4d  (%.1f%%)"
          % (res["changed"], 100.0 * res["changed"] / res["total"]))
    print("  blind    (same document)      : %4d  (%.1f%%)"
          % (len(res["blind"]), 100.0 * len(res["blind"]) / res["total"]))
    print("  blind bits by field: %s" % ", ".join(res["blind_fields"]))
    for bit in res["blind"]:
        byte, offset = divmod(bit, 8)
        print("    byte %2d bit %d  -> %s" % (byte, 7 - offset, field_of_bit(bit)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
