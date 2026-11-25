# -*- coding: utf-8 -*-
"""SM2 signature verification, checked against the national standard's own example.

Why this module exists: the BID protocol (§5) allows Ed25519 **and** SM2, and our
resolver used to say "SM2 not verifiable here" - honest, but a hole. This time the
vector problem is solved: GM/T 0003.5-2012 (published in English as GB/T 32918.5)
prints a complete worked example - curve, private key, public key, ZA, e, k, r, s -
so an implementation can be pinned to *someone else's* numbers instead of to itself.

Everything here is pure Python big-integer arithmetic plus OpenSSL's SM3. No
dependency, no C extension, no guessing: if `tests/test_sm2.py` passes, the
signature maths agrees with the standard on the standard's example.

Scope, stated rather than implied:
  * verification is complete; signing is provided so the example can be reproduced
    (a library that can only verify cannot re-derive the standard's r,s).
  * the distinguisher ID defaults to GM/T's "1234567812345678"; BID does not
    specify one, so callers that use another ID must pass it in.
"""
from typing import Optional, Tuple

P = 0xFFFFFFFEFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF00000000FFFFFFFFFFFFFFFF
A = 0xFFFFFFFEFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF00000000FFFFFFFFFFFFFFFC
B = 0x28E9FA9E9D9F5E344D5A9E4BCF6509A7F39789F515AB8F92DDBCBD414D940E93
N = 0xFFFFFFFEFFFFFFFFFFFFFFFFFFFFFFFF7203DF6B21C6052B53BBF40939D54123
GX = 0x32C4AE2C1F1981195F9904466A39C9948FE30BBFF2660BE1715A4589334C74C7
GY = 0xBC3736A2F4F6779C59BDCEE36B692153D0A9877CC62A474002DF32E52139F0A0

DEFAULT_ID = b"1234567812345678"


class SM2Error(Exception):
    """Structural problem (bad point, bad length), not a "signature is wrong" answer."""


# ------------------------------------------------------------------ curve maths
def _inv(x: int) -> int:
    return pow(x % P, P - 2, P)


def is_on_curve(x: int, y: int) -> bool:
    return (y * y - (x * x * x + A * x + B)) % P == 0


def add(p1, p2):
    if p1 is None:
        return p2
    if p2 is None:
        return p1
    x1, y1 = p1
    x2, y2 = p2
    if x1 == x2 and (y1 + y2) % P == 0:
        return None
    if p1 == p2:
        lam = (3 * x1 * x1 + A) * _inv(2 * y1) % P
    else:
        lam = (y2 - y1) * _inv(x2 - x1) % P
    x3 = (lam * lam - x1 - x2) % P
    y3 = (lam * (x1 - x3) - y1) % P
    return (x3, y3)


def mul(k: int, point):
    if k % N == 0 or point is None:
        return None
    result = None
    addend = point
    while k:
        if k & 1:
            result = add(result, addend)
        addend = add(addend, addend)
        k >>= 1
    return result


def public_key(private_key: int) -> Tuple[int, int]:
    point = mul(private_key, (GX, GY))
    if point is None:
        raise SM2Error("private key has no public point")
    return point


# ------------------------------------------------------------------ hashing
def sm3(data: bytes) -> bytes:
    import hashlib

    return hashlib.new("sm3", data).digest()


def za(px: int, py: int, id_bytes: bytes = DEFAULT_ID) -> bytes:
    """ZA = SM3(ENTL_A || ID_A || a || b || xG || yG || xA || yA)."""
    if len(id_bytes) >= 8192:
        raise SM2Error("ID is too long for ENTL (needs < 2^16 bits)")
    entl = len(id_bytes) * 8
    prefix = entl.to_bytes(2, "big")
    body = b"".join(v.to_bytes(32, "big") for v in (A, B, GX, GY, px, py))
    return sm3(prefix + id_bytes + body)


def digest(message: bytes, px: int, py: int, id_bytes: bytes = DEFAULT_ID) -> int:
    """e = SM3(ZA || M), as an integer (the standard treats it as one)."""
    return int.from_bytes(sm3(za(px, py, id_bytes) + message), "big")


# ------------------------------------------------------------------ signature
def sign(private_key: int, message: bytes, k: Optional[int] = None,
         px: Optional[int] = None, py: Optional[int] = None,
         id_bytes: bytes = DEFAULT_ID) -> Tuple[int, int]:
    """(r, s). `k` is exposed only so the standard's example can be reproduced."""
    if px is None or py is None:
        px, py = public_key(private_key)
    e = digest(message, px, py, id_bytes)
    while True:
        if k is None:
            import os

            k = int.from_bytes(os.urandom(32), "big") % (N - 1) + 1
        point = mul(k, (GX, GY))
        if point is None:
            k = None
            continue
        r = (e + point[0]) % N
        if r == 0 or r + k == N:
            k = None
            continue
        # the inverse is mod n, not mod p - the field inverse silently produces a
        # signature that our own verifier rejects, which is how this got caught
        s = pow((1 + private_key) % N, N - 2, N) * (k - r * private_key) % N
        if s == 0:
            k = None
            continue
        return r, s


def verify(px: int, py: int, message: bytes, r: int, s: int,
           id_bytes: bytes = DEFAULT_ID) -> bool:
    """GM/T 0003.2 verification. Returns False for a wrong signature, raises on bad input."""
    if not (1 <= r < N and 1 <= s < N):
        return False
    if not is_on_curve(px, py):
        raise SM2Error("public key is not on the SM2 curve")
    e = digest(message, px, py, id_bytes)
    t = (r + s) % N
    if t == 0:
        return False
    point = add(mul(s, (GX, GY)), mul(t, (px, py)))
    if point is None:
        return False
    return (e + point[0]) % N == r


# ------------------------------------------------------- wire helpers (BID)
def parse_public_key_hex(hexed: str) -> Tuple[int, int]:
    """Accept 64-byte x||y, with an optional 0xb0 or 0xb0 0x65 0x66 head.

    The head is the same BIF prefix Ed25519 keys carry (`b06566`), and BID's own
    SM2 sample encodes a point, not a JWK - so both shapes are read, nothing else.
    """
    raw = bytes.fromhex(hexed) if isinstance(hexed, str) else bytes(hexed)
    if raw[:3] == b"\xb0\x65\x66":
        raw = raw[3:]
    elif raw[:1] == b"\xb0":
        raw = raw[1:]
    if len(raw) != 64:
        raise SM2Error("SM2 public key must be 64 bytes (x||y) after the BIF prefix, got %d" % len(raw))
    px = int.from_bytes(raw[:32], "big")
    py = int.from_bytes(raw[32:], "big")
    if not is_on_curve(px, py):
        raise SM2Error("SM2 public key is not a point on the curve")
    return px, py


def parse_signature(raw: bytes) -> Tuple[int, int]:
    if len(raw) != 64:
        raise SM2Error("SM2 signature must be 64 bytes (r||s), got %d" % len(raw))
    return int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big")
