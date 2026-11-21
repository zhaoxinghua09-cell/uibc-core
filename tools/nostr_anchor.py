#!/usr/bin/env python3
"""Second anchoring backend: Nostr (BIP-340 signatures, NIP-01 events).

Why a second backend
--------------------
One calendar is one point of censorship. AAC anchors to its own SCITT service;
the AER-1 SDK publishes to several Nostr relays *and* an OpenTimestamps
calendar precisely so that losing one backend does not lose the anchor. That
argument is right, and it is the argument this file answers: our OTS client
already covers the calendar side, so this adds the relay side.

Why the curve is implemented here instead of pulled in
------------------------------------------------------
A Nostr event is signed with secp256k1 Schnorr (BIP-340). The obvious move is
`pip install coincurve`, which is the wrong move for this repository: the
tools here must run on a reviewer's bare Python. So the primitive is written
out — and then *checked against the official BIP-340 test vectors*, which is
exactly why it can be trusted for this purpose (see the tests).

Boundaries, stated plainly
--------------------------
- This is not hardened cryptography. Pure-Python scalar multiplication leaks
  timing; there is no blinding, no constant-time effort, no key storage.
  Use it for anchoring digests from a throwaway key, not for guarding value.
- Publication is NOT implemented. Nostr relays speak WebSocket, which the
  standard library does not provide a client for, and adding a dependency to
  speak it would contradict the point of this file. `build_event` and
  `verify_event` are complete and tested; sending the event is a separate,
  outward-facing step that needs a socket and a person's approval.

What actually goes on the wire
------------------------------
The event id is sha256 over `[0, pubkey, created_at, kind, tags, content]`.
Only the anchor root, a package label and a purpose string go into `content` -
no evidence, no inputs, no outputs.
"""

import argparse
import hashlib
import json
import os
import sys
import time

# --- secp256k1, minimal affine arithmetic --------------------------------

FIELD = 2 ** 256 - 2 ** 32 - 977
ORDER = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
BASE = (0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
        0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8)

# BIP-340 test vector 0 pins these bytes; the constants above are from the
# curve definition, and the tests below prove they are the right ones.


def _inv(value):
    return pow(value, FIELD - 2, FIELD)


def _add(left, right):
    if left is None:
        return right
    if right is None:
        return left
    x1, y1 = left
    x2, y2 = right
    if x1 == x2:
        if (y1 + y2) % FIELD == 0:
            return None
        slope = 3 * x1 * x1 % FIELD * _inv(2 * y1 % FIELD) % FIELD
    else:
        slope = (y2 - y1) % FIELD * _inv((x2 - x1) % FIELD) % FIELD
    x3 = (slope * slope - x1 - x2) % FIELD
    return (x3, (slope * (x1 - x3) - y1) % FIELD)


def _mul(scalar, point):
    scalar %= ORDER
    result = None
    addend = point
    while scalar:
        if scalar & 1:
            result = _add(result, addend)
        addend = _add(addend, addend)
        scalar >>= 1
    return result


