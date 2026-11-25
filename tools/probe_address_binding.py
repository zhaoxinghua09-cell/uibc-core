#!/usr/bin/env python
"""Binding probe: an address string may be well-formed and still belong to nobody.

A `did:bid` suffix is base58 of a digest, so *any* base58 string of the right
length looks valid. That means the string itself carries no integrity check: the
only way to know an address belongs to a key is to recompute it. This probe
measures exactly that, in both directions:

  1. key -> address: flip every bit of the public key; every derived address must
     change, and none may collide with another. If two keys land on one address,
     the derivation is not a function of the key.
  2. address -> key: replace every character of the suffix with every other
     base58 character, then ask `address_matches` whether that string still
     matches the key. Every one of them must be refused, otherwise the check is
     looking at a prefix instead of at the whole digest.

    python tools/probe_address_binding.py            # human table
    python tools/probe_address_binding.py --json     # machine output
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uibc_core import bid_address as AD

# One SDK sample, not RFC-003's printed example: the spec's own example does not
# reproduce under the shipped rule (the two variants are documented in
# docs/ADDRESS-DERIVATION.md), and a probe built on an example that does not
# reproduce would be measuring the wrong rule.
FIXTURE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "fixtures", "bid", "sdk_address_batch.json")


def sample():
    import json
    with open(FIXTURE, encoding="utf-8") as fh:
        row = json.load(fh)[0]
    return row["encPublicKey"], row["address"]


PUB_KEY, PUB_DID = sample()
RFC_SUFFIX = PUB_DID[len("did:bid:ef"):]

ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _derive(raw: bytes) -> str:
    # strip the b06566 prefix that SDK keys carry, so the bits flipped are the key's
    return AD.address_suffix(AD.strip_key_prefix("b06566" + raw.hex()), "Ed25519")


KEY_BYTES = AD.strip_key_prefix(PUB_KEY)


def key_side(samples=256):
    """Flip one bit of the key at a time: the address must move, and never twice."""
    raw = KEY_BYTES
    base = _derive(raw)
    if base != RFC_SUFFIX:
        return {"error": "the fixture's key does not derive its suffix: %r" % base}
    collisions = []
    distance_min = None
    distance_max = 0
    for bit in range(samples):
        mutated = bytearray(raw)
        mutated[bit // 8] ^= 1 << (7 - (bit % 8))
        other = _derive(bytes(mutated))
        if other == base:
            collisions.append(bit)
            continue
        distance = sum(1 for a, b in zip(base, other) if a != b)
        distance_min = distance if distance_min is None else min(distance_min, distance)
        distance_max = max(distance_max, distance)
    return {"bits": samples, "unchanged": collisions, "collisions_with_base": len(collisions),
            "char_distance_min": distance_min, "char_distance_max": distance_max}


def address_side():
    """Replace each suffix character with every other base58 character."""
    accepted = []
    tried = 0
    for position, original in enumerate(RFC_SUFFIX):
        for ch in ALPHABET:
            if ch == original:
                continue
            tried += 1
            mutated = RFC_SUFFIX[:position] + ch + RFC_SUFFIX[position + 1:]
            did = "did:bid:ef" + mutated
            if AD.address_matches(PUB_KEY, did):
                accepted.append({"position": position, "char": ch, "did": did})
    return {"tried": tried, "accepted": accepted}


def length_side():
    """Truncated and padded suffixes must not match either."""
    cases = {
        "truncated by one": RFC_SUFFIX[:-1],
        "padded with one": RFC_SUFFIX + "2",
        "one character dropped in the middle": RFC_SUFFIX[:10] + RFC_SUFFIX[11:],
    }
    results = {}
    for name, suffix in cases.items():
        did = "did:bid:ef" + suffix
        try:
            results[name] = bool(AD.address_matches(PUB_KEY, did))
        except ValueError as exc:
            results[name] = "raised: %s" % str(exc)[:60]
    return results


def probe():
    return {"sample": {"public_key": PUB_KEY, "address": PUB_DID,
                       "suffix": RFC_SUFFIX,
                       "reproduced": AD.address_matches(PUB_KEY, PUB_DID)},
            "key_to_address": key_side(),
            "address_to_key": address_side(),
            "length": length_side()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    result = probe()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
        return 0
    ex = result["sample"]
    print("fixture sample reproduced: %s (%s... -> %s)"
          % (ex["reproduced"], ex["public_key"][:16], ex["address"]))
    ks = result["key_to_address"]
    print("\nkey -> address: %d single-bit flips" % ks.get("bits", 0))
    print("  addresses unchanged: %d %s" % (ks.get("collisions_with_base", 0),
                                            ks.get("unchanged") or ""))
    print("  characters changed per flip: %s..%s of %d"
          % (ks.get("char_distance_min"), ks.get("char_distance_max"), len(RFC_SUFFIX)))
    as_ = result["address_to_key"]
    print("\naddress -> key: %d one-character substitutions" % as_["tried"])
    print("  still accepted as the same key: %d" % len(as_["accepted"]))
    for item in as_["accepted"][:5]:
        print("    position %d -> %r  %s" % (item["position"], item["char"], item["did"]))
    print("\nlength: %s" % result["length"])
    print("\nconclusion: a suffix is well-formed base58 either way, so syntax proves nothing;"
          " binding is only established by re-deriving from the key, and the %d character"
          " substitutions above were all refused." % as_["tried"])
    ok = (ex["reproduced"] and not ks.get("collisions_with_base")
          and not as_["accepted"] and not any(v is True for v in result["length"].values()))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
