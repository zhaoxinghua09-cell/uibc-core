"""Ed25519 signatures (RFC 8032) - pure Python, stdlib only.

Seal v0.3 adds an asymmetric seal so that ANY third party can verify a
package's provenance with the public key recorded in the seal - no shared
secret, no owner key. This module is a compact implementation of RFC 8032
section 5.1 built on hashlib's SHA-512. It signs/verifies seal payloads
(a few hundred bytes), where pure-Python speed is ample.

Correctness is pinned by the official RFC 8032 test vectors in
tests/test_seal_v03.py - if those pass, this implementation is the RFC's.
"""

import hashlib

_Q = 2 ** 255 - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493
_D = (-121665 * pow(121666, _Q - 2, _Q)) % _Q
_I = pow(2, (_Q - 1) // 4, _Q)


def _sha512(data: bytes) -> bytes:
    return hashlib.sha512(data).digest()


def _xrecover(y: int) -> int:
    xx = (y * y - 1) * pow(_D * y * y + 1, _Q - 2, _Q) % _Q
    x = pow(xx, (_Q + 3) // 8, _Q)
    if (x * x - xx) % _Q != 0:
        x = (x * _I) % _Q
    if x % 2 != 0:
        x = _Q - x
    return x


_BY = (4 * pow(5, _Q - 2, _Q)) % _Q
_BX = _xrecover(_BY)
_B = (_BX % _Q, _BY % _Q, 1, (_BX * _BY) % _Q)  # extended coordinates (X, Y, Z, T)
_IDENTITY = (0, 1, 1, 0)


def _edwards_add(P, Q):
    A = (P[1] - P[0]) * (Q[1] - Q[0]) % _Q
    Bv = (P[1] + P[0]) * (Q[1] + Q[0]) % _Q
    C = 2 * P[3] * Q[3] * _D % _Q
    Dv = 2 * P[2] * Q[2] % _Q
    E, F, G, H = Bv - A, Dv - C, Dv + C, Bv + A
    return (E * F % _Q, G * H % _Q, F * G % _Q, E * H % _Q)


def _scalarmult(P, e: int):
    Q = _IDENTITY
    while e > 0:
        if e & 1:
            Q = _edwards_add(Q, P)
        P = _edwards_add(P, P)
        e >>= 1
    return Q


def _encode_int(y: int) -> bytes:
    return y.to_bytes(32, "little")


def _encode_point(P) -> bytes:
    zi = pow(P[2], _Q - 2, _Q)
    x = P[0] * zi % _Q
    y = P[1] * zi % _Q
    bits = [(y >> i) & 1 for i in range(255)] + [x & 1]
    out = bytearray(32)
    for i, bit in enumerate(bits):
        out[i // 8] |= bit << (i % 8)
    return bytes(out)


def _decode_int(data: bytes) -> int:
    return int.from_bytes(data, "little")


def _decode_point(data: bytes):
    if len(data) != 32:
        raise ValueError("encoded point must be 32 bytes")
    y = sum(2 ** i * ((data[i // 8] >> (i % 8)) & 1) for i in range(255))
    sign = (data[31] >> 7) & 1
    x = _xrecover(y)
    if (x & 1) != sign:
        x = _Q - x
    return (x, y, 1, x * y % _Q)


def _hint(data: bytes) -> int:
    return int.from_bytes(_sha512(data), "little")


def publickey(seed: bytes) -> bytes:
    """Derive the 32-byte public key from a 32-byte seed (RFC 8032 5.1.5)."""
    if len(seed) != 32:
        raise ValueError("seed must be 32 bytes")
    h = bytearray(_sha512(seed))
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= (1 << 254)
    return _encode_point(_scalarmult(_B, a))


def sign(seed: bytes, message: bytes) -> bytes:
    """Return the 64-byte Ed25519 signature of message (RFC 8032 5.1.6)."""
    if len(seed) != 32:
        raise ValueError("seed must be 32 bytes")
    h = _sha512(seed)
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= (1 << 254)
    prefix = h[32:]
    pub = _encode_point(_scalarmult(_B, a))
    r = _hint(prefix + message) % _L
    R = _scalarmult(_B, r)
    S = (r + _hint(_encode_point(R) + pub + message) * a) % _L
    return _encode_point(R) + _encode_int(S)


def verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    """Return True iff signature is valid (RFC 8032 5.1.7). Never raises."""
    try:
        if len(public_key) != 32 or len(signature) != 64:
            return False
        R = _decode_point(signature[:32])
        A = _decode_point(public_key)
        S = _decode_int(signature[32:])
        if S >= _L:
            return False
        h = _hint(signature[:32] + public_key + message) % _L
        # [S]B == R + [H]A  (checked in extended coordinates via affine compare)
        left = _scalarmult(_B, S)
        right = _edwards_add(R, _scalarmult(A, h))
        zi_l, zi_r = pow(left[2], _Q - 2, _Q), pow(right[2], _Q - 2, _Q)
        return (left[0] * zi_l - right[0] * zi_r) % _Q == 0 and \
               (left[1] * zi_l - right[1] * zi_r) % _Q == 0
    except Exception:
        return False