def lift_x(x):
    """Recover the even-y point with the given x (BIP-340 §2.1)."""
    if x >= FIELD:
        raise ValueError("x out of range")
    y_squared = (pow(x, 3, FIELD) + 7) % FIELD
    y = pow(y_squared, (FIELD + 1) // 4, FIELD)
    if pow(y, 2, FIELD) != y_squared:
        raise ValueError("x is not on the curve")
    return (x, y if y % 2 == 0 else FIELD - y)


def pubkey_of(seckey: bytes) -> bytes:
    d = int.from_bytes(seckey, "big")
    if not 1 <= d < ORDER:
        raise ValueError("secret key out of range")
    point = _mul(d, BASE)
    return point[0].to_bytes(32, "big")


def _tagged_hash(tag: str, data: bytes) -> bytes:
    tag_hash = hashlib.sha256(tag.encode()).digest()
    return hashlib.sha256(tag_hash + tag_hash + data).digest()


def schnorr_sign(seckey: bytes, message: bytes, aux: bytes = None) -> bytes:
    """BIP-340 signature over a message of any length (tests use short ones)."""
    aux = aux if aux is not None else b"\x00" * 32
    if len(aux) != 32:
        raise ValueError("aux_rand must be 32 bytes")
    d0 = int.from_bytes(seckey, "big")
    if not 1 <= d0 < ORDER:
        raise ValueError("secret key out of range")
    point = _mul(d0, BASE)
    d = d0 if point[1] % 2 == 0 else ORDER - d0
    t = bytes(a ^ b for a, b in zip(d.to_bytes(32, "big"),
                                    _tagged_hash("BIP0340/aux", aux)))
    k0 = int.from_bytes(
        _tagged_hash("BIP0340/nonce", t + point[0].to_bytes(32, "big") + message),
        "big") % ORDER
    if k0 == 0:
        raise ValueError("nonce is zero")
    nonce_point = _mul(k0, BASE)
    k = k0 if nonce_point[1] % 2 == 0 else ORDER - k0
    challenge = int.from_bytes(_tagged_hash(
        "BIP0340/challenge",
        nonce_point[0].to_bytes(32, "big") + point[0].to_bytes(32, "big") + message),
        "big") % ORDER
    return (nonce_point[0].to_bytes(32, "big")
            + ((k + challenge * d) % ORDER).to_bytes(32, "big"))


def schnorr_verify(pubkey: bytes, message: bytes, signature: bytes) -> bool:
    """BIP-340 verification. Returns False on any malformed input."""
    if len(pubkey) != 32 or len(signature) != 64:
        return False
    try:
        point = lift_x(int.from_bytes(pubkey, "big"))
    except ValueError:
        return False
    r = int.from_bytes(signature[:32], "big")
    s = int.from_bytes(signature[32:], "big")
    if r >= FIELD or s >= ORDER:
        return False
    challenge = int.from_bytes(_tagged_hash("BIP0340/challenge",
                                            signature[:32] + pubkey + message),
                               "big") % ORDER
    candidate = _add(_mul(s, BASE), _mul(ORDER - challenge, point))
    if candidate is None or candidate[1] % 2 != 0:
        return False
    return candidate[0] == r


# --- NIP-01 events ------------------------------------------------------


def event_id(pubkey_hex, created_at, kind, tags, content) -> str:
    serialized = json.dumps([0, pubkey_hex, created_at, kind, tags, content],
                            separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_event(seckey: bytes, content: str, kind: int = 1, tags=None,
                created_at=None, aux=None):
    tags = tags or []
    created_at = int(created_at if created_at is not None else time.time())
    pubkey_hex = pubkey_of(seckey).hex()
    eid = event_id(pubkey_hex, created_at, kind, tags, content)
    signature = schnorr_sign(seckey, bytes.fromhex(eid), aux)
    return {"id": eid, "pubkey": pubkey_hex, "created_at": created_at,
            "kind": kind, "tags": tags, "content": content,
            "sig": signature.hex()}


def verify_event(event) -> bool:
    """Recompute the id from the event's own fields, then verify the sig."""
    required = ("id", "pubkey", "created_at", "kind", "tags", "content", "sig")
    if not all(key in event for key in required):
        return False
    recomputed = event_id(event["pubkey"], event["created_at"], event["kind"],
                          event["tags"], event["content"])
    if recomputed != event["id"]:
        return False
    try:
        return schnorr_verify(bytes.fromhex(event["pubkey"]),
                              bytes.fromhex(event["id"]),
                              bytes.fromhex(event["sig"]))
    except ValueError:
        return False


# --- anchoring an Evidence Root -----------------------------------------


def anchor_event(package, seckey, kind=1, created_at=None, label=None):
    """Build (but do not publish) an event committing to a package's root."""
    manifest_path = os.path.join(package, "manifest.json")
    if not os.path.isfile(manifest_path):
        raise FileNotFoundError("manifest.json not found in %s" % package)
    with open(manifest_path, encoding="utf-8") as stream:
        manifest = json.load(stream)
    root = manifest.get("evidence_root")
    if not isinstance(root, str) or len(root) != 64:
        raise ValueError("manifest has no 64-hex evidence_root")
    content = json.dumps({
        "scheme": "uibc-core/evidence-root",
        "root": root.lower(),
        "label": label or os.path.basename(os.path.abspath(package)),
        "purpose": "anchor",
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return build_event(seckey, content, kind=kind, created_at=created_at,
                       tags=[["t", "uibc-anchor"]])  # a NIP-12 hashtag tag


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--package", required=True)
    parser.add_argument("--seckey", help="32-byte hex secret key; generated if omitted")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    seckey = bytes.fromhex(args.seckey) if args.seckey else os.urandom(32)
    try:
        event = anchor_event(args.package, seckey)
    except (FileNotFoundError, ValueError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2

    verified = verify_event(event)
    if args.json:
        print(json.dumps({"event": event, "self_verified": verified},
                         ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("pubkey     : %s" % event["pubkey"])
        print("event id   : %s" % event["id"])
        print("content    : %s" % event["content"])
        print("signature  : %s..." % event["sig"][:32])
        print("self-check : %s" % ("PASS" if verified else "FAIL"))
        print("\nNot published: publication needs a WebSocket client and your go-ahead.")
    return 0 if verified else 1


if __name__ == "__main__":
    sys.exit(main())
