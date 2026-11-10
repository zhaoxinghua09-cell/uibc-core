#!/usr/bin/env python3
"""Self-contained verifier for the sample-ed25519 SCITT Signed Statement.

Zero dependencies (Python 3 standard library only): a minimal CBOR
decoder for the subset used by COSE_Sign1, and an Ed25519 verification
routine following RFC 8032 section 5.1.7 (reference-style code, not
constant-time — for test vectors, not production).

    python3 verify_statement.py v1/sample-ed25519

Checks, in order:
  1. statement.cose parses as COSE_Sign1 (tag 18) and its protected
     header carries alg EdDSA and the hash-envelope labels 258/259;
  2. the payload equals SHA-256 of package/manifest.json (preimage
     binding of the hash envelope);
  3. the signature verifies over the reconstructed Sig_structure
     against issuer-key.pub (SPKI PEM) — the same key that sealed
     the package.
Exit code 0 and "STATEMENT VALID" on success; non-zero otherwise.
"""
import base64
import hashlib
import os
import sys

# ---- minimal CBOR decoder (subset: ints, bstr, tstr, arrays, maps, tags) ----

class Tag:
    def __init__(self, tag, value):
        self.tag, self.value = tag, value


def _read_arg(buf, pos, ai):
    if ai < 24:
        return ai, pos
    n = {24: 1, 25: 2, 26: 4, 27: 8}[ai]
    return int.from_bytes(buf[pos:pos + n], "big"), pos + n


def decode(buf, pos=0):
    ib = buf[pos]
    pos += 1
    mt, ai = ib >> 5, ib & 31
    val, pos = _read_arg(buf, pos, ai)
    if mt == 0:
        return val, pos
    if mt == 1:
        return -1 - val, pos
    if mt == 2:
        return buf[pos:pos + val], pos + val
    if mt == 3:
        return buf[pos:pos + val].decode("utf-8"), pos + val
    if mt == 4:
        out = []
        for _ in range(val):
            v, pos = decode(buf, pos)
            out.append(v)
        return out, pos
    if mt == 5:
        out = {}
        for _ in range(val):
            k, pos = decode(buf, pos)
            v, pos = decode(buf, pos)
            out[k] = v
        return out, pos
    if mt == 6:
        v, pos = decode(buf, pos)
        return Tag(val, v), pos
    raise ValueError(f"unsupported major type {mt}")


def encode(obj):  # canonical CBOR for the Sig_structure only
    if isinstance(obj, int):
        if obj >= 0:
            return _enc_head(0, obj)
        return _enc_head(1, -1 - obj)
    if isinstance(obj, bytes):
        return _enc_head(2, len(obj)) + obj
    if isinstance(obj, str):
        b = obj.encode("utf-8")
        return _enc_head(3, len(b)) + b
    if isinstance(obj, (list, tuple)):
        return _enc_head(4, len(obj)) + b"".join(encode(x) for x in obj)
    raise ValueError(type(obj))


def _enc_head(mt, val):
    if val < 24:
        return bytes([(mt << 5) | val])
    if val < 256:
        return bytes([(mt << 5) | 24, val])
    if val < 65536:
        return bytes([(mt << 5) | 25]) + val.to_bytes(2, "big")
    return bytes([(mt << 5) | 26]) + val.to_bytes(4, "big")


# ---- Ed25519 verification, RFC 8032 5.1.7 (reference style) ----

_Q = 2 ** 255 - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493
_D = -121665 * pow(121666, _Q - 2, _Q) % _Q
_I = pow(2, (_Q - 1) // 4, _Q)


def _recover_x(y):
    xx = (y * y - 1) * pow(_D * y * y + 1, _Q - 2, _Q) % _Q
    x = pow(xx, (_Q + 3) // 8, _Q)
    if (x * x - xx) % _Q != 0:
        x = x * _I % _Q
    if x % 2 != 0:
        x = _Q - x
    return x


_BY = 4 * pow(5, _Q - 2, _Q) % _Q
_B = (_recover_x(_BY), _BY)


def _add(P, Q):
    x1, y1 = P
    x2, y2 = Q
    t = _D * x1 * x2 * y1 * y2 % _Q
    return ((x1 * y2 + x2 * y1) * pow(1 + t, _Q - 2, _Q) % _Q,
            (y1 * y2 + x1 * x2) * pow(1 - t, _Q - 2, _Q) % _Q)


def _scalarmult(P, e):
    Q = (0, 1)
    while e > 0:
        if e & 1:
            Q = _add(Q, P)
        P = _add(P, P)
        e >>= 1
    return Q


def _decode_point(data):
    y = int.from_bytes(data, "little") & (2 ** 255 - 1)
    x = _recover_x(y)
    if (x & 1) != (data[31] >> 7):
        x = _Q - x
    return (x, y)


def ed25519_verify(pub, msg, sig):
    if len(sig) != 64:
        return False
    R = _decode_point(sig[:32])
    A = _decode_point(pub)
    S = int.from_bytes(sig[32:], "little")
    if S >= _L:
        return False
    h = int.from_bytes(hashlib.sha512(sig[:32] + pub + msg).digest(), "little") % _L
    return _scalarmult(_B, S) == _add(R, _scalarmult(A, h))


# ---- main ----

def main(case_dir):
    raw = open(os.path.join(case_dir, "statement.cose"), "rb").read()
    obj, _ = decode(raw)
    assert isinstance(obj, Tag) and obj.tag == 18, "not a COSE_Sign1 (tag 18)"
    prot, _unprot, payload, sig = obj.value
    phdr, _ = decode(prot)
    assert phdr.get(1) == -8, "alg is not EdDSA"
    assert phdr.get(258) == -16 and phdr.get(259) == "application/json", "not the expected hash envelope"

    manifest = open(os.path.join(case_dir, "package", "manifest.json"), "rb").read()
    assert hashlib.sha256(manifest).digest() == payload, "payload != SHA-256(manifest.json)"

    pem = open(os.path.join(case_dir, "issuer-key.pub")).read()
    der = base64.b64decode("".join(pem.splitlines()[1:-1]))
    pub = der[-32:]
    sig_struct = encode(["Signature1", prot, b"", payload])
    assert ed25519_verify(pub, sig_struct, sig), "signature does not verify"

    claims = phdr[15]
    print(f"issuer:  {claims[1]}")
    print(f"subject: {claims[2]}")
    print(f"payload: sha256(manifest.json) = {payload.hex()}")
    print("STATEMENT VALID")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "v1/sample-ed25519"))
    except AssertionError as e:
        print(f"STATEMENT INVALID: {e}")
        sys.exit(1)
